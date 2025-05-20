import os
import json # For parsing stringified JSON arguments from LLM
import logging # Import the logging module
# Boto3 import removed, will be handled by the tool module
from dotenv import load_dotenv
from typing import TypedDict, Annotated, List, Union, Optional # Added Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, FunctionMessage
from langchain_core.tools import tool # Import the tool decorator
from langchain_core.utils.function_calling import convert_to_openai_function 
from openai import OpenAI, APIError # Import APIError directly
from devops_tools.ec2_tools import create_ec2_instance_tool # Import the tool

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

# AWS credentials and Boto3 client are now managed within the tool module (ec2_tools.py)
# OpenAI API key is still needed here for the LLM node.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# EC2 creation function and tool definition are now in devops_tools.ec2_tools
# create_ec2_instance_tool is imported from there.

ALL_AVAILABLE_TOOLS = [create_ec2_instance_tool]

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    pending_action_details: Optional[dict] = None # To store action details awaiting confirmation
    is_awaiting_confirmation: bool = False      # Flag if agent is waiting for user's yes/no

def convert_message_to_dict(message: BaseMessage) -> dict:
    """Converts BaseMessage to a dict suitable for OpenAI API, handling tool calls."""
    logger.debug(f"Converting message of type: {message.type} to dict")
    role = message.type
    if role == "human":
        role = "user"
    elif role == "ai":
        role = "assistant"
    # system, tool, function roles should map directly

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
        # If content is None and there are tool_calls, OpenAI API expects content to be omitted or be null string
        if not msg_dict["content"] and "tool_calls" in msg_dict:
             # OpenAI API sometimes errors if content is "" with tool_calls, so omit if empty
            if not msg_dict["content"]:
                del msg_dict["content"]


    elif isinstance(message, ToolMessage):
        msg_dict = {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "name": message.name, # ToolNode might populate this
            "content": str(message.content)
        }
    elif isinstance(message, FunctionMessage): # Deprecated but good to handle
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

    # New state fields for confirmation flow
    updated_pending_action_details = state.get("pending_action_details")
    updated_is_awaiting_confirmation = state.get("is_awaiting_confirmation", False)

    # If awaiting confirmation, process the user's yes/no
    if updated_is_awaiting_confirmation:
        logger.info("Agent is awaiting user confirmation.")
        user_response_message = state['messages'][-1]
        if not isinstance(user_response_message, HumanMessage):
            # Should not happen if graph is structured correctly, but good to handle
            logger.warning("Awaiting confirmation, but last message is not HumanMessage.")
            # Fall through to normal LLM call for recovery or re-prompt.
            # Reset confirmation flags as the expected yes/no was not received.
            updated_is_awaiting_confirmation = False
            updated_pending_action_details = None
        else:
            user_response_text = user_response_message.content.strip().lower()
            logger.info(f"User confirmation response: '{user_response_text}'")
            if user_response_text in ["yes", "y", "proceed", "ok", "confirm", "do it"]:
                if updated_pending_action_details:
                    logger.info("User confirmed action. Preparing tool call.")
                    # Construct AIMessage with the stored tool call
                    ai_message = AIMessage(
                        content=f"Okay, proceeding with the action: {updated_pending_action_details['tool_name']}.",
                        tool_calls=[{ # LangChain AIMessage expects tool_calls in this dict format
                            "name": updated_pending_action_details['tool_name'],
                            "args": updated_pending_action_details['tool_args'],
                            "id": updated_pending_action_details['tool_id'] 
                        }]
                    )
                    updated_pending_action_details = None # Clear pending action
                    updated_is_awaiting_confirmation = False
                    logger.info("Exiting llm_node after user confirmed action and tool call prepared.")
                    return {
                        "messages": [ai_message], 
                        "pending_action_details": updated_pending_action_details, 
                        "is_awaiting_confirmation": updated_is_awaiting_confirmation
                    }
                else: # User said "yes", but no action was pending (e.g., due to prior ambiguous input)
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
            else: # User did not confirm (said "no" or something else)
                logger.info("User did not confirm or cancelled action.")
                ai_message = AIMessage(content="Okay, I will not proceed with that action. What would you like to do instead?")
                updated_pending_action_details = None # Clear pending action
                updated_is_awaiting_confirmation = False
                logger.info("Exiting llm_node after user confirmation (no/other).")
                return {
                    "messages": [ai_message],
                    "pending_action_details": updated_pending_action_details,
                    "is_awaiting_confirmation": updated_is_awaiting_confirmation
                }
    # If not awaiting confirmation, proceed with normal LLM call flow
    logger.info("Not awaiting confirmation, proceeding with normal LLM call.")
    
    # Log the content of the last message if it's a ToolMessage, to see tool output
    if state['messages'] and isinstance(state['messages'][-1], ToolMessage):
        last_msg = state['messages'][-1]
        logger.info(f"Processing ToolMessage: Name='{last_msg.name}', Content='{last_msg.content}'")

    api_messages = [convert_message_to_dict(msg) for msg in state['messages']]
    
    # Determine if we should restrict tools for this LLM call
    # (e.g., after a successful critical tool execution)
    current_tools_for_llm = [{"type": "function", "function": convert_to_openai_function(t)} for t in ALL_AVAILABLE_TOOLS]
    last_message_in_state = state['messages'][-1] if state['messages'] else None
    
    if isinstance(last_message_in_state, ToolMessage) and \
       last_message_in_state.name == create_ec2_instance_tool.name and \
       "launched successfully" in str(last_message_in_state.content).lower():
        logger.info(f"Last action was a successful '{create_ec2_instance_tool.name}'. Forcing LLM to generate text response without tools.")
        current_tools_for_llm = [] # No tools for this call, force text response

    logger.debug(f"Formatted tools for LLM: {current_tools_for_llm}")
    
    ai_message = None # Ensure ai_message is defined
    try:
        logger.info(f"Calling OpenAI API with model: {OPENAI_MODEL_NAME}")
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL_NAME,
            messages=api_messages,
            tools=current_tools_for_llm, # Use potentially restricted list
            tool_choice="auto" if current_tools_for_llm else None # tool_choice must be None if tools is empty
        )
        logger.info("OpenAI API call successful.")
        logger.debug(f"OpenAI API raw response: {response}")
        
        api_response_message = response.choices[0].message
        
        raw_tool_calls = []
        if api_response_message.tool_calls:
            for tc in api_response_message.tool_calls:
                raw_tool_calls.append({
                    "id": tc.id, # Keep the original ID from OpenAI
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                })

        # Check if a critical tool (EC2 creation) is being called
        # For now, assume any call to create_ec2_instance_tool is critical
        critical_tool_called = False
        pending_action_to_confirm = None
        if raw_tool_calls:
            for tc_data in raw_tool_calls:
                if tc_data["name"] == create_ec2_instance_tool.name: # Check against the actual tool name
                    critical_tool_called = True
                    pending_action_to_confirm = {
                        "tool_name": tc_data["name"],
                        "tool_args": tc_data["args"],
                        "tool_id": tc_data["id"] # Store the ID for later use in AIMessage
                    }
                    logger.info(f"Critical tool '{tc_data['name']}' proposed by LLM. Parameters: {tc_data['args']}")
                    break # Handle one critical tool call proposal at a time for now

        if critical_tool_called and pending_action_to_confirm:
            logger.info("Critical action proposed, asking user for confirmation.")
            # Store action details and set flag
            updated_pending_action_details = pending_action_to_confirm
            updated_is_awaiting_confirmation = True
            
            # Formulate confirmation question
            params_summary = ", ".join(f"{k}={v}" for k, v in pending_action_to_confirm['tool_args'].items())
            confirmation_question = (
                f"I am about to perform the action: {pending_action_to_confirm['tool_name']} "
                f"with parameters: {params_summary}. Shall I proceed?"
            )
            ai_message = AIMessage(content=confirmation_question, tool_calls=[]) # No tool_calls in this message
        else:
            # Not a critical tool or no tool call, proceed as before
            ai_message = AIMessage(
                content=str(api_response_message.content or ""), 
                tool_calls=raw_tool_calls # Pass along any non-critical tool calls or if no tool calls
            )
        logger.debug(f"Constructed AIMessage: {ai_message}")

    except APIError as e:
        logger.error(f"OpenAI APIError in llm_node: {str(e)}", exc_info=True)
        error_content = f"LLM API Error: {str(e)}"
        ai_message = AIMessage(content=error_content, tool_calls=[])
        updated_pending_action_details = None # Clear any pending action on error
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

tool_node = ToolNode(ALL_AVAILABLE_TOOLS)

def should_continue(state: AgentState):
    logger.info("Entering should_continue...")
    logger.debug(f"Current state in should_continue: {state}")
    last_message = state['messages'][-1]
    
    if state.get("is_awaiting_confirmation", False):
        logger.info("Decision: Awaiting user confirmation, ending turn to get user input.")
        return END # End the turn to allow user to respond to confirmation question

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

# The agent_chat function is removed. main.py will now manage history
# and call _agent_runnable.invoke directly.
