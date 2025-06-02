"""
Multi-Agent DevOps Orchestrator API

This module provides a Flask API for interacting with the multi-agent orchestrator.
"""

import os
import json
import logging
import time
import threading
from typing import Dict, List, Optional, Any
from flask import Flask, request, jsonify
from multi_agent_orchestrator import Orchestrator, AgentType, ExecutionPlan

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger("orchestrator_api")

# Initialize Flask app
app = Flask(__name__)

# Initialize the orchestrator
orchestrator = Orchestrator(knowledge_base_path="knowledge_base.json")

# Create a lock for thread-safe access to the orchestrator
orchestrator_lock = threading.RLock()

def plan_to_dict(plan: ExecutionPlan) -> Dict[str, Any]:
    """Convert an ExecutionPlan to a JSON-serializable dictionary"""
    tasks = []
    for task in plan.tasks:
        tasks.append({
            "id": task.id,
            "agent_type": task.agent_type,
            "description": task.description,
            "parameters": task.parameters,
            "depends_on": task.depends_on,
            "status": task.status,
            "result": task.result,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "duration": task.duration,
        })
    
    return {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "tasks": tasks,
        "status": plan.status,
        "created_at": plan.created_at,
        "started_at": plan.started_at,
        "completed_at": plan.completed_at,
        "duration": plan.duration,
    }

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "timestamp": time.time(),
    })

@app.route('/agents', methods=['GET'])
def list_agents():
    """List all available agents"""
    with orchestrator_lock:
        agents = [
            {
                "type": agent_type.value,
                "description": agent.__class__.__doc__ or "No description available",
            }
            for agent_type, agent in orchestrator.agents.items()
        ]
        
    return jsonify({
        "agents": agents,
    })

@app.route('/process', methods=['POST'])
def process_request():
    """Process a user request"""
    if not request.is_json:
        return jsonify({
            "error": "Request must be JSON"
        }), 400
    
    data = request.get_json()
    
    if 'request' not in data:
        return jsonify({
            "error": "Missing 'request' field"
        }), 400
    
    # Get execution mode (sync or async)
    async_execution = data.get('async', False)
    
    # Optional plan name
    plan_name = data.get('plan_name')
    
    with orchestrator_lock:
        # First, create a plan
        plan = orchestrator.create_plan(data['request'], plan_name)
        
        if async_execution:
            # Start execution in background
            orchestrator.execute_plan(plan, async_execution=True)
            return jsonify({
                "message": "Request submitted for processing",
                "plan": plan_to_dict(plan),
            })
        else:
            # Execute synchronously
            plan = orchestrator.execute_plan(plan, async_execution=False)
            return jsonify({
                "message": "Request processed successfully",
                "plan": plan_to_dict(plan),
            })

@app.route('/plans', methods=['GET'])
def list_plans():
    """List active plans"""
    with orchestrator_lock:
        active_plans = [
            plan_to_dict(plan)
            for plan in orchestrator.active_plans.values()
        ]
    
    return jsonify({
        "active_plans": active_plans,
    })

@app.route('/plans/<plan_id>', methods=['GET'])
def get_plan(plan_id):
    """Get a specific plan"""
    with orchestrator_lock:
        plan = orchestrator.get_plan_status(plan_id)
        
    if not plan:
        return jsonify({
            "error": f"Plan {plan_id} not found"
        }), 404
        
    return jsonify({
        "plan": plan_to_dict(plan),
    })

@app.route('/resources', methods=['GET'])
def list_resources():
    """List all resources in the knowledge base"""
    resource_type = request.args.get('type')
    
    with orchestrator_lock:
        if resource_type:
            resources = orchestrator.knowledge_base.get_resources_by_type(resource_type)
        else:
            resources = orchestrator.knowledge_base.resources
    
    return jsonify({
        "resources": resources,
    })

@app.route('/deployments', methods=['GET'])
def list_deployments():
    """List all deployments in the knowledge base"""
    with orchestrator_lock:
        deployments = orchestrator.knowledge_base.get_deployments()
    
    return jsonify({
        "deployments": deployments,
    })

@app.route('/analyze', methods=['POST'])
def analyze_request():
    """Analyze a request to determine which agents would handle it"""
    if not request.is_json:
        return jsonify({
            "error": "Request must be JSON"
        }), 400
    
    data = request.get_json()
    
    if 'request' not in data:
        return jsonify({
            "error": "Missing 'request' field"
        }), 400
    
    with orchestrator_lock:
        required_agents = orchestrator.analyze_request(data['request'])
    
    return jsonify({
        "request": data['request'],
        "required_agents": [agent.value for agent in required_agents],
    })

if __name__ == '__main__':
    # Get port from environment or use default
    port = int(os.getenv('PORT', 5000))
    
    # Run Flask app
    app.run(host='0.0.0.0', port=port, debug=False)
