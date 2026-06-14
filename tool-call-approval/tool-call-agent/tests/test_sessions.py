import psycopg2
import pytest
from fastapi.testclient import TestClient

from main import app

TEST_URL = "postgresql://localhost:5432/postgres"
http = TestClient(app)


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
    conn.commit()
    conn.close()
    yield


def test_list_sessions_empty():
    response = http.get("/sessions")
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

    response = http.get("/sessions")
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

    data = http.get("/sessions").json()
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

    data = http.get("/sessions").json()
    assert [row["session_id"] for row in data] == ["has-message"]


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

    response = http.get("/sessions/history-id/history")

    assert response.status_code == 200
    assert response.json() == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
