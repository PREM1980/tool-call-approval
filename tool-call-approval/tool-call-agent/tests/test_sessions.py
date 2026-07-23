import psycopg2
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

import app.api.main as main_app
from app.domain.user import User
from main import app

TEST_URL = "postgresql://localhost:5432/postgres"
http = TestClient(app)
AUTH_USER = User(id="00000000-0000-0000-0000-000000000001", username="admin", role="admin")


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def _allow_auth(user: User = AUTH_USER):
    return patch.object(main_app._auth_service, "get_current_user", return_value=user)


def _owned_session_ids(session_ids: list[str]):
    return patch.object(
        main_app._session_ownership_service,
        "get_session_ids_for_user",
        return_value=session_ids,
    )


def _allow_owner(owns: bool = True):
    return patch.object(main_app._session_ownership_service, "user_owns_session", return_value=owns)


@pytest.fixture(autouse=True)
def clean_sessions():
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS ai")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai.session_records (
                session_id TEXT PRIMARY KEY,
                instance_id TEXT,
                system_prompt_id TEXT,
                system_prompt_name TEXT,
                system_prompt_instructions_snapshot TEXT,
                messages JSONB NOT NULL DEFAULT '[]',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("DELETE FROM ai.session_records")
        cur.execute("""CREATE TABLE IF NOT EXISTS ai.session_events (
            id BIGSERIAL PRIMARY KEY, session_id TEXT NOT NULL, run_id TEXT,
            event_type TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}',
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
        cur.execute("DELETE FROM ai.session_events")
    conn.commit()
    conn.close()
    yield


def test_list_sessions_empty():
    with _allow_auth(), _owned_session_ids([]):
        response = http.get("/sessions", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == []


def test_list_sessions_returns_session():
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ai.session_records (
                session_id,
                system_prompt_id,
                system_prompt_name,
                messages,
                created_at,
                updated_at
            )
            VALUES (
                'test-id-1',
                'prompt-1',
                'default_agent',
                '[{"role": "user", "content": "first question"}, {"role": "assistant", "content": "first answer"}, {"role": "user", "content": "second question"}]',
                to_timestamp(1000000),
                to_timestamp(1000010)
            )
        """)
    conn.commit()
    conn.close()

    with _allow_auth(), _owned_session_ids(["test-id-1"]):
        response = http.get("/sessions", headers=_auth_headers())

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["session_id"] == "test-id-1"
    assert data[0]["turn_count"] == 2
    assert data[0]["created_at"] == 1000000
    assert data[0]["updated_at"] == 1000010
    assert data[0]["first_message"] == "first question"
    assert data[0]["system_prompt_id"] == "prompt-1"
    assert data[0]["system_prompt_name"] == "default_agent"


def test_list_sessions_ordered_by_updated_at_desc():
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ai.session_records (session_id, messages, created_at, updated_at)
            VALUES ('older', '[{"role": "user", "content": "older question"}]', to_timestamp(1000000), to_timestamp(1000010)),
                   ('newer', '[{"role": "user", "content": "hi"}]', to_timestamp(1000020), to_timestamp(1000030))
        """)
    conn.commit()
    conn.close()

    with _allow_auth(), _owned_session_ids(["older", "newer"]):
        data = http.get("/sessions", headers=_auth_headers()).json()

    assert data[0]["session_id"] == "newer"
    assert data[1]["session_id"] == "older"


def test_list_sessions_excludes_empty_message_records():
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ai.session_records (session_id, messages, created_at, updated_at)
            VALUES ('no-messages', '[]', to_timestamp(1000000), to_timestamp(1000010)),
                   ('has-message', '[{"role": "user", "content": "hi"}]', to_timestamp(1000020), to_timestamp(1000030))
        """)
    conn.commit()
    conn.close()

    with _allow_auth(), _owned_session_ids(["no-messages", "has-message"]):
        data = http.get("/sessions", headers=_auth_headers()).json()

    assert [row["session_id"] for row in data] == ["has-message"]


def test_list_sessions_hides_legacy_unowned_records():
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ai.session_records (session_id, messages, created_at, updated_at)
            VALUES ('legacy-session', '[{"role": "user", "content": "old question"}]', NOW(), NOW())
        """)
    conn.commit()
    conn.close()

    with _allow_auth(), _owned_session_ids([]):
        response = http.get("/sessions", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == []


def test_get_history_reads_session_records_messages():
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ai.session_records (session_id, messages, created_at, updated_at)
            VALUES (
                'history-id',
                '[{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi there"}]',
                NOW(),
                NOW()
            )
        """)
    conn.commit()
    conn.close()

    with _allow_auth(), _allow_owner():
        response = http.get("/sessions/history-id/history", headers=_auth_headers())

    assert response.status_code == 200
    data = response.json()
    assert [(message["role"], message["content"]) for message in data] == [
        ("user", "hello"),
        ("assistant", "hi there"),
    ]
    assert "platform_context" in data[0]
    assert "ambient_context" in data[0]


def test_get_events_replays_ordered_session_trace():
    main_app._repository.append_session_event("events-id", "run-1", "tool_call_pending", {"tool_name": "kubectl"})
    main_app._repository.append_session_event("events-id", "run-1", "tool_result", {"result": "ok"})

    with _allow_auth(), _allow_owner():
        response = http.get("/sessions/events-id/events?after_sequence=0", headers=_auth_headers())

    assert response.status_code == 200
    assert [event["event_type"] for event in response.json()] == ["tool_call_pending", "tool_result"]
    assert response.json()[0]["sequence"] < response.json()[1]["sequence"]


def test_delete_session_removes_saved_history_and_ownership():
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ai.session_records (session_id, messages) VALUES ('delete-me', '[{\"role\": \"user\", \"content\": \"hello\"}]')"
        )
    conn.commit()
    conn.close()

    with _allow_auth(), _allow_owner(), patch.object(main_app._session_ownership_service, "delete_owner") as delete_owner:
        response = http.delete("/sessions/delete-me", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}
    assert main_app._repository.get_session_history("delete-me") == []
    delete_owner.assert_called_once_with(AUTH_USER, "delete-me")
