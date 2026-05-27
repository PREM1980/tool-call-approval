# Compact Tool Approval Card — Design Spec

**Date:** 2026-05-23
**Status:** Approved

## Problem

The current tool approval card is tall (header + body + footer, with a full JSON `<pre>` block) and interrupts the chat flow more than necessary. The JSON argument display is verbose and hard to read at a glance.

## Goal

Replace the multi-section card with a single compact inline row that shows the full reconstructed command string and the approve/reject buttons side by side.

## Design

### Layout

Single `<div class="card">` row with flex layout — no card-header, card-body, or card-footer:

```
┌──────────────────────────────────────────────────────────┐
│  ⚙  kubectl get pods -n default         [✕ Deny][✓ Allow] │
└──────────────────────────────────────────────────────────┘
```

- Yellow `border-warning` border retained for visual distinction
- `shadow-sm rounded-3 my-2` spacing unchanged
- `⚙️` icon on the left
- Command in `font-monospace text-primary` fills remaining space (`flex-grow-1`)
- `Deny` and `Allow` buttons on the right, same outline-danger / outline-success styling

### Command Formatting (`formattedCommand` getter)

| Tool | `tool_input` shape | Display |
|------|-------------------|---------|
| `kubectl` | `{ args: "get pods -n default" }` | `kubectl get pods -n default` |
| Other | any | `tool_name: first_arg_value` (fallback) |

### Files Changed

| File | Change |
|------|--------|
| `tool-call-ui/src/app/components/tool-approval/tool-approval.html` | Replace 3-section card with single flex row |
| `tool-call-ui/src/app/components/tool-approval/tool-approval.ts` | Update `formattedCommand` getter |

## Out of Scope

- No changes to approve/reject event logic
- No changes to how the backend sends tool calls
- No styling changes to other components
