# tool-call-ui

Angular 20 frontend for the tool-call-approval demo. Renders a real-time chat
interface with inline tool-call approval cards, connected to the FastAPI backend
via SSE and REST.

## Setup

```bash
npm install
ng serve          # runs on http://localhost:4200
```

Requires the `tool-call-fastapi` backend running on `http://localhost:8000`.

## Features

- **Chat window** — user and assistant messages rendered in a dark-themed UI
- **Tool approval cards** — when the agent wants to call a tool, an approval card
  appears with the tool name, input arguments, and Approve/Reject buttons
- **SSE streaming** — agent events (thinking, tool calls, results, final message)
  stream in real time from the backend
- **Automatic reconnect** — the SSE connection is re-opened after each response

## Components

| Component     | File                                          | Description                                     |
|---------------|-----------------------------------------------|-------------------------------------------------|
| `Chat`        | `components/chat/chat.ts`                     | Full-page chat UI; manages SSE and message list |
| `ToolApproval`| `components/tool-approval/tool-approval.ts`   | Approval card shown for pending tool calls      |

## Running Tests

```bash
ng test --watch=false --browsers=ChromeHeadless
```

## Running as Production Build

```bash
ng build
```

Output in `dist/tool-call-ui/browser/`.
