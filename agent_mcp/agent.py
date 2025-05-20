import os
import json
import logging
from dotenv import load_dotenv
from typing import TypedDict, Annotated, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
import requests # Import requests for HTTP calls
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, FunctionMessage
from langchain_core.tools import Tool, StructuredTool # Import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_function
from openai import OpenAI, APIError
from pydantic import BaseModel, Field, create_model # Import Pydantic components and create_model
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000") # Define your MCP server's base URL
openai_client = OpenAI(api_key=OPENAI_API_KEY)


# Create a LangChain Tool instance for the MCP tool.
# This function will now call the MCP server.
def execute_tool_via_mcp(tool_name: str, **kwargs) -> str:
    """
    Calls the MCP server to execute a specified tool with given arguments, with retries and timing.
    """
    endpoint = f"{MCP_SERVER_URL}/execute_tool/{tool_name}"
    logger.info(f"Calling MCP server endpoint: {endpoint} with args: {kwargs}")
    max_retries = 3
    backoff = 1
    for attempt in range(1, max_retries + 1):
        start = time.time()
        try:
            response = requests.post(endpoint, json=kwargs, timeout=60)
            response.raise_for_status()
            duration = time.time() - start
            logger.info(f"MCP server response for '{tool_name}' (attempt {attempt}), took {duration:.2f}s")
            mcp_response = response.json()
            if mcp_response.get("status") == "success":
                return str(mcp_response.get("result", f"Tool '{tool_name}' executed successfully via MCP."))
            error_msg = mcp_response.get("error", "Unknown error from MCP.")
            logger.error(f"Error from MCP server for tool '{tool_name}': {error_msg}")
            return f"Error from MCP server for tool '{tool_name}': {error_msg}"
        except requests.exceptions.RequestException as e:
            duration = time.time() - start
            logger.warning(f"Attempt {attempt} failed for MCP tool '{tool_name}' after {duration:.2f}s: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
                continue
            logger.error(f"All {max_retries} attempts failed for MCP tool '{tool_name}'.", exc_info=True)
            return f"Error: Could not connect to or get a valid response from MCP server for tool '{tool_name}'. Details: {e}"
        except Exception as e:
            duration = time.time() - start
            logger.error(f"Unexpected error during MCP tool execution for '{tool_name}' (attempt {attempt}) after {duration:.2f}s: {e}", exc_info=True)
    return f"Error: An unexpected error occurred while trying to execute tool '{tool_name}' via MCP. Details: {e}"

# Helper to map JSON schema types to Python types
def python_type_from_jsonschema(prop: dict) -> type:
    t = prop.get("type")
    if t == "string":
        return str
    if t in ("integer", "number"):
        return int
    if t == "boolean":
        return bool
    if t == "array":
        return list
    if t == "object":
        return dict
    return Any

# Dynamically load MCP tool definitions from the server
def load_mcp_tools() -> List[StructuredTool]:
    try:
        resp = requests.get(f"{MCP_SERVER_URL}/tools", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        tools: List[StructuredTool] = []
        for t in data.get("tools", []):
            props = t["inputSchema"].get("properties", {})
            required = t["inputSchema"].get("required", [])
            fields = {}
            for name, schema in props.items():
                py_type = python_type_from_jsonschema(schema)
                if name in required:
                    fields[name] = (py_type, Field(..., description=schema.get("description")))
                else:
                    default = schema.get("default", None)
                    fields[name] = (Optional[py_type], Field(default, description=schema.get("description")))
            model = create_model(f"{t['name'].title().replace('_', '')}Args", **fields)
            def _make_func(tool_name: str):
                def func(**kwargs):
                    return execute_tool_via_mcp(tool_name, **kwargs)
                return func
            tool_func = _make_func(t["name"])
            tools.append(
                StructuredTool.from_function(
                    func=tool_func,
                    name=t["name"],
                    description=t.get("description", ""),
                    args_schema=model,
                )
            )
        return tools
    except Exception as e:
        logger.error(f"Error loading MCP tools: {e}", exc_info=True)
        return []

# Load tools once at startup
MCP_LC_TOOLS: List[StructuredTool] = load_mcp_tools()

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    pending_action_details: Optional[dict] = None
    is_awaiting_confirmation: bool = False

def convert_message_to_dict(message: BaseMessage) -> dict:
    logger.debug(f"Converting message of type: {message.type} to dict")
    role = message.type
    if role == "human":
        role = "user"
    elif role == "ai":
        role = "assistant"
    msg_dict = {"role": role, "content": str(message.content)}
    if isinstance(message, AIMessage):
        if message.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["args"]) if isinstance(tc["args"], dict) else tc["args"]}
                } for tc in message.tool_calls
            ]
        if not msg_dict["content"] and "tool_calls" in msg_dict:
            if not msg_dict["content"]:
                del msg_dict["content"]
    elif isinstance(message, ToolMessage):
        msg_dict = {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "name": message.name,
            "content": str(message.content)
        }
    elif isinstance(message, FunctionMessage):
         msg_dict = {
            "role": "function",
            "name": message.name,
            "content": str(message.content)
        }
    logger.debug(f"Converted message dict: {msg_dict}")
    return msg_dict

def llm_node(state: AgentState):
    logger.info("Entering llm_node...")
    logger.debug(f"Current agent state: {state}")
    updated_pending_action_details = state.get("pending_action_details")
    updated_is_awaiting_confirmation = state.get("is_awaiting_confirmation", False)

    if updated_is_awaiting_confirmation:
        logger.info("Agent is awaiting user confirmation.")
        user_response_message = state['messages'][-1]
        if not isinstance(user_response_message, HumanMessage):
            logger.warning("Awaiting confirmation, but last message is not HumanMessage.")
            updated_is_awaiting_confirmation = False
            updated_pending_action_details = None
        else:
            user_response_text = user_response_message.content.strip().lower()
            logger.info(f"User confirmation response: '{user_response_text}'")
            if user_response_text in ["yes", "y", "proceed", "ok", "confirm", "do it"]:
                if updated_pending_action_details:
                    logger.info("User confirmed action. Preparing tool call.")
                    ai_message = AIMessage(
                        content=f"Okay, proceeding with the action: {updated_pending_action_details['tool_name']}.",
                        tool_calls=[{
                            "name": updated_pending_action_details['tool_name'],
                            "args": updated_pending_action_details['tool_args'],
                            "id": updated_pending_action_details['tool_id']
                        }]
                    )
                    updated_pending_action_details = None
                    updated_is_awaiting_confirmation = False
                    logger.info("Exiting llm_node after user confirmed action and tool call prepared.")
                    return {
                        "messages": [ai_message],
                        "pending_action_details": updated_pending_action_details,
                        "is_awaiting_confirmation": updated_is_awaiting_confirmation
                    }
                else:
                    logger.warning("User confirmed, but no pending_action_details found. Resetting state.")
                    ai_message = AIMessage(content="It seems there was no specific action pending my confirmation. Could you please clarify what you'd like to do or re-issue your command?")
                    updated_pending_action_details = None
                    updated_is_awaiting_confirmation = False
                    logger.info("Exiting llm_node after user 'yes' but no pending action.")
                    return {
                        "messages": [ai_message],
                        "pending_action_details": updated_pending_action_details,
                        "is_awaiting_confirmation": updated_is_awaiting_confirmation
                    }
            else:
                logger.info("User did not confirm or cancelled action.")
                ai_message = AIMessage(content="Okay, I will not proceed with that action. What would you like to do instead?")
                updated_pending_action_details = None
                updated_is_awaiting_confirmation = False
                logger.info("Exiting llm_node after user confirmation (no/other).")
                return {
                    "messages": [ai_message],
                    "pending_action_details": updated_pending_action_details,
                    "is_awaiting_confirmation": updated_is_awaiting_confirmation
                }

    logger.info("Not awaiting confirmation, proceeding with normal LLM call.")
    if state['messages'] and isinstance(state['messages'][-1], ToolMessage):
        last_msg = state['messages'][-1]
        logger.info(f"Processing ToolMessage: Name='{last_msg.name}', Content='{last_msg.content}'")

    api_messages = [convert_message_to_dict(msg) for msg in state['messages']]

    # Define the list of tools for the OpenAI API call by converting LangChain Tools.
    raw_openai_tool_definitions = [convert_to_openai_function(t) for t in MCP_LC_TOOLS]
    
    # Ensure each tool definition has the 'type: "function"' field
    openai_tool_definitions_for_api = []
    for tool_def in raw_openai_tool_definitions:
        if 'type' not in tool_def:
            # Assuming it's a function tool if type is missing
            openai_tool_definitions_for_api.append({"type": "function", "function": tool_def.get("function", tool_def)})
        else:
            # If type is already present, use as is (though OpenAI expects "function" for this usage)
            openai_tool_definitions_for_api.append(tool_def)

    last_message_in_state = state['messages'][-1] if state['messages'] else None
    if isinstance(last_message_in_state, ToolMessage) and \
       last_message_in_state.name == 'create_ec2_instance' and \
       "launched successfully" in str(last_message_in_state.content).lower():
        logger.info(f"Last action was a successful 'create_ec2_instance' (MCP tool). Forcing LLM to generate text response without tools.")
        openai_tool_definitions_for_api = [] # No tools for this call
        updated_pending_action_details = None
        updated_is_awaiting_confirmation = False

    logger.debug(f"Tools for OpenAI API call: {openai_tool_definitions_for_api}")
    ai_message = None
    try:
        logger.info(f"Calling OpenAI API with model: {OPENAI_MODEL_NAME}")
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL_NAME,
            messages=api_messages,
            tools=openai_tool_definitions_for_api if openai_tool_definitions_for_api else None,
            tool_choice="auto" if openai_tool_definitions_for_api else None
        )
        logger.info("OpenAI API call successful.")
        logger.debug(f"OpenAI API raw response: {response}")
        api_response_message = response.choices[0].message
        raw_tool_calls = []
        if api_response_message.tool_calls:
            for tc in api_response_message.tool_calls:
                raw_tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                })

        critical_tool_called = False
        pending_action_to_confirm = None
        if raw_tool_calls:
            for tc_data in raw_tool_calls:
                if tc_data["name"] == 'create_ec2_instance':
                    critical_tool_called = True
                    pending_action_to_confirm = {
                        "tool_name": tc_data["name"],
                        "tool_args": tc_data["args"],
                        "tool_id": tc_data["id"]
                    }
                    logger.info(f"Critical tool '{tc_data['name']}' proposed by LLM. Parameters: {tc_data['args']}")
                    break
        if critical_tool_called and pending_action_to_confirm:
            logger.info("Critical action proposed, asking user for confirmation.")
            updated_pending_action_details = pending_action_to_confirm
            updated_is_awaiting_confirmation = True
            params_summary = ", ".join(f"{k}={v}" for k, v in pending_action_to_confirm['tool_args'].items())
            confirmation_question = (
                f"I am about to perform the action: {pending_action_to_confirm['tool_name']} "
                f"with parameters: {params_summary}. Shall I proceed?"
            )
            ai_message = AIMessage(content=confirmation_question, tool_calls=[])
        else:
            ai_message = AIMessage(
                content=str(api_response_message.content or ""),
                tool_calls=raw_tool_calls
            )
        logger.debug(f"Constructed AIMessage: {ai_message}")
    except APIError as e:
        logger.error(f"OpenAI APIError in llm_node: {str(e)}", exc_info=True)
        error_content = f"LLM API Error: {str(e)}"
        ai_message = AIMessage(content=error_content, tool_calls=[])
        updated_pending_action_details = None
        updated_is_awaiting_confirmation = False
    except Exception as e:
        logger.error(f"Unexpected error in llm_node: {str(e)}", exc_info=True)
        error_content = f"An unexpected error occurred in the LLM node: {str(e)}"
        ai_message = AIMessage(content=error_content, tool_calls=[])
        updated_pending_action_details = None
        updated_is_awaiting_confirmation = False

    logger.info("Exiting llm_node.")
    return {
        "messages": [ai_message],
        "pending_action_details": updated_pending_action_details,
        "is_awaiting_confirmation": updated_is_awaiting_confirmation
    }

# Initialize ToolNode with the LangChain Tool instance(s).
tool_node = ToolNode(MCP_LC_TOOLS)

def should_continue(state: AgentState):
    logger.info("Entering should_continue...")
    logger.debug(f"Current state in should_continue: {state}")
    last_message = state['messages'][-1]
    if state.get("is_awaiting_confirmation", False):
        logger.info("Decision: Awaiting user confirmation, ending turn to get user input.")
        return END
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        logger.info("Decision: Route to tools.")
        return "tools"
    logger.info("Decision: End graph for this turn.")
    return END

def build_agent():
    logger.info("Building agent graph...")
    graph = StateGraph(AgentState)
    graph.add_node("llm", llm_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges(
        "llm",
        should_continue,
        {"tools": "tools", END: END}
    )
    graph.add_edge("tools", "llm")
    return graph.compile()

_agent_runnable = build_agent()
