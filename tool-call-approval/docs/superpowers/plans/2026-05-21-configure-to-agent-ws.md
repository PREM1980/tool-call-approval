# Move Configure to Agent-WS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `AgentConfigure` component from the Agents panel's Configure tab into the Agent-WS page, which renders it directly under an `<h2>Agent-WS</h2>` heading.

**Architecture:** Physical file move of 3 files from `agents/agent-configure/` to `agent-ws/agent-configure/`, import path fixup in the moved `.ts` file, Agent-WS updated to use the component, Configure tab removed from Agents.

**Tech Stack:** Angular 19, TypeScript, standalone components

---

## File Map

| File | Change |
|---|---|
| `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.ts` | Delete (replaced by move) |
| `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.html` | Delete (replaced by move) |
| `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.css` | Delete (replaced by move) |
| `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.ts` | Create (moved + import paths fixed) |
| `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.html` | Create (moved, unchanged) |
| `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.css` | Create (moved, unchanged) |
| `tool-call-ui/src/app/admin/agent-ws/agent-ws.ts` | Modify: replace stub with real component |
| `tool-call-ui/src/app/admin/agents/agents.ts` | Modify: remove AgentConfigure import + tab type |
| `tool-call-ui/src/app/admin/agents/agents.html` | Modify: remove Configure tab button + outlet |

---

## Task 1: Move agent-configure files to agent-ws

**Files:**
- Create: `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.ts`
- Create: `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.html`
- Create: `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.css`
- Delete: `tool-call-ui/src/app/admin/agents/agent-configure/` (all 3 files)

- [ ] **Step 1: Create the new directory and move all three files**

```bash
mkdir -p tool-call-ui/src/app/admin/agent-ws/agent-configure
mv tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.html \
   tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.html
mv tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.css \
   tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.css
mv tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.ts \
   tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.ts
rmdir tool-call-ui/src/app/admin/agents/agent-configure
```

- [ ] **Step 2: Fix the import paths in the moved agent-configure.ts**

The file moved one level up (out of `agents/`) so relative imports shift.

Open `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.ts` and replace the import line:

```typescript
// OLD (line 4 in the original file):
import { AdminService, AgentInstance, PersonaData, McpServer } from '../../../services/admin.service';
import { AgentsService, AgentDeployment } from '../../../services/agents.service';
```

with:

```typescript
// NEW — one fewer `..` because the file is now directly under agent-ws/
import { AdminService, AgentInstance, PersonaData, McpServer } from '../../services/admin.service';
import { AgentsService, AgentDeployment } from '../../services/agents.service';
```

The full corrected file should look like:

```typescript
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminService, AgentInstance, PersonaData, McpServer } from '../../services/admin.service';
import { AgentsService, AgentDeployment } from '../../services/agents.service';

interface InstanceForm {
  id: string | null;
  instance_name: string;
  persona_id: string | null;
  mcp_positions: number[];
  expanded: boolean;
  saving: boolean;
  error: string;
}

@Component({
  selector: 'app-agent-configure',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './agent-configure.html',
  styleUrl: './agent-configure.css',
})
export class AgentConfigure implements OnInit {
  agents: AgentDeployment[] = [];
  personas: PersonaData[] = [];
  mcpServers: McpServer[] = [];
  instances: InstanceForm[] = [];
  selectedAgent = '';
  loading = false;
  error = '';

  constructor(
    private adminService: AdminService,
    private agentsService: AgentsService,
  ) {}

  async ngOnInit() {
    const [agents, personas, mcpServers] = await Promise.all([
      this.agentsService.list(),
      this.adminService.getPersonas(),
      this.adminService.getMcpServers(),
    ]);
    this.agents = agents;
    this.personas = personas;
    this.mcpServers = mcpServers;
    if (agents.length > 0) {
      this.selectedAgent = agents[0].name;
      await this.loadInstances();
    }
  }

  async onAgentChange() {
    await this.loadInstances();
  }

  async loadInstances() {
    if (!this.selectedAgent) return;
    this.loading = true;
    try {
      const raw = await this.adminService.getAgentInstances(this.selectedAgent);
      this.instances = raw.map(i => this._toForm(i));
      this.error = '';
    } catch {
      this.error = 'Failed to load instances';
    } finally {
      this.loading = false;
    }
  }

  addInstance() {
    this.instances.push({
      id: null,
      instance_name: '',
      persona_id: null,
      mcp_positions: [],
      expanded: true,
      saving: false,
      error: '',
    });
  }

  toggle(form: InstanceForm) {
    form.expanded = !form.expanded;
  }

  isMcpSelected(form: InstanceForm, position: number): boolean {
    return form.mcp_positions.includes(position);
  }

  toggleMcp(form: InstanceForm, position: number) {
    const idx = form.mcp_positions.indexOf(position);
    if (idx >= 0) {
      form.mcp_positions.splice(idx, 1);
    } else {
      form.mcp_positions.push(position);
    }
  }

  async save(form: InstanceForm) {
    if (!form.instance_name.trim()) {
      form.error = 'Instance name is required';
      return;
    }
    form.saving = true;
    form.error = '';
    try {
      let saved: AgentInstance;
      if (form.id === null) {
        saved = await this.adminService.createAgentInstance(
          this.selectedAgent,
          form.instance_name,
          form.persona_id,
          form.mcp_positions,
        );
      } else {
        saved = await this.adminService.updateAgentInstance(
          form.id,
          form.instance_name,
          form.persona_id,
          form.mcp_positions,
        );
      }
      Object.assign(form, this._toForm(saved));
    } catch (e: any) {
      form.error = e?.error?.detail ?? 'Save failed';
    } finally {
      form.saving = false;
    }
  }

  async deleteInstance(form: InstanceForm, index: number) {
    if (!confirm(`Delete instance "${form.instance_name}"?`)) return;
    if (form.id !== null) {
      try {
        await this.adminService.deleteAgentInstance(form.id);
      } catch (e: any) {
        form.error = e?.error?.detail ?? 'Delete failed';
        return;
      }
    }
    this.instances.splice(index, 1);
  }

  personaName(id: string | null): string {
    if (!id) return '—';
    return this.personas.find(p => p.id === id)?.name ?? '—';
  }

  mcpSummary(positions: number[]): string {
    if (positions.length === 0) return '—';
    return positions
      .map(p => this.mcpServers.find(s => s.position === p)?.name ?? `#${p}`)
      .join(', ');
  }

  private _toForm(i: AgentInstance): InstanceForm {
    return {
      id: i.id,
      instance_name: i.instance_name,
      persona_id: i.persona_id,
      mcp_positions: [...i.mcp_positions],
      expanded: false,
      saving: false,
      error: '',
    };
  }
}
```

- [ ] **Step 3: Verify TypeScript compiles (expect errors — agent-ws.ts still has stub, agents.ts still imports AgentConfigure)**

```bash
cd tool-call-ui && npx tsc --noEmit 2>&1 | head -30
```

Expected: errors referencing the old import path in `agents.ts` and the missing import in `agent-ws.ts`. Proceed to Task 2.

---

## Task 2: Update Agent-WS to render AgentConfigure

**Files:**
- Modify: `tool-call-ui/src/app/admin/agent-ws/agent-ws.ts`

- [ ] **Step 1: Replace the stub component with one that renders AgentConfigure**

Replace the entire contents of `tool-call-ui/src/app/admin/agent-ws/agent-ws.ts` with:

```typescript
import { Component } from '@angular/core';
import { AgentConfigure } from './agent-configure/agent-configure';

@Component({
  selector: 'app-agent-ws',
  standalone: true,
  imports: [AgentConfigure],
  template: `
    <h2>Agent-WS</h2>
    <app-agent-configure />
  `,
})
export class AgentWs {}
```

---

## Task 3: Remove Configure tab from Agents

**Files:**
- Modify: `tool-call-ui/src/app/admin/agents/agents.ts`
- Modify: `tool-call-ui/src/app/admin/agents/agents.html`

- [ ] **Step 1: Update agents.ts — remove AgentConfigure import and narrow tab type**

Replace the entire contents of `tool-call-ui/src/app/admin/agents/agents.ts` with:

```typescript
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AgentsService } from '../../services/agents.service';
import { DeployForm } from './deploy-form/deploy-form';
import { AgentList } from './agent-list/agent-list';

@Component({
  selector: 'app-agents',
  standalone: true,
  imports: [CommonModule, DeployForm, AgentList],
  templateUrl: './agents.html',
  styleUrl: './agents.css',
})
export class Agents implements OnInit {
  tab: 'deployments' | 'view' = 'deployments';
  kubeconfigError = '';

  constructor(private agentsService: AgentsService) {}

  async ngOnInit() {
    try {
      await this.agentsService.syncKubeconfig();
    } catch {
      this.kubeconfigError = 'Kubeconfig not configured. Save credentials first.';
    }
  }

  onDeployed() {
    this.tab = 'view';
  }
}
```

- [ ] **Step 2: Update agents.html — remove Configure tab button and outlet**

Replace the entire contents of `tool-call-ui/src/app/admin/agents/agents.html` with:

```html
<h2>Agents</h2>

@if (kubeconfigError) {
  <div class="banner">{{ kubeconfigError }}</div>
}

<div class="tabs">
  <button type="button" class="tab" [class.active]="tab === 'deployments'" (click)="tab = 'deployments'">
    Deployments
  </button>
  <button type="button" class="tab" [class.active]="tab === 'view'" (click)="tab = 'view'">
    View
  </button>
</div>

@if (tab === 'deployments') {
  <app-deploy-form (deployed)="onDeployed()" />
}
@if (tab === 'view') {
  <app-agent-list />
}
```

---

## Task 4: Verify and commit

**Files:** no code changes — compile + smoke test + commit

- [ ] **Step 1: Verify TypeScript compiles with no errors**

```bash
cd tool-call-ui && npx tsc --noEmit
```

Expected: no output (clean compile).

- [ ] **Step 2: Smoke test in the browser**

Start the UI if not already running:
```bash
cd tool-call-ui && ng serve
```

Verify:
1. `/admin/agents` — shows two tabs only: Deployments and View (no Configure).
2. `/admin/agent-ws` — shows the `<h2>Agent-WS</h2>` heading followed by the agent selector and instance list.
3. On Agent-WS, selecting an agent loads its instances; Add Instance / Save / Delete all work.

- [ ] **Step 3: Commit**

```bash
git add \
  tool-call-ui/src/app/admin/agent-ws/agent-configure/ \
  tool-call-ui/src/app/admin/agent-ws/agent-ws.ts \
  tool-call-ui/src/app/admin/agents/agents.ts \
  tool-call-ui/src/app/admin/agents/agents.html
git commit -m "refactor(ui): move AgentConfigure from Agents tab to Agent-WS page"
```
