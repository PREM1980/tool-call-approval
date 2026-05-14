# Tool Call Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI backend with an Anthropic tool-calling agent that pauses for human approval, and an Angular frontend chat UI that renders approval cards and streams responses via SSE.

**Architecture:** The FastAPI backend maintains per-session state with an `asyncio.Event` to pause agent execution when a tool call is detected, then resumes after the Angular frontend POSTs an approve/reject decision. Events flow from backend to frontend via Server-Sent Events (SSE). The Angular app renders a chat window with inline tool-approval cards.

**Tech Stack:** Python 3.14, FastAPI, Anthropic SDK (`claude-sonnet-4-6`), pytest, Angular 20 (standalone components), TypeScript, Angular HttpClient + native EventSource.

---

## File Map

### Backend (`tool-call-fastapi/`)
- `models.py` — Pydantic request/response models
- `tools.py` — Tool definitions (calculator, weather mock, web search mock) + executor
- `agent.py` — Session dataclass + async `run_agent` loop with approval pause
- `main.py` — FastAPI app, CORS, four endpoints
- `requirements.txt` — Python dependencies
- `.env.example` — API key template
- `tests/test_tools.py` — Unit tests for tool executor
- `tests/test_agent.py` — Integration tests for session + approval flow
- `tests/test_main.py` — HTTP endpoint tests with TestClient

### Frontend (`tool-call-ui/`)
- `src/app/models/types.ts` — Shared TypeScript interfaces
- `src/app/services/chat.service.ts` — Session creation, SSE, HTTP calls
- `src/app/components/tool-approval/tool-approval.component.ts/html/css` — Approval card
- `src/app/components/chat/chat.component.ts/html/css` — Main chat UI
- `src/app/app.component.ts/html/css` — Root shell
- `src/app/app.config.ts` — `provideHttpClient()` bootstrap
- `src/app/components/chat/chat.component.spec.ts` — Unit tests

---

## Task 1: FastAPI Project Scaffold

**Files:**
- Create: `tool-call-fastapi/requirements.txt`
- Create: `tool-call-fastapi/.env.example`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.12
uvicorn[standard]==0.34.2
anthropic==0.52.0
python-dotenv==1.1.0
pytest==8.3.5
pytest-asyncio==0.25.3
httpx==0.28.1
```

- [ ] **Step 2: Create .env.example**

```
ANTHROPIC_API_KEY=your-api-key-here
```

- [ ] **Step 3: Install dependencies**

Run: `cd tool-call-fastapi && pip install -r requirements.txt`
Expected: All packages installed successfully.

- [ ] **Step 4: Commit**

```bash
git add tool-call-fastapi/requirements.txt tool-call-fastapi/.env.example
git commit -m "chore: scaffold tool-call-fastapi project"
```

---

## Task 2: Pydantic Models

**Files:**
- Create: `tool-call-fastapi/models.py`

- [ ] **Step 1: Write models.py**

```python
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ApprovalRequest(BaseModel):
    approved: bool


class SessionResponse(BaseModel):
    session_id: str
```

- [ ] **Step 2: Commit**

```bash
git add tool-call-fastapi/models.py
git commit -m "feat: add pydantic models for chat and approval"
```

---

## Task 3: Tool Definitions and Executor

**Files:**
- Create: `tool-call-fastapi/tools.py`
- Create: `tool-call-fastapi/tests/__init__.py`
- Create: `tool-call-fastapi/tests/test_tools.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_tools.py
import math
from tools import execute_tool, TOOL_DEFINITIONS


def test_calculate_addition():
    result = execute_tool("calculate", {"expression": "2 + 3"})
    assert result == "5"


def test_calculate_sqrt():
    result = execute_tool("calculate", {"expression": "math.sqrt(16)"})
    assert result == "4.0"


def test_calculate_invalid():
    result = execute_tool("calculate", {"expression": "import os"})
    assert "Error" in result


def test_get_weather_known_city():
    result = execute_tool("get_weather", {"city": "London"})
    assert "°C" in result


def test_get_weather_unknown_city():
    result = execute_tool("get_weather", {"city": "Atlantis"})
    assert "unavailable" in result


def test_search_web_returns_query():
    result = execute_tool("search_web", {"query": "Python testing"})
    assert "Python testing" in result


def test_unknown_tool():
    result = execute_tool("nonexistent", {})
    assert "Unknown tool" in result


def test_tool_definitions_have_required_keys():
    for tool in TOOL_DEFINITIONS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tool-call-fastapi && pytest tests/test_tools.py -v`
Expected: ImportError — `tools` module not found.

- [ ] **Step 3: Write tools.py**

```python
import math as _math

TOOL_DEFINITIONS = [
    {
        "name": "calculate",
        "description": "Evaluate a mathematical expression. Use math.sqrt(), math.pi, etc. for math functions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A Python math expression, e.g. '2 + 3' or 'math.sqrt(16)'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather conditions for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. 'London'"}
            },
            "required": ["city"],
        },
    },
    {
        "name": "search_web",
        "description": "Search the web for information on a topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"}
            },
            "required": ["query"],
        },
    },
]

_WEATHER_DB = {
    "london": "Cloudy, 15°C, humidity 80%",
    "new york": "Sunny, 22°C, humidity 45%",
    "tokyo": "Rainy, 18°C, humidity 90%",
    "paris": "Partly cloudy, 17°C, humidity 60%",
    "sydney": "Clear, 25°C, humidity 50%",
}


def execute_tool(name: str, tool_input: dict) -> str:
    if name == "calculate":
        try:
            result = eval(  # noqa: S307
                tool_input["expression"],
                {"__builtins__": {}},
                {"math": _math},
            )
            return str(result)
        except Exception as exc:
            return f"Error: {exc}"

    if name == "get_weather":
        city = tool_input["city"]
        return _WEATHER_DB.get(
            city.lower(), f"Weather data unavailable for {city}"
        )

    if name == "search_web":
        query = tool_input["query"]
        return (
            f"Search results for '{query}': "
            f"[Mock] Top result — Wikipedia article about {query}. "
            f"Additional results at example.com/search?q={query.replace(' ', '+')}"
        )

    return f"Unknown tool: {name}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tool-call-fastapi && pytest tests/test_tools.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add tool-call-fastapi/tools.py tool-call-fastapi/tests/
git commit -m "feat: add tool definitions and executor with tests"
```

---

## Task 4: Agent Session and Run Loop

**Files:**
- Create: `tool-call-fastapi/agent.py`
- Create: `tool-call-fastapi/tests/test_agent.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_agent.py
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
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


@pytest.mark.asyncio
async def test_run_agent_end_turn(session):
    """Agent completes when stop_reason is end_turn."""
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [MagicMock(type="text", text="Hello!")]

    with patch("agent.client.messages.create", return_value=mock_response):
        await run_agent(session, "Hi")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "message" in types
    assert "done" in types
    message_event = next(e for e in events if e["type"] == "message")
    assert message_event["content"] == "Hello!"


@pytest.mark.asyncio
async def test_run_agent_tool_approval_approved(session):
    """Agent executes tool when user approves."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_123"
    tool_block.name = "calculate"
    tool_block.input = {"expression": "2 + 2"}

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_block]

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    final_response.content = [MagicMock(type="text", text="The answer is 4.")]

    call_count = 0

    def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        return tool_response if call_count == 1 else final_response

    async def approve_after_delay():
        await asyncio.sleep(0.05)
        session.approval_result = True
        session.approval_event.set()

    with patch("agent.client.messages.create", side_effect=mock_create):
        asyncio.create_task(approve_after_delay())
        await run_agent(session, "What is 2+2?")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "tool_call_pending" in types
    assert "tool_result" in types
    assert "message" in types


@pytest.mark.asyncio
async def test_run_agent_tool_approval_rejected(session):
    """Agent receives rejection message when user rejects."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_456"
    tool_block.name = "get_weather"
    tool_block.input = {"city": "London"}

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_block]

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    final_response.content = [MagicMock(type="text", text="I cannot get the weather.")]

    call_count = 0

    def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        return tool_response if call_count == 1 else final_response

    async def reject_after_delay():
        await asyncio.sleep(0.05)
        session.approval_result = False
        session.approval_event.set()

    with patch("agent.client.messages.create", side_effect=mock_create):
        asyncio.create_task(reject_after_delay())
        await run_agent(session, "What's the weather?")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "tool_call_pending" in types
    assert "tool_rejected" in types
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tool-call-fastapi && pytest tests/test_agent.py -v`
Expected: ImportError — `agent` module not found.

- [ ] **Step 3: Create pytest.ini for async**

```ini
# tool-call-fastapi/pytest.ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 4: Write agent.py**

```python
import asyncio
from dataclasses import dataclass, field
from typing import Any

import anthropic
from dotenv import load_dotenv

from tools import TOOL_DEFINITIONS, execute_tool

load_dotenv()

client = anthropic.Anthropic()


@dataclass
class Session:
    id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    approval_event: asyncio.Event = field(default_factory=asyncio.Event)
    approval_result: bool = False


async def run_agent(session: Session, user_message: str) -> None:
    session.messages.append({"role": "user", "content": user_message})
    await session.queue.put({"type": "thinking", "content": "Thinking..."})

    while True:
        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=TOOL_DEFINITIONS,
            messages=session.messages,
        )

        if response.stop_reason == "end_turn":
            text = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            session.messages.append(
                {"role": "assistant", "content": response.content}
            )
            await session.queue.put({"type": "message", "content": text})
            await session.queue.put({"type": "done"})
            break

        if response.stop_reason == "tool_use":
            session.messages.append(
                {"role": "assistant", "content": response.content}
            )
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                await session.queue.put(
                    {
                        "type": "tool_call_pending",
                        "tool_use_id": block.id,
                        "tool_name": block.name,
                        "tool_input": block.input,
                    }
                )

                session.approval_event.clear()
                await session.approval_event.wait()

                if session.approval_result:
                    result = execute_tool(block.name, block.input)
                    await session.queue.put(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "tool_name": block.name,
                            "result": result,
                        }
                    )
                else:
                    result = "The user rejected this tool call."
                    await session.queue.put(
                        {
                            "type": "tool_rejected",
                            "tool_use_id": block.id,
                            "tool_name": block.name,
                        }
                    )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

            session.messages.append({"role": "user", "content": tool_results})

        else:
            await session.queue.put(
                {"type": "error", "content": f"Unexpected stop reason: {response.stop_reason}"}
            )
            await session.queue.put({"type": "done"})
            break
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd tool-call-fastapi && pytest tests/test_agent.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add tool-call-fastapi/agent.py tool-call-fastapi/pytest.ini tool-call-fastapi/tests/test_agent.py
git commit -m "feat: add agent session and run loop with approval pause"
```

---

## Task 5: FastAPI App and Endpoints

**Files:**
- Create: `tool-call-fastapi/main.py`
- Create: `tool-call-fastapi/tests/test_main.py`

- [ ] **Step 1: Write failing endpoint tests**

```python
# tests/test_main.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from main import app

client = TestClient(app)


def test_create_session_returns_session_id():
    response = client.post("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 0


def test_chat_unknown_session_returns_404():
    response = client.post(
        "/sessions/nonexistent/chat", json={"message": "hello"}
    )
    assert response.status_code == 404


def test_approve_unknown_session_returns_404():
    response = client.post(
        "/sessions/nonexistent/approve", json={"approved": True}
    )
    assert response.status_code == 404


def test_stream_unknown_session_returns_404():
    response = client.get("/sessions/nonexistent/stream")
    assert response.status_code == 404


def test_chat_known_session_returns_processing():
    session_res = client.post("/sessions")
    sid = session_res.json()["session_id"]

    with patch("main.asyncio.create_task"):
        response = client.post(f"/sessions/{sid}/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json()["status"] == "processing"


def test_approve_known_session_returns_ok():
    session_res = client.post("/sessions")
    sid = session_res.json()["session_id"]

    response = client.post(f"/sessions/{sid}/approve", json={"approved": True})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tool-call-fastapi && pytest tests/test_main.py -v`
Expected: ImportError — `main` module not found.

- [ ] **Step 3: Write main.py**

```python
import asyncio
import json
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent import Session, run_agent
from models import ApprovalRequest, ChatRequest, SessionResponse

app = FastAPI(title="Tool Call Approval API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, Session] = {}


@app.post("/sessions", response_model=SessionResponse)
async def create_session() -> SessionResponse:
    session_id = str(uuid.uuid4())
    sessions[session_id] = Session(id=session_id)
    return SessionResponse(session_id=session_id)


@app.post("/sessions/{session_id}/chat")
async def chat(session_id: str, request: ChatRequest) -> dict:
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    asyncio.create_task(run_agent(session, request.message))
    return {"status": "processing"}


@app.get("/sessions/{session_id}/stream")
async def stream_events(session_id: str) -> StreamingResponse:
    session = sessions.get(session_id)
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
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.approval_result = request.approved
    session.approval_event.set()
    return {"status": "ok"}
```

- [ ] **Step 4: Run all backend tests**

Run: `cd tool-call-fastapi && pytest -v`
Expected: All tests pass (tools + agent + main).

- [ ] **Step 5: Commit**

```bash
git add tool-call-fastapi/main.py tool-call-fastapi/tests/test_main.py
git commit -m "feat: add FastAPI endpoints for sessions, chat, stream, and approval"
```

---

## Task 6: Scaffold Angular App

**Files:**
- Creates: entire `tool-call-ui/` via `ng new`

- [ ] **Step 1: Scaffold with Angular CLI**

Run from `tool-call-approval/`:
```bash
npx @angular/cli new tool-call-ui \
  --routing=false \
  --style=css \
  --ssr=false \
  --no-interactive \
  --skip-git
```
Expected: `tool-call-ui/` directory created with Angular project structure.

- [ ] **Step 2: Verify it builds**

Run: `cd tool-call-ui && npm run build -- --configuration development`
Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add tool-call-ui/
git commit -m "chore: scaffold Angular 20 standalone app"
```

---

## Task 7: TypeScript Types and Chat Service

**Files:**
- Create: `tool-call-ui/src/app/models/types.ts`
- Create: `tool-call-ui/src/app/services/chat.service.ts`

- [ ] **Step 1: Write types.ts**

```typescript
export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export interface ToolCall {
  tool_use_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface SseEvent {
  type:
    | 'thinking'
    | 'tool_call_pending'
    | 'tool_result'
    | 'tool_rejected'
    | 'message'
    | 'done'
    | 'error';
  content?: string;
  tool_use_id?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  result?: string;
}
```

- [ ] **Step 2: Write chat.service.ts**

```typescript
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Subject } from 'rxjs';
import { firstValueFrom } from 'rxjs';
import { SseEvent } from '../models/types';

const API_URL = 'http://localhost:8000';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private sessionId: string | null = null;
  private eventSource: EventSource | null = null;

  readonly sseEvents$ = new Subject<SseEvent>();

  constructor(private http: HttpClient) {}

  async createSession(): Promise<void> {
    const res = await firstValueFrom(
      this.http.post<{ session_id: string }>(`${API_URL}/sessions`, {})
    );
    this.sessionId = res.session_id;
  }

  connectStream(): void {
    if (!this.sessionId) return;
    this.eventSource?.close();
    this.eventSource = new EventSource(
      `${API_URL}/sessions/${this.sessionId}/stream`
    );
    this.eventSource.onmessage = (event: MessageEvent) => {
      const data: SseEvent = JSON.parse(event.data);
      this.sseEvents$.next(data);
    };
    this.eventSource.onerror = () => {
      this.eventSource?.close();
    };
  }

  async sendMessage(message: string): Promise<void> {
    if (!this.sessionId) throw new Error('No active session');
    await firstValueFrom(
      this.http.post(`${API_URL}/sessions/${this.sessionId}/chat`, { message })
    );
  }

  async approveTool(approved: boolean): Promise<void> {
    if (!this.sessionId) throw new Error('No active session');
    await firstValueFrom(
      this.http.post(`${API_URL}/sessions/${this.sessionId}/approve`, {
        approved,
      })
    );
  }

  closeStream(): void {
    this.eventSource?.close();
    this.eventSource = null;
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add tool-call-ui/src/app/models/ tool-call-ui/src/app/services/
git commit -m "feat: add TypeScript types and chat service"
```

---

## Task 8: Tool Approval Component

**Files:**
- Create: `tool-call-ui/src/app/components/tool-approval/tool-approval.component.ts`
- Create: `tool-call-ui/src/app/components/tool-approval/tool-approval.component.html`
- Create: `tool-call-ui/src/app/components/tool-approval/tool-approval.component.css`

- [ ] **Step 1: Write tool-approval.component.ts**

```typescript
import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ToolCall } from '../../models/types';

@Component({
  selector: 'app-tool-approval',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './tool-approval.component.html',
  styleUrls: ['./tool-approval.component.css'],
})
export class ToolApprovalComponent {
  @Input() toolCall!: ToolCall;
  @Input() disabled = false;
  @Output() approved = new EventEmitter<boolean>();

  get formattedInput(): string {
    return JSON.stringify(this.toolCall.tool_input, null, 2);
  }

  approve(): void {
    this.approved.emit(true);
  }

  reject(): void {
    this.approved.emit(false);
  }
}
```

- [ ] **Step 2: Write tool-approval.component.html**

```html
<div class="approval-card">
  <div class="approval-header">
    <span class="tool-icon">⚙️</span>
    <div class="tool-info">
      <span class="label">Tool Call Request</span>
      <span class="tool-name">{{ toolCall.tool_name }}</span>
    </div>
    <span class="badge pending">Awaiting Approval</span>
  </div>

  <div class="approval-body">
    <span class="args-label">Arguments</span>
    <pre class="args-block"><code>{{ formattedInput }}</code></pre>
  </div>

  <div class="approval-actions">
    <button class="btn btn-reject" [disabled]="disabled" (click)="reject()">
      ✕ Reject
    </button>
    <button class="btn btn-approve" [disabled]="disabled" (click)="approve()">
      ✓ Approve
    </button>
  </div>
</div>
```

- [ ] **Step 3: Write tool-approval.component.css**

```css
.approval-card {
  background: #1e2433;
  border: 1px solid #f59e0b;
  border-radius: 10px;
  padding: 16px;
  margin: 8px 0;
  max-width: 540px;
}

.approval-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.tool-icon {
  font-size: 1.4rem;
}

.tool-info {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.label {
  font-size: 0.7rem;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.tool-name {
  font-size: 1rem;
  font-weight: 600;
  color: #f1f5f9;
  font-family: monospace;
}

.badge {
  font-size: 0.7rem;
  padding: 3px 8px;
  border-radius: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge.pending {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
  border: 1px solid #f59e0b;
}

.args-label {
  font-size: 0.7rem;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  display: block;
  margin-bottom: 6px;
}

.args-block {
  background: #0f172a;
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 0.85rem;
  color: #7dd3fc;
  overflow-x: auto;
  margin: 0 0 14px;
  font-family: 'Fira Code', 'Cascadia Code', monospace;
}

.approval-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.btn {
  padding: 8px 20px;
  border-radius: 6px;
  border: none;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-reject {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid #ef4444;
}

.btn-reject:not(:disabled):hover {
  background: rgba(239, 68, 68, 0.3);
}

.btn-approve {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
  border: 1px solid #22c55e;
}

.btn-approve:not(:disabled):hover {
  background: rgba(34, 197, 94, 0.3);
}
```

- [ ] **Step 4: Commit**

```bash
git add tool-call-ui/src/app/components/tool-approval/
git commit -m "feat: add tool approval card component"
```

---

## Task 9: Chat Component

**Files:**
- Create: `tool-call-ui/src/app/components/chat/chat.component.ts`
- Create: `tool-call-ui/src/app/components/chat/chat.component.html`
- Create: `tool-call-ui/src/app/components/chat/chat.component.css`
- Create: `tool-call-ui/src/app/components/chat/chat.component.spec.ts`

- [ ] **Step 1: Write failing unit tests**

```typescript
// chat.component.spec.ts
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ChatComponent } from './chat.component';
import { ChatService } from '../../services/chat.service';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { Subject } from 'rxjs';
import { SseEvent } from '../../models/types';

describe('ChatComponent', () => {
  let component: ChatComponent;
  let fixture: ComponentFixture<ChatComponent>;
  let chatService: jasmine.SpyObj<ChatService>;
  let sseSubject: Subject<SseEvent>;

  beforeEach(async () => {
    sseSubject = new Subject<SseEvent>();
    chatService = jasmine.createSpyObj(
      'ChatService',
      ['createSession', 'connectStream', 'sendMessage', 'approveTool'],
      { sseEvents$: sseSubject }
    );
    chatService.createSession.and.returnValue(Promise.resolve());
    chatService.sendMessage.and.returnValue(Promise.resolve());
    chatService.approveTool.and.returnValue(Promise.resolve());

    await TestBed.configureTestingModule({
      imports: [ChatComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ChatService, useValue: chatService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize a session on init', () => {
    expect(chatService.createSession).toHaveBeenCalled();
  });

  it('should add a user message when sendMessage is called', async () => {
    component.userInput = 'Hello';
    await component.sendMessage();
    const userMsg = component.messages.find((m) => m.role === 'user');
    expect(userMsg?.content).toBe('Hello');
    expect(component.userInput).toBe('');
  });

  it('should not send empty messages', async () => {
    component.userInput = '   ';
    await component.sendMessage();
    expect(chatService.sendMessage).not.toHaveBeenCalled();
  });

  it('should add assistant message on SSE message event', () => {
    sseSubject.next({ type: 'message', content: 'Hi there!' });
    fixture.detectChanges();
    const assistantMsg = component.messages.find((m) => m.role === 'assistant');
    expect(assistantMsg?.content).toBe('Hi there!');
  });

  it('should set pendingToolCall on tool_call_pending event', () => {
    sseSubject.next({
      type: 'tool_call_pending',
      tool_use_id: 'abc',
      tool_name: 'calculate',
      tool_input: { expression: '2+2' },
    });
    fixture.detectChanges();
    expect(component.pendingToolCall).not.toBeNull();
    expect(component.pendingToolCall?.tool_name).toBe('calculate');
  });

  it('should clear pendingToolCall after approval', async () => {
    component.pendingToolCall = {
      tool_use_id: 'abc',
      tool_name: 'calculate',
      tool_input: { expression: '2+2' },
    };
    await component.handleApproval(true);
    expect(chatService.approveTool).toHaveBeenCalledWith(true);
    expect(component.pendingToolCall).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tool-call-ui && npx ng test --watch=false --browsers=ChromeHeadless`
Expected: Multiple failures — `ChatComponent` not found.

- [ ] **Step 3: Write chat.component.ts**

```typescript
import {
  Component,
  OnInit,
  OnDestroy,
  ViewChild,
  ElementRef,
  AfterViewChecked,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ChatService } from '../../services/chat.service';
import { ToolApprovalComponent } from '../tool-approval/tool-approval.component';
import { Message, ToolCall } from '../../models/types';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, ToolApprovalComponent],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.css'],
})
export class ChatComponent implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('messageList') private messageListRef!: ElementRef;

  messages: Message[] = [];
  userInput = '';
  pendingToolCall: ToolCall | null = null;
  isWaiting = false;
  private sseSubscription!: Subscription;
  private shouldScrollToBottom = false;

  constructor(private chatService: ChatService) {}

  async ngOnInit(): Promise<void> {
    await this.chatService.createSession();
    this.chatService.connectStream();
    this.sseSubscription = this.chatService.sseEvents$.subscribe((event) => {
      switch (event.type) {
        case 'thinking':
          this.isWaiting = true;
          break;
        case 'tool_call_pending':
          this.isWaiting = false;
          this.pendingToolCall = {
            tool_use_id: event.tool_use_id!,
            tool_name: event.tool_name!,
            tool_input: event.tool_input ?? {},
          };
          break;
        case 'tool_result':
          this.addSystemMessage(
            `Tool "${event.tool_name}" returned: ${event.result}`
          );
          break;
        case 'tool_rejected':
          this.addSystemMessage(`Tool "${event.tool_name}" was rejected.`);
          break;
        case 'message':
          this.isWaiting = false;
          this.addMessage('assistant', event.content ?? '');
          break;
        case 'done':
          this.isWaiting = false;
          this.chatService.connectStream();
          break;
        case 'error':
          this.isWaiting = false;
          this.addSystemMessage(`Error: ${event.content}`);
          break;
      }
      this.shouldScrollToBottom = true;
    });
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom();
      this.shouldScrollToBottom = false;
    }
  }

  ngOnDestroy(): void {
    this.sseSubscription?.unsubscribe();
    this.chatService.closeStream();
  }

  async sendMessage(): Promise<void> {
    const text = this.userInput.trim();
    if (!text) return;
    this.userInput = '';
    this.addMessage('user', text);
    this.isWaiting = true;
    await this.chatService.sendMessage(text);
  }

  async handleApproval(approved: boolean): Promise<void> {
    this.pendingToolCall = null;
    this.isWaiting = true;
    await this.chatService.approveTool(approved);
  }

  private addMessage(role: 'user' | 'assistant', content: string): void {
    this.messages.push({
      id: crypto.randomUUID(),
      role,
      content,
      timestamp: new Date(),
    });
  }

  private addSystemMessage(content: string): void {
    this.messages.push({
      id: crypto.randomUUID(),
      role: 'system',
      content,
      timestamp: new Date(),
    });
  }

  private scrollToBottom(): void {
    try {
      const el = this.messageListRef?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    } catch {}
  }
}
```

- [ ] **Step 4: Write chat.component.html**

```html
<div class="chat-container">
  <header class="chat-header">
    <span class="header-icon">🤖</span>
    <div>
      <h1>Tool Call Approval</h1>
      <span class="subtitle">Claude agent with human-in-the-loop</span>
    </div>
  </header>

  <div class="message-list" #messageList>
    @if (messages.length === 0) {
      <div class="empty-state">
        <p>Try asking:</p>
        <ul>
          <li>"What is 1234 × 5678?"</li>
          <li>"What's the weather in London?"</li>
          <li>"Search for information about black holes"</li>
        </ul>
      </div>
    }

    @for (message of messages; track message.id) {
      <div class="message" [ngClass]="message.role">
        <div class="bubble">{{ message.content }}</div>
        <span class="timestamp">{{ message.timestamp | date: 'HH:mm' }}</span>
      </div>
    }

    @if (pendingToolCall) {
      <app-tool-approval
        [toolCall]="pendingToolCall"
        [disabled]="isWaiting"
        (approved)="handleApproval($event)"
      />
    }

    @if (isWaiting && !pendingToolCall) {
      <div class="thinking">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
    }
  </div>

  <form class="input-area" (ngSubmit)="sendMessage()">
    <input
      class="input-field"
      type="text"
      [(ngModel)]="userInput"
      name="userInput"
      placeholder="Ask the agent something..."
      [disabled]="isWaiting || !!pendingToolCall"
      autocomplete="off"
    />
    <button
      class="send-btn"
      type="submit"
      [disabled]="isWaiting || !!pendingToolCall || !userInput.trim()"
    >
      Send
    </button>
  </form>
</div>
```

- [ ] **Step 5: Write chat.component.css**

```css
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0f172a;
  color: #f1f5f9;
  font-family: 'Inter', system-ui, sans-serif;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  background: #1e2433;
  border-bottom: 1px solid #334155;
}

.header-icon {
  font-size: 2rem;
}

.chat-header h1 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: #f1f5f9;
}

.subtitle {
  font-size: 0.75rem;
  color: #64748b;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.empty-state {
  color: #475569;
  font-size: 0.9rem;
  text-align: center;
  margin: auto;
}

.empty-state ul {
  list-style: none;
  padding: 0;
  margin-top: 8px;
}

.empty-state li {
  background: #1e2433;
  border-radius: 8px;
  padding: 8px 16px;
  margin: 4px 0;
  cursor: default;
}

.message {
  display: flex;
  flex-direction: column;
  max-width: 68%;
}

.message.user {
  align-self: flex-end;
  align-items: flex-end;
}

.message.assistant {
  align-self: flex-start;
  align-items: flex-start;
}

.message.system {
  align-self: center;
  align-items: center;
  max-width: 90%;
}

.bubble {
  padding: 10px 16px;
  border-radius: 14px;
  font-size: 0.9rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.message.user .bubble {
  background: #3b82f6;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.message.assistant .bubble {
  background: #1e2433;
  color: #e2e8f0;
  border-bottom-left-radius: 4px;
}

.message.system .bubble {
  background: rgba(148, 163, 184, 0.1);
  color: #94a3b8;
  font-size: 0.8rem;
  border-radius: 8px;
  font-style: italic;
}

.timestamp {
  font-size: 0.65rem;
  color: #475569;
  margin-top: 3px;
}

.thinking {
  display: flex;
  gap: 5px;
  padding: 12px 16px;
  align-self: flex-start;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #64748b;
  animation: pulse 1.2s infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes pulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

.input-area {
  display: flex;
  gap: 10px;
  padding: 16px 24px;
  background: #1e2433;
  border-top: 1px solid #334155;
}

.input-field {
  flex: 1;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 10px 16px;
  color: #f1f5f9;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.15s;
}

.input-field:focus {
  border-color: #3b82f6;
}

.input-field:disabled {
  opacity: 0.5;
}

.send-btn {
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 22px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.send-btn:hover:not(:disabled) {
  background: #2563eb;
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

- [ ] **Step 6: Run tests**

Run: `cd tool-call-ui && npx ng test --watch=false --browsers=ChromeHeadless`
Expected: All ChatComponent tests pass.

- [ ] **Step 7: Commit**

```bash
git add tool-call-ui/src/app/components/chat/
git commit -m "feat: add chat component with SSE and tool approval integration"
```

---

## Task 10: Wire Up App Root and Config

**Files:**
- Modify: `tool-call-ui/src/app/app.component.ts`
- Modify: `tool-call-ui/src/app/app.component.html`
- Modify: `tool-call-ui/src/app/app.component.css`
- Modify: `tool-call-ui/src/app/app.config.ts`
- Modify: `tool-call-ui/src/styles.css`

- [ ] **Step 1: Update app.config.ts**

```typescript
import { ApplicationConfig } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';

export const appConfig: ApplicationConfig = {
  providers: [provideHttpClient()],
};
```

- [ ] **Step 2: Update app.component.ts**

```typescript
import { Component } from '@angular/core';
import { ChatComponent } from './components/chat/chat.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [ChatComponent],
  template: '<app-chat />',
  styles: [':host { display: block; height: 100vh; }'],
})
export class AppComponent {}
```

- [ ] **Step 3: Update src/styles.css**

```css
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  height: 100%;
  background: #0f172a;
}
```

- [ ] **Step 4: Build to verify no errors**

Run: `cd tool-call-ui && npm run build -- --configuration development`
Expected: Build succeeds, 0 errors.

- [ ] **Step 5: Commit**

```bash
git add tool-call-ui/src/app/app.component.ts tool-call-ui/src/app/app.config.ts tool-call-ui/src/styles.css
git commit -m "feat: wire up root component and http client"
```

---

## Task 11: Backend README

**Files:**
- Create: `tool-call-fastapi/README.md`

- [ ] **Step 1: Write README.md**

```markdown
# tool-call-fastapi

FastAPI backend for the tool-call-approval demo. Runs an Anthropic Claude agent
with human-in-the-loop tool approval via SSE.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
uvicorn main:app --reload
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions` | Create a new agent session |
| POST | `/sessions/{id}/chat` | Send a user message |
| GET  | `/sessions/{id}/stream` | SSE stream of agent events |
| POST | `/sessions/{id}/approve` | Approve or reject a pending tool call |

## SSE Event Types

| type | payload fields | description |
|------|----------------|-------------|
| `thinking` | `content` | Agent is processing |
| `tool_call_pending` | `tool_use_id`, `tool_name`, `tool_input` | Agent wants to call a tool |
| `tool_result` | `tool_use_id`, `tool_name`, `result` | Tool executed successfully |
| `tool_rejected` | `tool_use_id`, `tool_name` | Tool call was rejected |
| `message` | `content` | Final assistant response |
| `done` | — | Stream complete |
| `error` | `content` | Unexpected error |

## Tests

```bash
pytest -v
```
```

- [ ] **Step 2: Commit**

```bash
git add tool-call-fastapi/README.md
git commit -m "docs: add backend README with endpoint and SSE event reference"
```

---

## Task 12: Frontend README

**Files:**
- Create: `tool-call-ui/README.md`

- [ ] **Step 1: Write README.md**

```markdown
# tool-call-ui

Angular 20 frontend for the tool-call-approval demo. Renders a chat interface
with inline tool-call approval cards that connect to the FastAPI backend.

## Setup

```bash
npm install
ng serve          # runs on http://localhost:4200
```

Requires the `tool-call-fastapi` backend running on `http://localhost:8000`.

## Components

- **ChatComponent** — full-page chat UI; manages SSE subscription and message list
- **ToolApprovalComponent** — approval card displayed when agent requests a tool call

## Running Tests

```bash
ng test --watch=false --browsers=ChromeHeadless
```
```

- [ ] **Step 2: Commit**

```bash
git add tool-call-ui/README.md
git commit -m "docs: add frontend README"
```
