# AI Agent Project

## Project Goal

The ultimate goal of this project is to build an autonomous DevOps multi-agent system, inspired by concepts like Manus AI. This system aims to create and modify cloud infrastructure dynamically based on user needs.

Currently, the project includes:
1. An agent that directly uses Boto3 for creating cloud resources (e.g., EC2, S3).
2. An agent that utilizes an MCP (Model Context Protocol) server to communicate with AWS.

This README details the current single-agent architecture with MCP server integration, which serves as a foundation for the multi-agent system.

## Overview

The core of this project is an AI agent designed to perform various tasks, leveraging a flexible architecture that includes Model Context Protocol (MCP) servers for extended capabilities. It can interact with the file system, run commands, and potentially integrate with external services.

## Model Context Protocol (MCP) Servers

MCP servers are a key component of this agent's architecture. They act as extendable modules that provide specialized tools and resources to the agent. This allows the agent to interface with various services and perform a wider range of actions.

### How MCP Servers Work

-   **Tools**: MCP servers expose specific `tools` (functions or operations) that the agent can invoke. For example, a `aws-devops-mcp-server` might provide tools to create and manage AWS resources like EC2 instances or S3 buckets.
-   **Resources**: They can also provide access to `resources` (data or information) that the agent can use as context.
-   **Extensibility**: New MCP servers can be developed and integrated to add new functionalities to the agent without modifying its core code. This makes the system highly modular and adaptable.

### Example: `aws-devops-mcp-server`

The `Cline/MCP/aws-devops-mcp-server/` directory in this project contains an example of an MCP server. This server is designed to provide DevOps capabilities related to AWS, such as:
-   Creating EC2 instances
-   Managing S3 buckets

When the agent needs to perform an AWS-related task, it can communicate with this MCP server, which then executes the necessary actions using the AWS SDK.

## Project Structure

Here's a brief overview of the important directories and files in this project:

-   `agent.py`: Likely contains the main logic for the core agent.
-   `main.py`: Could be the entry point for running the agent or a specific part of the application.
-   `requirements.txt`: Lists the Python dependencies for the project.
-   `agent_mcp/`: This directory seems to contain components related to the agent's interaction with MCP servers or a specific MCP-enabled agent implementation.
    -   `agent_mcp/agent.py`
    -   `agent_mcp/main.py`
-   `Cline/MCP/aws-devops-mcp-server/`: Contains the source code and build files for the AWS DevOps MCP server.
    -   `src/`: TypeScript source files for the server.
    -   `build/`: Compiled JavaScript files for the server.
    -   `index.js` (in `build/`): The entry point for running this Node.js-based MCP server.
-   `devops_tools/`: May contain scripts or modules related to DevOps tasks, possibly used by the agent or MCP servers.
-   `orchestrator/`: Suggests a component responsible for managing or coordinating different parts of the system, perhaps including the agent and MCP servers.
    -   `app.py`: Main application file for the orchestrator.
    -   `Dockerfile`: Indicates that the orchestrator can be containerized using Docker.

## Getting Started

This section provides basic instructions to get the project up and running.

### Prerequisites

-   Python 3.8+
-   Node.js and npm (for the `aws-devops-mcp-server`)
-   Docker (optional, for the `orchestrator`)

### 1. Setup Python Environment & Install Dependencies

It's recommended to use a virtual environment.

```bash
# Create a virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install Python dependencies
pip install -r requirements.txt
```

If the `orchestrator` has its own dependencies, navigate to its directory and install them:
```bash
cd orchestrator
pip install -r requirements.txt
cd ..
```

### 2. Running the Agent

The main entry point for the agent might be `main.py` or `agent_mcp/main.py`.

To run the primary agent:
```bash
python main.py
```
Or, if the MCP-specific agent is the main one to run:
```bash
python agent_mcp/main.py
```
(Please verify the correct entry point for your specific use case.)

### 3. Setting Up and Running the `aws-devops-mcp-server`

This MCP server is a Node.js application.

```bash
# Navigate to the server directory
cd Cline/MCP/aws-devops-mcp-server

# Install Node.js dependencies
npm install

# Build the TypeScript source (if not already built or if changes were made in src/)
npm run build  # Assuming a build script is defined in package.json, e.g., "build": "tsc"

# Run the MCP server
node build/index.js
```
This server will then be available for the agent to communicate with. Ensure any necessary AWS credentials and configurations are set up in the environment where this server runs.

### 4. Running the Orchestrator (Optional)

The `orchestrator` component can be run directly using Python or as a Docker container.

**Directly with Python:**
```bash
cd orchestrator
# Ensure environment variables are set if needed (e.g., via a .env file based on .env.example)
python app.py
cd ..
```

**Using Docker:**
```bash
cd orchestrator
docker build -t my-orchestrator .
docker run -p <host_port>:<container_port> my-orchestrator # Replace ports as needed
cd ..
```

### Configuration

-   Ensure any `.env` files or environment variables required by the agent, MCP server, or orchestrator are properly configured. For example, the `orchestrator/.env.example` suggests that environment variables might be used.
-   The `aws-devops-mcp-server` will likely require AWS credentials to be configured in its environment (e.g., via `~/.aws/credentials`, environment variables like `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, or an IAM role if running on EC2).

With these steps, you should be able to run the AI agent and its associated MCP server. You can then start interacting with the agent to perform tasks.
