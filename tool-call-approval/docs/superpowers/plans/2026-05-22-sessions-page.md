# Sessions Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Sessions tab to the AI-Engineer page that lists all past sessions and shows full chat history inline when a row is clicked.

**Architecture:** A new `AiEngg` shell component wraps the existing `Chat` component (unchanged) and a new `Sessions` component under a tab switcher. The backend gets a new `GET /sessions` endpoint that queries `ai.agno_sessions` directly, proxied through `tool-call-api`. The Angular `SessionsService` fetches both the list and per-session history.

**Tech Stack:** Python 3.12, FastAPI, psycopg2, pytest | Angular 19, TypeScript, standalone components

---

## File Map

| File | Change |
|---|---|
| `tool-call-agent/repository.py` | Add `list_sessions()` to `PostgresRepository` |
| `tool-call-agent/models.py` | Add `SessionSummaryResponse` Pydantic model |
| `tool-call-agent/main.py` | Add `GET /sessions` endpoint |
| `tool-call-agent/tests/test_sessions.py` | New test file for the sessions endpoint |
| `tool-call-api/main.py` | Add `GET /api/sessions` proxy route |
| `tool-call-ui/src/app/models/types.ts` | Add `SessionSummary` and `ChatMessage` interfaces |
| `tool-call-ui/src/app/services/sessions.service.ts` | New service: `getAll()`, `getHistory()` |
| `tool-call-ui/src/app/ai-engg/sessions/sessions.ts` | New Sessions component |
| `tool-call-ui/src/app/ai-engg/sessions/sessions.html` | Sessions table + inline chat detail |
| `tool-call-ui/src/app/ai-engg/sessions/sessions.css` | Table and chat bubble styles |
| `tool-call-ui/src/app/ai-engg/ai-engg.ts` | New AiEngg shell with tab switcher |
| `tool-call-ui/src/app/ai-engg/ai-engg.html` | Tab bar + conditional Chat / Sessions |
| `tool-call-ui/src/app/ai-engg/ai-engg.css` | Tab bar styles |
| `tool-call-ui/src/app/app.routes.ts` | Point `/ai-engg` at `AiEngg` instead of `Chat` |

---

## Task 1: Backend — `GET /sessions` endpoint

**Files:**
- Modify: `tool-call-agent/repository.py`
- Modify: `tool-call-agent/models.py`
- Modify: `tool-call-agent/main.py`
- Create: `tool-call-agent/tests/test_sessions.py`

- [ ] **Step 1: Write failing tests**

Create `tool-call-agent/tests/test_sessions.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd tool-call-agent && python -m pytest tests/test_sessions.py -v
```

Expected: FAIL — `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Add `list_sessions()` to `PostgresRepository`**

In `tool-call-agent/repository.py`, add `import psycopg2` and `import psycopg2.extras` at the top, then add the method to `PostgresRepository`:

```python
import psycopg2
import psycopg2.extras
```

Add method after `get_db`:

```python
    def list_sessions(self) -> list[dict]:
        url = self._url.replace("postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(url)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT session_id,
                           created_at,
                           updated_at,
                           COALESCE(jsonb_array_length(runs), 0) AS turn_count
                    FROM ai.agno_sessions
                    ORDER BY updated_at DESC NULLS LAST
                """)
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
```

- [ ] **Step 4: Add `SessionSummaryResponse` to `models.py`**

In `tool-call-agent/models.py`, add at the end:

```python
class SessionSummaryResponse(BaseModel):
    session_id: str
    created_at: int
    updated_at: int | None
    turn_count: int
```

- [ ] **Step 5: Add `GET /sessions` endpoint to `main.py`**

In `tool-call-agent/main.py`, update the `SessionSummaryResponse` import — add it to the `from models import ...` line:

```python
from models import ApprovalRequest, ChatRequest, CreateSessionRequest, SessionResponse, SessionSummaryResponse
```

Then add the endpoint after the `create_session` route:

```python
@app.get("/sessions", response_model=list[SessionSummaryResponse])
async def list_sessions() -> list[dict]:
    return _repository.list_sessions()
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
cd tool-call-agent && python -m pytest tests/test_sessions.py -v
```

Expected: 4 tests PASS

- [ ] **Step 7: Add proxy route to `tool-call-api/main.py`**

In `tool-call-api/main.py`, add after the existing `create_session` route (around line 72):

```python
@app.get("/api/sessions")
async def list_sessions() -> JSONResponse:
    return await _proxy(
        _get_client().get(f"{_BACKEND}/sessions", timeout=30.0)
    )
```

- [ ] **Step 8: Commit**

```bash
git add tool-call-agent/repository.py tool-call-agent/models.py tool-call-agent/main.py \
        tool-call-agent/tests/test_sessions.py tool-call-api/main.py
git commit -m "feat(api): add GET /sessions endpoint and web proxy"
```

---

## Task 2: Angular types and SessionsService

**Files:**
- Modify: `tool-call-ui/src/app/models/types.ts`
- Create: `tool-call-ui/src/app/services/sessions.service.ts`

- [ ] **Step 1: Add interfaces to `types.ts`**

In `tool-call-ui/src/app/models/types.ts`, add at the end:

```typescript
export interface SessionSummary {
  session_id: string;
  created_at: number;
  updated_at: number | null;
  turn_count: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}
```

- [ ] **Step 2: Create `sessions.service.ts`**

Create `tool-call-ui/src/app/services/sessions.service.ts`:

```typescript
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ChatMessage, SessionSummary } from '../models/types';

const API_URL = 'http://localhost:8080/api';

@Injectable({ providedIn: 'root' })
export class SessionsService {
  constructor(private http: HttpClient) {}

  getAll(): Promise<SessionSummary[]> {
    return firstValueFrom(
      this.http.get<SessionSummary[]>(`${API_URL}/sessions`)
    );
  }

  getHistory(sessionId: string): Promise<ChatMessage[]> {
    return firstValueFrom(
      this.http.get<ChatMessage[]>(`${API_URL}/sessions/${sessionId}/history`)
    );
  }
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd tool-call-ui && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add tool-call-ui/src/app/models/types.ts \
        tool-call-ui/src/app/services/sessions.service.ts
git commit -m "feat(ui): add SessionSummary/ChatMessage types and SessionsService"
```

---

## Task 3: Sessions component

**Files:**
- Create: `tool-call-ui/src/app/ai-engg/sessions/sessions.ts`
- Create: `tool-call-ui/src/app/ai-engg/sessions/sessions.html`
- Create: `tool-call-ui/src/app/ai-engg/sessions/sessions.css`

- [ ] **Step 1: Create the component class**

Create `tool-call-ui/src/app/ai-engg/sessions/sessions.ts`:

```typescript
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatMessage, SessionSummary } from '../../../models/types';
import { SessionsService } from '../../../services/sessions.service';

@Component({
  selector: 'app-sessions',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './sessions.html',
  styleUrl: './sessions.css',
})
export class Sessions implements OnInit {
  sessions: SessionSummary[] = [];
  selectedId: string | null = null;
  history: ChatMessage[] = [];
  loadingSessions = false;
  loadingHistory = false;
  error = '';
  historyError = '';

  constructor(private sessionsService: SessionsService) {}

  async ngOnInit(): Promise<void> {
    this.loadingSessions = true;
    try {
      this.sessions = await this.sessionsService.getAll();
    } catch {
      this.error = 'Failed to load sessions';
    } finally {
      this.loadingSessions = false;
    }
  }

  async selectSession(id: string): Promise<void> {
    if (this.selectedId === id) {
      this.selectedId = null;
      this.history = [];
      return;
    }
    this.selectedId = id;
    this.history = [];
    this.historyError = '';
    this.loadingHistory = true;
    try {
      this.history = await this.sessionsService.getHistory(id);
    } catch {
      this.historyError = 'Failed to load chat history';
    } finally {
      this.loadingHistory = false;
    }
  }

  formatTimestamp(epoch: number): string {
    return new Date(epoch * 1000).toLocaleString();
  }

  shortId(id: string): string {
    return id.slice(0, 8);
  }
}
```

- [ ] **Step 2: Create the template**

Create `tool-call-ui/src/app/ai-engg/sessions/sessions.html`:

```html
@if (error) {
  <p class="error">{{ error }}</p>
}

@if (loadingSessions) {
  <p class="muted">Loading sessions…</p>
}

@if (!loadingSessions && sessions.length === 0 && !error) {
  <p class="muted">No sessions yet.</p>
}

@if (sessions.length > 0) {
  <table class="sessions-table">
    <thead>
      <tr>
        <th>Session ID</th>
        <th>Last Active</th>
        <th>Turns</th>
      </tr>
    </thead>
    <tbody>
      @for (s of sessions; track s.session_id) {
        <tr
          class="session-row"
          [class.selected]="selectedId === s.session_id"
          (click)="selectSession(s.session_id)"
        >
          <td class="session-id">{{ shortId(s.session_id) }}</td>
          <td>{{ formatTimestamp(s.updated_at ?? s.created_at) }}</td>
          <td>{{ s.turn_count }}</td>
        </tr>
        @if (selectedId === s.session_id) {
          <tr class="detail-row">
            <td colspan="3">
              @if (loadingHistory) {
                <p class="muted padded">Loading…</p>
              }
              @if (historyError) {
                <p class="error padded">{{ historyError }}</p>
              }
              @if (!loadingHistory && history.length === 0 && !historyError) {
                <p class="muted padded">No messages in this session.</p>
              }
              <div class="history">
                @for (msg of history; track $index) {
                  <div class="bubble" [class.user]="msg.role === 'user'" [class.assistant]="msg.role === 'assistant'">
                    <span class="role-label">{{ msg.role }}</span>
                    <p class="content">{{ msg.content }}</p>
                  </div>
                }
              </div>
            </td>
          </tr>
        }
      }
    </tbody>
  </table>
}
```

- [ ] **Step 3: Create styles**

Create `tool-call-ui/src/app/ai-engg/sessions/sessions.css`:

```css
.error  { color: #f85149; font-size: 13px; margin-bottom: 12px; }
.muted  { color: #8b949e; font-size: 13px; }
.padded { padding: 12px 14px; margin: 0; }

.sessions-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.sessions-table th {
  color: #8b949e;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-align: left;
  text-transform: uppercase;
  padding: 0 12px 8px;
  border-bottom: 1px solid #30363d;
}

.session-row {
  cursor: pointer;
  transition: background 0.1s;
}

.session-row td {
  color: #e6edf3;
  padding: 10px 12px;
  border-bottom: 1px solid #21262d;
}

.session-row:hover td { background: #161b22; }
.session-row.selected td { background: #1c2a3a; }

.session-id {
  font-family: monospace;
  font-size: 12px;
  color: #58a6ff;
}

.detail-row > td {
  padding: 0;
  border-bottom: 1px solid #30363d;
  background: #0d1117;
}

.history {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  max-height: 400px;
  overflow-y: auto;
}

.bubble {
  max-width: 70%;
  padding: 8px 12px;
  border-radius: 8px;
}

.bubble.user {
  align-self: flex-end;
  background: #1f4a8f;
}

.bubble.assistant {
  align-self: flex-start;
  background: #161b22;
  border: 1px solid #30363d;
}

.role-label {
  color: #8b949e;
  display: block;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  margin-bottom: 4px;
  text-transform: uppercase;
}

.content {
  color: #e6edf3;
  font-size: 13px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd tool-call-ui && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add tool-call-ui/src/app/ai-engg/sessions/
git commit -m "feat(ui): add Sessions component"
```

---

## Task 4: AiEngg shell + routing update

**Files:**
- Create: `tool-call-ui/src/app/ai-engg/ai-engg.ts`
- Create: `tool-call-ui/src/app/ai-engg/ai-engg.html`
- Create: `tool-call-ui/src/app/ai-engg/ai-engg.css`
- Modify: `tool-call-ui/src/app/app.routes.ts`

- [ ] **Step 1: Create the AiEngg shell component**

Create `tool-call-ui/src/app/ai-engg/ai-engg.ts`:

```typescript
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Chat } from '../components/chat/chat';
import { Sessions } from './sessions/sessions';

@Component({
  selector: 'app-ai-engg',
  standalone: true,
  imports: [CommonModule, Chat, Sessions],
  templateUrl: './ai-engg.html',
  styleUrl: './ai-engg.css',
})
export class AiEngg {
  tab: 'chat' | 'sessions' = 'chat';
}
```

- [ ] **Step 2: Create the template**

Create `tool-call-ui/src/app/ai-engg/ai-engg.html`:

```html
<div class="tabs">
  <button type="button" class="tab" [class.active]="tab === 'chat'" (click)="tab = 'chat'">
    Chat
  </button>
  <button type="button" class="tab" [class.active]="tab === 'sessions'" (click)="tab = 'sessions'">
    Sessions
  </button>
</div>

@if (tab === 'chat') {
  <app-chat />
}
@if (tab === 'sessions') {
  <app-sessions />
}
```

- [ ] **Step 3: Create styles**

Create `tool-call-ui/src/app/ai-engg/ai-engg.css`:

```css
.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  border-bottom: 1px solid #30363d;
  padding-bottom: 0;
}

.tab {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #8b949e;
  cursor: pointer;
  font-size: 14px;
  margin-bottom: -1px;
  padding: 8px 16px;
  transition: color 0.15s, border-color 0.15s;
}

.tab:hover { color: #e6edf3; }

.tab.active {
  border-bottom-color: #58a6ff;
  color: #58a6ff;
}
```

- [ ] **Step 4: Update `app.routes.ts` to load `AiEngg`**

Replace the `ai-engg` route in `tool-call-ui/src/app/app.routes.ts`:

```typescript
import { Routes } from '@angular/router';
import { AppShell } from './app-shell/app-shell';

export const routes: Routes = [
  {
    path: '',
    component: AppShell,
    children: [
      { path: '', redirectTo: 'ai-engg', pathMatch: 'full' },
      {
        path: 'ai-engg',
        loadComponent: () =>
          import('./ai-engg/ai-engg').then((m) => m.AiEngg),
      },
      {
        path: 'admin',
        loadComponent: () =>
          import('./admin/admin-layout/admin-layout').then((m) => m.AdminLayout),
        loadChildren: () =>
          import('./admin/admin.routes').then((m) => m.adminRoutes),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd tool-call-ui && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 6: Smoke test in browser**

Start both servers if not running:

```bash
# Terminal 1 — agent API
cd tool-call-agent && uvicorn main:app --reload

# Terminal 2 — Angular dev server
cd tool-call-ui && ng serve
```

Navigate to `http://localhost:4200`. Verify:
1. AI-Engineer page shows **Chat** and **Sessions** tabs
2. Chat tab works exactly as before (send a message, get a response)
3. Sessions tab loads and shows a table of past sessions
4. Clicking a row expands an inline panel with chat bubbles (user right-aligned, assistant left-aligned)
5. Clicking the same row again collapses the panel
6. Clicking a different row closes the first and opens the new one

- [ ] **Step 7: Commit**

```bash
git add tool-call-ui/src/app/ai-engg/ai-engg.ts \
        tool-call-ui/src/app/ai-engg/ai-engg.html \
        tool-call-ui/src/app/ai-engg/ai-engg.css \
        tool-call-ui/src/app/app.routes.ts
git commit -m "feat(ui): add AiEngg shell with Chat and Sessions tabs"
```
