"""
Multi-Agent Orchestrator for DevOps

This module implements a basic orchestrator for coordinating multiple specialized AI agents
for DevOps tasks. It builds on the existing MCP infrastructure to enable agent collaboration.
"""

import os
import json
import logging
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
from dataclasses import dataclass, field
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger("multi_agent_orchestrator")

# Agent types
class AgentType(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    SECURITY = "security"
    COST = "cost"

@dataclass
class AgentTask:
    """A task to be performed by an agent"""
    id: str
    agent_type: AgentType
    description: str
    parameters: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def mark_started(self):
        self.status = "running"
        self.started_at = time.time()
        
    def mark_completed(self, result: Dict[str, Any]):
        self.status = "completed"
        self.result = result
        self.completed_at = time.time()
        
    def mark_failed(self, error: str):
        self.status = "failed"
        self.result = {"error": error}
        self.completed_at = time.time()
        
    @property
    def duration(self) -> Optional[float]:
        """Return task duration in seconds, or None if not completed"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

@dataclass
class ExecutionPlan:
    """A plan for executing a sequence of agent tasks"""
    id: str
    name: str
    description: str
    tasks: List[AgentTask]
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def get_next_runnable_tasks(self) -> List[AgentTask]:
        """Get tasks that are ready to run (all dependencies satisfied)"""
        completed_task_ids = {t.id for t in self.tasks if t.status == "completed"}
        return [
            task for task in self.tasks
            if task.status == "pending" and all(dep in completed_task_ids for dep in task.depends_on)
        ]
    
    def is_complete(self) -> bool:
        """Check if all tasks are completed or failed"""
        return all(task.status in ["completed", "failed"] for task in self.tasks)
    
    def mark_started(self):
        self.status = "running"
        self.started_at = time.time()
        
    def mark_completed(self):
        self.status = "completed"
        self.completed_at = time.time()
    
    def mark_failed(self):
        self.status = "failed"
        self.completed_at = time.time()
        
    @property
    def duration(self) -> Optional[float]:
        """Return plan duration in seconds, or None if not completed"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

class KnowledgeBase:
    """Shared knowledge base for multi-agent system"""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize knowledge base"""
        self.resources = {}  # AWS resources indexed by resource_id
        self.resources_by_type = {}  # AWS resources indexed by resource_type
        self.deployments = []  # Deployment records
        self.execution_history = []  # Previous execution plans
        self.agent_memories = {}  # Agent-specific memories
        self.lock = threading.RLock()  # Thread-safe operations
        self.db_path = db_path
        
        if db_path and os.path.exists(db_path):
            self.load()
    
    def register_resource(self, resource_type: str, resource_id: str, metadata: Dict[str, Any]):
        """Register a resource in the knowledge base"""
        with self.lock:
            self.resources[resource_id] = {
                "type": resource_type,
                "id": resource_id,
                "metadata": metadata,
                "created_at": time.time()
            }
            
            if resource_type not in self.resources_by_type:
                self.resources_by_type[resource_type] = {}
            
            self.resources_by_type[resource_type][resource_id] = self.resources[resource_id]
            
            if self.db_path:
                self.save()
    
    def get_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """Get a resource by ID"""
        with self.lock:
            return self.resources.get(resource_id)
    
    def get_resources_by_type(self, resource_type: str) -> Dict[str, Dict[str, Any]]:
        """Get all resources of a specific type"""
        with self.lock:
            return self.resources_by_type.get(resource_type, {})
    
    def register_deployment(self, deployment_info: Dict[str, Any]):
        """Register a deployment"""
        with self.lock:
            deployment_record = {
                **deployment_info,
                "created_at": time.time()
            }
            self.deployments.append(deployment_record)
            
            if self.db_path:
                self.save()
            
            return deployment_record
    
    def get_deployments(self) -> List[Dict[str, Any]]:
        """Get all deployments"""
        with self.lock:
            return self.deployments.copy()
    
    def add_execution_plan(self, plan: ExecutionPlan):
        """Add an execution plan to history"""
        with self.lock:
            self.execution_history.append(plan)
            
            if self.db_path:
                self.save()
    
    def update_agent_memory(self, agent_type: AgentType, key: str, value: Any):
        """Update an agent's memory"""
        with self.lock:
            if agent_type not in self.agent_memories:
                self.agent_memories[agent_type] = {}
                
            self.agent_memories[agent_type][key] = value
            
            if self.db_path:
                self.save()
    
    def get_agent_memory(self, agent_type: AgentType, key: str, default: Any = None) -> Any:
        """Get an item from an agent's memory"""
        with self.lock:
            if agent_type not in self.agent_memories:
                return default
                
            return self.agent_memories[agent_type].get(key, default)
    
    def save(self):
        """Save knowledge base to disk"""
        try:
            with open(self.db_path, 'w') as f:
                json.dump({
                    "resources": self.resources,
                    "deployments": self.deployments,
                    "agent_memories": self.agent_memories,
                    # Don't save execution_history as it contains non-serializable objects
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save knowledge base: {e}")
    
    def load(self):
        """Load knowledge base from disk"""
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
                self.resources = data.get("resources", {})
                self.resources_by_type = {}
                
                # Rebuild resources_by_type index
                for resource_id, resource in self.resources.items():
                    resource_type = resource["type"]
                    if resource_type not in self.resources_by_type:
                        self.resources_by_type[resource_type] = {}
                    self.resources_by_type[resource_type][resource_id] = resource
                
                self.deployments = data.get("deployments", [])
                self.agent_memories = data.get("agent_memories", {})
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")


class BaseAgent:
    """Base class for all specialized agents"""
    
    def __init__(self, agent_type: AgentType, knowledge_base: KnowledgeBase):
        self.agent_type = agent_type
        self.knowledge_base = knowledge_base
        self.mcp_servers = {}  # MCP servers indexed by server_name
        
    def register_mcp_server(self, server_name: str, server_url: str):
        """Register an MCP server for this agent"""
        self.mcp_servers[server_name] = server_url
        
    def can_handle(self, task_description: str) -> bool:
        """Determine if this agent can handle a given task (to be implemented by subclasses)"""
        raise NotImplementedError("Subclasses must implement can_handle")
    
    def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute a task (to be implemented by subclasses)"""
        raise NotImplementedError("Subclasses must implement execute_task")


class InfrastructureAgent(BaseAgent):
    """Agent responsible for AWS infrastructure management"""
    
    def __init__(self, knowledge_base: KnowledgeBase):
        super().__init__(AgentType.INFRASTRUCTURE, knowledge_base)
        # Register AWS MCP server
        self.register_mcp_server("aws-devops", "http://localhost:8000")
        
    def can_handle(self, task_description: str) -> bool:
        """Determine if this agent can handle a given task"""
        # Simple keyword-based determination for now
        infrastructure_keywords = [
            "ec2", "s3", "vpc", "subnet", "security group", "load balancer",
            "create instance", "launch instance", "provision", "infrastructure"
        ]
        return any(keyword in task_description.lower() for keyword in infrastructure_keywords)
    
    def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute an infrastructure task"""
        logger.info(f"Infrastructure agent executing task: {task.description}")
        
        # This is where you would integrate with your existing AWS MCP server
        # For now, we'll simulate success with mock data
        
        if "ec2" in task.description.lower():
            # Simulate EC2 instance creation
            instance_id = f"i-{int(time.time())}"
            self.knowledge_base.register_resource(
                "ec2_instance", 
                instance_id, 
                {
                    "instance_type": task.parameters.get("instance_type", "t2.micro"),
                    "region": task.parameters.get("region", "us-east-1"),
                    "status": "running"
                }
            )
            return {
                "instance_id": instance_id,
                "status": "running",
                "public_ip": "192.168.1.1"  # Mock IP
            }
            
        elif "s3" in task.description.lower():
            # Simulate S3 bucket creation
            bucket_name = task.parameters.get("bucket_name", f"bucket-{int(time.time())}")
            self.knowledge_base.register_resource(
                "s3_bucket", 
                bucket_name, 
                {
                    "region": task.parameters.get("region", "us-east-1"),
                    "acl": task.parameters.get("acl", "private")
                }
            )
            return {
                "bucket_name": bucket_name,
                "bucket_url": f"https://{bucket_name}.s3.amazonaws.com"
            }
            
        # Default case
        return {
            "message": f"Simulated infrastructure task: {task.description}",
            "status": "completed"
        }


class DeploymentAgent(BaseAgent):
    """Agent responsible for application deployment"""
    
    def __init__(self, knowledge_base: KnowledgeBase):
        super().__init__(AgentType.DEPLOYMENT, knowledge_base)
        
    def can_handle(self, task_description: str) -> bool:
        """Determine if this agent can handle a given task"""
        deployment_keywords = [
            "deploy", "release", "version", "build", "pipeline", "ci/cd",
            "continuous integration", "continuous deployment", "git", "docker"
        ]
        return any(keyword in task_description.lower() for keyword in deployment_keywords)
    
    def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute a deployment task"""
        logger.info(f"Deployment agent executing task: {task.description}")
        
        # Simulate deployment
        deployment_id = f"dep-{int(time.time())}"
        deployment_info = {
            "id": deployment_id,
            "application": task.parameters.get("application", "unknown"),
            "version": task.parameters.get("version", "1.0.0"),
            "environment": task.parameters.get("environment", "dev"),
            "status": "success"
        }
        
        self.knowledge_base.register_deployment(deployment_info)
        
        return {
            "deployment_id": deployment_id,
            "status": "success",
            "url": f"https://{deployment_info['environment']}.example.com"
        }


class MonitoringAgent(BaseAgent):
    """Agent responsible for monitoring and alerting"""
    
    def __init__(self, knowledge_base: KnowledgeBase):
        super().__init__(AgentType.MONITORING, knowledge_base)
        
    def can_handle(self, task_description: str) -> bool:
        """Determine if this agent can handle a given task"""
        monitoring_keywords = [
            "monitor", "alert", "metric", "log", "dashboard", "cloudwatch",
            "performance", "health", "status", "notification"
        ]
        return any(keyword in task_description.lower() for keyword in monitoring_keywords)
    
    def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute a monitoring task"""
        logger.info(f"Monitoring agent executing task: {task.description}")
        
        # Simulate monitoring setup
        return {
            "message": f"Set up monitoring for: {task.description}",
            "dashboard_url": "https://monitoring.example.com/dashboard/123",
            "alerts_configured": ["CPU > 80%", "Memory > 90%"]
        }


class Orchestrator:
    """Orchestrator for coordinating multiple agents"""
    
    def __init__(self, knowledge_base_path: Optional[str] = None):
        """Initialize the orchestrator with agents"""
        self.knowledge_base = KnowledgeBase(knowledge_base_path)
        
        # Initialize agents
        self.agents = {
            AgentType.INFRASTRUCTURE: InfrastructureAgent(self.knowledge_base),
            AgentType.DEPLOYMENT: DeploymentAgent(self.knowledge_base),
            AgentType.MONITORING: MonitoringAgent(self.knowledge_base)
        }
        
        # Track active plans
        self.active_plans: Dict[str, ExecutionPlan] = {}
        self.plan_threads: Dict[str, threading.Thread] = {}
        self.lock = threading.RLock()
    
    def analyze_request(self, request: str) -> List[AgentType]:
        """Determine which agents are needed for this request"""
        required_agents = []
        
        for agent_type, agent in self.agents.items():
            if agent.can_handle(request):
                required_agents.append(agent_type)
                
        if not required_agents:
            # Default to infrastructure if no agent matched
            required_agents.append(AgentType.INFRASTRUCTURE)
            
        return required_agents
    
    def create_plan(self, request: str, plan_name: str = None) -> ExecutionPlan:
        """Create an execution plan for a request"""
        logger.info(f"Creating plan for request: {request}")
        
        required_agent_types = self.analyze_request(request)
        plan_id = f"plan-{int(time.time())}"
        
        if not plan_name:
            plan_name = f"Plan for: {request[:50]}..."
            
        tasks = []
        
        # For this basic implementation, create one task per required agent
        # In a more advanced implementation, you would use LLM to break down
        # the request into specific tasks with dependencies
        
        for i, agent_type in enumerate(required_agent_types):
            task_id = f"{plan_id}-task-{i}"
            depends_on = []
            
            # Simple sequential dependencies for now
            if i > 0:
                depends_on = [f"{plan_id}-task-{i-1}"]
                
            task = AgentTask(
                id=task_id,
                agent_type=agent_type,
                description=f"{agent_type.value.capitalize()} task for: {request}",
                parameters={},  # Would be populated by LLM in full implementation
                depends_on=depends_on
            )
            tasks.append(task)
            
        plan = ExecutionPlan(
            id=plan_id,
            name=plan_name,
            description=request,
            tasks=tasks
        )
        
        return plan
    
    def execute_plan(self, plan: ExecutionPlan, async_execution: bool = False) -> ExecutionPlan:
        """Execute a plan, either synchronously or asynchronously"""
        with self.lock:
            self.active_plans[plan.id] = plan
            
        if async_execution:
            thread = threading.Thread(target=self._execute_plan_thread, args=(plan.id,))
            thread.daemon = True
            with self.lock:
                self.plan_threads[plan.id] = thread
            thread.start()
            return plan
        else:
            return self._execute_plan(plan.id)
    
    def _execute_plan_thread(self, plan_id: str):
        """Thread function for asynchronous plan execution"""
        try:
            self._execute_plan(plan_id)
        except Exception as e:
            logger.error(f"Error executing plan {plan_id}: {e}")
            with self.lock:
                if plan_id in self.active_plans:
                    self.active_plans[plan_id].mark_failed()
    
    def _execute_plan(self, plan_id: str) -> ExecutionPlan:
        """Internal method to execute a plan"""
        with self.lock:
            if plan_id not in self.active_plans:
                raise ValueError(f"Plan {plan_id} not found")
            
            plan = self.active_plans[plan_id]
            plan.mark_started()
            
        logger.info(f"Executing plan: {plan.name} ({plan.id})")
        
        while True:
            # Get next tasks to run
            with self.lock:
                if plan_id not in self.active_plans:
                    # Plan was removed
                    break
                
                next_tasks = plan.get_next_runnable_tasks()
                
                if not next_tasks:
                    # No more tasks to run
                    if plan.is_complete():
                        logger.info(f"Plan {plan.id} completed")
                        plan.mark_completed()
                    else:
                        # This shouldn't happen in a properly constructed plan
                        logger.warning(f"Plan {plan.id} has no runnable tasks but is not complete")
                        plan.mark_failed()
                    break
            
            # Execute each ready task
            for task in next_tasks:
                self._execute_task(task)
        
        # Store completed plan in knowledge base
        self.knowledge_base.add_execution_plan(plan)
        
        # Clean up
        with self.lock:
            if plan_id in self.active_plans:
                completed_plan = self.active_plans[plan_id]
                del self.active_plans[plan_id]
                if plan_id in self.plan_threads:
                    del self.plan_threads[plan_id]
                return completed_plan
        
        # This should not happen
        return plan
    
    def _execute_task(self, task: AgentTask):
        """Execute a single task"""
        logger.info(f"Executing task: {task.description} ({task.id})")
        
        try:
            task.mark_started()
            
            agent = self.agents.get(task.agent_type)
            if not agent:
                raise ValueError(f"No agent available for type: {task.agent_type}")
                
            result = agent.execute_task(task)
            task.mark_completed(result)
            
            logger.info(f"Task {task.id} completed successfully")
            return task
            
        except Exception as e:
            logger.error(f"Error executing task {task.id}: {e}")
            task.mark_failed(str(e))
            return task
    
    def get_plan_status(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Get the status of a plan"""
        with self.lock:
            return self.active_plans.get(plan_id)
    
    def process_request(self, request: str, async_execution: bool = False) -> Union[ExecutionPlan, str]:
        """Process a user request"""
        try:
            plan = self.create_plan(request)
            return self.execute_plan(plan, async_execution)
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return f"Error: {str(e)}"


# Example usage
if __name__ == "__main__":
    # Initialize orchestrator
    orchestrator = Orchestrator("knowledge_base.json")
    
    # Process a request
    plan = orchestrator.process_request("Deploy a web application with EC2 instances and S3 storage")
    
    # Print results
    print(f"Plan: {plan.name} ({plan.id})")
    print(f"Status: {plan.status}")
    print(f"Duration: {plan.duration:.2f} seconds")
    print("\nTasks:")
    
    for task in plan.tasks:
        print(f"  - {task.agent_type.value}: {task.status} ({task.duration:.2f}s)")
        if task.result:
            print(f"    Result: {task.result}")
