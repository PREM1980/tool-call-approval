# Sessions Page Design

**Date:** 2026-05-22
**Status:** Approved

---

## Goal

Add a Sessions tab to the AI-Engineer page so users can browse all past sessions and inspect their full chat history without leaving the page.

---

## Architecture

### Approach

Wrap the existing AI-Engineer view in a new `AiEngg` shell component that owns a tab switcher. The existing `Chat` component is unchanged — it becomes the "Chat" tab. A new `Sessions` component becomes the "Sessions" tab. This mirrors exactly how `Agents` wraps `DeployForm`, `AgentList`, and `AgentConfigure`.

### File Map

| File | Change |
|---|---|
| `tool-call-agent/main.py` | Add `GET /sessions` list endpoint |
| `tool-call-agent/repository.py` | Add `list_sessions()` method to `PostgresRepository` |
| `tool-call-ui/src/app/app.routes.ts` | Point `/ai-engg` at `AiEngg` instead of `Chat` |
| `tool-call-ui/src/app/ai-engg/ai-engg.ts` | New shell component with tab switcher |
| `tool-call-ui/src/app/ai-engg/ai-engg.html` | Tab bar + conditional render of Chat or Sessions |
| `tool-call-ui/src/app/ai-engg/ai-engg.css` | Tab bar styles matching existing admin pattern |
| `tool-call-ui/src/app/ai-engg/sessions/sessions.ts` | New sessions list + inline detail component |
| `tool-call-ui/src/app/ai-engg/sessions/sessions.html` | Sessions table + expandable chat history panel |
| `tool-call-ui/src/app/ai-engg/sessions/sessions.css` | Table and chat bubble styles |
| `tool-call-ui/src/app/services/sessions.service.ts` | New service: `getAll()`, `getHistory()` |

---

## Backend

### New endpoint: `GET /sessions`

Returns a lightweight list of all sessions — no message content, just enough for the table.

**Response schema:**
```json
[
  {
    "session_id": "uuid",
    "created_at": 1779219493,
    "updated_at": 1779219515,
    "turn_count": 2
  }
]
```

**Implementation:** Query `ai.agno_sessions` directly via `psycopg2`, ordering by `updated_at DESC`. The `turn_count` is `jsonb_array_length(runs)`.

### Existing endpoint: `GET /sessions/{id}/history`

Already implemented. Returns `[{ "role": "user"|"assistant", "content": "..." }]`. No changes needed.

---

## Frontend

### AiEngg shell (`ai-engg/`)

- Standalone Angular component, loaded lazily at `/ai-engg`
- Owns `tab: 'chat' | 'sessions'` state
- Renders `<app-chat />` or `<app-sessions />` based on active tab
- Tab bar uses the same CSS class pattern as the admin `Agents` component (`.tabs`, `.tab`, `.tab.active`)

### Sessions component (`ai-engg/sessions/`)

**List view:** A table with three columns:
- **Session ID** — first 8 chars of UUID, monospace, clickable
- **Last active** — `updated_at` epoch converted to a human-readable local datetime
- **Turns** — integer turn count

Clicking a row selects it. The selected row highlights and an inline detail panel expands below the table (no navigation, no modal).

**Detail panel:** Renders the full chat history for the selected session as role-labelled message bubbles — `user` messages right-aligned, `assistant` messages left-aligned. Same visual language as the existing Chat component. Shows a loading state while fetching.

Clicking the same row again collapses the panel.

### SessionsService (`services/sessions.service.ts`)

```typescript
interface SessionSummary {
  session_id: string;
  created_at: number;   // Unix epoch (seconds)
  updated_at: number;
  turn_count: number;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

class SessionsService {
  getAll(): Promise<SessionSummary[]>           // GET /sessions
  getHistory(id: string): Promise<ChatMessage[]> // GET /sessions/{id}/history
}
```

Timestamp conversion (epoch seconds → JS Date) happens in the component template via a pipe or inline `Date` constructor.

---

## Data Flow

```
Sessions component
  → ngOnInit → SessionsService.getAll() → GET /sessions
  → renders table

User clicks row
  → SessionsService.getHistory(session_id) → GET /sessions/{id}/history
  → renders inline detail panel
  → clicking same row again collapses panel
```

---

## Error Handling

- List load failure: show inline error message in place of table
- History load failure: show error inside the detail panel
- Empty sessions list: show "No sessions yet" placeholder

---

## Testing

- Backend: pytest test for `GET /sessions` — returns correct shape, `turn_count` matches actual runs length
- Frontend: TypeScript compile (`npx tsc --noEmit`) passes with no errors
