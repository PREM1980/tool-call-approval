# Move Configure Logic to Agent-WS — Design

**Date:** 2026-05-21  
**Status:** Approved

## Goal

Relocate the `AgentConfigure` component from the Agents panel's Configure tab into the `Agent-WS` page, which renders it directly (no tabs).

## Current State

- `/admin/agents` has three tabs: Deployments, View, Configure.
- Configure tab renders `AgentConfigure` (agent instance CRUD — persona + MCP server assignments).
- `/admin/agent-ws` is a stub ("Coming soon").

## Target State

- `/admin/agents` has two tabs: Deployments, View.
- `/admin/agent-ws` renders `AgentConfigure` directly under an `<h2>Agent-WS</h2>` heading.

## Changes

### File moves

| From | To |
|---|---|
| `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.ts` | `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.ts` |
| `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.html` | `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.html` |
| `tool-call-ui/src/app/admin/agents/agent-configure/agent-configure.css` | `tool-call-ui/src/app/admin/agent-ws/agent-configure/agent-configure.css` |

### Updated files

| File | Change |
|---|---|
| `agent-configure.ts` (moved) | Fix relative imports: `../../services/` → `../services/` |
| `agent-ws/agent-ws.ts` | Replace stub with standalone component importing `AgentConfigure`; render it under `<h2>Agent-WS</h2>` |
| `agents/agents.ts` | Remove `AgentConfigure` import; narrow tab type to `'deployments' \| 'view'` |
| `agents/agents.html` | Remove Configure tab button and `@if (tab === 'configure')` block |

### No changes needed

- `admin.routes.ts` — routes unchanged; Agent-WS already registered.
- All backend files — no API changes.
- `admin.service.ts`, `agents.service.ts` — no service changes.

## Constraints

- No new routes.
- No new components (AgentConfigure already exists; Agent-WS component is updated in-place).
- Import paths in `agent-configure.ts` must be adjusted for the new folder depth.
