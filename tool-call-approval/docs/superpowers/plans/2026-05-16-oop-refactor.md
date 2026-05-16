# OOP Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `tool-call-fastapi/` from a flat `agent.py` into a Repository + Service + Strategy OOP design across focused files.

**Architecture:** `PostgresRepository` abstracts storage behind an `IAgentStorage` ABC. `AgentService` owns session lifecycle (Factory), agent construction, and event dispatch (Strategy via `dict[type, handler]`). `main.py` becomes a thin HTTP layer that delegates to `AgentService`. `Session` becomes a pure data object.

**Tech Stack:** agno 2.6.6, FastAPI, AWS Bedrock (claude-sonnet-4), PostgreSQL via psycopg2, Langfuse, pytest + pytest-asyncio (asyncio_mode=auto)

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Create | `tool-call-fastapi/repository.py` | `IAgentStorage` ABC + `PostgresRepository` |
| Create | `tool-call-fastapi/session.py` | Pure `Session` dataclass — queue + approval state only |
| Create | `tool-call-fastapi/agent_service.py` | Tool defs, `AgentService` (Factory + Strategy + run loop) |
| Modify | `tool-call-fastapi/main.py` | Wire `AgentService`; routes delegate to service |
| Rewrite | `tool-call-fastapi/tests/test_agent.py` | Tests for new structure |
| Delete | `tool-call-fastapi/agent.py` | Replaced by the three new files above |
| Unchanged | `tool-call-fastapi/tools.py` | `execute_tool()` — not touched |
| Unchanged | `tool-call-fastapi/models.py` | Pydantic models — not touched |

---

## Task 1: `repository.py` — Storage Abstraction

**Files:**
- Create: `tool-call-fastapi/repository.py`
- Modify: `tool-call-fastapi/tests/test_agent.py` (add repository tests)

- [ ] **Step 1: Write failing tests for PostgresRepository**

Add to `tests/test_agent.py` (replacing entire file for now):

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd tool-call-fastapi && pytest tests/test_agent.py -v -k "repository"
```

Expected: `ModuleNotFoundError: No module named 'repository'`

- [ ] **Step 3: Create `repository.py`**

```python
import socket
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from agno.db.postgres.postgres import PostgresDb


class IAgentStorage(ABC):
    @abstractmethod
    def get_db(self) -> PostgresDb: ...


class PostgresRepository(IAgentStorage):
    def __init__(self, url: str) -> None:
        self._url = url
        self._db: PostgresDb | None = None

    def get_db(self) -> PostgresDb:
        if self._db is None:
            self._check_reachable()
            self._db = PostgresDb(db_url=self._url)
        return self._db

    def _check_reachable(self) -> None:
        parsed = urlparse(self._url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        try:
            with socket.create_connection((host, port), timeout=2):
                pass
        except OSError:
            raise RuntimeError(
                f"Postgres is not reachable at {host}:{port}. "
                "Please ensure it is running."
            )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd tool-call-fastapi && pytest tests/test_agent.py -v -k "repository"
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tool-call-fastapi/repository.py tool-call-fastapi/tests/test_agent.py
git commit -m "feat(storage): add IAgentStorage ABC and PostgresRepository"
```

---

## Task 2: `session.py` — Pure Session Dataclass

**Files:**
- Create: `tool-call-fastapi/session.py`
- Modify: `tool-call-fastapi/tests/test_agent.py` (add session tests)

- [ ] **Step 1: Write failing session tests**

Append to `tests/test_agent.py`:

```python
from session import Session


def test_session_defaults():
    session = Session(id="abc-123")
    assert session.id == "abc-123"
    assert session.queue.empty()
    assert not session.approval_event.is_set()
    assert session.approval_result is False
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd tool-call-fastapi && pytest tests/test_agent.py -v -k "session_defaults"
```

Expected: `ModuleNotFoundError: No module named 'session'`

- [ ] **Step 3: Create `session.py`**

```python
import asyncio
from dataclasses import dataclass, field


@dataclass
class Session:
    id: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    approval_event: asyncio.Event = field(default_factory=asyncio.Event)
    approval_result: bool = False
```

- [ ] **Step 4: Run to confirm pass**

```bash
cd tool-call-fastapi && pytest tests/test_agent.py -v -k "session_defaults"
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add tool-call-fastapi/session.py tool-call-fastapi/tests/test_agent.py
git commit -m "feat(session): add pure Session dataclass"
```

---

## Task 3: `agent_service.py` — AgentService

**Files:**
- Create: `tool-call-fastapi/agent_service.py`
- Modify: `tool-call-fastapi/tests/test_agent.py` (add service tests)

- [ ] **Step 1: Write failing AgentService tests**

Append to `tests/test_agent.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from agno.models.response import ToolExecution
from agno.run.agent import RunCompletedEvent, RunContentEvent, RunErrorEvent, RunPausedEvent, ToolCallCompletedEvent
from agno.run.requirement import RunRequirement

from agent_service import AgentService
from repository import IAgentStorage


class MockStorage(IAgentStorage):
    def get_db(self):
        return MagicMock()


@pytest.fixture
def service():
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        svc = AgentService(repository=MockStorage())
    return svc


@pytest.fixture
def session_in_service(service):
    with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
        return service.create_session()


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
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd tool-call-fastapi && pytest tests/test_agent.py -v -k "service or run_ or on_ or dispatch or approve or create"
```

Expected: `ModuleNotFoundError: No module named 'agent_service'`

- [ ] **Step 3: Create `agent_service.py`**

```python
import asyncio
from typing import Any
from uuid import uuid4

from agno.agent import Agent
from agno.models.aws.bedrock import AwsBedrock
from agno.run.agent import (
    RunCompletedEvent,
    RunContentEvent,
    RunErrorEvent,
    RunPausedEvent,
    ToolCallCompletedEvent,
)
from agno.tools import tool
from langfuse.decorators import langfuse_context, observe

from repository import IAgentStorage
from session import Session
from tools import execute_tool

_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"


@tool(requires_confirmation=True)
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression. Use math.sqrt(), math.pi, etc. for math functions."""
    return execute_tool("calculate", {"expression": expression})


@tool(requires_confirmation=True)
def get_weather(city: str) -> str:
    """Get current weather conditions for a city."""
    return execute_tool("get_weather", {"city": city})


@tool(requires_confirmation=True)
def search_web(query: str) -> str:
    """Search the web for information on a topic."""
    return execute_tool("search_web", {"query": query})


class AgentService:
    def __init__(self, repository: IAgentStorage) -> None:
        self._repository = repository
        self._sessions: dict[str, tuple[Session, Agent]] = {}
        self._handlers: dict[type, Any] = {
            RunPausedEvent: self._on_paused,
            RunContentEvent: self._on_content,
            RunCompletedEvent: self._on_completed,
            RunErrorEvent: self._on_error,
            ToolCallCompletedEvent: self._on_tool_completed,
        }

    # ── Session lifecycle ──────────────────────────────────────────────────

    def create_session(self) -> Session:
        session = Session(id=str(uuid4()))
        agent = self._build_agent(session.id)
        self._sessions[session.id] = (session, agent)
        return session

    def get_session(self, session_id: str) -> Session | None:
        pair = self._sessions.get(session_id)
        return pair[0] if pair else None

    def approve(self, session: Session, approved: bool) -> None:
        session.approval_result = approved
        session.approval_event.set()

    # ── Factory ───────────────────────────────────────────────────────────

    def _build_agent(self, session_id: str) -> Agent:
        return Agent(
            model=AwsBedrock(id=_MODEL_ID),
            tools=[calculate, get_weather, search_web],
            instructions=(
                "You are a helpful assistant with access to tools. "
                "Always use tools when appropriate to provide accurate information."
            ),
            stream=True,
            session_id=session_id,
            user_id=session_id,
            db=self._repository.get_db(),
        )

    def _get_agent(self, session_id: str) -> Agent | None:
        pair = self._sessions.get(session_id)
        return pair[1] if pair else None

    def _remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    # ── Run loop ──────────────────────────────────────────────────────────

    @observe(name="agent-run", capture_input=False, capture_output=False)
    async def run(self, session: Session, message: str) -> None:
        agent = self._get_agent(session.id)
        if agent is None:
            return

        langfuse_context.update_current_trace(
            user_id=session.id,
            tags=["tool-call-approval"],
        )
        langfuse_context.update_current_observation(input=message)
        await session.queue.put({"type": "thinking", "content": "Thinking..."})

        tool_spans: list = []
        response_parts: list = []

        try:
            async for event in agent.arun(
                message,
                stream=True,
                stream_events=True,
                yield_run_output=True,
            ):
                done = await self._dispatch(session, event, tool_spans, response_parts)
                if done and isinstance(event, RunCompletedEvent):
                    break
        except Exception as e:
            langfuse_context.update_current_observation(
                level="ERROR", status_message=str(e)
            )
            await session.queue.put({"type": "error", "content": f"Unexpected error: {str(e)}"})
            await session.queue.put({"type": "done"})
            self._remove_session(session.id)
            return

        final_output = "".join(response_parts)
        langfuse_context.update_current_observation(
            output=final_output,
            metadata={"tool_calls": tool_spans},
        )
        langfuse_context.update_current_trace(output=final_output)

    # ── Strategy dispatch ─────────────────────────────────────────────────

    async def _dispatch(
        self, session: Session, event: Any, tool_spans: list, response_parts: list
    ) -> bool:
        handler = self._handlers.get(type(event))
        if handler:
            return await handler(session, event, tool_spans, response_parts)
        return False

    async def _on_paused(
        self, session: Session, event: RunPausedEvent, tool_spans: list, response_parts: list
    ) -> bool:
        requirements = event.requirements or []
        requirement = next((r for r in requirements if r.needs_confirmation), None)
        if requirement is None or requirement.tool_execution is None:
            return False

        tool_execution = requirement.tool_execution
        await session.queue.put({
            "type": "tool_call_pending",
            "tool_use_id": tool_execution.tool_call_id,
            "tool_name": tool_execution.tool_name,
            "tool_input": tool_execution.tool_args or {},
        })

        session.approval_event.clear()
        await session.approval_event.wait()

        if not session.approval_result:
            requirement.reject()
            await session.queue.put({
                "type": "tool_rejected",
                "tool_use_id": tool_execution.tool_call_id,
                "tool_name": tool_execution.tool_name,
            })
            return False

        requirement.confirm()
        agent = self._get_agent(session.id)
        if agent is None:
            return False

        async for resumed_event in agent.acontinue_run(
            run_id=event.run_id,
            requirements=[requirement],
            stream=True,
            stream_events=True,
            yield_run_output=True,
        ):
            if isinstance(resumed_event, ToolCallCompletedEvent) and resumed_event.tool:
                result = str(resumed_event.content)
                tool_spans.append({"tool": tool_execution.tool_name, "result": result})
                await session.queue.put({
                    "type": "tool_result",
                    "tool_use_id": resumed_event.tool.tool_call_id,
                    "tool_name": resumed_event.tool.tool_name,
                    "result": result,
                })
            else:
                done = await self._dispatch(session, resumed_event, tool_spans, response_parts)
                if done:
                    return True

        return True

    async def _on_content(
        self, session: Session, event: RunContentEvent, tool_spans: list, response_parts: list
    ) -> bool:
        if event.content:
            response_parts.append(str(event.content))
            await session.queue.put({"type": "message", "content": str(event.content)})
        return False

    async def _on_completed(
        self, session: Session, event: RunCompletedEvent, tool_spans: list, response_parts: list
    ) -> bool:
        await session.queue.put({"type": "done"})
        self._remove_session(session.id)
        return True

    async def _on_error(
        self, session: Session, event: RunErrorEvent, tool_spans: list, response_parts: list
    ) -> bool:
        await session.queue.put({"type": "error", "content": f"Agent error: {event.content}"})
        await session.queue.put({"type": "done"})
        self._remove_session(session.id)
        return True

    async def _on_tool_completed(
        self, session: Session, event: ToolCallCompletedEvent, tool_spans: list, response_parts: list
    ) -> bool:
        if event.tool:
            await session.queue.put({
                "type": "tool_result",
                "tool_use_id": event.tool.tool_call_id,
                "tool_name": event.tool.tool_name,
                "result": str(event.content),
            })
        return False
```

- [ ] **Step 4: Run all tests to confirm they pass**

```bash
cd tool-call-fastapi && pytest tests/test_agent.py -v
```

Expected: All tests pass (repository + session + service tests)

- [ ] **Step 5: Commit**

```bash
git add tool-call-fastapi/agent_service.py tool-call-fastapi/tests/test_agent.py
git commit -m "feat(agent): add AgentService with Factory and Strategy event dispatch"
```

---

## Task 4: Update `main.py`

**Files:**
- Modify: `tool-call-fastapi/main.py`

- [ ] **Step 1: Replace `main.py` content**

```python
import asyncio
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent_service import AgentService
from models import ApprovalRequest, ChatRequest, SessionResponse
from repository import PostgresRepository

app = FastAPI(title="Tool Call Approval API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_repository = PostgresRepository(
    url=os.getenv("POSTGRES_URL", "postgresql+psycopg2://localhost:5432/postgres")
)
service = AgentService(repository=_repository)


@app.post("/sessions", response_model=SessionResponse)
async def create_session() -> SessionResponse:
    session = service.create_session()
    return SessionResponse(session_id=session.id)


@app.post("/sessions/{session_id}/chat")
async def chat(session_id: str, request: ChatRequest) -> dict:
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    asyncio.create_task(service.run(session, request.message))
    return {"status": "processing"}


@app.get("/sessions/{session_id}/stream")
async def stream_events(session_id: str) -> StreamingResponse:
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        while True:
            event = await session.queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "done":
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/sessions/{session_id}/approve")
async def approve_tool(session_id: str, request: ApprovalRequest) -> dict:
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    service.approve(session, request.approved)
    return {"status": "ok"}
```

- [ ] **Step 2: Verify the server starts without error**

```bash
cd tool-call-fastapi && uvicorn main:app --reload
```

Expected: `Application startup complete.` with no import errors

- [ ] **Step 3: Commit**

```bash
git add tool-call-fastapi/main.py
git commit -m "refactor(main): delegate all session logic to AgentService"
```

---

## Task 5: Delete `agent.py` and Run Full Test Suite

**Files:**
- Delete: `tool-call-fastapi/agent.py`

- [ ] **Step 1: Delete `agent.py`**

```bash
rm tool-call-fastapi/agent.py
```

- [ ] **Step 2: Run full test suite to confirm nothing breaks**

```bash
cd tool-call-fastapi && pytest tests/ -v
```

Expected: All tests pass. No import of `agent` module anywhere.

- [ ] **Step 3: Verify no remaining references to `agent.py`**

```bash
grep -r "from agent import\|import agent" tool-call-fastapi/ --include="*.py"
```

Expected: No output

- [ ] **Step 4: Commit**

```bash
git add -u tool-call-fastapi/agent.py
git commit -m "refactor: remove agent.py — replaced by repository, session, agent_service"
```
