import asyncio
import pytest
from unittest.mock import MagicMock, patch

from repository import IAgentStorage, PostgresRepository


def test_postgres_repository_is_lazy():
    repo = PostgresRepository(url="postgresql+psycopg2://localhost:9999/postgres")
    assert repo._db is None


def test_postgres_repository_raises_when_unreachable():
    repo = PostgresRepository(url="postgresql+psycopg2://localhost:9999/postgres")
    with pytest.raises(RuntimeError, match="not reachable"):
        repo.get_db()


def test_postgres_repository_singleton():
    repo = PostgresRepository(url="postgresql+psycopg2://localhost:5432/postgres")
    with patch("repository.socket.create_connection"), \
         patch("repository.PostgresDb") as MockDb:
        MockDb.return_value = MagicMock()
        db1 = repo.get_db()
        db2 = repo.get_db()
        assert db1 is db2
        assert MockDb.call_count == 1


from session import Session


def test_session_defaults():
    session = Session(id="abc-123")
    assert session.id == "abc-123"
    assert session.queue.empty()
    assert not session.approval_event.is_set()
    assert session.approval_result is False
