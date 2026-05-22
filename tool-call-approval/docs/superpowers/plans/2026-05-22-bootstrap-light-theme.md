# Bootstrap 5 Light Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Bootstrap 5 and restyle the entire Angular app with a warm, approachable light theme using indigo as the primary accent.

**Architecture:** Install Bootstrap 5 via npm, wire it into the Angular build via SCSS, override Bootstrap variables in a single `_theme.scss` file. Replace all component CSS with Bootstrap utility classes; keep only irreplaceable layout CSS (flex heights, scroll) in component files.

**Tech Stack:** Angular 20, Bootstrap 5.3, SCSS (via Angular's built-in esbuild sass support), Google Fonts Inter.

---

## File Map

| File | Change |
| --- | --- |
| `tool-call-ui/src/styles.css` → `styles.scss` | Renamed; imports theme + Bootstrap |
| `tool-call-ui/src/styles/_theme.scss` | New file — Bootstrap variable overrides |
| `tool-call-ui/angular.json` | Update styles path; add stylePreprocessorOptions |
| `tool-call-ui/src/index.html` | Add Inter Google Font link |
| `tool-call-ui/src/app/app.css` | Cleared |
| `app-shell/app-shell.html` + `.css` | Bootstrap navbar |
| `ai-engg/ai-engg.html` + `.css` | Bootstrap nav-tabs |
| `ai-engg/sessions/sessions.html` + `.css` | Bootstrap table + inline history |
| `components/chat/chat.html` + `.css` | Bootstrap layout; keep scroll CSS |
| `components/tool-approval/tool-approval.html` + `.css` | Bootstrap card |
| `admin/admin-layout/admin-layout.html` + `.css` | Bootstrap sidebar; keep host CSS |
| `admin/credentials/credentials.html` + `.css` | Bootstrap form |
| `admin/mcp-servers/mcp-servers.html` + `.css` | Bootstrap cards |
| `admin/skills/skills.html` + `.css` | Bootstrap table |
| `admin/persona/persona.html` + `.css` | Bootstrap form + list; keep host CSS |
| `admin/agents/agents.html` + `.css` | Bootstrap nav-tabs |
| `admin/agents/agent-list/agent-list.html` + `.css` | Bootstrap table |
| `admin/agents/deploy-form/deploy-form.html` + `.css` | Bootstrap form |
| `admin/agent-ws/agent-configure/agent-configure.html` + `.css` | Bootstrap accordion-style cards |

---

## Task 1: Bootstrap + SCSS Infrastructure

**Files:**
- Create: `tool-call-ui/src/styles/_theme.scss`
- Create: `tool-call-ui/src/styles.scss` (replaces `styles.css`)
- Delete: `tool-call-ui/src/styles.css`
- Modify: `tool-call-ui/angular.json`
- Modify: `tool-call-ui/src/index.html`

- [ ] **Step 1: Install Bootstrap**

```bash
cd tool-call-ui && npm install bootstrap@5
```

Expected: `bootstrap` appears in `package.json` dependencies.

- [ ] **Step 2: Create the theme variables file**

Create `tool-call-ui/src/styles/_theme.scss`:

```scss
$primary: #6366f1;
$secondary: #6b7280;
$success: #10b981;
$danger: #ef4444;
$warning: #f59e0b;
$light: #f3f4f6;
$body-bg: #f9fafb;
$body-color: #111827;
$border-color: #e5e7eb;
$border-radius: 0.5rem;
$border-radius-lg: 0.75rem;
$border-radius-sm: 0.375rem;
$font-family-base: 'Inter', system-ui, -apple-system, sans-serif;
$input-bg: #ffffff;
$card-bg: #ffffff;
$card-border-color: #e5e7eb;
$navbar-light-brand-color: #6366f1;
$navbar-light-active-color: #6366f1;
$navbar-light-color: #6b7280;
$navbar-light-hover-color: #111827;
$link-color: #6366f1;
$link-hover-color: #4f46e5;
$nav-link-color: #6b7280;
$nav-link-hover-color: #111827;
$nav-tabs-link-active-color: #6366f1;
```

- [ ] **Step 3: Create styles.scss**

Create `tool-call-ui/src/styles.scss`:

```scss
@import 'theme';
@import 'bootstrap/scss/bootstrap';

html,
body {
  height: 100%;
}
```

- [ ] **Step 4: Delete styles.css**

```bash
rm tool-call-ui/src/styles.css
```

- [ ] **Step 5: Update angular.json**

Open `tool-call-ui/angular.json`. Find every occurrence of `"src/styles.css"` and replace with `"src/styles.scss"`. Also add `"stylePreprocessorOptions"` under `projects.tool-call-ui.architect.build.options`:

```json
"stylePreprocessorOptions": {
  "includePaths": ["node_modules"]
},
```

The build options block should look like:

```json
"options": {
  "outputPath": "dist/tool-call-ui",
  "index": "src/index.html",
  "browser": "src/main.ts",
  "polyfills": ["zone.js"],
  "tsConfig": "tsconfig.app.json",
  "assets": [
    { "glob": "**/*", "input": "public" }
  ],
  "styles": ["src/styles.scss"],
  "scripts": [],
  "stylePreprocessorOptions": {
    "includePaths": ["node_modules"]
  }
}
```

- [ ] **Step 6: Add Inter font to index.html**

In `tool-call-ui/src/index.html`, add inside `<head>` before the closing tag:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

- [ ] **Step 7: Verify build**

```bash
cd tool-call-ui && npx ng build --configuration development 2>&1 | tail -20
```

Expected: Build succeeds with no errors. If you see `Can't find stylesheet to import`, the `stylePreprocessorOptions.includePaths` is missing — recheck Step 5.

- [ ] **Step 8: Commit**

```bash
cd tool-call-ui && git add src/styles.scss src/styles/_theme.scss src/index.html angular.json package.json package-lock.json && git commit -m "feat(ui): add Bootstrap 5 with indigo light theme SCSS setup"
```

---

## Task 2: App Shell + Global CSS

**Files:**
- Modify: `tool-call-ui/src/app/app-shell/app-shell.html`
- Modify: `tool-call-ui/src/app/app-shell/app-shell.css`
- Modify: `tool-call-ui/src/app/app.css`

- [ ] **Step 1: Clear app.css**

Replace `tool-call-ui/src/app/app.css` with empty content:

```css
```

- [ ] **Step 2: Update app-shell.html**

Replace `tool-call-ui/src/app/app-shell/app-shell.html` with:

```html
<div class="d-flex flex-column vh-100">
  <nav class="navbar navbar-expand navbar-light bg-white border-bottom py-2 flex-shrink-0">
    <div class="container-fluid">
      <span class="navbar-brand fw-bold text-primary fs-6">Tool Call Approval</span>
      <div class="navbar-nav">
        <a class="nav-link" routerLink="/ai-engg" routerLinkActive="active">AI Engineer</a>
        <a class="nav-link" routerLink="/admin" routerLinkActive="active">Admin</a>
      </div>
    </div>
  </nav>
  <div class="flex-grow-1 overflow-hidden d-flex flex-column">
    <router-outlet />
  </div>
</div>
```

- [ ] **Step 3: Replace app-shell.css**

Replace `tool-call-ui/src/app/app-shell/app-shell.css` with:

```css
.nav-link.active {
  color: #6366f1 !important;
  font-weight: 600;
}
```

- [ ] **Step 4: Verify build**

```bash
cd tool-call-ui && npx ng build --configuration development 2>&1 | tail -10
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
cd tool-call-ui && git add src/app/app.css src/app/app-shell/app-shell.html src/app/app-shell/app-shell.css && git commit -m "feat(ui): restyle app shell with Bootstrap navbar"
```

---

## Task 3: AI-Engineer Tabs

**Files:**
- Modify: `tool-call-ui/src/app/ai-engg/ai-engg.html`
- Modify: `tool-call-ui/src/app/ai-engg/ai-engg.css`

- [ ] **Step 1: Update ai-engg.html**

Replace `tool-call-ui/src/app/ai-engg/ai-engg.html` with:

```html
<div class="d-flex flex-column h-100 px-4 pt-4">
  <ul class="nav nav-tabs flex-shrink-0">
    <li class="nav-item">
      <button type="button" class="nav-link" [class.active]="tab === 'chat'" (click)="tab = 'chat'">Chat</button>
    </li>
    <li class="nav-item">
      <button type="button" class="nav-link" [class.active]="tab === 'sessions'" (click)="tab = 'sessions'">Sessions</button>
    </li>
  </ul>
  <div class="flex-grow-1 border border-top-0 rounded-bottom bg-white overflow-hidden d-flex flex-column">
    @if (tab === 'chat') {
      <app-chat />
    }
    @if (tab === 'sessions') {
      <app-sessions />
    }
  </div>
</div>
```

- [ ] **Step 2: Replace ai-engg.css**

Replace `tool-call-ui/src/app/ai-engg/ai-engg.css` with:

```css
:host {
  display: flex;
  flex-direction: column;
  height: 100%;
}
```

- [ ] **Step 3: Verify build**

```bash
cd tool-call-ui && npx ng build --configuration development 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
cd tool-call-ui && git add src/app/ai-engg/ai-engg.html src/app/ai-engg/ai-engg.css && git commit -m "feat(ui): restyle AI-Engineer tabs with Bootstrap nav-tabs"
```

---

## Task 4: Chat Component

**Files:**
- Modify: `tool-call-ui/src/app/components/chat/chat.html`
- Modify: `tool-call-ui/src/app/components/chat/chat.css`

- [ ] **Step 1: Update chat.html**

Replace `tool-call-ui/src/app/components/chat/chat.html` with:

```html
<div class="d-flex flex-column h-100">
  <div class="d-flex align-items-center gap-2 px-4 py-3 bg-white border-bottom flex-shrink-0">
    <span class="fs-4">🤖</span>
    <div class="flex-grow-1">
      <div class="fw-bold text-dark" style="font-size: 0.95rem;">Tool Call Approval</div>
      <div class="text-secondary" style="font-size: 0.72rem;">Claude agent with human-in-the-loop</div>
    </div>
    <button
      type="button"
      class="btn btn-outline-secondary btn-sm"
      [disabled]="isSwitching || isWaiting"
      (click)="newSession()"
    >+ New</button>
    <div class="btn-group btn-group-sm">
      <button type="button" class="btn"
        [class.btn-primary]="mode === 'sse'"
        [class.btn-outline-secondary]="mode !== 'sse'"
        [disabled]="isSwitching"
        (click)="switchMode('sse')">SSE</button>
      <button type="button" class="btn"
        [class.btn-primary]="mode === 'websocket'"
        [class.btn-outline-secondary]="mode !== 'websocket'"
        [disabled]="isSwitching"
        (click)="switchMode('websocket')">WebSocket</button>
    </div>
  </div>

  @if (instances.length > 0) {
    <div class="d-flex align-items-center gap-2 px-4 py-2 bg-light border-bottom flex-shrink-0">
      <label class="text-secondary fw-medium" style="font-size: 0.8rem; white-space: nowrap;">Agent instance</label>
      <select
        class="form-select form-select-sm"
        [(ngModel)]="selectedInstanceId"
        (ngModelChange)="onInstanceChange()"
        name="instanceSelect"
        title="Agent instance"
      >
        <option [ngValue]="null">— none —</option>
        @for (inst of instances; track inst.id) {
          <option [ngValue]="inst.id">{{ inst.agent_name }} / {{ inst.instance_name }}</option>
        }
      </select>
    </div>
  }

  <div class="message-list p-4 d-flex flex-column gap-2" #messageList>
    @if (messages.length === 0) {
      <div class="text-center text-secondary my-auto">
        <p class="mb-2" style="font-size: 0.9rem;">Try asking:</p>
        <div class="d-flex flex-column gap-1 align-items-center">
          <span class="badge bg-light text-secondary border px-3 py-2 fw-normal">"What is 1234 × 5678?"</span>
          <span class="badge bg-light text-secondary border px-3 py-2 fw-normal">"What's the weather in London?"</span>
          <span class="badge bg-light text-secondary border px-3 py-2 fw-normal">"Search for information about black holes"</span>
        </div>
      </div>
    }

    @for (message of messages; track message.id) {
      <div class="d-flex flex-column"
        [class.align-items-end]="message.role === 'user'"
        [class.align-items-start]="message.role !== 'user' && message.role !== 'system'"
        [class.align-items-center]="message.role === 'system'">
        <div style="max-width: 68%;">
          <div class="px-3 py-2 rounded-3"
            style="font-size: 0.88rem; line-height: 1.5; white-space: pre-wrap; word-break: break-word;"
            [class.bg-primary]="message.role === 'user'"
            [class.text-white]="message.role === 'user'"
            [class.bg-white]="message.role === 'assistant'"
            [class.border]="message.role === 'assistant'"
            [class.bg-light]="message.role === 'system'"
            [class.text-secondary]="message.role === 'system'"
            [class.fst-italic]="message.role === 'system'"
          >{{ message.content }}</div>
          <div class="text-secondary mt-1" style="font-size: 0.65rem;">{{ message.timestamp | date: 'HH:mm' }}</div>
        </div>
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
      <div class="d-flex gap-1 align-self-start ps-1">
        <span class="thinking-dot"></span>
        <span class="thinking-dot"></span>
        <span class="thinking-dot"></span>
      </div>
    }
  </div>

  <form class="d-flex gap-2 p-3 bg-white border-top flex-shrink-0" (ngSubmit)="sendMessage()">
    <input
      class="form-control"
      type="text"
      [(ngModel)]="userInput"
      name="userInput"
      placeholder="Ask the agent something..."
      [disabled]="isWaiting || !!pendingToolCall"
      autocomplete="off"
    />
    <button
      class="btn btn-primary"
      type="submit"
      [disabled]="isWaiting || !!pendingToolCall || !userInput.trim()"
    >Send</button>
  </form>
</div>
```

- [ ] **Step 2: Replace chat.css**

Replace `tool-call-ui/src/app/components/chat/chat.css` with:

```css
:host {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.message-list {
  flex: 1;
  overflow-y: auto;
}

.thinking-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6b7280;
  animation: pulse 1.2s infinite;
}

.thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes pulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}
```

- [ ] **Step 3: Verify build**

```bash
cd tool-call-ui && npx ng build --configuration development 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
cd tool-call-ui && git add src/app/components/chat/chat.html src/app/components/chat/chat.css && git commit -m "feat(ui): restyle chat component with Bootstrap light theme"
```

---

## Task 5: Sessions Tab

**Files:**
- Modify: `tool-call-ui/src/app/ai-engg/sessions/sessions.html`
- Modify: `tool-call-ui/src/app/ai-engg/sessions/sessions.css`

- [ ] **Step 1: Update sessions.html**

Replace `tool-call-ui/src/app/ai-engg/sessions/sessions.html` with:

```html
@if (error) {
  <div class="alert alert-danger py-2 px-3 m-3" style="font-size: 0.85rem;">{{ error }}</div>
}

@if (loadingSessions) {
  <div class="d-flex justify-content-center py-5">
    <div class="spinner-border text-primary" role="status">
      <span class="visually-hidden">Loading…</span>
    </div>
  </div>
}

@if (!loadingSessions && sessions.length === 0 && !error) {
  <div class="text-center text-secondary py-5" style="font-size: 0.875rem;">No sessions yet.</div>
}

@if (sessions.length > 0) {
  <div class="p-3">
    <table class="table table-hover align-middle" style="font-size: 0.875rem;">
      <thead class="table-light">
        <tr>
          <th class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.06em;">Session ID</th>
          <th class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.06em;">Last Active</th>
          <th class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.06em;">Turns</th>
        </tr>
      </thead>
      <tbody>
        @for (s of sessions; track s.session_id) {
          <tr style="cursor: pointer;" [class.table-active]="selectedId === s.session_id" (click)="selectSession(s.session_id)">
            <td class="font-monospace text-primary" style="font-size: 0.82rem;">{{ shortId(s.session_id) }}</td>
            <td class="text-secondary">{{ formatTimestamp(s.updated_at ?? s.created_at) }}</td>
            <td>{{ s.turn_count }}</td>
          </tr>
          @if (selectedId === s.session_id) {
            <tr>
              <td colspan="3" class="p-0 bg-light">
                @if (loadingHistory) {
                  <div class="d-flex justify-content-center py-3">
                    <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
                  </div>
                }
                @if (historyError) {
                  <div class="alert alert-danger m-3 py-2 px-3" style="font-size: 0.85rem;">{{ historyError }}</div>
                }
                @if (!loadingHistory && history.length === 0 && !historyError) {
                  <p class="text-secondary text-center py-3 mb-0" style="font-size: 0.85rem;">No messages in this session.</p>
                }
                <div class="d-flex flex-column gap-2 p-3" style="max-height: 400px; overflow-y: auto;">
                  @for (msg of history; track $index) {
                    <div class="d-flex" [class.justify-content-end]="msg.role === 'user'" [class.justify-content-start]="msg.role !== 'user'">
                      <div class="px-3 py-2 rounded-3" style="max-width: 70%; font-size: 0.85rem;"
                        [class.bg-primary]="msg.role === 'user'"
                        [class.text-white]="msg.role === 'user'"
                        [class.bg-white]="msg.role !== 'user'"
                        [class.border]="msg.role !== 'user'">
                        <div class="text-uppercase fw-semibold mb-1" style="font-size: 0.65rem; letter-spacing: 0.06em;"
                          [class.text-white-50]="msg.role === 'user'"
                          [class.text-secondary]="msg.role !== 'user'">{{ msg.role }}</div>
                        <p class="mb-0" style="white-space: pre-wrap; word-break: break-word;">{{ msg.content }}</p>
                      </div>
                    </div>
                  }
                </div>
              </td>
            </tr>
          }
        }
      </tbody>
    </table>
  </div>
}
```

- [ ] **Step 2: Clear sessions.css**

Replace `tool-call-ui/src/app/ai-engg/sessions/sessions.css` with empty content (just a newline).

- [ ] **Step 3: Verify build**

```bash
cd tool-call-ui && npx ng build --configuration development 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
cd tool-call-ui && git add src/app/ai-engg/sessions/sessions.html src/app/ai-engg/sessions/sessions.css && git commit -m "feat(ui): restyle sessions tab with Bootstrap table"
```

---

## Task 6: Tool Approval Component

**Files:**
- Modify: `tool-call-ui/src/app/components/tool-approval/tool-approval.html`
- Modify: `tool-call-ui/src/app/components/tool-approval/tool-approval.css`

- [ ] **Step 1: Update tool-approval.html**

Replace `tool-call-ui/src/app/components/tool-approval/tool-approval.html` with:

```html
<div class="card border-warning shadow-sm rounded-3 my-2" style="max-width: 540px;">
  <div class="card-header bg-white d-flex align-items-center gap-2">
    <span style="font-size: 1.4rem;">⚙️</span>
    <div class="flex-grow-1">
      <div class="text-uppercase text-secondary fw-semibold" style="font-size: 0.7rem; letter-spacing: 0.08em;">Tool Call Request</div>
      <div class="fw-bold font-monospace" style="font-size: 0.95rem;">{{ toolCall.tool_name }}</div>
    </div>
    <span class="badge text-bg-warning">Awaiting Approval</span>
  </div>
  <div class="card-body">
    <div class="text-uppercase text-secondary fw-semibold mb-2" style="font-size: 0.7rem; letter-spacing: 0.08em;">Arguments</div>
    <pre class="bg-light border rounded-2 p-3 mb-0" style="font-size: 0.82rem; overflow-x: auto;"><code class="text-primary">{{ formattedInput }}</code></pre>
  </div>
  <div class="card-footer bg-white d-flex justify-content-end gap-2">
    <button class="btn btn-outline-danger btn-sm" [disabled]="disabled" (click)="reject()">✕ Reject</button>
    <button class="btn btn-outline-success btn-sm" [disabled]="disabled" (click)="approve()">✓ Approve</button>
  </div>
</div>
```

- [ ] **Step 2: Clear tool-approval.css**

Replace `tool-call-ui/src/app/components/tool-approval/tool-approval.css` with empty content.

- [ ] **Step 3: Verify build**

```bash
cd tool-call-ui && npx ng build --configuration development 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
cd tool-call-ui && git add src/app/components/tool-approval/tool-approval.html src/app/components/tool-approval/tool-approval.css && git commit -m "feat(ui): restyle tool-approval card with Bootstrap"
```

---

## Task 7: Admin Layout + Sidebar

**Files:**
- Modify: `tool-call-ui/src/app/admin/admin-layout/admin-layout.html`
- Modify: `tool-call-ui/src/app/admin/admin-layout/admin-layout.css`

- [ ] **Step 1: Update admin-layout.html**

Replace `tool-call-ui/src/app/admin/admin-layout/admin-layout.html` with:

```html
<div class="d-flex h-100">
  <nav class="bg-light border-end p-3 flex-shrink-0 overflow-y-auto" style="width: 220px;">
    <div class="text-uppercase text-secondary fw-semibold mb-2" style="font-size: 0.7rem; letter-spacing: 0.06em;">Configuration</div>
    <ul class="nav flex-column mb-3">
      <li class="nav-item">
        <a class="nav-link px-2 py-1 rounded text-dark sidebar-link" routerLink="/admin/credentials" routerLinkActive="active">Credentials</a>
      </li>
      <li class="nav-item">
        <a class="nav-link px-2 py-1 rounded text-dark sidebar-link" routerLink="/admin/mcp-servers" routerLinkActive="active">MCP Servers</a>
      </li>
      <li class="nav-item">
        <a class="nav-link px-2 py-1 rounded text-dark sidebar-link" routerLink="/admin/skills" routerLinkActive="active">Skills</a>
      </li>
      <li class="nav-item">
        <a class="nav-link px-2 py-1 rounded text-dark sidebar-link" routerLink="/admin/persona" routerLinkActive="active">Persona</a>
      </li>
    </ul>
    <div class="text-uppercase text-secondary fw-semibold mb-2" style="font-size: 0.7rem; letter-spacing: 0.06em;">Agents</div>
    <ul class="nav flex-column">
      <li class="nav-item">
        <a class="nav-link px-2 py-1 rounded text-dark sidebar-link" routerLink="/admin/agents" routerLinkActive="active">Agents</a>
      </li>
      <li class="nav-item">
        <a class="nav-link px-2 py-1 rounded text-dark sidebar-link" routerLink="/admin/agent-ws" routerLinkActive="active">Agent-WS</a>
      </li>
    </ul>
  </nav>
  <div class="flex-grow-1 p-4 overflow-y-auto">
    <router-outlet />
  </div>
</div>
```

- [ ] **Step 2: Replace admin-layout.css**

Replace `tool-call-ui/src/app/admin/admin-layout/admin-layout.css` with:

```css
:host {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.sidebar-link.active {
  color: #6366f1 !important;
  font-weight: 600;
  background-color: #ffffff;
}
```

- [ ] **Step 3: Verify build**

```bash
cd tool-call-ui && npx ng build --configuration development 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
cd tool-call-ui && git add src/app/admin/admin-layout/admin-layout.html src/app/admin/admin-layout/admin-layout.css && git commit -m "feat(ui): restyle admin sidebar with Bootstrap"
```

---

## Task 8: Credentials Page

**Files:**
- Modify: `tool-call-ui/src/app/admin/credentials/credentials.html`
- Modify: `tool-call-ui/src/app/admin/credentials/credentials.css`

- [ ] **Step 1: Update credentials.html**

Replace `tool-call-ui/src/app/admin/credentials/credentials.html` with:

```html
<h2 class="h5 fw-semibold mb-4">Credentials</h2>

<div class="d-flex flex-column gap-3" style="max-width: 600px;">
  <div>
    <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.05em;">AWS Access Key ID</label>
    <input type="text" class="form-control" [(ngModel)]="form.aws_access_key_id" placeholder="AKIA..." />
  </div>

  <div>
    <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.05em;">AWS Secret Access Key</label>
    <input type="password" class="form-control" [(ngModel)]="form.aws_secret_access_key" placeholder="Enter secret key" />
  </div>

  <div>
    <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.05em;">AWS Region</label>
    <input type="text" class="form-control" [(ngModel)]="form.aws_region" placeholder="us-east-1" />
  </div>

  <div>
    <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.05em;">Kubeconfig</label>
    <input type="file" class="form-control form-control-sm mb-2" accept=".yaml,.yml,.txt" (change)="onKubeconfigFile($event)" />
    <textarea
      class="form-control font-monospace"
      style="font-size: 0.85rem;"
      [(ngModel)]="form.kubeconfig"
      placeholder="Paste kubeconfig YAML here or upload a file above"
      rows="10"
    ></textarea>
  </div>

  <div class="d-flex align-items-center gap-3">
    <button class="btn btn-primary" (click)="save()" [disabled]="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
    @if (saved) { <span class="text-success fw-medium" style="font-size: 0.875rem;">Saved!</span> }
    @if (error) { <span class="text-danger" style="font-size: 0.875rem;">{{ error }}</span> }
  </div>
</div>
```

- [ ] **Step 2: Clear credentials.css**

Replace `tool-call-ui/src/app/admin/credentials/credentials.css` with empty content.

- [ ] **Step 3: Verify build**

```bash
cd tool-call-ui && npx ng build --configuration development 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
cd tool-call-ui && git add src/app/admin/credentials/credentials.html src/app/admin/credentials/credentials.css && git commit -m "feat(ui): restyle credentials page with Bootstrap form"
```

---

## Task 9: MCP Servers Page

**Files:**
- Modify: `tool-call-ui/src/app/admin/mcp-servers/mcp-servers.html`
- Modify: `tool-call-ui/src/app/admin/mcp-servers/mcp-servers.css`

- [ ] **Step 1: Update mcp-servers.html**

Replace `tool-call-ui/src/app/admin/mcp-servers/mcp-servers.html` with:

```html
<h2 class="h5 fw-semibold mb-1">MCP Servers</h2>
<p class="text-secondary mb-4" style="font-size: 0.875rem;">Configure up to 5 MCP server connections.</p>

<div class="d-flex flex-column gap-3" style="max-width: 640px;">
  @for (slot of slots; track $index) {
    <div class="card shadow-sm rounded-3">
      <div class="card-body">
        <div class="d-flex align-items-center gap-2 mb-3">
          <span class="badge rounded-pill bg-light text-secondary border d-flex align-items-center justify-content-center" style="width: 28px; height: 28px; font-size: 0.75rem;">{{ $index + 1 }}</span>
          <input
            type="text"
            class="form-control form-control-sm flex-grow-1"
            [(ngModel)]="slot.name"
            placeholder="Server name"
          />
        </div>
        <textarea
          class="form-control font-monospace mb-3"
          style="font-size: 0.82rem;"
          [(ngModel)]="slot.config"
          placeholder='{ "url": "http://localhost:3001" }'
          rows="4"
          [class.is-invalid]="slot.error === 'Invalid JSON'"
        ></textarea>
        <div class="d-flex align-items-center gap-2">
          <button class="btn btn-primary btn-sm" (click)="save($index)" [disabled]="slot.saving">{{ slot.saving ? 'Saving…' : 'Save' }}</button>
          <button class="btn btn-outline-secondary btn-sm" (click)="clear($index)">Clear</button>
          @if (slot.saved) { <span class="text-success fw-medium" style="font-size: 0.82rem;">Saved!</span> }
          @if (slot.error) { <span class="text-danger" style="font-size: 0.82rem;">{{ slot.error }}</span> }
        </div>
      </div>
    </div>
  }
</div>
```

- [ ] **Step 2: Clear mcp-servers.css**

Replace `tool-call-ui/src/app/admin/mcp-servers/mcp-servers.css` with empty content.

- [ ] **Step 3: Verify build and commit**

```bash
cd tool-call-ui && npx ng build --configuration development 2>&1 | tail -10 && git add src/app/admin/mcp-servers/mcp-servers.html src/app/admin/mcp-servers/mcp-servers.css && git commit -m "feat(ui): restyle MCP servers page with Bootstrap cards"
```

---

## Task 10: Skills Page

**Files:**
- Modify: `tool-call-ui/src/app/admin/skills/skills.html`
- Modify: `tool-call-ui/src/app/admin/skills/skills.css`

- [ ] **Step 1: Update skills.html**

Replace `tool-call-ui/src/app/admin/skills/skills.html` with:

```html
<h2 class="h5 fw-semibold mb-4">Skills</h2>

<div class="d-flex align-items-center gap-3 mb-4">
  <label class="d-inline-block">
    <input type="file" (change)="onFile($event)" [disabled]="uploading" hidden />
    <span class="btn btn-outline-primary btn-sm">{{ uploading ? 'Uploading…' : '+ Upload Skill File' }}</span>
  </label>
  @if (error) { <span class="text-danger" style="font-size: 0.875rem;">{{ error }}</span> }
</div>

@if (skills.length === 0) {
  <p class="text-secondary" style="font-size: 0.875rem;">No skills uploaded yet.</p>
} @else {
  <table class="table table-hover" style="font-size: 0.875rem;">
    <thead class="table-light">
      <tr>
        <th class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.05em;">Filename</th>
        <th class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.05em;">Uploaded</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      @for (skill of skills; track skill.id) {
        <tr>
          <td>{{ skill.filename }}</td>
          <td class="text-secondary">{{ skill.uploaded_at | date:'medium' }}</td>
          <td class="text-end"><button class="btn btn-outline-danger btn-sm" style="font-size: 0.75rem;" (click)="delete(skill.id)">Delete</button></td>
        </tr>
      }
    </tbody>
  </table>
}
```

- [ ] **Step 2: Clear skills.css and commit**

```bash
cd tool-call-ui && echo "" > src/app/admin/skills/skills.css && npx ng build --configuration development 2>&1 | tail -10 && git add src/app/admin/skills/skills.html src/app/admin/skills/skills.css && git commit -m "feat(ui): restyle skills page with Bootstrap table"
```

---

## Task 11: Persona Page

**Files:**
- Modify: `tool-call-ui/src/app/admin/persona/persona.html`
- Modify: `tool-call-ui/src/app/admin/persona/persona.css`

- [ ] **Step 1: Update persona.html**

Replace `tool-call-ui/src/app/admin/persona/persona.html` with:

```html
<div class="d-flex gap-4 h-100">
  <div class="flex-shrink-0 d-flex flex-column" style="width: 240px;">
    <div class="d-flex align-items-center justify-content-between mb-3">
      <h2 class="h5 fw-semibold mb-0">Personas</h2>
      <button class="btn btn-primary btn-sm" (click)="startNew()">+ New</button>
    </div>
    @if (personas.length === 0) {
      <p class="text-secondary" style="font-size: 0.875rem;">No personas yet.</p>
    } @else {
      @for (persona of personas; track persona.id) {
        <div
          class="d-flex align-items-center px-3 py-2 rounded-2 gap-2 mb-1"
          style="cursor: pointer; border: 1px solid transparent;"
          [class.bg-white]="selected?.id === persona.id"
          [class.border-primary]="selected?.id === persona.id"
          [class.bg-light]="selected?.id !== persona.id"
          (click)="selectPersona(persona)"
        >
          <span class="flex-grow-1" style="font-size: 0.875rem;">{{ persona.name }}</span>
          <span class="text-secondary" style="font-size: 0.75rem;">{{ persona.skill_ids.length }} skill{{ persona.skill_ids.length !== 1 ? 's' : '' }}</span>
          <button class="btn btn-link btn-sm p-0 text-secondary lh-1" (click)="$event.stopPropagation(); deletePersona(persona)">✕</button>
        </div>
      }
    }
  </div>

  <div class="flex-grow-1 d-flex flex-column gap-3">
    @if (showForm) {
      <h3 class="h6 fw-semibold mb-0">{{ isNew ? 'New Persona' : 'Edit Persona' }}</h3>
      <div>
        <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.05em;">Name</label>
        <input type="text" class="form-control" [(ngModel)]="form.name" placeholder="e.g. DevOps Engineer" />
      </div>
      <div>
        <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.05em;">Skills</label>
        @if (skills.length === 0) {
          <p class="text-secondary" style="font-size: 0.875rem;">No skills uploaded yet. Upload skills first.</p>
        } @else {
          <div class="d-flex flex-column gap-2">
            @for (skill of skills; track skill.id) {
              <div class="form-check">
                <input class="form-check-input" type="checkbox" [id]="'skill-' + skill.id" [checked]="isSkillSelected(skill.id)" (change)="toggleSkill(skill.id)" />
                <label class="form-check-label" [for]="'skill-' + skill.id" style="font-size: 0.875rem;">{{ skill.filename }}</label>
              </div>
            }
          </div>
        }
      </div>
      <div class="d-flex align-items-center gap-3">
        <button class="btn btn-primary" (click)="save()" [disabled]="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        @if (error) { <span class="text-danger" style="font-size: 0.875rem;">{{ error }}</span> }
      </div>
    } @else {
      <p class="text-secondary" style="font-size: 0.875rem;">Select a persona to edit, or create a new one.</p>
    }
  </div>
</div>
```

- [ ] **Step 2: Replace persona.css**

Replace `tool-call-ui/src/app/admin/persona/persona.css` with:

```css
:host {
  display: flex;
  flex: 1;
  overflow: hidden;
}
```

- [ ] **Step 3: Verify build and commit**

```bash
cd tool-call-ui && npx ng build --configuration development 2>&1 | tail -10 && git add src/app/admin/persona/persona.html src/app/admin/persona/persona.css && git commit -m "feat(ui): restyle persona page with Bootstrap"
```

---

## Task 12: Agents Page + Agent List

**Files:**
- Modify: `tool-call-ui/src/app/admin/agents/agents.html`
- Modify: `tool-call-ui/src/app/admin/agents/agents.css`
- Modify: `tool-call-ui/src/app/admin/agents/agent-list/agent-list.html`
- Modify: `tool-call-ui/src/app/admin/agents/agent-list/agent-list.css`

- [ ] **Step 1: Update agents.html**

Replace `tool-call-ui/src/app/admin/agents/agents.html` with:

```html
<h2 class="h5 fw-semibold mb-3">Agents</h2>

@if (kubeconfigError) {
  <div class="alert alert-danger py-2 px-3 mb-3" style="font-size: 0.875rem;">{{ kubeconfigError }}</div>
}

<ul class="nav nav-tabs mb-4">
  <li class="nav-item">
    <button type="button" class="nav-link" [class.active]="tab === 'deployments'" (click)="tab = 'deployments'">Deployments</button>
  </li>
  <li class="nav-item">
    <button type="button" class="nav-link" [class.active]="tab === 'view'" (click)="tab = 'view'">View</button>
  </li>
</ul>

@if (tab === 'deployments') {
  <app-deploy-form (deployed)="onDeployed()" />
}
@if (tab === 'view') {
  <app-agent-list />
}
```

- [ ] **Step 2: Clear agents.css**

Replace `tool-call-ui/src/app/admin/agents/agents.css` with empty content.

- [ ] **Step 3: Update agent-list.html**

Replace `tool-call-ui/src/app/admin/agents/agent-list/agent-list.html` with:

```html
@if (loading) {
  <div class="d-flex justify-content-center py-4">
    <div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading…</span></div>
  </div>
}
@if (error) {
  <div class="alert alert-danger py-2 px-3" style="font-size: 0.875rem;">{{ error }}</div>
}
@if (!loading && !error && agents.length === 0) {
  <p class="text-secondary" style="font-size: 0.875rem;">No agents deployed yet.</p>
}
@if (agents.length > 0) {
  <table class="table table-hover align-middle" style="font-size: 0.875rem;">
    <thead class="table-light">
      <tr>
        <th class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.07em;">Name</th>
        <th class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.07em;">Namespace</th>
        <th class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.07em;">Image</th>
        <th class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.07em;">Replicas</th>
        <th class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.07em;">Status</th>
        <th class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.07em;">Actions</th>
      </tr>
    </thead>
    <tbody>
      @for (a of agents; track a.name) {
        <tr>
          <td class="fw-medium">{{ a.name }}</td>
          <td class="text-secondary">{{ a.namespace }}</td>
          <td class="text-secondary font-monospace" style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ a.image }}</td>
          <td>
            <div class="d-flex align-items-center gap-2">
              {{ a.replicas }}
              <div class="btn-group btn-group-sm">
                <button class="btn btn-outline-secondary" style="padding: 1px 7px;" (click)="scale(a, -1)">−</button>
                <button class="btn btn-outline-secondary" style="padding: 1px 7px;" (click)="scale(a, 1)">+</button>
              </div>
            </div>
          </td>
          <td>
            <span class="badge rounded-pill"
              [class.text-bg-success]="a.status === 'Running'"
              [class.text-bg-warning]="a.status === 'Pending'"
              [class.text-bg-danger]="a.status === 'Failed'"
              [class.text-bg-primary]="a.status === 'Restarting'"
              [class.text-bg-secondary]="a.status !== 'Running' && a.status !== 'Pending' && a.status !== 'Failed' && a.status !== 'Restarting'"
            >{{ a.status }}</span>
          </td>
          <td>
            <div class="d-flex gap-1">
              <button class="btn btn-outline-warning btn-sm" style="font-size: 0.75rem;" (click)="restart(a)">Restart</button>
              <button class="btn btn-outline-danger btn-sm" style="font-size: 0.75rem;" (click)="delete(a)">Delete</button>
            </div>
          </td>
        </tr>
      }
    </tbody>
  </table>
}
```

- [ ] **Step 4: Clear agent-list.css**

Replace `tool-call-ui/src/app/admin/agents/agent-list/agent-list.css` with empty content.

- [ ] **Step 5: Verify build and commit**

```bash
cd tool-call-ui && npx ng build --configuration development 2>&1 | tail -10 && git add src/app/admin/agents/agents.html src/app/admin/agents/agents.css src/app/admin/agents/agent-list/agent-list.html src/app/admin/agents/agent-list/agent-list.css && git commit -m "feat(ui): restyle agents page and agent list with Bootstrap"
```

---

## Task 13: Deploy Form

**Files:**
- Modify: `tool-call-ui/src/app/admin/agents/deploy-form/deploy-form.html`
- Modify: `tool-call-ui/src/app/admin/agents/deploy-form/deploy-form.css`

- [ ] **Step 1: Update deploy-form.html**

Replace `tool-call-ui/src/app/admin/agents/deploy-form/deploy-form.html` with:

```html
<div class="d-flex flex-column gap-4" style="max-width: 640px;">
  <div class="row g-3">
    <div class="col-6">
      <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.05em;">Name</label>
      <input type="text" class="form-control" [(ngModel)]="form.name" placeholder="my-agent" />
      @if (fullName) {
        <div class="text-primary mt-1" style="font-size: 0.8rem;">→ {{ fullName }}</div>
      }
    </div>
    <div class="col-6">
      <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.05em;">Docker Image</label>
      <input type="text" class="form-control" [(ngModel)]="form.image" placeholder="my-org/my-agent:latest" />
    </div>
  </div>

  <div class="row g-3">
    <div class="col-6">
      <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.05em;">Namespace</label>
      <input type="text" class="form-control" [(ngModel)]="form.namespace" />
    </div>
    <div class="col-6">
      <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.05em;">Replicas</label>
      <input type="number" class="form-control" [(ngModel)]="form.replicas" min="1" />
    </div>
  </div>

  <div>
    <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.05em;">Environment Variables</label>
    @for (ev of env; track $index) {
      <div class="d-flex gap-2 mb-2">
        <input type="text" class="form-control form-control-sm" [(ngModel)]="ev.key" placeholder="KEY" />
        <input type="text" class="form-control form-control-sm" [(ngModel)]="ev.value" placeholder="value" />
        <button class="btn btn-outline-danger btn-sm" (click)="removeEnvVar($index)">✕</button>
      </div>
    }
    <button class="btn btn-link btn-sm p-0" (click)="addEnvVar()">+ Add variable</button>
  </div>

  <div class="d-flex align-items-center gap-3">
    <button class="btn btn-primary" (click)="deploy()" [disabled]="deploying || !form.name || !form.image">
      {{ deploying ? 'Deploying…' : 'Deploy' }}
    </button>
    @if (error) { <span class="text-danger" style="font-size: 0.875rem;">{{ error }}</span> }
  </div>
</div>
```

- [ ] **Step 2: Clear deploy-form.css and commit**

```bash
cd tool-call-ui && echo "" > src/app/admin/agents/deploy-form/deploy-form.css && npx ng build --configuration development 2>&1 | tail -10 && git add src/app/admin/agents/deploy-form/deploy-form.html src/app/admin/agents/deploy-form/deploy-form.css && git commit -m "feat(ui): restyle deploy form with Bootstrap"
```

---

## Task 14: Agent-WS Configure

**Files:**
- Modify: `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.html`
- Modify: `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.css`

- [ ] **Step 1: Update agent-configure.html**

Replace `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.html` with:

```html
@if (error) {
  <div class="alert alert-danger py-2 px-3 mb-3" style="font-size: 0.875rem;">{{ error }}</div>
}

<div class="d-flex align-items-center gap-3 mb-4">
  <label class="text-uppercase text-secondary fw-semibold" style="font-size: 0.72rem; letter-spacing: 0.06em; white-space: nowrap;">Agent</label>
  @if (agents.length === 0) {
    <p class="text-secondary mb-0" style="font-size: 0.875rem;">No agents deployed. Deploy an agent first.</p>
  } @else {
    <select class="form-select form-select-sm" style="min-width: 280px;" [(ngModel)]="selectedAgent" (ngModelChange)="onAgentChange()">
      @for (a of agents; track a.name) {
        <option [value]="a.name">{{ a.name }}</option>
      }
    </select>
  }
</div>

@if (selectedAgent) {
  <div class="d-flex align-items-center justify-content-between mb-3">
    <span class="text-secondary" style="font-size: 0.875rem;">{{ instances.length }} instance{{ instances.length !== 1 ? 's' : '' }}</span>
    <button class="btn btn-outline-primary btn-sm" (click)="addInstance()">+ Add Instance</button>
  </div>

  @if (loading) {
    <div class="d-flex justify-content-center py-3">
      <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
    </div>
  }

  <div class="d-flex flex-column gap-2">
    @for (form of instances; track $index; let i = $index) {
      <div class="card rounded-3" [class.border-primary]="form.expanded">
        <div class="card-header bg-white d-flex align-items-center justify-content-between" style="cursor: pointer;" (click)="toggle(form)">
          <div class="d-flex align-items-center gap-3 flex-grow-1 overflow-hidden">
            <span class="fw-medium" style="font-size: 0.875rem;">{{ form.instance_name || 'New Instance' }}</span>
            @if (!form.expanded && form.id) {
              <span class="text-secondary text-truncate" style="font-size: 0.75rem;">
                Persona: {{ personaName(form.persona_id) }} · MCP: {{ mcpSummary(form.mcp_positions) }}
              </span>
            }
          </div>
          <div class="d-flex align-items-center gap-2 flex-shrink-0">
            <button class="btn btn-outline-danger btn-sm" style="font-size: 0.75rem;" (click)="deleteInstance(form, i); $event.stopPropagation()">Delete</button>
            <span class="text-secondary" style="font-size: 0.72rem;">{{ form.expanded ? '▲' : '▼' }}</span>
          </div>
        </div>

        @if (form.expanded) {
          <div class="card-body">
            @if (form.error) {
              <div class="alert alert-danger py-2 px-3 mb-3" style="font-size: 0.82rem;">{{ form.error }}</div>
            }
            <div class="row g-3 mb-3">
              <div class="col-4">
                <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.7rem; letter-spacing: 0.06em;">Instance Name</label>
                <input class="form-control form-control-sm" [(ngModel)]="form.instance_name" placeholder="e.g. Customer Support" />
              </div>
              <div class="col-4">
                <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.7rem; letter-spacing: 0.06em;">Persona</label>
                <select class="form-select form-select-sm" [(ngModel)]="form.persona_id">
                  <option [ngValue]="null">— None —</option>
                  @for (p of personas; track p.id) {
                    <option [value]="p.id">{{ p.name }}</option>
                  }
                </select>
              </div>
              <div class="col-4">
                <label class="form-label text-uppercase text-secondary fw-semibold" style="font-size: 0.7rem; letter-spacing: 0.06em;">MCP Servers</label>
                <div class="d-flex flex-column gap-1">
                  @for (s of mcpServers; track s.position) {
                    <div class="form-check">
                      <input
                        class="form-check-input"
                        type="checkbox"
                        [id]="'mcp-' + i + '-' + s.position"
                        [checked]="isMcpSelected(form, s.position)"
                        (change)="toggleMcp(form, s.position)"
                      />
                      <label class="form-check-label" style="font-size: 0.8rem;" [for]="'mcp-' + i + '-' + s.position">{{ s.name }}</label>
                    </div>
                  }
                  @if (mcpServers.length === 0) {
                    <span class="text-secondary" style="font-size: 0.8rem;">No MCP servers configured.</span>
                  }
                </div>
              </div>
            </div>
            <div class="d-flex justify-content-end">
              <button class="btn btn-primary btn-sm" (click)="save(form)" [disabled]="form.saving">
                {{ form.saving ? 'Saving…' : 'Save' }}
              </button>
            </div>
          </div>
        }
      </div>
    }
  </div>
}
```

- [ ] **Step 2: Clear agent-configure.css and commit**

```bash
cd tool-call-ui && echo "" > src/app/admin/agent-ws/agent-configure/agent-configure.css && npx ng build --configuration development 2>&1 | tail -10 && git add src/app/admin/agent-ws/agent-configure/agent-configure.html src/app/admin/agent-ws/agent-configure/agent-configure.css && git commit -m "feat(ui): restyle agent-configure with Bootstrap accordion cards"
```

---

## Task 15: Final Verification

- [ ] **Step 1: Full production build**

```bash
cd tool-call-ui && npx ng build 2>&1 | tail -20
```

Expected: Build succeeds with no errors or warnings about missing styles.

- [ ] **Step 2: Serve and visually inspect**

```bash
cd tool-call-ui && npx ng serve --open
```

Navigate to each route and verify:
- `http://localhost:4200/` — white navbar, indigo brand, Inter font
- `http://localhost:4200/ai-engg` — Chat tab with light card, rounded bubbles, indigo Send button
- Sessions tab — hover table, expandable rows, chat history bubbles
- `http://localhost:4200/admin/credentials` — clean Bootstrap form
- `http://localhost:4200/admin/mcp-servers` — card-per-slot layout
- `http://localhost:4200/admin/skills` — table with upload button
- `http://localhost:4200/admin/persona` — two-pane layout
- `http://localhost:4200/admin/agents` — tabs + table
- `http://localhost:4200/admin/agent-ws` — expandable instance cards

- [ ] **Step 3: Final commit if any fixups needed**

```bash
cd tool-call-ui && git add -p && git commit -m "fix(ui): Bootstrap theme fixups after visual review"
```
