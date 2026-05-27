# Agents View Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the plain Bootstrap table on the Agents → View tab with an Ops Dashboard layout — stats bar + flat flex-row agent cards.

**Architecture:** All logic stays in `agent-list.ts` (unchanged). Only the template and styles are replaced. Stats counts are derived inline in the template from the existing `agents` array using Angular's `@let` declarations. No new dependencies.

**Tech Stack:** Angular 17+ (standalone components, `@for`/`@if`/`@let` control flow), Bootstrap 5, plain CSS scoped to the component.

---

## File Map

| File | Change |
| ---- | ------ |
| `tool-call-ui/src/app/admin/agents/agent-list/agent-list.html` | Full replacement |
| `tool-call-ui/src/app/admin/agents/agent-list/agent-list.css` | Full replacement |
| `tool-call-ui/src/app/admin/agents/agent-list/agent-list.spec.ts` | Create — component tests |
| `tool-call-ui/src/app/admin/agents/agent-list/agent-list.ts` | Add one `countByStatus(status)` helper method (3 lines) — all existing logic unchanged |

All services and all other components are **not touched**.

---

## Task 1: Write the component spec

**Files:**
- Create: `tool-call-ui/src/app/admin/agents/agent-list/agent-list.spec.ts`

- [ ] **Step 1.1 — Create the spec file**

```typescript
// tool-call-ui/src/app/admin/agents/agent-list/agent-list.spec.ts
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AgentList } from './agent-list';
import { AgentsService } from '../../../services/agents.service';

const RUNNING = { name: 'alpha-agent', namespace: 'default', image: 'alpha:latest', replicas: 2, ready_replicas: 2, status: 'Running' };
const PENDING = { name: 'beta-agent',  namespace: 'staging', image: 'beta:v1',     replicas: 1, ready_replicas: 0, status: 'Pending' };
const FAILED  = { name: 'gamma-agent', namespace: 'prod',    image: 'gamma:v2',    replicas: 1, ready_replicas: 0, status: 'Failed'  };

function makeService(agents: any[] = []) {
  return { list: () => Promise.resolve(agents), scale: () => Promise.resolve(), restart: () => Promise.resolve(), delete: () => Promise.resolve() };
}

async function build(agents: any[]) {
  await TestBed.configureTestingModule({
    imports: [AgentList],
    providers: [{ provide: AgentsService, useValue: makeService(agents) }],
  }).compileComponents();
  const fixture: ComponentFixture<AgentList> = TestBed.createComponent(AgentList);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  return fixture;
}

describe('AgentList', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('shows empty state when no agents', async () => {
    const f = await build([]);
    expect(f.nativeElement.querySelector('.agent-empty')).toBeTruthy();
    expect(f.nativeElement.querySelector('.agent-row')).toBeNull();
  });

  it('renders one row per agent', async () => {
    const f = await build([RUNNING, PENDING]);
    expect(f.nativeElement.querySelectorAll('.agent-row').length).toBe(2);
  });

  it('stat card shows correct running count', async () => {
    const f = await build([RUNNING, PENDING, FAILED]);
    const cards = f.nativeElement.querySelectorAll('.stat-card');
    // Running card is first
    expect(cards[0].querySelector('.stat-num').textContent.trim()).toBe('1');
  });

  it('stat card shows correct total count', async () => {
    const f = await build([RUNNING, PENDING, FAILED]);
    const cards = f.nativeElement.querySelectorAll('.stat-card');
    // Total card is second
    expect(cards[1].querySelector('.stat-num').textContent.trim()).toBe('3');
  });

  it('stat card shows correct pending count', async () => {
    const f = await build([RUNNING, PENDING, FAILED]);
    const cards = f.nativeElement.querySelectorAll('.stat-card');
    expect(cards[2].querySelector('.stat-num').textContent.trim()).toBe('1');
  });

  it('stat card shows correct failed count', async () => {
    const f = await build([RUNNING, PENDING, FAILED]);
    const cards = f.nativeElement.querySelectorAll('.stat-card');
    expect(cards[3].querySelector('.stat-num').textContent.trim()).toBe('1');
  });

  it('Running row has running status badge', async () => {
    const f = await build([RUNNING]);
    const badge = f.nativeElement.querySelector('.status-badge');
    expect(badge.classList).toContain('running');
    expect(badge.textContent).toContain('Running');
  });

  it('Pending row has pending status badge', async () => {
    const f = await build([PENDING]);
    const badge = f.nativeElement.querySelector('.status-badge');
    expect(badge.classList).toContain('pending');
  });

  it('Failed row has failed status badge', async () => {
    const f = await build([FAILED]);
    const badge = f.nativeElement.querySelector('.status-badge');
    expect(badge.classList).toContain('failed');
  });

  it('shows agent name and namespace pill', async () => {
    const f = await build([RUNNING]);
    const row = f.nativeElement.querySelector('.agent-row');
    expect(row.querySelector('.agent-name').textContent.trim()).toBe('alpha-agent');
    expect(row.querySelector('.agent-ns').textContent.trim()).toBe('default');
  });

  it('shows replica count', async () => {
    const f = await build([RUNNING]);
    expect(f.nativeElement.querySelector('.rep-count').textContent.trim()).toBe('2');
  });
});
```

- [ ] **Step 1.2 — Run tests to confirm they all fail (template not updated yet)**

```bash
cd tool-call-ui && npx ng test --include='**/agent-list.spec.ts' --watch=false --browsers=ChromeHeadless 2>&1 | tail -20
```

Expected: multiple FAILED — `agent-empty`, `agent-row`, `stat-card`, `stat-num`, `status-badge`, etc. not found.

- [ ] **Step 1.3 — Commit the spec**

```bash
git add tool-call-ui/src/app/admin/agents/agent-list/agent-list.spec.ts
git commit -m "test(agents): add AgentList component spec for ops dashboard redesign"
```

---

## Task 2: Replace the template

**Files:**
- Modify: `tool-call-ui/src/app/admin/agents/agent-list/agent-list.html`

- [ ] **Step 2.1 — Replace agent-list.html entirely**

```html
@if (loading) {
  <div class="d-flex justify-content-center py-4">
    <div class="spinner-border text-primary" role="status">
      <span class="visually-hidden">Loading…</span>
    </div>
  </div>
}

@if (error) {
  <div class="alert alert-danger py-2 px-3 agent-list-alert">{{ error }}</div>
}

@if (!loading && !error) {
  <!-- Stats bar -->
  <div class="stats-bar">
    <div class="stat-card running">
      <div class="stat-icon running">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" fill="#16a34a" opacity=".2"/>
          <circle cx="8" cy="8" r="3" fill="#16a34a"/>
        </svg>
      </div>
      <div class="stat-body">
        <div class="stat-num running">{{ countByStatus('Running') }}</div>
        <div class="stat-label">Running</div>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-icon total">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <rect x="2" y="2" width="12" height="12" rx="3" fill="#6366f1" opacity=".2"/>
          <rect x="5" y="5" width="6" height="6" rx="1.5" fill="#6366f1"/>
        </svg>
      </div>
      <div class="stat-body">
        <div class="stat-num">{{ agents.length }}</div>
        <div class="stat-label">Total</div>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-icon pending">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" fill="#f59e0b" opacity=".2"/>
          <path d="M8 5v3.5l2 2" stroke="#f59e0b" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </div>
      <div class="stat-body">
        <div class="stat-num pending">{{ countByStatus('Pending') }}</div>
        <div class="stat-label">Pending</div>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-icon failed">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" fill="#ef4444" opacity=".2"/>
          <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="#ef4444" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </div>
      <div class="stat-body">
        <div class="stat-num failed">{{ countByStatus('Failed') }}</div>
        <div class="stat-label">Failed</div>
      </div>
    </div>
  </div>

  <!-- Agent rows -->
  @if (agents.length === 0) {
    <div class="agent-empty">
      <div class="agent-empty-icon">⬡</div>
      <p>No agents deployed yet.</p>
    </div>
  }

  <div class="agents-list">
    @for (a of agents; track a.name) {
      <div class="agent-row">
        <!-- Name + namespace -->
        <div class="agent-name-col">
          <div class="agent-name">{{ a.name }}</div>
          <span class="agent-ns">{{ a.namespace }}</span>
        </div>

        <!-- Image -->
        <div class="agent-image-col">
          <div class="col-label">Image</div>
          <div class="agent-image" [title]="a.image">{{ a.image }}</div>
        </div>

        <!-- Replica stepper -->
        <div class="agent-replicas-col">
          <div class="col-label">Replicas</div>
          <div class="replica-stepper">
            <button type="button" class="step-btn" (click)="scale(a, -1)">−</button>
            <span class="rep-count">{{ a.replicas }}</span>
            <button type="button" class="step-btn" (click)="scale(a, 1)">+</button>
          </div>
        </div>

        <!-- Status badge -->
        <div class="agent-status-col">
          <span class="status-badge"
            [class.running]="a.status === 'Running'"
            [class.pending]="a.status === 'Pending'"
            [class.failed]="a.status === 'Failed'"
            [class.restarting]="a.status === 'Restarting'"
          >
            <span class="status-dot"></span>{{ a.status }}
          </span>
        </div>

        <!-- Actions -->
        <div class="agent-actions-col">
          <button type="button" class="act-btn act-restart" (click)="restart(a)">Restart</button>
          <button type="button" class="act-btn act-delete"  (click)="delete(a)">Delete</button>
        </div>
      </div>
    }
  </div>

  @if (agents.length > 0) {
    <div class="refresh-hint">Auto-refreshes every 10s</div>
  }
}
```

- [ ] **Step 2.2 — Add `countByStatus` method to `agent-list.ts`**

The template calls `countByStatus('Running')` — add this pure helper method to the component class. Open `agent-list.ts` and add after the `delete` method:

```typescript
countByStatus(status: string): number {
  return this.agents.filter(a => a.status === status).length;
}
```

- [ ] **Step 2.3 — Run tests — expect failures only on CSS class selectors (template structure is correct)**

```bash
cd tool-call-ui && npx ng test --include='**/agent-list.spec.ts' --watch=false --browsers=ChromeHeadless 2>&1 | tail -20
```

Expected: tests referencing `.stat-card`, `.stat-num`, `.agent-row`, `.agent-empty`, `.status-badge`, `.agent-name`, `.agent-ns`, `.rep-count` may still fail because the CSS classes don't exist yet — that is expected at this step.

- [ ] **Step 2.4 — Commit the template + helper**

```bash
git add tool-call-ui/src/app/admin/agents/agent-list/agent-list.html
git add tool-call-ui/src/app/admin/agents/agent-list/agent-list.ts
git commit -m "feat(agents): replace table with ops dashboard template"
```

---

## Task 3: Replace the stylesheet

**Files:**
- Modify: `tool-call-ui/src/app/admin/agents/agent-list/agent-list.css`

- [ ] **Step 3.1 — Replace agent-list.css entirely**

```css
/* ── Stats bar ─────────────────────────────────────────────────────── */
.stats-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 14px 20px;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 14px;
}

.stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon.running { background: #dcfce7; }
.stat-icon.total   { background: #e0e7ff; }
.stat-icon.pending { background: #fef3c7; }
.stat-icon.failed  { background: #fee2e2; }

.stat-num {
  font-size: 22px;
  font-weight: 800;
  line-height: 1;
  color: #0f172a;
}

.stat-num.running { color: #16a34a; }
.stat-num.pending { color: #d97706; }
.stat-num.failed  { color: #dc2626; }

.stat-label {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-top: 3px;
}

/* ── Agent list ─────────────────────────────────────────────────────── */
.agents-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-row {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 14px 18px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: box-shadow 0.15s, border-color 0.15s;
}

.agent-row:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.07);
  border-color: #cbd5e1;
}

/* ── Name column ────────────────────────────────────────────────────── */
.agent-name-col {
  flex: 0 0 170px;
}

.agent-name {
  font-weight: 700;
  font-size: 14px;
  color: #0f172a;
}

.agent-ns {
  display: inline-block;
  background: #f1f5f9;
  color: #64748b;
  border-radius: 4px;
  padding: 1px 7px;
  font-size: 10.5px;
  margin-top: 4px;
}

/* ── Image column ───────────────────────────────────────────────────── */
.agent-image-col {
  flex: 1;
  min-width: 0;
}

.col-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #94a3b8;
  margin-bottom: 2px;
}

.agent-image {
  font-family: 'SF Mono', 'Fira Mono', ui-monospace, monospace;
  font-size: 11.5px;
  color: #475569;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Replicas column ────────────────────────────────────────────────── */
.agent-replicas-col {
  flex: 0 0 auto;
}

.replica-stepper {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}

.step-btn {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  border-radius: 5px;
  width: 24px;
  height: 24px;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #475569;
  padding: 0;
  line-height: 1;
}

.step-btn:hover {
  background: #e2e8f0;
}

.rep-count {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  min-width: 18px;
  text-align: center;
}

/* ── Status column ──────────────────────────────────────────────────── */
.agent-status-col {
  flex: 0 0 120px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 20px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  background: #f1f5f9;
  color: #64748b;
}

.status-badge.running    { background: #dcfce7; color: #16a34a; }
.status-badge.pending    { background: #fef3c7; color: #d97706; }
.status-badge.failed     { background: #fee2e2; color: #dc2626; }
.status-badge.restarting { background: #e0e7ff; color: #4f46e5; }

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

/* ── Actions column ─────────────────────────────────────────────────── */
.agent-actions-col {
  flex: 0 0 auto;
  display: flex;
  gap: 6px;
}

.act-btn {
  border: none;
  border-radius: 7px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.1s;
}

.act-btn:hover { opacity: 0.8; }

.act-restart { background: #fef3c7; color: #b45309; }
.act-delete  { background: #fee2e2; color: #b91c1c; }

/* ── Empty state ────────────────────────────────────────────────────── */
.agent-empty {
  text-align: center;
  padding: 48px 0;
  color: #94a3b8;
}

.agent-empty-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.agent-empty p {
  font-size: 14px;
  margin: 0;
}

/* ── Misc ───────────────────────────────────────────────────────────── */
.refresh-hint {
  font-size: 11px;
  color: #94a3b8;
  text-align: right;
  margin-top: 10px;
}

.agent-list-alert {
  font-size: 0.875rem;
}
```

- [ ] **Step 3.2 — Run all tests — all should pass**

```bash
cd tool-call-ui && npx ng test --include='**/agent-list.spec.ts' --watch=false --browsers=ChromeHeadless 2>&1 | tail -25
```

Expected: `11 specs, 0 failures`

- [ ] **Step 3.3 — Run the full test suite to check for regressions**

```bash
cd tool-call-ui && npx ng test --watch=false --browsers=ChromeHeadless 2>&1 | tail -10
```

Expected: 0 failures.

- [ ] **Step 3.4 — Commit the stylesheet**

```bash
git add tool-call-ui/src/app/admin/agents/agent-list/agent-list.css
git commit -m "feat(agents): ops dashboard stylesheet — stats bar, flat rows, status badges"
```

---

## Task 4: Visual verification

- [ ] **Step 4.1 — Serve the app**

```bash
cd tool-call-ui && npx ng serve --open
```

Navigate to **Admin → Agents → View** tab.

- [ ] **Step 4.2 — Verify the following**

| Check | Expected |
| ----- | -------- |
| Stats bar visible | 4 cards: Running (green), Total (neutral), Pending (amber), Failed (red) |
| Counts correct | Reflect actual deployed agents |
| Agent rows | Each row: name + namespace pill, image with label, replica stepper, colored status badge, Restart/Delete buttons |
| Row hover | Subtle shadow lift on hover |
| Empty state | "No agents deployed yet." message when list is empty |
| Refresh hint | "Auto-refreshes every 10s" bottom-right when agents exist |
| Status badge colors | Running=green, Pending=amber, Failed=red, Restarting=indigo |

- [ ] **Step 4.3 — Final commit if any minor visual tweaks were needed**

```bash
git add -p
git commit -m "fix(agents): visual tweaks to ops dashboard"
```
