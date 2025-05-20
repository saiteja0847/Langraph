import os

import httpx
import pytest
from fastapi.testclient import TestClient

from orchestrator.app import app, MCP_SERVERS

client = TestClient(app)

def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

def test_list_agents(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code

    def fake_get(url, timeout):
        return FakeResponse(200)

    monkeypatch.setattr(httpx, "get", fake_get)
    resp = client.get("/agents")
    assert resp.status_code == 200
    data = resp.json()
    for name in MCP_SERVERS:
        assert data[name] == "healthy"

def test_provision_dev_environment(monkeypatch):
    spec = {"image_id": "ami-0abcdef1234567890", "bucket_name": "my-bucket"}

    class FakeResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json = json_data

        def json(self):
            return self._json

    async def fake_post(self, url, json, timeout):
        if "create_ec2_instance" in url:
            return FakeResponse(200, {"status": "success", "result": "ec2-ok"})
        if "create_s3_bucket" in url:
            return FakeResponse(200, {"status": "success", "result": "s3-ok"})
        return FakeResponse(500, {})

    monkeypatch.setenv("AWS_DEVOPS_MCP_URL", "http://fake-server")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    resp = client.post("/orchestrate/provision_dev_environment", json=spec)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ec2"]["result"] == "ec2-ok"
    assert data["s3"]["result"] == "s3-ok"