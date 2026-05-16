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


from agno.models.response import ToolExecution
from agno.run.agent import RunCompletedEvent, RunContentEvent, RunErrorEvent, RunPausedEvent, ToolCallCompletedEvent
from agno.run.requirement import RunRequirement

from agent_service import AgentService


class MockStorage(IAgentStorage):
    def get_db(self):
        return MagicMock()


@pytest.fixture
def service():
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        svc = AgentService(repository=MockStorage())
    return svc


def test_create_session_returns_session_with_id(service):
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        session = service.create_session()
    assert session.id is not None
    assert len(session.id) == 36  # UUID


def test_get_session_returns_none_for_unknown(service):
    assert service.get_session("nonexistent") is None


def test_get_session_returns_session(service):
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        session = service.create_session()
    assert service.get_session(session.id) is session


def test_approve_sets_result_and_fires_event(service):
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        session = service.create_session()
    service.approve(session, approved=True)
    assert session.approval_result is True
    assert session.approval_event.is_set()


async def test_on_content_puts_message_on_queue(service):
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        session = service.create_session()
    event = RunContentEvent(content="Hello!")
    await service._on_content(session, event, [], [])
    item = await session.queue.get()
    assert item == {"type": "message", "content": "Hello!"}


async def test_on_completed_puts_done_and_removes_session(service):
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        session = service.create_session()
    session_id = session.id
    await service._on_completed(session, RunCompletedEvent(), [], [])
    item = await session.queue.get()
    assert item == {"type": "done"}
    assert service.get_session(session_id) is None


async def test_on_error_puts_error_and_done(service):
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        session = service.create_session()
    event = RunErrorEvent(content="boom")
    await service._on_error(session, event, [], [])
    items = []
    while not session.queue.empty():
        items.append(await session.queue.get())
    types = [i["type"] for i in items]
    assert "error" in types
    assert "done" in types


async def test_dispatch_ignores_unknown_event(service):
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        session = service.create_session()
    result = await service._dispatch(session, object(), [], [])
    assert result is False


async def test_run_happy_path(service):
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        session = service.create_session()

    mock_agent = MagicMock()

    async def fake_arun(*args, **kwargs):
        yield RunContentEvent(content="Hello!")
        yield RunCompletedEvent()

    mock_agent.arun = fake_arun
    service._sessions[session.id] = (session, mock_agent)

    with patch("agent_service.langfuse_context"):
        await service.run(session, "Hi")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "thinking" in types
    assert "message" in types
    assert "done" in types


async def test_run_tool_approved(service):
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        session = service.create_session()

    tool_exec = ToolExecution(
        tool_call_id="tool_123",
        tool_name="calculate",
        tool_args={"expression": "2 + 2"},
        requires_confirmation=True,
    )
    requirement = RunRequirement(tool_execution=tool_exec)
    paused_event = RunPausedEvent(tools=[tool_exec], requirements=[requirement], run_id="run-1")

    mock_agent = MagicMock()

    async def fake_arun(*args, **kwargs):
        yield paused_event

    async def fake_acontinue_run(*args, **kwargs):
        yield ToolCallCompletedEvent(tool=tool_exec, content="4")
        yield RunContentEvent(content="The answer is 4.")
        yield RunCompletedEvent()

    mock_agent.arun = fake_arun
    mock_agent.acontinue_run = fake_acontinue_run
    service._sessions[session.id] = (session, mock_agent)

    async def approve_after_delay():
        await asyncio.sleep(0.05)
        service.approve(session, approved=True)

    asyncio.create_task(approve_after_delay())

    with patch("agent_service.langfuse_context"):
        await service.run(session, "What is 2+2?")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "tool_call_pending" in types
    assert "tool_result" in types
    assert "message" in types


async def test_run_tool_rejected(service):
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        session = service.create_session()

    tool_exec = ToolExecution(
        tool_call_id="tool_456",
        tool_name="get_weather",
        tool_args={"city": "London"},
        requires_confirmation=True,
    )
    requirement = RunRequirement(tool_execution=tool_exec)
    paused_event = RunPausedEvent(tools=[tool_exec], requirements=[requirement], run_id="run-2")

    mock_agent = MagicMock()

    async def fake_arun(*args, **kwargs):
        yield paused_event

    async def fake_acontinue_run(*args, **kwargs):
        yield RunCompletedEvent()

    mock_agent.arun = fake_arun
    mock_agent.acontinue_run = fake_acontinue_run
    service._sessions[session.id] = (session, mock_agent)

    async def reject_after_delay():
        await asyncio.sleep(0.05)
        service.approve(session, approved=False)

    asyncio.create_task(reject_after_delay())

    with patch("agent_service.langfuse_context"):
        await service.run(session, "What's the weather?")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "tool_call_pending" in types
    assert "tool_rejected" in types
