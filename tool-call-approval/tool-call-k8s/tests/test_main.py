from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _agent(name: str = "my-agent-ui-agents") -> dict:
    return {
        "name": name,
        "namespace": "default",
        "image": "img:latest",
        "replicas": 1,
        "ready_replicas": 1,
        "status": "Running",
    }


# ── POST /kubeconfig ─────────────────────────────────────────────────────────

def test_save_kubeconfig_calls_write():
    with patch("k8s_service.write_kubeconfig") as mock:
        resp = client.post("/kubeconfig", json={"content": "apiVersion: v1"})
    assert resp.status_code == 200
    mock.assert_called_once_with("apiVersion: v1")


def test_save_kubeconfig_propagates_error():
    with patch("k8s_service.write_kubeconfig", side_effect=OSError("permission denied")):
        resp = client.post("/kubeconfig", json={"content": "x"})
    assert resp.status_code == 500


# ── POST /agents ─────────────────────────────────────────────────────────────

def test_create_agent_returns_201():
    with patch("k8s_service.create_deployment", return_value=_agent()):
        resp = client.post("/agents", json={
            "name": "my-agent", "image": "img:latest",
            "namespace": "default", "replicas": 1, "env": [],
        })
    assert resp.status_code == 201
    assert resp.json()["name"] == "my-agent-ui-agents"


def test_create_agent_already_exists_returns_400():
    with patch("k8s_service.create_deployment", side_effect=RuntimeError("already exists")):
        resp = client.post("/agents", json={"name": "x", "image": "img"})
    assert resp.status_code == 400


def test_create_agent_no_kubeconfig_returns_503():
    with patch("k8s_service.create_deployment", side_effect=RuntimeError("kubeconfig not configured")):
        resp = client.post("/agents", json={"name": "x", "image": "img"})
    assert resp.status_code == 503


# ── GET /agents ───────────────────────────────────────────────────────────────

def test_list_agents():
    with patch("k8s_service.list_deployments", return_value=[_agent()]):
        resp = client.get("/agents")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "Running"


def test_list_agents_no_kubeconfig_returns_503():
    with patch("k8s_service.list_deployments", side_effect=RuntimeError("kubeconfig not configured")):
        resp = client.get("/agents")
    assert resp.status_code == 503


# ── DELETE /agents/{name} ────────────────────────────────────────────────────

def test_delete_agent():
    with patch("k8s_service.delete_deployment") as mock:
        resp = client.delete("/agents/my-agent-ui-agents")
    assert resp.status_code == 200
    mock.assert_called_once_with("my-agent-ui-agents", "default")


def test_delete_agent_not_found_returns_404():
    with patch("k8s_service.delete_deployment", side_effect=RuntimeError("not found")):
        resp = client.delete("/agents/missing-ui-agents")
    assert resp.status_code == 404


# ── POST /agents/{name}/restart ───────────────────────────────────────────────

def test_restart_agent():
    with patch("k8s_service.restart_deployment") as mock:
        resp = client.post("/agents/my-agent-ui-agents/restart")
    assert resp.status_code == 200
    mock.assert_called_once_with("my-agent-ui-agents", "default")


def test_restart_agent_not_found_returns_404():
    with patch("k8s_service.restart_deployment", side_effect=RuntimeError("not found")):
        resp = client.post("/agents/missing-ui-agents/restart")
    assert resp.status_code == 404


# ── PATCH /agents/{name}/scale ───────────────────────────────────────────────

def test_scale_agent():
    with patch("k8s_service.scale_deployment") as mock:
        resp = client.patch("/agents/my-agent-ui-agents/scale", json={"replicas": 3})
    assert resp.status_code == 200
    mock.assert_called_once_with("my-agent-ui-agents", "default", 3)


def test_scale_agent_not_found_returns_404():
    with patch("k8s_service.scale_deployment", side_effect=RuntimeError("not found")):
        resp = client.patch("/agents/missing-ui-agents/scale", json={"replicas": 2})
    assert resp.status_code == 404
