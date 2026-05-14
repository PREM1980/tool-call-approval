import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app

client = TestClient(app)


def test_create_session_returns_session_id():
    response = client.post("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 0


def test_chat_unknown_session_returns_404():
    response = client.post(
        "/sessions/nonexistent/chat", json={"message": "hello"}
    )
    assert response.status_code == 404


def test_approve_unknown_session_returns_404():
    response = client.post(
        "/sessions/nonexistent/approve", json={"approved": True}
    )
    assert response.status_code == 404


def test_stream_unknown_session_returns_404():
    response = client.get("/sessions/nonexistent/stream")
    assert response.status_code == 404


def test_chat_known_session_returns_processing():
    session_res = client.post("/sessions")
    sid = session_res.json()["session_id"]

    with patch("main.asyncio.create_task"):
        response = client.post(f"/sessions/{sid}/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json()["status"] == "processing"


def test_approve_known_session_returns_ok():
    session_res = client.post("/sessions")
    sid = session_res.json()["session_id"]

    response = client.post(f"/sessions/{sid}/approve", json={"approved": True})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
