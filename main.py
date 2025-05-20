from agent import _agent_runnable # Import the compiled agent
import boto3
import os

ec2_client = boto3.client('ec2', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage # Import SystemMessage
from typing import List

SYSTEM_PROMPT_TEXT = """You are a helpful DevOps AI assistant. Your primary goal is to assist users with managing AWS resources.

Currently, you have the following capabilities:
- Create AWS EC2 instances.

When a user asks to perform an action:
- If necessary parameters for a tool are missing or ambiguous, ask the user for clarification before proceeding.
- **Crucial Safety Instruction:** Before invoking any tool that creates, modifies, or deletes AWS resources (such as creating an EC2 instance):
    1. Clearly list the key parameters you have gathered and intend to use for the operation (e.g., AMI ID, instance type, count).
    2. You MUST then explicitly ask the user for confirmation (for example, by asking 'Shall I proceed with creating this EC2 instance with these parameters?').
    3. Wait for the user to provide an affirmative response (e.g., 'yes', 'proceed', 'ok', 'confirm') before you decide to call the tool. If the user does not confirm, or expresses doubt, or asks to cancel, you must NOT call the tool and should instead ask for further instructions or clarification.
- Once a tool has been executed successfully based on user confirmation, your primary goal is to report the success to the user. Do not attempt to re-run the same tool or propose the same action again for the same initial request unless the user explicitly asks for a new, distinct operation or a modification.
- If an operation fails, explain the error to the user clearly.
- If the user's request is unclear or not related to your capabilities, respond naturally or ask for clarification.

Maintain a helpful and professional tone.
"""

from agent import AgentState # Import AgentState TypedDict

def main():
    print("DevOps AI Agent (type 'exit' to quit)")
    
    # Initialize the full agent state
    current_agent_state: AgentState = {
        "messages": [SystemMessage(content=SYSTEM_PROMPT_TEXT)],
        "pending_action_details": None,
        "is_awaiting_confirmation": False
    }

    while True:
        user_input = input("User: ")
        if user_input.strip().lower() == "exit":
            print("Exiting agent.")
            break

        # Prepare the input for the agent, including all parts of the current state
        # and adding the new user message.
        invoke_input: AgentState = {
            "messages": current_agent_state["messages"] + [HumanMessage(content=user_input)],
            "pending_action_details": current_agent_state.get("pending_action_details"),
            "is_awaiting_confirmation": current_agent_state.get("is_awaiting_confirmation", False)
        }
        
        response_state = _agent_runnable.invoke(invoke_input, config={"recursion_limit": 10})
        
        # Update the full agent state with the response from the agent
        current_agent_state = response_state
        
        # Extract the last AI message for display
        agent_reply_content = "Agent did not provide a response."
        if current_agent_state and current_agent_state.get("messages"):
            last_message = current_agent_state["messages"][-1]
            if isinstance(last_message, AIMessage):
                agent_reply_content = str(last_message.content or "Agent processed the request.")
        
        print(f"Agent: {agent_reply_content}")

def run_ec2_instance():
    try:
        response = ec2_client.run_instances()
        instance_ids = [inst.get('InstanceId') for inst in response.get('Instances', [])]
        ids_str = ", ".join(instance_ids)
        return f"EC2 instance launched successfully. Instance IDs: {ids_str}"
    except Exception as e:
        return f"Error launching EC2 instance: {str(e)}"

def parse_intent(text: str) -> str:
    lower = text.lower()
    if 'ec2' in lower and any(word in lower for word in ('run', 'launch')):
        return 'run_ec2_instance'
    return 'unknown'

if __name__ == "__main__":
    main()
