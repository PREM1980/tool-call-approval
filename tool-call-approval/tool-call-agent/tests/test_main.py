import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace
from unittest.mock import patch
import main
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

    with patch("main.asyncio.create_task"), \
         patch.object(main.service, "record_user_message") as record_user_message:
        response = client.post(f"/sessions/{sid}/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    record_user_message.assert_called_once()
    assert record_user_message.call_args.args[1] == "hello"


def test_approve_known_session_returns_ok():
    session_res = client.post("/sessions")
    sid = session_res.json()["session_id"]

    response = client.post(f"/sessions/{sid}/approve", json={"approved": True})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_all_agent_instances_no_filter():
    response = client.get("/admin/agent-instances")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_session_with_null_instance_id():
    response = client.post("/sessions", json={"instance_id": None})
    assert response.status_code == 200
    assert "session_id" in response.json()


def test_create_session_with_instance_id_string():
    import uuid
    response = client.post("/sessions", json={"instance_id": str(uuid.uuid4())})
    assert response.status_code == 200
    assert "session_id" in response.json()


def test_create_session_passes_system_prompt_id_to_service():
    with patch.object(
        main.service,
        "create_session",
        return_value=SimpleNamespace(id="session-123"),
    ) as create_session:
        response = client.post(
            "/sessions",
            json={"instance_id": "inst-1", "system_prompt_id": "prompt-1"},
        )

    assert response.status_code == 200
    assert response.json() == {"session_id": "session-123"}
    create_session.assert_called_once_with("inst-1", "prompt-1")


def test_create_session_no_body_still_works():
    response = client.post("/sessions")
    assert response.status_code == 200
    assert "session_id" in response.json()
