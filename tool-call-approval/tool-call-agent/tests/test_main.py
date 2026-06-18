from __future__ import annotations

from fastapi.testclient import TestClient
from types import SimpleNamespace
from unittest.mock import Mock, patch
import app.api.main as main_app
from main import app
from app.domain.session import Session

client = TestClient(app)

EMPTY_DATA = {
    "cmds": [],
    "executed_cmds": [],
    "url_configs": [],
    "user_file_uploads": [],
}
EMPTY_PLATFORM_CONTEXT = {
    "k8s_namespace": None,
    "duplo_base_url": None,
    "duplo_token": None,
    "tenant_name": None,
    "aws_credentials": None,
    "kubeconfig": None,
}
EMPTY_AMBIENT_CONTEXT = {"user_terminal_cmds": []}
EMPTY_SESSION = {
    "session_id": None,
    "instance_id": None,
    "persona_id": None,
    "persona_ids": [],
    "system_prompt_id": None,
    "model_id": None,
    "provider": None,
}


def _session_envelope(**session_overrides: str | None) -> dict:
    session = dict(EMPTY_SESSION)
    session.update(session_overrides)
    return {"session": session, "messages": [], "approval": None}


def _chat_envelope(message: str = "hello", session_id: str | None = None) -> dict:
    session = dict(EMPTY_SESSION)
    if session_id is not None:
        session["session_id"] = session_id
    return {
        "session": session,
        "messages": [
            {
                "role": "user",
                "content": message,
                "data": EMPTY_DATA,
                "timestamp": "2026-06-17T10:00:00Z",
                "user": None,
                "agent": None,
                "platform_context": {
                    **EMPTY_PLATFORM_CONTEXT,
                    "kubeconfig": "apiVersion: v1",
                },
                "ambient_context": EMPTY_AMBIENT_CONTEXT,
            }
        ],
        "approval": None,
    }


def _approval_envelope(session_id: str | None = None) -> dict:
    session = dict(EMPTY_SESSION)
    if session_id is not None:
        session["session_id"] = session_id
    return {
        "session": session,
        "messages": [],
        "approval": {"tool_use_id": "tool-1", "approved": True},
    }


def test_create_session_returns_session_id():
    with patch.object(
        main_app.service,
        "create_session",
        return_value=SimpleNamespace(id="session-123"),
    ):
        response = client.post("/sessions", json=_session_envelope())

    assert response.status_code == 200
    assert response.json() == {"session_id": "session-123"}


def test_chat_unknown_session_returns_404():
    response = client.post(
        "/sessions/nonexistent/chat", json=_chat_envelope("hello", "nonexistent")
    )
    assert response.status_code == 404


def test_approve_unknown_session_returns_404():
    response = client.post(
        "/sessions/nonexistent/approve", json=_approval_envelope("nonexistent")
    )
    assert response.status_code == 404


def test_stream_unknown_session_returns_404():
    response = client.get("/sessions/nonexistent/stream")
    assert response.status_code == 404


def test_chat_known_session_returns_processing():
    sid = "session-123"
    session = Session(id=sid)

    with patch("app.api.main.asyncio.create_task"), \
         patch.object(main_app.service, "get_session", return_value=session), \
         patch.object(main_app.service, "run", new=Mock(return_value=object())), \
         patch.object(main_app.service, "record_user_message") as record_user_message:
        response = client.post(f"/sessions/{sid}/chat", json=_chat_envelope("hello", sid))

    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    record_user_message.assert_called_once()
    assert record_user_message.call_args.args[1] == "hello"
    assert record_user_message.call_args.args[2] == _chat_envelope("hello", sid)["messages"][0]
    assert session.kubeconfig == "apiVersion: v1"


def test_chat_rejects_old_body_shape():
    response = client.post("/sessions/session-123/chat", json={"message": "hello"})

    assert response.status_code == 422


def test_chat_rejects_mismatched_session_id():
    response = client.post(
        "/sessions/session-123/chat",
        json=_chat_envelope("hello", "different-session"),
    )

    assert response.status_code == 400


def test_approve_known_session_returns_ok():
    sid = "session-123"
    session = Session(id=sid)

    with patch.object(main_app.service, "get_session", return_value=session), \
         patch.object(main_app.service, "approve") as approve:
        response = client.post(f"/sessions/{sid}/approve", json=_approval_envelope(sid))

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    approve.assert_called_once_with(session, "tool-1", True)


def test_approve_rejects_old_body_shape():
    response = client.post("/sessions/session-123/approve", json={"approved": True})

    assert response.status_code == 422


def test_get_all_agent_instances_no_filter():
    with patch.object(main_app._admin_repository, "get_all_agent_instances", return_value=[]):
        response = client.get("/admin/agent-instances")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_session_with_null_instance_id():
    with patch.object(
        main_app.service,
        "create_session",
        return_value=SimpleNamespace(id="session-123"),
    ):
        response = client.post("/sessions", json=_session_envelope(instance_id=None))

    assert response.status_code == 200
    assert "session_id" in response.json()


def test_create_session_with_instance_id_string():
    import uuid
    with patch.object(
        main_app.service,
        "create_session",
        return_value=SimpleNamespace(id="session-123"),
    ):
        response = client.post("/sessions", json=_session_envelope(instance_id=str(uuid.uuid4())))

    assert response.status_code == 200
    assert "session_id" in response.json()


def test_create_session_passes_system_prompt_id_to_service():
    with patch.object(
        main_app.service,
        "create_session",
        return_value=SimpleNamespace(id="session-123"),
    ) as create_session:
        response = client.post(
            "/sessions",
            json=_session_envelope(
                instance_id="inst-1",
                system_prompt_id="prompt-1",
                model_id="nemotron-3-super",
                provider="LOCAL",
            ),
        )

    assert response.status_code == 200
    assert response.json() == {"session_id": "session-123"}
    create_session.assert_called_once_with(
        "inst-1",
        None,
        [],
        "prompt-1",
        "nemotron-3-super",
        "LOCAL",
    )


def test_create_session_passes_persona_id_to_service():
    with patch.object(
        main_app.service,
        "create_session",
        return_value=SimpleNamespace(id="session-123"),
    ) as create_session:
        response = client.post(
            "/sessions",
            json=_session_envelope(
                instance_id=None,
                persona_id="persona-1",
                system_prompt_id="prompt-1",
                model_id="nemotron-3-super",
                provider="LOCAL",
            ),
        )

    assert response.status_code == 200
    create_session.assert_called_once_with(
        None,
        "persona-1",
        [],
        "prompt-1",
        "nemotron-3-super",
        "LOCAL",
    )


def test_create_session_passes_persona_ids_to_service():
    with patch.object(
        main_app.service,
        "create_session",
        return_value=SimpleNamespace(id="session-123"),
    ) as create_session:
        response = client.post(
            "/sessions",
            json=_session_envelope(
                instance_id=None,
                persona_id="persona-1",
                persona_ids=["persona-1", "persona-2"],
                system_prompt_id="prompt-1",
                model_id="nemotron-3-super",
                provider="LOCAL",
            ),
        )

    assert response.status_code == 200
    create_session.assert_called_once_with(
        None,
        "persona-1",
        ["persona-1", "persona-2"],
        "prompt-1",
        "nemotron-3-super",
        "LOCAL",
    )


def test_create_session_no_body_is_rejected():
    response = client.post("/sessions")
    assert response.status_code == 422


def test_create_session_rejects_old_body_shape():
    response = client.post("/sessions", json={"instance_id": "inst-1"})
    assert response.status_code == 422
