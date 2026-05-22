# Bootstrap Light Theme — Design Spec

## Overview

Add Bootstrap 5 to the Angular 20 app and restyle it with a warm, approachable light theme across all pages: top nav, AI-Engineer (Chat + Sessions), and all Admin pages.

**Approach:** Bootstrap 5 npm package wired into `angular.json`, with a `_theme.scss` SCSS override file. All 15 existing component CSS files are replaced with Bootstrap utility classes. A single theme file controls every color and radius in the app.

---

## Color Palette & Typography

### Bootstrap SCSS variable overrides (`src/styles/_theme.scss`)

| Variable | Value | Role |
| --- | --- | --- |
| `$primary` | `#6366f1` | Indigo — buttons, links, active states |
| `$body-bg` | `#f9fafb` | Warm off-white page background |
| `$body-color` | `#111827` | Near-black body text |
| `$secondary` | `#6b7280` | Muted labels, timestamps |
| `$light` | `#f3f4f6` | Sidebar and nav backgrounds |
| `$border-color` | `#e5e7eb` | Card and input borders |
| `$success` | `#10b981` | Success states |
| `$danger` | `#ef4444` | Error states |
| `$border-radius` | `0.5rem` | Default corner radius |
| `$border-radius-lg` | `0.75rem` | Large corner radius |
| `$font-family-base` | `'Inter', system-ui, sans-serif` | Body typeface |

Inter is loaded from Google Fonts in `index.html`.

Bootstrap is imported after variable overrides in `src/styles.scss`:

```scss
@import 'theme';
@import 'bootstrap/scss/bootstrap';
```

---

## Navigation

### Top Navbar (`app-shell`)

- `navbar navbar-light bg-white border-bottom sticky-top`
- Brand: "Tool Call Approval" in indigo (`text-primary`), left-aligned
- Nav links: Bootstrap `nav nav-underline` with indigo active underline
- Links: "AI Engineer" → `/ai-engg`, "Admin" → `/admin`
- Compact padding (`py-2`)

### Admin Sidebar (`admin-layout`)

- Left column: `bg-light`, 220px wide, full-height, `border-end`
- Section headings: `text-uppercase text-secondary` small labels (e.g., CONFIGURATION, AGENTS)
- Links: plain anchor, `text-dark` default, `text-primary fw-semibold` when active, no background pill
- Right content: white background, `p-4`

Layout:

```text
┌─────────────────────────────────────────┐
│  navbar (white, sticky-top)             │
├─────────────────────────────────────────┤
│  sidebar (220px) │  content (flex-1)    │
└─────────────────────────────────────────┘
```

---

## AI-Engineer Page

### Tab bar

- `nav nav-tabs` with indigo active underline
- Tabs: "Chat", "Sessions"
- Content below in a white `card shadow-sm rounded-3`

### Chat Tab

- **Instance picker:** `form-select form-select-sm` at top of card body, full width
- **Message thread:** scrollable `div`, max-height `65vh`, `overflow-y: auto`
  - User messages: indigo pill (`bg-primary text-white rounded-pill px-3 py-2`), right-aligned (`d-flex justify-content-end`)
  - Assistant messages: white `card border rounded-3 p-3`, left-aligned
  - Tool call events: `badge bg-light text-secondary border` inline label
- **Input row:** `input-group` pinned to card footer — `form-control rounded-start` + `btn btn-primary` Send button

### Sessions Tab

- Bootstrap `table table-hover align-middle` — columns: Session ID (truncated monospace), Created, Last Updated, Turns
- Clicking a row opens an inline `accordion-collapse` showing full chat history as a mini thread (same user/assistant bubble styles as Chat tab)
- Empty state: `text-center text-secondary py-5` — "No sessions yet"
- Loading state: `spinner-border text-primary` centered

---

## Admin Pages

### Shared patterns

- List items: Bootstrap `card shadow-sm mb-3` per item, or `table table-hover` for tabular data
- "Add" action: `btn btn-primary btn-sm` in card header top-right
- Destructive action: `btn btn-outline-danger btn-sm`
- Secondary action: `btn btn-outline-secondary btn-sm`

### Credentials, MCP Servers, Skills, Persona

- Each uses a `card shadow-sm` list layout
- Form fields: `form-label` + `form-control` / `form-select`
- Submit: `btn btn-primary`, Cancel: `btn btn-outline-secondary`
- Validation errors: Bootstrap `is-invalid` + `invalid-feedback`

### Agents

- Responsive grid: `row row-cols-1 row-cols-md-2 g-3`
- Each agent: `card h-100 shadow-sm` with `card-title`, `card-text`, actions in `card-footer`

### Agent Instances (agent-ws / agent-list)

- Same card grid pattern as Agents
- Status indicators: `badge bg-success` / `badge bg-danger` / `badge bg-secondary`

---

## Implementation Notes

### Files to install/create

- `npm install bootstrap@5` — adds Bootstrap to `node_modules`
- `src/styles/_theme.scss` — new file with all SCSS variable overrides
- `src/styles.scss` — updated to `@import 'theme'; @import 'bootstrap/scss/bootstrap';`
- `angular.json` — no styles array change needed (handled via `styles.scss`); add `"stylePreprocessorOptions": { "includePaths": ["node_modules"] }` if needed

### Files to update (templates + CSS)

All existing component `.css` files are replaced with Bootstrap utility classes in templates. The `.css` files themselves become empty (or deleted). Full list:

- `src/app/app.css`
- `app-shell/app-shell.html` + `app-shell.css`
- `ai-engg/ai-engg.html` + `ai-engg.css`
- `ai-engg/sessions/sessions.html` + `sessions.css`
- `components/chat/chat.html` + `chat.css`
- `components/tool-approval/tool-approval.html` + `tool-approval.css`
- `admin/admin-layout/admin-layout.html` + `admin-layout.css`
- `admin/credentials/credentials.html` + `credentials.css`
- `admin/mcp-servers/mcp-servers.html` + `mcp-servers.css`
- `admin/skills/skills.html` + `skills.css`
- `admin/persona/persona.html` + `persona.css`
- `admin/agents/agents.html` + `agents.css`
- `admin/agents/agent-list/agent-list.html` + `agent-list.css`
- `admin/agents/deploy-form/deploy-form.html` + `deploy-form.css`
- `admin/agent-ws/agent-configure/agent-configure.html` + `agent-configure.css`

### No routing or logic changes

This is a pure presentation change. No TypeScript component logic, services, or routes are modified.
