# Multi-Agent DevOps Orchestrator

This orchestrator coordinates multiple specialized AI agents to handle DevOps tasks in a collaborative manner. It's designed to be an extensible framework for building a system similar to Manus AI.

## Overview

The multi-agent orchestrator manages several specialized agents, each focused on a specific aspect of DevOps:

- **Infrastructure Agent**: Manages AWS resources (EC2, S3, etc.)
- **Deployment Agent**: Handles application deployment and CI/CD
- **Monitoring Agent**: Sets up monitoring, alerting, and dashboards

These agents collaborate through a shared knowledge base and are coordinated by the orchestrator to handle complex tasks that span multiple domains.

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                       Orchestrator                            │
└───────────┬───────────────┬───────────────┬───────────────────┘
            │               │               │
            ▼               ▼               ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Infrastructure │   │   Deployment  │   │   Monitoring  │
│     Agent      │   │     Agent     │   │     Agent     │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────────────────────────────────────────────────────┐
│                     Shared Knowledge Base                      │
└───────────────────────────────────────────────────────────────┘
```

## Features

- **Task Distribution**: Automatically routes requests to the appropriate specialized agents
- **Execution Planning**: Creates dependency-based plans for complex tasks
- **Knowledge Sharing**: Maintains a shared state of resources and deployments
- **API Interface**: RESTful API for programmatic access
- **Asynchronous Execution**: Support for background processing of long-running tasks

## Getting Started

### Prerequisites

- Python 3.8+
- Flask (for the API interface)
- AWS credentials configured (for the Infrastructure Agent)

### Installation

1. Install dependencies:
   ```bash
   pip install flask dataclasses requests threading enum
   ```

2. Configure AWS credentials (for the Infrastructure Agent):
   ```bash
   # Option 1: Environment variables
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   export AWS_DEFAULT_REGION=us-east-1
   
   # Option 2: AWS CLI
   aws configure
   ```

### Running the Orchestrator

1. Start the API server:
   ```bash
   cd orchestrator
   python app.py
   ```

2. The API will be available at `http://localhost:5000`

## API Usage

### Process a DevOps Request

```bash
curl -X POST http://localhost:5000/process \
  -H "Content-Type: application/json" \
  -d '{"request": "Deploy a web application with EC2 instances and S3 storage", "async": true}'
```

### List Available Agents

```bash
curl -X GET http://localhost:5000/agents
```

### List Active Plans

```bash
curl -X GET http://localhost:5000/plans
```

### Get Plan Status

```bash
curl -X GET http://localhost:5000/plans/plan-12345678
```

### List Resources

```bash
curl -X GET http://localhost:5000/resources
```

### List Resources by Type

```bash
curl -X GET "http://localhost:5000/resources?type=ec2_instance"
```

### List Deployments

```bash
curl -X GET http://localhost:5000/deployments
```

### Analyze a Request

```bash
curl -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{"request": "Set up monitoring for my EC2 instances"}'
```

## Extending the System

### Adding a New Agent Type

1. Create a new agent class in `multi_agent_orchestrator.py`:

```python
class SecurityAgent(BaseAgent):
    """Agent responsible for security and compliance"""
    
    def __init__(self, knowledge_base: KnowledgeBase):
        super().__init__(AgentType.SECURITY, knowledge_base)
    
    def can_handle(self, task_description: str) -> bool:
        security_keywords = [
            "security", "compliance", "vulnerability", "scan",
            "iam", "permission", "encrypt", "firewall"
        ]
        return any(keyword in task_description.lower() for keyword in security_keywords)
    
    def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        # Implement security operations
        # ...
        return {"message": "Security task completed"}
```

2. Add the new agent type to the `AgentType` enum:

```python
class AgentType(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    SECURITY = "security"  # New agent type
    COST = "cost"
```

3. Register the new agent in the Orchestrator's `__init__` method:

```python
self.agents = {
    AgentType.INFRASTRUCTURE: InfrastructureAgent(self.knowledge_base),
    AgentType.DEPLOYMENT: DeploymentAgent(self.knowledge_base),
    AgentType.MONITORING: MonitoringAgent(self.knowledge_base),
    AgentType.SECURITY: SecurityAgent(self.knowledge_base),  # New agent
}
```

### Creating an MCP Server for a New Agent

1. Create a new MCP server following the pattern in `Cline/MCP/aws-devops-mcp-server`
2. Implement handlers for the agent's tools
3. Register the MCP server URL in the agent's `__init__` method:

```python
def __init__(self, knowledge_base: KnowledgeBase):
    super().__init__(AgentType.SECURITY, knowledge_base)
    self.register_mcp_server("security-mcp", "http://localhost:8001")
```

## Advanced Usage

### Custom Execution Plans

You can create and execute custom plans with specific task dependencies:

```python
from multi_agent_orchestrator import Orchestrator, AgentTask, AgentType

orchestrator = Orchestrator()

# Create tasks
task1 = AgentTask(
    id="task-1",
    agent_type=AgentType.INFRASTRUCTURE,
    description="Create EC2 instances",
    parameters={"instance_type": "t2.micro", "count": 3},
    depends_on=[]
)

task2 = AgentTask(
    id="task-2",
    agent_type=AgentType.DEPLOYMENT,
    description="Deploy application",
    parameters={"git_repo": "https://github.com/user/repo"},
    depends_on=["task-1"]  # This task depends on task1
)

# Create and execute plan
plan = orchestrator.create_custom_plan("Custom deployment", [task1, task2])
result = orchestrator.execute_plan(plan)
```

### Integrating with LLMs for Plan Generation

For more advanced plan generation, you can integrate with LLMs:

```python
def generate_plan_with_llm(request: str) -> List[Dict]:
    # Use OpenAI or other LLM to break down the request into tasks
    # ...
    return [
        {
            "id": "task-1",
            "agent_type": "infrastructure",
            "description": "Create VPC",
            "parameters": {"cidr_block": "10.0.0.0/16"},
            "depends_on": []
        },
        # More tasks...
    ]

# Then convert the LLM output to AgentTasks and create a plan
```

## Troubleshooting

### Common Issues

- **MCP Server Connection**: Ensure all required MCP servers are running
- **AWS Credentials**: Check that AWS credentials are properly configured
- **Concurrent Operations**: The orchestrator uses locks to prevent race conditions

### Logging

The system logs to both console and file:

- API logs: `orchestrator_api.log`
- Orchestrator logs: `multi_agent_orchestrator.log`

Set log level by setting the `LOG_LEVEL` environment variable:

```bash
export LOG_LEVEL=DEBUG
```

## License

[Your license information]
