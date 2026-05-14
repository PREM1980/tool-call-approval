import asyncio
import pytest
from unittest.mock import patch
from agno.models.response import ToolExecution
from agno.run.agent import RunCompletedEvent, RunContentEvent, RunPausedEvent, ToolCallCompletedEvent
from agno.run.requirement import RunRequirement

from agent import Session, run_agent


@pytest.fixture
def session():
    return Session(id="test-session")


def test_session_initializes_with_empty_messages(session):
    assert session.messages == []


def test_session_has_queue(session):
    assert session.queue is not None


def test_session_has_approval_event(session):
    assert session.approval_event is not None


async def test_run_agent_end_turn(session):
    async def fake_arun(*args, **kwargs):
        yield RunContentEvent(content="Hello!")
        yield RunCompletedEvent()

    with patch.object(session.agent, "arun", side_effect=fake_arun):
        await run_agent(session, "Hi")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "message" in types
    assert "done" in types
    message_event = next(e for e in events if e["type"] == "message")
    assert message_event["content"] == "Hello!"


async def test_run_agent_tool_approval_approved(session):
    tool_exec = ToolExecution(
        tool_call_id="tool_123",
        tool_name="calculate",
        tool_args={"expression": "2 + 2"},
        requires_confirmation=True,
    )
    requirement = RunRequirement(tool_execution=tool_exec)
    paused_event = RunPausedEvent(tools=[tool_exec], requirements=[requirement], run_id="run-1")

    async def fake_arun(*args, **kwargs):
        yield paused_event

    async def fake_acontinue_run(*args, **kwargs):
        yield ToolCallCompletedEvent(tool=tool_exec, content="4")
        yield RunContentEvent(content="The answer is 4.")
        yield RunCompletedEvent()

    with patch.object(session.agent, "arun", side_effect=fake_arun), patch.object(
        session.agent, "acontinue_run", side_effect=fake_acontinue_run
    ):
        async def approve_after_delay():
            await asyncio.sleep(0.05)
            session.approval_result = True
            session.approval_event.set()

        asyncio.create_task(approve_after_delay())
        await run_agent(session, "What is 2+2?")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "tool_call_pending" in types
    assert "tool_result" in types
    assert "message" in types


async def test_run_agent_tool_approval_rejected(session):
    tool_exec = ToolExecution(
        tool_call_id="tool_456",
        tool_name="get_weather",
        tool_args={"city": "London"},
        requires_confirmation=True,
    )
    requirement = RunRequirement(tool_execution=tool_exec)
    paused_event = RunPausedEvent(tools=[tool_exec], requirements=[requirement], run_id="run-2")

    async def fake_arun(*args, **kwargs):
        yield paused_event

    async def fake_acontinue_run(*args, **kwargs):
        yield RunCompletedEvent()

    with patch.object(session.agent, "arun", side_effect=fake_arun), patch.object(
        session.agent, "acontinue_run", side_effect=fake_acontinue_run
    ):
        async def reject_after_delay():
            await asyncio.sleep(0.05)
            session.approval_result = False
            session.approval_event.set()

        asyncio.create_task(reject_after_delay())
        await run_agent(session, "What's the weather?")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "tool_call_pending" in types
    assert "tool_rejected" in types
