# Agents View Redesign — Design Spec

**Date:** 2026-05-24
**Status:** Approved

---

## Overview

Replace the plain Bootstrap table on the Agents → View tab with an Ops Dashboard layout: a stats summary bar at the top followed by flat agent rows. The goal is a polished, information-dense design that feels like a real Kubernetes ops tool.

---

## Layout

### Stats Bar

Four stat cards in a horizontal row above the agent list:

| Card | Value | Color |
| ---- | ----- | ----- |
| Running | count of agents with status `Running` | Green (`#16a34a`) |
| Total | total agent count | Neutral (`#0f172a`) |
| Pending | count with status `Pending` | Amber (`#d97706`) |
| Failed | count with status `Failed` | Red (`#dc2626`) |

Each card: white background, `1px #e2e8f0` border, `12px` border-radius, icon pill on the left, large bold number + small uppercase label on the right.

Counts are derived from the already-fetched `agents` array in `AgentList` — no extra API calls.

### Agent Rows

Each agent renders as a flat card row (no expand/collapse). Columns left to right:

1. **Name col** (`flex: 0 0 170px`) — agent name in bold, namespace as a small pill tag below
2. **Image col** (`flex: 1`) — small `IMAGE` uppercase label, monospace image string (truncate with ellipsis)
3. **Replicas col** (`flex: 0 0 auto`) — small `REPLICAS` label, `−` / count / `+` stepper
4. **Status col** (`flex: 0 0 110px`) — colored pill badge with a dot: green=Running, amber=Pending, red=Failed, blue=Restarting, grey=unknown
5. **Actions col** (`flex: 0 0 auto`) — `Restart` (amber fill) and `Delete` (red fill) buttons

Row styling: white background, `1px #e2e8f0` border, `12px` radius, hover lifts with `box-shadow`.

### Empty State

When no agents are deployed: centered message "No agents deployed yet" with a subtle icon.

### Refresh Hint

Small `text-secondary` line at the bottom-right: "Auto-refreshes every 10s" — communicates the existing polling behavior without adding UI chrome.

---

## Component Changes

Only `agent-list.html` and `agent-list.css` change. `agent-list.ts` is unchanged — all data and logic (polling, scale, restart, delete) stay as-is.

### `agent-list.html`

- Remove the `<table>` entirely
- Add stats bar above the list using inline template expressions for counts (e.g. `agents | filter by status`-style logic in the component or pure template expressions)
- Replace each `<tr>` with a flex row div
- Add the refresh hint at the bottom

### `agent-list.css`

Full replacement with the new styles scoped to the component. Uses CSS custom properties where practical. No new dependencies — stays within Bootstrap 5 + plain CSS.

---

## Non-Goals

- No expandable row details
- No sorting or filtering
- No pagination
- No changes to `agent-list.ts`, `agents.ts`, `deploy-form`, or any service
