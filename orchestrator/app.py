import os
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()

AWS_DEVOPS_MCP_URL = os.getenv("AWS_DEVOPS_MCP_URL", "http://localhost:8000")
CODE_MCP_URL = os.getenv("CODE_MCP_URL", "http://localhost:8001")

MCP_SERVERS = {
    "aws_devops": AWS_DEVOPS_MCP_URL,
    "code_analysis": CODE_MCP_URL,
}

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/agents")
async def list_agents():
    statuses = {}
    for name, base_url in MCP_SERVERS.items():
        url = f"{base_url.rstrip('/')}/healthz"
        try:
            resp = httpx.get(url, timeout=2)
            statuses[name] = "healthy" if resp.status_code == 200 else f"error:{resp.status_code}"
        except Exception as e:
            statuses[name] = f"down:{e}"
    return statuses

class ProvisionSpec(BaseModel):
    image_id: str
    bucket_name: str
    instance_type: str = "t2.micro"
    min_count: int = 1
    max_count: int = 1

@app.post("/orchestrate/provision_dev_environment")
async def provision_dev_environment(spec: ProvisionSpec):
    ec2_payload = {
        "image_id": spec.image_id,
        "min_count": spec.min_count,
        "max_count": spec.max_count,
        "instance_type": spec.instance_type,
    }
    s3_payload = {
        "bucket_name": spec.bucket_name,
        "region": os.getenv("AWS_DEFAULT_REGION", None),
    }
    results = {}
    async with httpx.AsyncClient() as client:
        ec2_resp = await client.post(
            f"{AWS_DEVOPS_MCP_URL.rstrip('/')}/execute_tool/create_ec2_instance",
            json=ec2_payload,
            timeout=60,
        )
        if ec2_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="EC2 agent error")
        results["ec2"] = ec2_resp.json()

        s3_resp = await client.post(
            f"{AWS_DEVOPS_MCP_URL.rstrip('/')}/execute_tool/create_s3_bucket",
            json=s3_payload,
            timeout=60,
        )
        if s3_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="S3 agent error")
        results["s3"] = s3_resp.json()

    return results