# tool-call-web — API Gateway Design

**Date:** 2026-05-20
**Status:** Approved

## Overview

Add a new FastAPI service `tool-call-web` that sits between the Angular UI (`tool-call-ui`) and the agent backend (`tool-call-fastapi`). It acts as an API gateway: the UI talks only to `tool-call-web`, which routes requests to `tool-call-fastapi`.

```
tool-call-ui (Angular :4200)
       │  HTTP + SSE
       ▼
tool-call-web (FastAPI :8080)   ← new service
       │  HTTP + SSE (httpx async)
       ▼
tool-call-fastapi (FastAPI :8000)   ← agent backend, unchanged internals
```

## Architecture

`tool-call-web` is a new top-level directory alongside `tool-call-ui` and `tool-call-fastapi`. It is a standalone FastAPI application — no shared code with the other services.

**Stateless by design.** `tool-call-web` holds no user data, session state, or conversation history between requests. Every request is self-contained: `session_id` comes from the URL, payloads come from the request body. This makes it trivially horizontally scalable — any instance can handle any request.

**CORS boundaries:**
- `tool-call-web` allows `http://localhost:4200` (the Angular UI)
- `tool-call-fastapi` CORS is updated to allow `http://localhost:8080` only (no longer directly accessible from the browser)

**Backend URL** is configurable via `AGENT_BACKEND_URL` env var (default: `http://localhost:8000`).

## Route Mapping

All routes are exposed under the `/api` prefix. Admin routes are not exposed.

| tool-call-web | → tool-call-fastapi | Notes |
|---|---|---|
| `POST /api/sessions` | `POST /sessions` | Create a new session |
| `POST /api/sessions/{id}/chat` | `POST /sessions/{id}/chat` | Send a message |
| `GET /api/sessions/{id}/stream` | `GET /sessions/{id}/stream` | SSE pass-through |
| `GET /api/sessions/{id}/history` | `GET /sessions/{id}/history` | Fetch chat history |
| `POST /api/sessions/{id}/approve` | `POST /sessions/{id}/approve` | Approve/reject tool call |

`/admin/*` routes remain internal to `tool-call-fastapi` and are not proxied.

## HTTP Client Design

A single shared `httpx.AsyncClient` is created at FastAPI lifespan startup and closed at shutdown. It is stream-capable with a large connection pool to support concurrent SSE connections.

```python
client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=500, max_keepalive_connections=500),
    timeout=None,  # default: no timeout (correct for SSE streams)
)
```

**Per-request timeout override** for short-lived routes (all except SSE stream):

```python
# Short-lived routes — 30s safety net against a hung backend
resp = await client.post(..., timeout=30.0)

# SSE stream — no timeout, connection held for duration of chat
async with client.stream("GET", ...) as resp:
    async for chunk in resp.aiter_text():
        yield chunk
```

**Why one client:**
- SSE connections hold a pool slot open for the entire chat duration
- Separating into two clients (stream vs regular) adds complexity with no meaningful benefit at current scale
- Horizontal scaling of `tool-call-web` (stateless) naturally distributes pool pressure across instances

**Scalability path:** When concurrent users grow, `tool-call-web` scales horizontally — each instance gets its own client with its own pool. The real scaling bottleneck is `tool-call-fastapi`'s in-memory session store, which requires either sticky-session routing or externalising session state to Redis (out of scope for this spec).

## Project Structure

```
tool-call-web/
  main.py           # FastAPI app: lifespan, CORS, routes
  requirements.txt  # fastapi, uvicorn, httpx, python-dotenv, pytest, pytest-asyncio
  .env.example      # AGENT_BACKEND_URL=http://localhost:8000
  tests/
    __init__.py
    test_main.py    # pytest-asyncio, httpx mock transport
```

**No `models.py`.** Request bodies are forwarded verbatim using FastAPI's raw `Request` object (`await request.body()`). This means `tool-call-web` never needs to change when `tool-call-fastapi` adds or removes fields from its request models.

## SSE Pass-Through

The stream route forwards SSE chunks as they arrive from `tool-call-fastapi`:

```python
@app.get("/api/sessions/{session_id}/stream")
async def stream(session_id: str) -> StreamingResponse:
    async def event_generator():
        async with client.stream("GET", f"{BACKEND}/sessions/{session_id}/stream") as resp:
            async for chunk in resp.aiter_text():
                yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

## Error Handling

- 4xx responses from `tool-call-fastapi` (e.g., 404 session not found) are surfaced to the UI with the same status code and body.
- If `tool-call-fastapi` is unreachable, `tool-call-web` returns 502 Bad Gateway.
- Short-lived route timeouts (30s) raise a 504 Gateway Timeout to the UI.

## Testing

Tests use `pytest-asyncio` and `httpx.MockTransport` — no real backend required.

| Test | Verifies |
|---|---|
| `test_create_session` | `POST /api/sessions` returns session ID forwarded from backend |
| `test_chat` | `POST /api/sessions/{id}/chat` forwards body, returns `processing` |
| `test_approve` | `POST /api/sessions/{id}/approve` forwards approval decision |
| `test_history` | `GET /api/sessions/{id}/history` returns forwarded list |
| `test_stream` | `GET /api/sessions/{id}/stream` forwards SSE chunks end-to-end |
| `test_session_not_found` | 404 from backend is surfaced to the UI with correct status |
| `test_backend_unreachable` | Connection error from backend returns 502 |

## What Is Not In Scope

- Authentication / JWT validation (to be added in a future iteration)
- Request transformation or response shaping (pure pass-through)
- Admin route proxying
- Externalising `tool-call-fastapi` session state to Redis
- Containerisation via Dockerfile / docker-compose (follow-on: Loki/Grafana spec)
