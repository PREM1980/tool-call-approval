# OOP Refactor Design — tool-call-fastapi

**Date:** 2026-05-16  
**Scope:** `tool-call-fastapi/` directory  
**Patterns:** Repository, Factory, Strategy

---

## Problem

`agent.py` mixes four distinct concerns in one flat file:

- Postgres connectivity and `PostgresDb` construction
- `Session` dataclass carrying agent, queue, approval state, and message history
- Tool definitions
- Event processing logic (`_process_event`, `run_agent`) as module-level functions

This makes individual pieces hard to test, hard to swap, and hard to reason about independently.

---

## Approach: Service + Repository

Split `agent.py` into three focused files. `main.py`, `models.py`, and `tools.py` stay untouched except `main.py` which is updated to delegate to `AgentService`.

---

## File Structure

```
tool-call-fastapi/
├── repository.py      ← Repository pattern: storage abstraction
├── session.py         ← Pure data: Session state only
├── agent_service.py   ← Factory + Strategy + run loop
├── main.py            ← HTTP layer: thin delegator to AgentService
├── tools.py           ← unchanged
├── models.py          ← unchanged
└── agent.py           ← deleted
```

---

## Component Design

### `repository.py` — Repository Pattern

Abstracts Postgres behind an interface so it is swappable (e.g. for SQLite in tests).

```python
class IAgentStorage(ABC):
    @abstractmethod
    def get_db(self) -> PostgresDb: ...

class PostgresRepository(IAgentStorage):
    def __init__(self, url: str): ...
    def get_db(self) -> PostgresDb: ...      # lazy singleton
    def _check_reachable(self) -> None: ...  # raises RuntimeError if port 5432 unreachable
```

**Rules:**
- `get_db()` is a lazy singleton — creates `PostgresDb` on first call
- `_check_reachable()` does a socket probe on `localhost:5432` before creating the db
- Raises `RuntimeError` immediately if unreachable — fail fast at startup
- URL defaults to `postgresql+psycopg2://localhost:5432/postgres`, overridable via `POSTGRES_URL` env var

---

### `session.py` — Pure Session State

A thin dataclass carrying only runtime primitives. No agent reference, no message list.

```python
@dataclass
class Session:
    id: str
    queue: asyncio.Queue        = field(default_factory=asyncio.Queue)
    approval_event: asyncio.Event = field(default_factory=asyncio.Event)
    approval_result: bool       = False
```

**Why remove `messages` and `agent`:** Message history is owned by agno's `PostgresDb`-backed `AgentSession`. The `Agent` instance is owned by `AgentService`, which co-locates it with the `Session` in an internal dict. `Session` is now a pure value object — no logic, no side effects.

---

### `agent_service.py` — Factory + Strategy

The central service class. Owns three responsibilities:

#### 1. Session + Agent lifecycle (Factory)

```python
class AgentService:
    def __init__(self, repository: IAgentStorage):
        self._repository = repository
        self._sessions: dict[str, tuple[Session, Agent]] = {}
        self._handlers = {
            RunPausedEvent:       self._on_paused,
            RunContentEvent:      self._on_content,
            RunCompletedEvent:    self._on_completed,
            RunErrorEvent:        self._on_error,
            ToolCallCompletedEvent: self._on_tool_completed,
        }

    def create_session(self) -> Session: ...
    def get_session(self, session_id: str) -> Session | None: ...
    def approve(self, session: Session, approved: bool) -> None: ...
    def _build_agent(self, session_id: str) -> Agent: ...
```

`create_session()` creates a `Session`, calls `_build_agent(session.id)`, stores both together in `_sessions`, and returns the `Session`.

`_build_agent()` is the Factory — it wires `AwsBedrock`, tools, and `PostgresDb` into a configured `Agent` with `session_id` and `user_id` set.

#### 2. Run loop

```python
    @observe(name="agent-run", ...)
    async def run(self, session: Session, message: str) -> None: ...
```

Iterates `agent.arun(...)` events and delegates each to `_dispatch()`. Langfuse `@observe` and `langfuse_context` calls live here, moved from `agent.py`.

#### 3. Event dispatch (Strategy)

```python
    async def _dispatch(self, session, event, tool_spans, response_parts) -> bool:
        handler = self._handlers.get(type(event))
        return await handler(session, event, tool_spans, response_parts) if handler else False

    async def _on_paused(self, ...)        -> bool: ...
    async def _on_content(self, ...)       -> bool: ...
    async def _on_completed(self, ...)     -> bool: ...
    async def _on_error(self, ...)         -> bool: ...
    async def _on_tool_completed(self, ...) -> bool: ...
```

The `isinstance` chain is replaced by a `dict[type, handler]` lookup. Adding a new event type means adding one entry to the dict and one `_on_*` method — no existing code changes.

---

### `main.py` — Updated HTTP Layer

`AgentService` is constructed once at module level. Routes become one-liners.

```python
repository = PostgresRepository(url=os.getenv("POSTGRES_URL", "postgresql+psycopg2://localhost:5432/postgres"))
service    = AgentService(repository=repository)

POST /sessions          → session = service.create_session()
POST /{id}/chat         → asyncio.create_task(service.run(session, message))
GET  /{id}/stream       → streams session.queue (unchanged logic)
POST /{id}/approve      → service.approve(session, approved)
```

The `sessions: dict[str, Session]` in-memory store moves inside `AgentService._sessions`. `main.py` no longer manages session state directly.

---

## Data Flow

```
POST /chat
  → AgentService.run(session, message)       [background task]
      → queue.put({type: "thinking"})
      → agent.arun(message, stream=True)
          → for each event:
              → _dispatch(event)
                  RunContentEvent      → queue.put({type: "message"})
                  ToolCallCompleted    → queue.put({type: "tool_result"})
                  RunPausedEvent       → queue.put({type: "tool_call_pending"})
                                       → wait approval_event
                                       → agent.acontinue_run(...)
                  RunCompletedEvent    → queue.put({type: "done"})
                  RunErrorEvent        → queue.put({type: "error"}) + {type: "done"}
```

---

## Error Handling

| Location | Condition | Behaviour |
|---|---|---|
| `PostgresRepository._check_reachable` | Port 5432 unreachable | `RuntimeError` at startup — fail fast |
| `AgentService.get_session` | Unknown `session_id` | Returns `None` → `main.py` raises HTTP 404 |
| `AgentService.run` | Bedrock / agno exception | `_on_error` puts `{type: "error"}` then `{type: "done"}` on queue |
| `AgentService._dispatch` | Unrecognised event type | Returns `False`, loop continues silently |
| `AgentService.approve` | Unknown session | `get_session` returns `None`, 404 raised before `approve` is called |

---

## Testing Strategy

| What to test | How |
|---|---|
| `PostgresRepository` | Inject a bad URL → assert `RuntimeError` on `get_db()` |
| `AgentService` (unit) | Inject a mock `IAgentStorage` → verify `create_session` builds correct Agent params |
| `AgentService._dispatch` | Pass mock events → assert correct items appear on `session.queue` |
| `AgentService.approve` | Set `approval_result`, assert `approval_event` is set |
| `main.py` (integration) | Use `httpx.AsyncClient` with app — existing test file pattern |

---

## What Does Not Change

- `tools.py` — tool definitions and `execute_tool` are untouched
- `models.py` — Pydantic request/response models are untouched
- Langfuse tracing — `@observe` and `langfuse_context` calls move to `AgentService.run()` verbatim
- SSE streaming logic in `main.py` — the `event_generator` function is unchanged
- `requirements.txt` — no new dependencies
