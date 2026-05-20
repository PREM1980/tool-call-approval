# tool-call-web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new FastAPI API gateway service `tool-call-web` that sits between the Angular UI and the agent backend, routing `/api/*` requests to `tool-call-fastapi`.

**Architecture:** `tool-call-web` is a stateless FastAPI proxy on port 8080. It owns a single shared `httpx.AsyncClient` (created at lifespan startup) with a 500-connection pool. All five session routes are forwarded verbatim; request bodies are passed as raw bytes so the gateway never needs updating when `tool-call-fastapi` changes its models. The SSE stream route uses `client.stream()` to forward chunks as they arrive.

**Tech Stack:** FastAPI 0.115, uvicorn, httpx 0.28, python-dotenv, pytest 8.3, pytest-asyncio 0.25 (asyncio_mode=auto), unittest.mock for backend mocking.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `tool-call-web/main.py` | App factory, lifespan, CORS, `_proxy` helper, all 5 routes |
| Create | `tool-call-web/requirements.txt` | Runtime + test dependencies |
| Create | `tool-call-web/.env.example` | `AGENT_BACKEND_URL` template |
| Create | `tool-call-web/pytest.ini` | `asyncio_mode = auto` |
| Create | `tool-call-web/tests/__init__.py` | Empty, marks package |
| Create | `tool-call-web/tests/test_main.py` | All route + error tests |
| Create | `tool-call-web/README.md` | Usage, env vars, run commands |
| Modify | `tool-call-fastapi/main.py:21-27` | Update CORS origin from `:4200` to `:8080` |

---

## Task 1: Project Scaffold

**Files:**
- Create: `tool-call-web/requirements.txt`
- Create: `tool-call-web/.env.example`
- Create: `tool-call-web/pytest.ini`
- Create: `tool-call-web/tests/__init__.py`
- Create: `tool-call-web/main.py`

- [ ] **Step 1: Create directory and support files**

```bash
mkdir -p tool-call-web/tests
```

Create `tool-call-web/requirements.txt`:
```
fastapi==0.115.12
uvicorn[standard]==0.34.2
httpx==0.28.1
python-dotenv==1.1.0
pytest==8.3.5
pytest-asyncio==0.25.3
```

Create `tool-call-web/.env.example`:
```
AGENT_BACKEND_URL=http://localhost:8000
```

Create `tool-call-web/pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
```

Create `tool-call-web/tests/__init__.py`:
```python
```

- [ ] **Step 2: Install dependencies**

```bash
cd tool-call-web && pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 3: Write main.py skeleton (lifespan, CORS, _proxy helper — no routes yet)**

Create `tool-call-web/main.py`:
```python
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Awaitable

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

load_dotenv()

_BACKEND = os.getenv("AGENT_BACKEND_URL", "http://localhost:8000")
_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _client
    _client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=500, max_keepalive_connections=500),
        timeout=None,
    )
    yield
    await _client.aclose()


app = FastAPI(title="Tool Call Web", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialised")
    return _client


async def _proxy(coro: Awaitable[httpx.Response]) -> JSONResponse:
    try:
        resp = await coro
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Backend unreachable")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Backend timeout")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=resp.json().get("detail", "Not found"))
    resp.raise_for_status()
    return JSONResponse(content=resp.json(), status_code=resp.status_code)
```

- [ ] **Step 4: Verify the app imports cleanly**

```bash
cd tool-call-web && python -c "from main import app; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit scaffold**

```bash
git add tool-call-web/
git commit -m "feat(tool-call-web): scaffold FastAPI gateway with lifespan and proxy helper"
```

---

## Task 2: Session Creation Route (TDD)

**Files:**
- Modify: `tool-call-web/main.py` — add `POST /api/sessions`
- Modify: `tool-call-web/tests/test_main.py` — add `test_create_session`

- [ ] **Step 1: Write the failing test**

Create `tool-call-web/tests/test_main.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_create_session(ac):
    mock_client = AsyncMock()
    mock_client.post.return_value = httpx.Response(200, json={"session_id": "abc-123"})

    with patch("main._client", mock_client):
        resp = await ac.post("/api/sessions")

    assert resp.status_code == 200
    assert resp.json() == {"session_id": "abc-123"}
    mock_client.post.assert_called_once_with("http://localhost:8000/sessions", timeout=30.0)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd tool-call-web && pytest tests/test_main.py::test_create_session -v
```

Expected: FAIL — `404 Not Found` (route doesn't exist yet).

- [ ] **Step 3: Add the route to main.py**

Append to `tool-call-web/main.py`:
```python

@app.post("/api/sessions")
async def create_session() -> JSONResponse:
    return await _proxy(
        _get_client().post(f"{_BACKEND}/sessions", timeout=30.0)
    )
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd tool-call-web && pytest tests/test_main.py::test_create_session -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tool-call-web/main.py tool-call-web/tests/test_main.py
git commit -m "feat(tool-call-web): add POST /api/sessions route"
```

---

## Task 3: Chat Route (TDD)

**Files:**
- Modify: `tool-call-web/main.py` — add `POST /api/sessions/{session_id}/chat`
- Modify: `tool-call-web/tests/test_main.py` — add `test_chat`

- [ ] **Step 1: Write the failing test**

Append to `tool-call-web/tests/test_main.py`:
```python

async def test_chat(ac):
    mock_client = AsyncMock()
    mock_client.post.return_value = httpx.Response(200, json={"status": "processing"})

    with patch("main._client", mock_client):
        resp = await ac.post(
            "/api/sessions/abc-123/chat",
            json={"message": "hello"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "processing"}
    call_args = mock_client.post.call_args
    assert "/sessions/abc-123/chat" in call_args.args[0]
    assert b'"message": "hello"' in call_args.kwargs["content"]
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd tool-call-web && pytest tests/test_main.py::test_chat -v
```

Expected: FAIL — `404 Not Found`.

- [ ] **Step 3: Add the route to main.py**

Append to `tool-call-web/main.py`:
```python

@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, request: Request) -> JSONResponse:
    body = await request.body()
    return await _proxy(
        _get_client().post(
            f"{_BACKEND}/sessions/{session_id}/chat",
            content=body,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
    )
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd tool-call-web && pytest tests/test_main.py::test_chat -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tool-call-web/main.py tool-call-web/tests/test_main.py
git commit -m "feat(tool-call-web): add POST /api/sessions/{id}/chat route"
```

---

## Task 4: History Route (TDD)

**Files:**
- Modify: `tool-call-web/main.py` — add `GET /api/sessions/{session_id}/history`
- Modify: `tool-call-web/tests/test_main.py` — add `test_history`

- [ ] **Step 1: Write the failing test**

Append to `tool-call-web/tests/test_main.py`:
```python

async def test_history(ac):
    mock_client = AsyncMock()
    mock_client.get.return_value = httpx.Response(
        200, json=[{"role": "user", "content": "hello"}]
    )

    with patch("main._client", mock_client):
        resp = await ac.get("/api/sessions/abc-123/history")

    assert resp.status_code == 200
    assert resp.json() == [{"role": "user", "content": "hello"}]
    mock_client.get.assert_called_once_with(
        "http://localhost:8000/sessions/abc-123/history", timeout=30.0
    )
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd tool-call-web && pytest tests/test_main.py::test_history -v
```

Expected: FAIL — `404 Not Found`.

- [ ] **Step 3: Add the route to main.py**

Append to `tool-call-web/main.py`:
```python

@app.get("/api/sessions/{session_id}/history")
async def history(session_id: str) -> JSONResponse:
    return await _proxy(
        _get_client().get(f"{_BACKEND}/sessions/{session_id}/history", timeout=30.0)
    )
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd tool-call-web && pytest tests/test_main.py::test_history -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tool-call-web/main.py tool-call-web/tests/test_main.py
git commit -m "feat(tool-call-web): add GET /api/sessions/{id}/history route"
```

---

## Task 5: Approve Route (TDD)

**Files:**
- Modify: `tool-call-web/main.py` — add `POST /api/sessions/{session_id}/approve`
- Modify: `tool-call-web/tests/test_main.py` — add `test_approve`

- [ ] **Step 1: Write the failing test**

Append to `tool-call-web/tests/test_main.py`:
```python

async def test_approve(ac):
    mock_client = AsyncMock()
    mock_client.post.return_value = httpx.Response(200, json={"status": "ok"})

    with patch("main._client", mock_client):
        resp = await ac.post(
            "/api/sessions/abc-123/approve",
            json={"approved": True},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    call_args = mock_client.post.call_args
    assert "/sessions/abc-123/approve" in call_args.args[0]
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd tool-call-web && pytest tests/test_main.py::test_approve -v
```

Expected: FAIL — `404 Not Found`.

- [ ] **Step 3: Add the route to main.py**

Append to `tool-call-web/main.py`:
```python

@app.post("/api/sessions/{session_id}/approve")
async def approve(session_id: str, request: Request) -> JSONResponse:
    body = await request.body()
    return await _proxy(
        _get_client().post(
            f"{_BACKEND}/sessions/{session_id}/approve",
            content=body,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
    )
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd tool-call-web && pytest tests/test_main.py::test_approve -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tool-call-web/main.py tool-call-web/tests/test_main.py
git commit -m "feat(tool-call-web): add POST /api/sessions/{id}/approve route"
```

---

## Task 6: Stream Route (TDD)

**Files:**
- Modify: `tool-call-web/main.py` — add `GET /api/sessions/{session_id}/stream`
- Modify: `tool-call-web/tests/test_main.py` — add `test_stream`

- [ ] **Step 1: Write the failing test**

Append to `tool-call-web/tests/test_main.py`:
```python

async def test_stream(ac):
    async def fake_aiter_text():
        yield 'data: {"type": "message", "content": "hi"}\n\n'
        yield 'data: {"type": "done"}\n\n'

    stream_ctx = MagicMock()
    stream_ctx.aiter_text = fake_aiter_text
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_client = MagicMock()
    mock_client.stream.return_value = stream_ctx

    with patch("main._client", mock_client):
        resp = await ac.get("/api/sessions/abc-123/stream")

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert 'data: {"type": "message"' in resp.text
    assert 'data: {"type": "done"}' in resp.text
    mock_client.stream.assert_called_once_with(
        "GET", "http://localhost:8000/sessions/abc-123/stream"
    )
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd tool-call-web && pytest tests/test_main.py::test_stream -v
```

Expected: FAIL — `404 Not Found`.

- [ ] **Step 3: Add the route to main.py**

Append to `tool-call-web/main.py`:
```python

@app.get("/api/sessions/{session_id}/stream")
async def stream_events(session_id: str) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        async with _get_client().stream(
            "GET", f"{_BACKEND}/sessions/{session_id}/stream"
        ) as resp:
            async for chunk in resp.aiter_text():
                yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd tool-call-web && pytest tests/test_main.py::test_stream -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tool-call-web/main.py tool-call-web/tests/test_main.py
git commit -m "feat(tool-call-web): add GET /api/sessions/{id}/stream SSE pass-through"
```

---

## Task 7: Error Handling Tests (TDD)

**Files:**
- Modify: `tool-call-web/tests/test_main.py` — add 404, 502, 504 tests

- [ ] **Step 1: Write the failing error tests**

Append to `tool-call-web/tests/test_main.py`:
```python

async def test_session_not_found(ac):
    mock_client = AsyncMock()
    mock_client.get.return_value = httpx.Response(404, json={"detail": "Session not found"})

    with patch("main._client", mock_client):
        resp = await ac.get("/api/sessions/bad-id/history")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Session not found"


async def test_backend_unreachable(ac):
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ConnectError("connection refused")

    with patch("main._client", mock_client):
        resp = await ac.post("/api/sessions")

    assert resp.status_code == 502
    assert resp.json()["detail"] == "Backend unreachable"


async def test_backend_timeout(ac):
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("timed out")

    with patch("main._client", mock_client):
        resp = await ac.post("/api/sessions")

    assert resp.status_code == 504
    assert resp.json()["detail"] == "Backend timeout"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd tool-call-web && pytest tests/test_main.py::test_session_not_found tests/test_main.py::test_backend_unreachable tests/test_main.py::test_backend_timeout -v
```

Expected: all three FAIL — the error handling is already implemented in `_proxy`, so these should actually PASS if the implementation is correct. If they fail, check the `_proxy` function in `main.py` matches the implementation from Task 1 exactly.

- [ ] **Step 3: Run the full test suite**

```bash
cd tool-call-web && pytest -v
```

Expected: all 9 tests PASS.

```
tests/test_main.py::test_create_session PASSED
tests/test_main.py::test_chat PASSED
tests/test_main.py::test_history PASSED
tests/test_main.py::test_approve PASSED
tests/test_main.py::test_stream PASSED
tests/test_main.py::test_session_not_found PASSED
tests/test_main.py::test_backend_unreachable PASSED
tests/test_main.py::test_backend_timeout PASSED
```

- [ ] **Step 4: Commit**

```bash
git add tool-call-web/tests/test_main.py
git commit -m "test(tool-call-web): add error handling tests for 404, 502, 504"
```

---

## Task 8: Update tool-call-fastapi CORS

**Files:**
- Modify: `tool-call-fastapi/main.py:21-27`

- [ ] **Step 1: Update the allowed CORS origin**

In `tool-call-fastapi/main.py`, change:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

To:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 2: Run tool-call-fastapi tests to confirm nothing broke**

```bash
cd tool-call-fastapi && pytest -v
```

Expected: all existing tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tool-call-fastapi/main.py
git commit -m "fix(tool-call-fastapi): restrict CORS to tool-call-web origin only"
```

---

## Task 9: README

**Files:**
- Create: `tool-call-web/README.md`

- [ ] **Step 1: Write README**

Create `tool-call-web/README.md`:
```markdown
# tool-call-web

API gateway that sits between `tool-call-ui` and `tool-call-fastapi`. The Angular UI communicates exclusively with this service; it forwards requests to the agent backend.

## Architecture

```
tool-call-ui (:4200) → tool-call-web (:8080) → tool-call-fastapi (:8000)
```

## Routes

| Method | Path | Forwards to |
|---|---|---|
| POST | `/api/sessions` | `POST /sessions` |
| POST | `/api/sessions/{id}/chat` | `POST /sessions/{id}/chat` |
| GET | `/api/sessions/{id}/stream` | `GET /sessions/{id}/stream` (SSE) |
| GET | `/api/sessions/{id}/history` | `GET /sessions/{id}/history` |
| POST | `/api/sessions/{id}/approve` | `POST /sessions/{id}/approve` |

## Setup

```bash
cp .env.example .env
pip install -r requirements.txt
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AGENT_BACKEND_URL` | `http://localhost:8000` | URL of the `tool-call-fastapi` backend |

## Running

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

## Tests

```bash
pytest -v
```
```

- [ ] **Step 2: Commit**

```bash
git add tool-call-web/README.md
git commit -m "docs(tool-call-web): add README with routes and setup instructions"
```

---

## Final Verification

- [ ] **Run all tests in both services**

```bash
cd tool-call-web && pytest -v && cd ../tool-call-fastapi && pytest -v
```

Expected: all tests in both services PASS with no failures.

- [ ] **Smoke test the gateway manually**

In three terminals:
```bash
# Terminal 1 — start backend
cd tool-call-fastapi && uvicorn main:app --port 8000 --reload

# Terminal 2 — start gateway
cd tool-call-web && uvicorn main:app --port 8080 --reload

# Terminal 3 — create a session through the gateway
curl -s -X POST http://localhost:8080/api/sessions | python3 -m json.tool
```

Expected: `{"session_id": "<uuid>"}` returned via the gateway.
