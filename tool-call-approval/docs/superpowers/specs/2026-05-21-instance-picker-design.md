# AI-Engg Instance Picker — Design

**Date:** 2026-05-21  
**Status:** Approved

## Goal

Add an agent instance dropdown to the AI-Engg chat page so users can pick which configured instance (persona + skills) to chat with. The selected instance's persona skills are loaded into the Agno agent at session creation time via `Skills(loaders=[LocalSkills(tmpdir)])`.

## Current State

- `GET /admin/agent-instances` requires `agent_name` query param — no way to fetch all instances in one call.
- `POST /sessions` accepts no body — no instance context.
- `AgentService._build_agent()` uses hardcoded Kubernetes agent instructions.
- Chat component has no instance awareness.

## Architecture & Data Flow

```text
AI-Engg page (Chat component)
│
├── on init:
│   GET /api/admin/agent-instances  (agent_name omitted → returns ALL instances)
│   → dropdown: "<agent_name> / <instance_name>" (flat list, sorted)
│
├── user picks instance (default = first; "— none —" if no instances exist)
│
├── on page load / "New Session":
│   POST /api/sessions  { instance_id: "uuid" | null }
│   │
│   └── AgentService.create_session(instance_id)
│       ├── if instance_id:
│       │   1. look up instance → persona_id, mcp_positions
│       │   2. fetch persona → skill_ids
│       │   3. fetch (filename, content) for each skill_id from DB
│       │   4. write each skill: {tmpdir}/{skill_name}/SKILL.md
│       │   5. build Agent with Skills(loaders=[LocalSkills(tmpdir)])
│       │   6. store tmpdir on Session for cleanup on session end
│       └── if no instance_id:
│           build Agent with current hardcoded default instructions (existing behaviour)
│
└── chat proceeds normally — message/stream/approve flow unchanged
    session cleanup (_remove_session) deletes tmpdir
```

**Out of scope:** MCP server wiring (`mcp_positions`) — requires a separate Agno MCP integration design.

## Backend Changes

### `admin_repository.py`

Add three methods:

- `get_all_agent_instances() -> list[dict]` — SELECT all rows from `admin_agent_instances` ordered by `(agent_name, instance_name)`.
- `get_agent_instance(instance_id: str) -> dict | None` — SELECT single row by UUID.
- `get_skill_content(skill_id: str) -> tuple[str, str] | None` — returns `(filename, content)` from `admin_skills`.

### `admin_router.py`

Make `agent_name` optional on `GET /agent-instances`:

```python
async def get_agent_instances(agent_name: str | None = None):
    if agent_name:
        return _get_repo().get_agent_instances(agent_name)
    return _get_repo().get_all_agent_instances()
```

### `models.py`

Add a session create request model:

```python
class CreateSessionRequest(BaseModel):
    instance_id: str | None = None
```

### `main.py`

Accept the new body on `POST /sessions`:

```python
@app.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest = Body(default_factory=CreateSessionRequest)):
    session = service.create_session(request.instance_id)
    ...
```

### `agent_service.py`

- `AgentService.__init__` accepts `admin_repository: AdminRepository`.
- `create_session(instance_id: str | None = None) -> Session` resolves the instance, writes skills to tmpdir, builds the agent with `Skills(loaders=[LocalSkills(tmpdir)])` when an instance is provided; otherwise builds with the existing hardcoded instructions.
- `Session` gains a `tmpdir: str | None` field.
- `_remove_session()` deletes the tmpdir via `shutil.rmtree(session.tmpdir, ignore_errors=True)` when present.
- If a skill ID is missing from DB, that skill is silently skipped. If no skills load, falls back to default instructions.

### `session.py`

Add `tmpdir: str | None = None` field to `Session`.

## Frontend Changes

### `services/admin.service.ts`

Add:

```typescript
getAllAgentInstances() {
  return firstValueFrom(this.http.get<AgentInstance[]>(`${API}/agent-instances`));
}
```

### `services/chat.service.ts`

Update `createSession()` to accept optional `instanceId`:

```typescript
async createSession(instanceId?: string | null): Promise<void> {
  const body = instanceId ? { instance_id: instanceId } : {};
  const res = await firstValueFrom(
    this.http.post<{ session_id: string }>(`${API_URL}/sessions`, body)
  );
  this.sessionId = res.session_id;
}
```

### `services/websocket-chat.service.ts`

Same change as `chat.service.ts` — `createSession()` accepts and forwards optional `instanceId`.

### `components/chat/chat.ts`

- `instances: AgentInstance[] = []` and `selectedInstanceId: string | null = null`.
- `ngOnInit`: fetch all instances via `adminService.getAllAgentInstances()`; default-select `instances[0]?.id ?? null`.
- `onInstanceChange()`: calls `newSession()` (already resets messages and stream).
- `initConnection()`: passes `this.selectedInstanceId` to `activeService.createSession()`.

### `components/chat/chat.html`

Add above the message list:

```html
<div class="instance-bar" *ngIf="instances.length > 0">
  <label>Agent instance</label>
  <select [(ngModel)]="selectedInstanceId" (ngModelChange)="onInstanceChange()">
    <option [ngValue]="null">— none —</option>
    <option *ngFor="let i of instances" [ngValue]="i.id">
      {{ i.agent_name }} / {{ i.instance_name }}
    </option>
  </select>
</div>
```

Minimal CSS in `chat.css` for the `.instance-bar` row.

## Error Handling

| Scenario | Behaviour |
|---|---|
| No instances in DB | Dropdown hidden; `instance_id` is `null`; default agent used |
| Invalid `instance_id` | Backend returns `400`; frontend shows error banner |
| Skill fetch fails for one skill | That skill silently skipped; agent built with remaining skills |
| All skill fetches fail / empty persona | Falls back to default hardcoded instructions |
| Tmpdir write fails | `create_session` raises → `500`; frontend shows error banner |
| Instance switch mid-chat | `onInstanceChange()` → `newSession()` → clears messages, new session |

## Testing

### Backend (`pytest`)

- `test_admin.py`: `GET /admin/agent-instances` without `agent_name` returns all; with `agent_name` filters correctly.
- `test_agent.py`: `create_session(instance_id=None)` builds default agent; `create_session(instance_id=<valid>)` with mocked DB writes correct tmpdir structure and builds agent with `Skills`.
- `test_main.py`: `POST /sessions` with and without `instance_id` body; invalid UUID returns `400`.

### Frontend

- `chat.spec.ts`: instances fetched on init; dropdown change triggers `newSession()` with correct instance ID; `null` selection passes no instance ID.

## Files Changed

| File | Change |
|---|---|
| `tool-call-agent/admin_repository.py` | Add `get_all_agent_instances`, `get_agent_instance`, `get_skill_content` |
| `tool-call-agent/admin_router.py` | Make `agent_name` optional on `GET /agent-instances` |
| `tool-call-agent/models.py` | Add `CreateSessionRequest` |
| `tool-call-agent/session.py` | Add `tmpdir` field to `Session` |
| `tool-call-agent/agent_service.py` | Wire instance → persona → skills → `LocalSkills`; cleanup tmpdir |
| `tool-call-agent/main.py` | Accept `CreateSessionRequest` body on `POST /sessions` |
| `tool-call-ui/src/app/services/admin.service.ts` | Add `getAllAgentInstances()` |
| `tool-call-ui/src/app/services/chat.service.ts` | Accept `instanceId` in `createSession()` |
| `tool-call-ui/src/app/services/websocket-chat.service.ts` | Accept `instanceId` in `createSession()` |
| `tool-call-ui/src/app/components/chat/chat.ts` | Instance picker state; wire to session creation |
| `tool-call-ui/src/app/components/chat/chat.html` | Add instance `<select>` |
| `tool-call-ui/src/app/components/chat/chat.css` | `.instance-bar` styles |
