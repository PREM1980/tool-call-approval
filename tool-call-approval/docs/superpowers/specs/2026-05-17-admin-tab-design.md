# Admin Tab — Design Spec
**Date:** 2026-05-17
**Status:** Approved for implementation

---

## Overview

Add a two-tab shell (AI-Engg / Admin) to the existing tool-call-approval app. The current chat interface moves under the AI-Engg tab. The Admin tab provides a left-nav + content panel for managing credentials, MCP servers, skills, and personas — all backed by the existing Postgres instance.

---

## Frontend Architecture

### Routing

Angular Router is added to the app. Routes:

```
/                       → redirect to /ai-engg
/ai-engg                → Chat component (existing, unchanged)
/admin                  → redirect to /admin/agent-ws
/admin/agent-ws         → AgentWs placeholder
/admin/persona          → Persona management
/admin/skills           → Skills file upload
/admin/mcp-servers      → MCP server configuration
/admin/credentials      → Credentials form
```

### Component Tree

```
AppShell                         ← new root component; renders top tab bar + <router-outlet>
├── Chat                         ← existing, mounted at /ai-engg
└── AdminLayout                  ← new; renders left sidebar nav + nested <router-outlet>
    ├── AgentWs                  ← placeholder ("Coming soon")
    ├── Persona                  ← persona list + create form + skill assignment
    ├── Skills                   ← file upload + uploaded skills list
    ├── McpServers               ← 5 named server slots (name + JSON config)
    └── Credentials              ← kubeconfig textarea + AWS key/secret fields
```

### New Files (frontend)

| File | Purpose |
|---|---|
| `app/app-shell/app-shell.ts` | Top tab bar, router outlet |
| `app/app-shell/app-shell.html` | Tab bar markup |
| `app/admin/admin-layout/admin-layout.ts` | Left sidebar nav + nested router outlet |
| `app/admin/admin-layout/admin-layout.html` | Sidebar markup |
| `app/admin/agent-ws/agent-ws.ts` | Placeholder component |
| `app/admin/credentials/credentials.ts` | Credentials form component |
| `app/admin/credentials/credentials.html` | Form markup |
| `app/admin/mcp-servers/mcp-servers.ts` | MCP server slots component |
| `app/admin/mcp-servers/mcp-servers.html` | 5-slot form markup |
| `app/admin/skills/skills.ts` | Skills upload component |
| `app/admin/skills/skills.html` | Upload + list markup |
| `app/admin/persona/persona.ts` | Persona management component |
| `app/admin/persona/persona.html` | Persona list + form markup |
| `app/services/admin.service.ts` | HTTP client for all /admin/* endpoints |
| `app/app.routes.ts` | Route definitions |

### Key UI Behaviours

**AppShell:** Two tabs in a top bar — "AI-Engg" and "Admin". Active tab is highlighted. Clicking a tab navigates to the corresponding base route.

**AdminLayout:** Persistent left sidebar with five nav items. Clicking an item navigates to its route. Active item is highlighted. Right side renders the active admin component.

**Credentials:** Single form with fields: AWS Access Key ID (text), AWS Secret Access Key (password), AWS Region (text, default `us-east-1`), Kubeconfig (textarea for paste or file upload button). One Save button — POSTs to backend. On load, GETs existing values (secret key shown masked).

**MCP Servers:** Five numbered slots. Each slot has: Name (text input), Config (JSON textarea). Empty slots are visually distinct from filled ones. Each slot has its own Save button. JSON textarea validates on save — rejects invalid JSON with an inline error message.

**Skills:** File upload input (accepts any file type). On upload, file content is sent to backend. Below the upload area, a list of previously uploaded skills with filename and upload date. Each entry has a Delete button.

**Persona:** Left side shows list of existing personas (name + skill count). "New Persona" button opens a form on the right: name field + multi-select list of uploaded skills (checkboxes). Save creates the persona. Clicking an existing persona opens it for editing. Delete button on each persona.

**Agent-WS:** Static placeholder — just a heading and "Coming soon" message.

---

## Backend Architecture

### New Files (backend)

| File | Purpose |
|---|---|
| `admin_repository.py` | `AdminRepository` class — table creation + CRUD |
| `admin_models.py` | Pydantic request/response models for admin endpoints |
| `admin_router.py` | `APIRouter` with all `/admin/*` routes |

`admin_router.py` is mounted into `main.py` via `app.include_router(admin_router, prefix="/admin")`.

### Database Tables

All tables are created in the `public` schema using `psycopg2` directly (same `POSTGRES_URL` from `.env`). `AdminRepository.__init__` runs `CREATE TABLE IF NOT EXISTS` for all four tables.

#### `admin_credentials`
Single-row singleton, always upserted with `id = 1`.

```sql
CREATE TABLE IF NOT EXISTS admin_credentials (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    aws_access_key_id       TEXT,
    aws_secret_access_key   TEXT,
    aws_region              TEXT NOT NULL DEFAULT 'us-east-1',
    kubeconfig              TEXT,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT single_row CHECK (id = 1)
);
```

#### `admin_mcp_servers`
Up to 5 rows. `position` (1–5) is unique — upsert on conflict.

```sql
CREATE TABLE IF NOT EXISTS admin_mcp_servers (
    position    INTEGER PRIMARY KEY CHECK (position BETWEEN 1 AND 5),
    name        TEXT NOT NULL,
    config      JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### `admin_skills`
One row per uploaded file.

```sql
CREATE TABLE IF NOT EXISTS admin_skills (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename    TEXT NOT NULL,
    content     TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### `admin_personas`
One row per persona. `skill_ids` is a JSON array of skill UUIDs.

```sql
CREATE TABLE IF NOT EXISTS admin_personas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    skill_ids   JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### API Endpoints

#### Credentials
| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/credentials` | Returns current credentials (secret key masked as `"***"`) |
| `POST` | `/admin/credentials` | Upserts all credential fields |

#### MCP Servers
| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/mcp-servers` | Returns all saved server slots (positions 1–5) |
| `POST` | `/admin/mcp-servers/{position}` | Upserts a single slot (1–5); validates JSON config |
| `DELETE` | `/admin/mcp-servers/{position}` | Removes a slot |

#### Skills
| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/skills` | Lists all uploaded skills (id, filename, uploaded_at) |
| `POST` | `/admin/skills` | Accepts `multipart/form-data` file upload; stores content |
| `DELETE` | `/admin/skills/{id}` | Deletes a skill by UUID |

#### Personas
| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/personas` | Lists all personas |
| `POST` | `/admin/personas` | Creates a new persona |
| `PUT` | `/admin/personas/{id}` | Updates name and/or skill_ids |
| `DELETE` | `/admin/personas/{id}` | Deletes a persona |

---

## Error Handling

- Invalid JSON in MCP server config → `422 Unprocessable Entity` with message
- MCP server position out of range (not 1–5) → `422`
- Persona name conflict → `409 Conflict`
- Skill or persona not found on DELETE/PUT → `404`
- Postgres unreachable on admin request → `503 Service Unavailable`

---

## Out of Scope

- Credential encryption at rest (plain text for now, noted as future work)
- Agent-WS and Persona pages beyond what is described above
- Skill file type validation (any file accepted)
- MCP server connectivity testing (just stores config, no ping)
