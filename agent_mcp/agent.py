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


# Define a list of critical tools that require confirmation
CRITICAL_TOOLS = [
    'create_ec2_instance',
    'create_s3_bucket',
    # Add other critical tools here
]

def is_critical_tool(tool_name: str) -> bool:
    """Determine if a tool is considered critical and requires confirmation."""
    return tool_name in CRITICAL_TOOLS

def format_tool_response(tool_name: str, response: str) -> str:
    """Format tool responses for better presentation to the user."""
    # Extract the most relevant information based on tool type
    if tool_name == 'create_ec2_instance' and 'launched successfully' in response.lower():
        # Try to extract instance IDs
        import re
        instance_ids = re.search(r'Instance IDs?: ([\w-]+(?:, [\w-]+)*)', response)
        if instance_ids:
            return f"✅ EC2 instance(s) created successfully!\nInstance ID(s): {instance_ids.group(1)}\n\nYou can check the status of your instance(s) in the AWS Console."
        return f"✅ {response}"
    
    if tool_name == 'create_s3_bucket' and 'created successfully' in response.lower():
        # Extract bucket name
        import re
        bucket_name = re.search(r"'([^']+)' created successfully", response)
        if bucket_name:
            return f"✅ S3 bucket '{bucket_name.group(1)}' created successfully!\n\nYou can access this bucket in the AWS Console or use AWS CLI/SDK to upload files to it."
        return f"✅ {response}"
        
    # Error handling
    if 'error' in response.lower():
        return f"❌ {response}"
        
    # Default formatting
    return response

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
            # Add request validation
            if not MCP_SERVER_URL:
                return "Error: MCP server URL is not configured. Please set the MCP_SERVER_URL environment variable."
                
            # Add timeout handling with a specific message
            response = requests.post(endpoint, json=kwargs, timeout=60)
            
            # More detailed HTTP error handling
            if response.status_code >= 400:
                error_info = f"HTTP {response.status_code}"
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        error_info += f": {error_body.get('error', 'Unknown error')}"
                except:
                    error_info += f": {response.text[:100]}..."
                
                if 400 <= response.status_code < 500:
                    return f"Client error when calling MCP tool '{tool_name}': {error_info}"
                else:
                    # Only retry server errors
                    if attempt < max_retries:
                        logger.warning(f"Server error (attempt {attempt}): {error_info}. Retrying in {backoff}s...")
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    return f"Server error when calling MCP tool '{tool_name}' after {max_retries} attempts: {error_info}"
            
            # Regular response processing
            response.raise_for_status()
            duration = time.time() - start
            logger.info(f"MCP server response for '{tool_name}' (attempt {attempt}), took {duration:.2f}s")
            
            mcp_response = response.json()
            if mcp_response.get("status") == "success":
                result_text = str(mcp_response.get("result", f"Tool '{tool_name}' executed successfully via MCP."))
                return format_tool_response(tool_name, result_text)
                
            error_msg = mcp_response.get("error", "Unknown error from MCP.")
            logger.error(f"Error from MCP server for tool '{tool_name}': {error_msg}")
            return f"❌ Error from MCP server for tool '{tool_name}': {error_msg}"
            
        except requests.exceptions.Timeout:
            duration = time.time() - start
            logger.warning(f"Timeout (attempt {attempt}) for MCP tool '{tool_name}' after {duration:.2f}s")
            if attempt < max_retries:
                logger.info(f"Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
                continue
            return f"❌ Error: MCP server timeout after {max_retries} attempts for tool '{tool_name}'. The operation might be taking longer than expected or the server might be overloaded."
            
        except requests.exceptions.ConnectionError:
            duration = time.time() - start
            logger.warning(f"Connection error (attempt {attempt}) for MCP tool '{tool_name}' after {duration:.2f}s")
            if attempt < max_retries:
                logger.info(f"Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
                continue
            return f"❌ Error: Could not connect to MCP server after {max_retries} attempts for tool '{tool_name}'. Please check that the server is running and accessible."
            
        except json.JSONDecodeError:
            duration = time.time() - start
            logger.error(f"Invalid JSON response from MCP server for tool '{tool_name}' after {duration:.2f}s")
            return f"❌ Error: MCP server returned an invalid response format for tool '{tool_name}'. Expected JSON but received: {response.text[:100]}..."
            
        except Exception as e:
            duration = time.time() - start
            logger.error(f"Unexpected error during MCP tool execution for '{tool_name}' (attempt {attempt}) after {duration:.2f}s: {e}", exc_info=True)
            if attempt < max_retries:
                logger.info(f"Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
                continue
            return f"❌ Error: An unexpected error occurred while trying to execute tool '{tool_name}' via MCP: {str(e)}"

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

# Check MCP server health
def check_mcp_server_health() -> bool:
    """
    Check if the MCP server is healthy and operational.
    Returns True if healthy, False otherwise.
    """
    try:
        health_endpoint = f"{MCP_SERVER_URL}/health"
        logger.info(f"Checking MCP server health at: {health_endpoint}")
        
        response = requests.get(health_endpoint, timeout=5)
        if response.status_code == 200:
            logger.info("MCP server health check passed")
            return True
        
        logger.warning(f"MCP server health check failed with status code: {response.status_code}")
        try:
            error_body = response.json()
            logger.warning(f"Health check error response: {error_body}")
        except:
            logger.warning(f"Health check raw response: {response.text[:100]}")
        
        return False
    except requests.exceptions.RequestException as e:
        logger.warning(f"MCP server health check failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during MCP server health check: {e}", exc_info=True)
        return False

# Dynamically load MCP tool definitions from the server
def load_mcp_tools() -> List[StructuredTool]:
    try:
        # First perform a health check
        is_healthy = check_mcp_server_health()
        if not is_healthy:
            logger.warning("MCP server health check failed, but will attempt to load tools anyway")
        
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

# MCP server monitoring service
def start_mcp_server_monitor(check_interval_seconds: int = 60):
    """
    Start a background thread that periodically checks the health of the MCP server.
    
    Args:
        check_interval_seconds: How often to check the server health (in seconds)
    """
    import threading
    
    def monitor_loop():
        logger.info(f"Starting MCP server monitoring service (interval: {check_interval_seconds}s)")
        consecutive_failures = 0
        max_failures_to_report = 3  # Only log errors for this many consecutive failures
        
        while True:
            try:
                is_healthy = check_mcp_server_health()
                
                if is_healthy:
                    if consecutive_failures > 0:
                        logger.info(f"MCP server is healthy again after {consecutive_failures} failed checks")
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures <= max_failures_to_report:
                        logger.warning(f"MCP server health check failed (attempt {consecutive_failures})")
                    elif consecutive_failures % 10 == 0:  # Log every 10th failure after max_failures_to_report
                        logger.warning(f"MCP server health check still failing after {consecutive_failures} attempts")
                
                # Add server statistics logging here if needed
                # For example, count of calls to each tool, response times, etc.
                
            except Exception as e:
                logger.error(f"Error in MCP server monitoring thread: {e}", exc_info=True)
            
            # Sleep for the specified interval
            time.sleep(check_interval_seconds)
    
    # Start the monitoring in a daemon thread (will exit when main program exits)
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    logger.info("MCP server monitoring thread started")

# Global variables to track tool state
MCP_LC_TOOLS: List[StructuredTool] = []
last_tools_update_time = 0
tools_load_lock = threading.Lock()  # To prevent concurrent tool reloading

def reload_mcp_tools_if_needed(force: bool = False) -> List[StructuredTool]:
    """
    Reload MCP tools if they haven't been loaded yet or if forced.
    Returns the current list of tools.
    
    Args:
        force: If True, reload tools regardless of when they were last loaded
    """
    global MCP_LC_TOOLS, last_tools_update_time
    
    # Use a lock to prevent multiple threads from loading tools simultaneously
    with tools_load_lock:
        current_time = time.time()
        time_since_last_update = current_time - last_tools_update_time
        
        # Reload if:
        # 1. Tools have never been loaded (last_tools_update_time == 0)
        # 2. Forced reload is requested
        # 3. Tools are empty (perhaps initial load failed)
        if force or last_tools_update_time == 0 or len(MCP_LC_TOOLS) == 0:
            logger.info(f"Loading MCP tools (forced={force}, time_since_last_update={time_since_last_update:.1f}s)")
            new_tools = load_mcp_tools()
            
            if new_tools:
                # Update the global tool list only if we got valid tools
                MCP_LC_TOOLS = new_tools
                last_tools_update_time = current_time
                
                # Log the loaded tools
                tool_names = [t.name for t in MCP_LC_TOOLS]
                logger.info(f"Loaded {len(MCP_LC_TOOLS)} MCP tools: {', '.join(tool_names)}")
            else:
                logger.warning("Failed to load MCP tools or no tools were returned")
        
    return MCP_LC_TOOLS

# Update MCP server monitoring to include tool reloading
def start_mcp_server_monitor(check_interval_seconds: int = 60, tool_reload_interval_hours: int = 12):
    """
    Start a background thread that periodically checks the health of the MCP server
    and reloads tools at a specified interval.
    
    Args:
        check_interval_seconds: How often to check the server health (in seconds)
        tool_reload_interval_hours: How often to reload tools regardless of server health (in hours)
    """
    import threading
    
    tool_reload_interval_seconds = tool_reload_interval_hours * 3600
    
    def monitor_loop():
        logger.info(f"Starting MCP server monitoring service (health check interval: {check_interval_seconds}s, tool reload interval: {tool_reload_interval_hours}h)")
        consecutive_failures = 0
        max_failures_to_report = 3  # Only log errors for this many consecutive failures
        last_tool_reload_time = time.time()
        
        # Perform initial tool load
        reload_mcp_tools_if_needed(force=True)
        
        while True:
            try:
                # Check server health
                is_healthy = check_mcp_server_health()
                
                current_time = time.time()
                time_since_last_reload = current_time - last_tool_reload_time
                
                if is_healthy:
                    if consecutive_failures > 0:
                        logger.info(f"MCP server is healthy again after {consecutive_failures} failed checks")
                        # Reload tools when server becomes healthy after failures
                        reload_mcp_tools_if_needed(force=True)
                        last_tool_reload_time = current_time
                    consecutive_failures = 0
                    
                    # Reload tools periodically even if server is healthy
                    if time_since_last_reload >= tool_reload_interval_seconds:
                        logger.info(f"Performing periodic tool reload after {time_since_last_reload/3600:.1f} hours")
                        reload_mcp_tools_if_needed(force=True)
                        last_tool_reload_time = current_time
                else:
                    consecutive_failures += 1
                    if consecutive_failures <= max_failures_to_report:
                        logger.warning(f"MCP server health check failed (attempt {consecutive_failures})")
                    elif consecutive_failures % 10 == 0:  # Log every 10th failure after max_failures_to_report
                        logger.warning(f"MCP server health check still failing after {consecutive_failures} attempts")
                
            except Exception as e:
                logger.error(f"Error in MCP server monitoring thread: {e}", exc_info=True)
            
            # Sleep for the specified interval
            time.sleep(check_interval_seconds)
    
    # Start the monitoring in a daemon thread (will exit when main program exits)
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    logger.info("MCP server monitoring thread started")

# Start MCP server monitoring
start_mcp_server_monitor()

# Initial load of tools
reload_mcp_tools_if_needed()

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
       is_critical_tool(last_message_in_state.name) and \
       any(success_indicator in str(last_message_in_state.content).lower() 
           for success_indicator in ["launched successfully", "created successfully"]):
        logger.info(f"Last action was a successful '{last_message_in_state.name}' (critical MCP tool). Forcing LLM to generate text response without tools.")
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
                if is_critical_tool(tc_data["name"]):
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

# Initialize ToolNode with current tools and allow refreshing
def get_tool_node():
    """Get a ToolNode with the latest MCP tools."""
    # Ensure we have the latest tools (but don't force reload)
    current_tools = reload_mcp_tools_if_needed()
    return ToolNode(current_tools)

# Initial tool node
tool_node = get_tool_node()

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
    """
    Build the agent graph with the latest tools.
    This ensures that any new or modified MCP tools are included when the agent is built.
    """
    logger.info("Building agent graph...")
    
    # Force a tool reload before building the agent to ensure we have the latest tools
    reload_mcp_tools_if_needed(force=True)
    
    # Get a fresh tool node with the latest tools
    current_tool_node = get_tool_node()
    
    # Create the graph with the latest tools
    graph = StateGraph(AgentState)
    graph.add_node("llm", llm_node)
    graph.add_node("tools", current_tool_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges(
        "llm",
        should_continue,
        {"tools": "tools", END: END}
    )
    graph.add_edge("tools", "llm")
    
    logger.info("Agent graph built successfully with latest MCP tools")
    return graph.compile()

_agent_runnable = build_agent()
