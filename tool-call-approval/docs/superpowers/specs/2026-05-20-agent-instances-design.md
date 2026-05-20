# Agent Instance Configuration Design

## Goal

Add a Configure tab to the Agents admin panel where each K8s agent deployment can have multiple named instances, each with its own persona and MCP server assignments stored in Postgres.

## Architecture

### Concepts

- **Agent** — a running K8s deployment (e.g. `tool-call-agent-ui-agents`). Already managed by the Agents panel (Deploy / View tabs).
- **Instance** — a named logical configuration within an agent. One agent hosts multiple instances (e.g. "Customer Support", "Sales Bot"), each with its own persona and MCP servers.

### Data Model

New table `admin_agent_instances` in Postgres:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key, auto-generated |
| `agent_name` | TEXT | K8s deployment name, e.g. `tool-call-agent-ui-agents` |
| `instance_name` | TEXT | Customer-friendly name, e.g. "Customer Support" |
| `persona_id` | UUID NULL | FK to `admin_personas.id` |
| `mcp_positions` | JSONB | Array of ints referencing `admin_mcp_servers.position`, e.g. `[1, 3]` |
| `created_at` | TIMESTAMP | Set on insert |
| `updated_at` | TIMESTAMP | Updated on upsert |

Constraint: `(agent_name, instance_name)` unique — no duplicate instance names per agent.

### Backend

New methods in `admin_repository.py`:
- `get_agent_instances(agent_name) -> list[dict]`
- `create_agent_instance(agent_name, instance_name, persona_id, mcp_positions) -> dict`
- `update_agent_instance(id, instance_name, persona_id, mcp_positions) -> dict`
- `delete_agent_instance(id) -> bool`

New routes in `admin_router.py`:
- `GET /admin/agent-instances?agent_name=<name>` — list instances for an agent
- `POST /admin/agent-instances` — create instance
- `PUT /admin/agent-instances/{id}` — update instance
- `DELETE /admin/agent-instances/{id}` — delete instance

### Frontend

New Angular component `AgentConfigure` at `admin/agents/agent-configure/`.

**UI flow:**
1. On load: fetch agents (`GET /api/agents`), personas, MCP servers in parallel
2. Agent dropdown at top — selecting one loads its instances (`GET /admin/agent-instances?agent_name=...`)
3. Instances render as collapsible rows — each shows instance name, persona summary, MCP summary in collapsed state
4. Expanding a row shows: instance name input, persona dropdown, MCP server checkboxes, Save + Delete buttons
5. "+ Add Instance" button appends a blank expanded row
6. Save calls POST (new) or PUT (existing); row collapses on success with "Saved" flash
7. Delete calls DELETE; row is removed from list

**New service method** in `admin.service.ts`:
- `getAgentInstances(agentName: string) -> AgentInstance[]`
- `createAgentInstance(agentName, instanceName, personaId, mcpPositions) -> AgentInstance`
- `updateAgentInstance(id, instanceName, personaId, mcpPositions) -> AgentInstance`
- `deleteAgentInstance(id) -> void`

**Agents panel** (`agents.ts`) gains a third tab: Deploy | View | Configure, routing to the new component.

## Error Handling

- Duplicate `(agent_name, instance_name)` → 409, shown inline on the row
- Unknown `persona_id` → 422, shown inline
- Agent not found in K8s (stale dropdown) → still allowed; config is stored independently of pod state

## Testing

- Repository: create, list, update, delete, duplicate name returns error
- Router: GET list, POST create, PUT update, DELETE
- Angular: selecting agent loads instances, add/save/delete row interactions
