# Agent Instance Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Configure tab to the Agents admin panel where each K8s agent deployment can have multiple named instances, each with its own persona and MCP server assignments stored in Postgres.

**Architecture:** New `admin_agent_instances` Postgres table keyed by `(agent_name, instance_name)`. Four CRUD endpoints on the existing admin router. New Angular `AgentConfigure` component added as a third tab in the Agents panel.

**Tech Stack:** Python 3.12, FastAPI, psycopg2, pytest | Angular 19, TypeScript, standalone components

---

## File Map

| File | Change |
|---|---|
| `tool-call-agent/admin_repository.py` | Add table + 4 repository methods |
| `tool-call-agent/admin_models.py` | Add 3 new Pydantic models |
| `tool-call-agent/admin_router.py` | Add 4 new route handlers |
| `tool-call-agent/tests/test_admin.py` | Add repository + API tests, extend clean_tables fixture |
| `tool-call-ui/src/app/services/admin.service.ts` | Add AgentInstance interface + 4 methods |
| `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.ts` | New component (create) |
| `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.html` | New template (create) |
| `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.css` | New styles (create) |
| `tool-call-ui/src/app/admin/agents/agents.ts` | Add Configure tab |
| `tool-call-ui/src/app/admin/agents/agents.html` | Add Configure tab button + outlet |

---

## Task 1: DB schema + repository methods

**Files:**
- Modify: `tool-call-agent/admin_repository.py`
- Test: `tool-call-agent/tests/test_admin.py`

- [ ] **Step 1: Write failing repository tests**

Open `tool-call-agent/tests/test_admin.py`. Find the `repo` fixture (around line 6) and add `DELETE FROM admin_agent_instances` to the clean slate block:

```python
@pytest.fixture
def repo():
    r = AdminRepository(TEST_URL)
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM admin_credentials")
        cur.execute("DELETE FROM admin_mcp_servers")
        cur.execute("DELETE FROM admin_skills")
        cur.execute("DELETE FROM admin_personas")
        cur.execute("DELETE FROM admin_agent_instances")
    conn.commit()
    conn.close()
    return r
```

Then add these tests at the end of the repo section (before `# ── API-level tests`):

```python
# ── Agent Instances ────────────────────────────────────────────────────────

def test_agent_instances_empty_initially(repo):
    assert repo.get_agent_instances("my-agent") == []


def test_create_and_list_agent_instances(repo):
    inst = repo.create_agent_instance("my-agent", "Support", None, [1, 2])
    assert inst["instance_name"] == "Support"
    assert inst["mcp_positions"] == [1, 2]
    assert inst["persona_id"] is None
    instances = repo.get_agent_instances("my-agent")
    assert len(instances) == 1


def test_create_agent_instance_with_persona(repo):
    persona = repo.create_persona("DevOps", [])
    inst = repo.create_agent_instance("my-agent", "Sales", str(persona["id"]), [3])
    assert str(inst["persona_id"]) == str(persona["id"])


def test_create_agent_instance_duplicate_name_raises(repo):
    repo.create_agent_instance("my-agent", "Support", None, [])
    with pytest.raises(Exception):
        repo.create_agent_instance("my-agent", "Support", None, [])


def test_update_agent_instance(repo):
    inst = repo.create_agent_instance("my-agent", "Support", None, [1])
    updated = repo.update_agent_instance(str(inst["id"]), "Sales", None, [2, 3])
    assert updated["instance_name"] == "Sales"
    assert updated["mcp_positions"] == [2, 3]


def test_update_nonexistent_agent_instance_returns_none(repo):
    result = repo.update_agent_instance(
        "00000000-0000-0000-0000-000000000000", "X", None, []
    )
    assert result is None


def test_delete_agent_instance(repo):
    inst = repo.create_agent_instance("my-agent", "Support", None, [])
    assert repo.delete_agent_instance(str(inst["id"])) is True
    assert repo.get_agent_instances("my-agent") == []


def test_delete_nonexistent_agent_instance(repo):
    assert repo.delete_agent_instance("00000000-0000-0000-0000-000000000000") is False


def test_get_instances_only_returns_matching_agent(repo):
    repo.create_agent_instance("agent-a", "Inst1", None, [])
    repo.create_agent_instance("agent-b", "Inst2", None, [])
    assert len(repo.get_agent_instances("agent-a")) == 1
    assert len(repo.get_agent_instances("agent-b")) == 1
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd tool-call-agent && python -m pytest tests/test_admin.py -k "agent_instance" -v
```

Expected: FAIL — `AttributeError: 'AdminRepository' object has no attribute 'get_agent_instances'`

- [ ] **Step 3: Add table creation to `_create_tables`**

In `tool-call-agent/admin_repository.py`, inside `_create_tables`, add after the `admin_personas` block:

```python
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS admin_agent_instances (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        agent_name TEXT NOT NULL,
                        instance_name TEXT NOT NULL,
                        persona_id UUID,
                        mcp_positions JSONB NOT NULL DEFAULT '[]',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE (agent_name, instance_name)
                    )
                """)
```

- [ ] **Step 4: Add the four repository methods**

At the end of `tool-call-agent/admin_repository.py`, add:

```python
    # ── Agent Instances ────────────────────────────────────────────────────

    def get_agent_instances(self, agent_name: str) -> list[dict]:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM admin_agent_instances WHERE agent_name = %s ORDER BY created_at",
                    (agent_name,),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def create_agent_instance(
        self,
        agent_name: str,
        instance_name: str,
        persona_id: str | None,
        mcp_positions: list[int],
    ) -> dict:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO admin_agent_instances
                           (agent_name, instance_name, persona_id, mcp_positions)
                       VALUES (%s, %s, %s::uuid, %s::jsonb) RETURNING *""",
                    (agent_name, instance_name, persona_id, json.dumps(mcp_positions)),
                )
                row = dict(cur.fetchone())
            conn.commit()
            return row
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_agent_instance(
        self,
        instance_id: str,
        instance_name: str,
        persona_id: str | None,
        mcp_positions: list[int],
    ) -> dict | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """UPDATE admin_agent_instances
                       SET instance_name = %s,
                           persona_id    = %s::uuid,
                           mcp_positions = %s::jsonb,
                           updated_at    = NOW()
                       WHERE id = %s::uuid
                       RETURNING *""",
                    (instance_name, persona_id, json.dumps(mcp_positions), instance_id),
                )
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_agent_instance(self, instance_id: str) -> bool:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM admin_agent_instances WHERE id = %s::uuid", (instance_id,)
                )
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd tool-call-agent && python -m pytest tests/test_admin.py -k "agent_instance" -v
```

Expected: 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add tool-call-agent/admin_repository.py tool-call-agent/tests/test_admin.py
git commit -m "feat(db): add admin_agent_instances table and repository methods"
```

---

## Task 2: Pydantic models + router endpoints

**Files:**
- Modify: `tool-call-agent/admin_models.py`
- Modify: `tool-call-agent/admin_router.py`
- Test: `tool-call-agent/tests/test_admin.py`

- [ ] **Step 1: Write failing API tests**

In `tool-call-agent/tests/test_admin.py`, find the `clean_tables` fixture (the `autouse=True` one used by API tests) and add `DELETE FROM admin_agent_instances`:

```python
@pytest.fixture(autouse=True)
def clean_tables():
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM admin_credentials")
        cur.execute("DELETE FROM admin_mcp_servers")
        cur.execute("DELETE FROM admin_skills")
        cur.execute("DELETE FROM admin_personas")
        cur.execute("DELETE FROM admin_agent_instances")
    conn.commit()
    conn.close()
    yield
```

Then add API tests at the end of the file:

```python
# ── Agent Instances API ────────────────────────────────────────────────────

def test_list_agent_instances_empty():
    response = http.get("/admin/agent-instances?agent_name=my-agent")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_list_agent_instances_via_api():
    response = http.post("/admin/agent-instances", json={
        "agent_name": "my-agent",
        "instance_name": "Support",
        "mcp_positions": [1, 2],
    })
    assert response.status_code == 201
    inst = response.json()
    assert inst["instance_name"] == "Support"
    assert inst["mcp_positions"] == [1, 2]
    assert inst["persona_id"] is None

    listed = http.get("/admin/agent-instances?agent_name=my-agent").json()
    assert len(listed) == 1
    assert listed[0]["id"] == inst["id"]


def test_create_duplicate_instance_returns_409():
    http.post("/admin/agent-instances", json={
        "agent_name": "my-agent", "instance_name": "Support", "mcp_positions": [],
    })
    response = http.post("/admin/agent-instances", json={
        "agent_name": "my-agent", "instance_name": "Support", "mcp_positions": [],
    })
    assert response.status_code == 409


def test_update_agent_instance_via_api():
    inst = http.post("/admin/agent-instances", json={
        "agent_name": "my-agent", "instance_name": "Support", "mcp_positions": [1],
    }).json()
    response = http.put(f"/admin/agent-instances/{inst['id']}", json={
        "instance_name": "Sales",
        "mcp_positions": [2, 3],
    })
    assert response.status_code == 200
    assert response.json()["instance_name"] == "Sales"


def test_update_nonexistent_instance_returns_404():
    response = http.put(
        "/admin/agent-instances/00000000-0000-0000-0000-000000000000",
        json={"instance_name": "X", "mcp_positions": []},
    )
    assert response.status_code == 404


def test_delete_agent_instance_via_api():
    inst = http.post("/admin/agent-instances", json={
        "agent_name": "my-agent", "instance_name": "Support", "mcp_positions": [],
    }).json()
    response = http.delete(f"/admin/agent-instances/{inst['id']}")
    assert response.status_code == 200
    assert http.get("/admin/agent-instances?agent_name=my-agent").json() == []


def test_delete_nonexistent_instance_returns_404():
    response = http.delete("/admin/agent-instances/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd tool-call-agent && python -m pytest tests/test_admin.py -k "agent_instances_via_api or agent_instances_empty or duplicate_instance or nonexistent_instance" -v
```

Expected: FAIL — 404 from router (routes don't exist yet)

- [ ] **Step 3: Add Pydantic models**

In `tool-call-agent/admin_models.py`, add at the end:

```python
class AgentInstanceRequest(BaseModel):
    agent_name: str
    instance_name: str
    persona_id: UUID | None = None
    mcp_positions: list[int] = []


class AgentInstanceUpdateRequest(BaseModel):
    instance_name: str
    persona_id: UUID | None = None
    mcp_positions: list[int] = []


class AgentInstanceResponse(BaseModel):
    id: UUID
    agent_name: str
    instance_name: str
    persona_id: UUID | None
    mcp_positions: list[int]
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Add router endpoints**

In `tool-call-agent/admin_router.py`, update the import from `admin_models` to include the new models:

```python
from admin_models import (
    CredentialsRequest,
    CredentialsResponse,
    McpServerRequest,
    McpServerResponse,
    PersonaRequest,
    PersonaResponse,
    SkillResponse,
    AgentInstanceRequest,
    AgentInstanceUpdateRequest,
    AgentInstanceResponse,
)
```

Then add at the end of the file:

```python
# ── Agent Instances ────────────────────────────────────────────────────────

@router.get("/agent-instances", response_model=list[AgentInstanceResponse])
async def get_agent_instances(agent_name: str):
    return _get_repo().get_agent_instances(agent_name)


@router.post("/agent-instances", response_model=AgentInstanceResponse, status_code=201)
async def create_agent_instance(request: AgentInstanceRequest):
    try:
        return _get_repo().create_agent_instance(
            request.agent_name,
            request.instance_name,
            str(request.persona_id) if request.persona_id else None,
            request.mcp_positions,
        )
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail="Instance name already exists for this agent",
            )
        raise


@router.put("/agent-instances/{instance_id}", response_model=AgentInstanceResponse)
async def update_agent_instance(instance_id: str, request: AgentInstanceUpdateRequest):
    instance = _get_repo().update_agent_instance(
        instance_id,
        request.instance_name,
        str(request.persona_id) if request.persona_id else None,
        request.mcp_positions,
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Agent instance not found")
    return instance


@router.delete("/agent-instances/{instance_id}")
async def delete_agent_instance(instance_id: str):
    if not _get_repo().delete_agent_instance(instance_id):
        raise HTTPException(status_code=404, detail="Agent instance not found")
    return {"status": "ok"}
```

- [ ] **Step 5: Run all admin tests**

```bash
cd tool-call-agent && python -m pytest tests/test_admin.py -v
```

Expected: all tests PASS (including new agent instance tests)

- [ ] **Step 6: Commit**

```bash
git add tool-call-agent/admin_models.py tool-call-agent/admin_router.py tool-call-agent/tests/test_admin.py
git commit -m "feat(api): add agent instance CRUD endpoints"
```

---

## Task 3: Angular admin service

**Files:**
- Modify: `tool-call-ui/src/app/services/admin.service.ts`

- [ ] **Step 1: Add the AgentInstance interface and service methods**

In `tool-call-ui/src/app/services/admin.service.ts`, add the interface after the `PersonaData` interface:

```typescript
export interface AgentInstance {
  id: string;
  agent_name: string;
  instance_name: string;
  persona_id: string | null;
  mcp_positions: number[];
  created_at: string;
  updated_at: string;
}
```

Then add these four methods to the `AdminService` class, after `deletePersona`:

```typescript
  getAgentInstances(agentName: string) {
    return firstValueFrom(
      this.http.get<AgentInstance[]>(
        `${API}/agent-instances?agent_name=${encodeURIComponent(agentName)}`
      )
    );
  }

  createAgentInstance(
    agentName: string,
    instanceName: string,
    personaId: string | null,
    mcpPositions: number[]
  ) {
    return firstValueFrom(
      this.http.post<AgentInstance>(`${API}/agent-instances`, {
        agent_name: agentName,
        instance_name: instanceName,
        persona_id: personaId,
        mcp_positions: mcpPositions,
      })
    );
  }

  updateAgentInstance(
    id: string,
    instanceName: string,
    personaId: string | null,
    mcpPositions: number[]
  ) {
    return firstValueFrom(
      this.http.put<AgentInstance>(`${API}/agent-instances/${id}`, {
        instance_name: instanceName,
        persona_id: personaId,
        mcp_positions: mcpPositions,
      })
    );
  }

  deleteAgentInstance(id: string) {
    return firstValueFrom(this.http.delete(`${API}/agent-instances/${id}`));
  }
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd tool-call-ui && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add tool-call-ui/src/app/services/admin.service.ts
git commit -m "feat(ui): add AgentInstance service methods"
```

---

## Task 4: AgentConfigure component

**Files:**
- Create: `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.ts`
- Create: `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.html`
- Create: `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.css`

- [ ] **Step 1: Create the component class**

Create `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.ts`:

```typescript
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminService, AgentInstance, PersonaData, McpServer } from '../../../services/admin.service';
import { AgentsService, AgentDeployment } from '../../../services/agents.service';

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

- [ ] **Step 2: Create the template**

Create `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.html`:

```html
@if (error) {
  <p class="error">{{ error }}</p>
}

<div class="agent-selector">
  <label class="field-label">Agent</label>
  @if (agents.length === 0) {
    <p class="muted">No agents deployed. Deploy an agent first.</p>
  } @else {
    <select [(ngModel)]="selectedAgent" (ngModelChange)="onAgentChange()">
      @for (a of agents; track a.name) {
        <option [value]="a.name">{{ a.name }}</option>
      }
    </select>
  }
</div>

@if (selectedAgent) {
  <div class="instances-header">
    <span class="muted">{{ instances.length }} instance{{ instances.length !== 1 ? 's' : '' }}</span>
    <button class="btn-add" (click)="addInstance()">+ Add Instance</button>
  </div>

  @if (loading) {
    <p class="muted">Loading…</p>
  }

  <div class="instance-list">
    @for (form of instances; track $index; let i = $index) {
      <div class="instance-row" [class.expanded]="form.expanded">
        <div class="instance-header" (click)="toggle(form)">
          <div class="instance-summary">
            <span class="instance-name">{{ form.instance_name || 'New Instance' }}</span>
            @if (!form.expanded && form.id) {
              <span class="muted summary-text">
                Persona: {{ personaName(form.persona_id) }} · MCP: {{ mcpSummary(form.mcp_positions) }}
              </span>
            }
          </div>
          <div class="instance-actions">
            <button class="btn-delete" (click)="deleteInstance(form, i); $event.stopPropagation()">Delete</button>
            <span class="chevron">{{ form.expanded ? '▲' : '▼' }}</span>
          </div>
        </div>

        @if (form.expanded) {
          <div class="instance-body">
            @if (form.error) {
              <p class="error">{{ form.error }}</p>
            }
            <div class="fields">
              <div class="field">
                <label class="field-label">Instance Name</label>
                <input [(ngModel)]="form.instance_name" placeholder="e.g. Customer Support" />
              </div>
              <div class="field">
                <label class="field-label">Persona</label>
                <select [(ngModel)]="form.persona_id">
                  <option [ngValue]="null">— None —</option>
                  @for (p of personas; track p.id) {
                    <option [value]="p.id">{{ p.name }}</option>
                  }
                </select>
              </div>
              <div class="field">
                <label class="field-label">MCP Servers</label>
                <div class="mcp-list">
                  @for (s of mcpServers; track s.position) {
                    <label class="mcp-item">
                      <input
                        type="checkbox"
                        [checked]="isMcpSelected(form, s.position)"
                        (change)="toggleMcp(form, s.position)"
                      />
                      {{ s.name }}
                    </label>
                  }
                  @if (mcpServers.length === 0) {
                    <span class="muted">No MCP servers configured.</span>
                  }
                </div>
              </div>
            </div>
            <div class="instance-footer">
              <button class="btn-save" (click)="save(form)" [disabled]="form.saving">
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

- [ ] **Step 3: Create the styles**

Create `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.css`:

```css
.error  { color: #f85149; font-size: 13px; margin-bottom: 12px; }
.muted  { color: #8b949e; font-size: 13px; }

.agent-selector {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.agent-selector select {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 5px;
  color: #e6edf3;
  font-size: 13px;
  padding: 6px 10px;
  min-width: 280px;
}

.field-label {
  color: #8b949e;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
}

.instances-header {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.btn-add {
  background: none;
  border: 1px solid #238636;
  border-radius: 5px;
  color: #3fb950;
  cursor: pointer;
  font-size: 12px;
  padding: 4px 12px;
}

.btn-add:hover { background: #0d2a13; }

.instance-list { display: flex; flex-direction: column; gap: 6px; }

.instance-row {
  border: 1px solid #30363d;
  border-radius: 6px;
  overflow: hidden;
}

.instance-row.expanded { border-color: #58a6ff; }

.instance-header {
  align-items: center;
  background: #161b22;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  user-select: none;
}

.instance-summary { display: flex; align-items: center; gap: 12px; min-width: 0; }

.instance-name { color: #e6edf3; font-size: 13px; font-weight: 500; }

.summary-text { font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.instance-actions { align-items: center; display: flex; gap: 8px; flex-shrink: 0; }

.chevron { color: #8b949e; font-size: 11px; }

.instance-body {
  background: #0d1117;
  border-top: 1px solid #1c2128;
  padding: 14px;
}

.fields {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 14px;
  margin-bottom: 12px;
}

.field { display: flex; flex-direction: column; gap: 6px; }

.field input, .field select {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 4px;
  color: #e6edf3;
  font-size: 12px;
  padding: 6px 8px;
  width: 100%;
  box-sizing: border-box;
}

.mcp-list { display: flex; flex-direction: column; gap: 5px; }

.mcp-item { align-items: center; color: #e6edf3; display: flex; font-size: 12px; gap: 6px; }

.instance-footer { display: flex; justify-content: flex-end; }

.btn-save {
  background: #238636;
  border: none;
  border-radius: 5px;
  color: #fff;
  cursor: pointer;
  font-size: 12px;
  padding: 5px 16px;
}

.btn-save:disabled { background: #1a4a1f; color: #6e7681; cursor: not-allowed; }

.btn-delete {
  background: none;
  border: 1px solid #f85149;
  border-radius: 4px;
  color: #f85149;
  cursor: pointer;
  font-size: 11px;
  padding: 2px 8px;
}

.btn-delete:hover { background: #3d1f1f; }
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd tool-call-ui && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add tool-call-ui/src/app/admin/agents/agent-configure/
git commit -m "feat(ui): add AgentConfigure component"
```

---

## Task 5: Wire Configure tab into Agents panel

**Files:**
- Modify: `tool-call-ui/src/app/admin/agents/agents.ts`
- Modify: `tool-call-ui/src/app/admin/agents/agents.html`

- [ ] **Step 1: Update the Agents component class**

Replace the contents of `tool-call-ui/src/app/admin/agents/agents.ts`:

```typescript
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AgentsService } from '../../services/agents.service';
import { DeployForm } from './deploy-form/deploy-form';
import { AgentList } from './agent-list/agent-list';
import { AgentConfigure } from './agent-configure/agent-configure';

@Component({
  selector: 'app-agents',
  standalone: true,
  imports: [CommonModule, DeployForm, AgentList, AgentConfigure],
  templateUrl: './agents.html',
  styleUrl: './agents.css',
})
export class Agents implements OnInit {
  tab: 'deployments' | 'view' | 'configure' = 'deployments';
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

- [ ] **Step 2: Update the template**

Replace the contents of `tool-call-ui/src/app/admin/agents/agents.html`:

```html
<h2>Agents</h2>

@if (kubeconfigError) {
  <div class="banner">{{ kubeconfigError }}</div>
}

<div class="tabs">
  <button class="tab" [class.active]="tab === 'deployments'" (click)="tab = 'deployments'">
    Deployments
  </button>
  <button class="tab" [class.active]="tab === 'view'" (click)="tab = 'view'">
    View
  </button>
  <button class="tab" [class.active]="tab === 'configure'" (click)="tab = 'configure'">
    Configure
  </button>
</div>

@if (tab === 'deployments') {
  <app-deploy-form (deployed)="onDeployed()" />
}
@if (tab === 'view') {
  <app-agent-list />
}
@if (tab === 'configure') {
  <app-agent-configure />
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd tool-call-ui && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Smoke test in the browser**

Start both servers if not running:
```bash
# Terminal 1
cd tool-call-agent && uvicorn main:app --reload

# Terminal 2
cd tool-call-ui && ng serve
```

Navigate to `http://localhost:4200/admin/agents`. Verify:
1. Three tabs visible: Deployments, View, Configure
2. Configure tab shows agent dropdown populated with running K8s agents
3. "+ Add Instance" adds a blank expanded row
4. Filling in a name, persona, MCP servers and clicking Save persists the instance
5. Row collapses after save, showing summary (persona name, MCP server names)
6. Expanding a saved row shows the saved values
7. Delete removes the row after confirmation

- [ ] **Step 5: Commit**

```bash
git add tool-call-ui/src/app/admin/agents/agents.ts tool-call-ui/src/app/admin/agents/agents.html
git commit -m "feat(ui): add Configure tab to Agents panel"
```
