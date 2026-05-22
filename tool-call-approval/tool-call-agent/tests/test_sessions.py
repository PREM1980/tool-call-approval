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
        cur.execute("DELETE FROM ai.agno_sessions")
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
            INSERT INTO ai.agno_sessions (session_id, session_type, created_at, updated_at, runs)
            VALUES ('test-id-1', 'agent', 1000000, 1000010, '[{}, {}]')
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


def test_list_sessions_ordered_by_updated_at_desc():
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ai.agno_sessions (session_id, session_type, created_at, updated_at, runs)
            VALUES ('older', 'agent', 1000000, 1000010, '[]'),
                   ('newer', 'agent', 1000020, 1000030, '[{}]')
        """)
    conn.commit()
    conn.close()

    data = http.get("/sessions").json()
    assert data[0]["session_id"] == "newer"
    assert data[1]["session_id"] == "older"


def test_list_sessions_null_runs_returns_zero_turns():
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ai.agno_sessions (session_id, session_type, created_at, updated_at, runs)
            VALUES ('no-runs', 'agent', 1000000, 1000010, NULL)
        """)
    conn.commit()
    conn.close()

    data = http.get("/sessions").json()
    assert data[0]["turn_count"] == 0
