# tool-call-fastapi

FastAPI backend for the tool-call-approval demo. Runs an Anthropic Claude agent
with human-in-the-loop tool approval via Server-Sent Events (SSE).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
uvicorn main:app --reload
```

The server starts on `http://localhost:8000`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions` | Create a new agent session |
| POST | `/sessions/{id}/chat` | Send a user message |
| GET  | `/sessions/{id}/stream` | SSE stream of agent events |
| POST | `/sessions/{id}/approve` | Approve or reject a pending tool call |

## SSE Event Types

| `type` | Additional fields | Description |
|--------|-------------------|-------------|
| `thinking` | `content` | Agent is processing |
| `tool_call_pending` | `tool_use_id`, `tool_name`, `tool_input` | Agent wants to call a tool — **awaits approval** |
| `tool_result` | `tool_use_id`, `tool_name`, `result` | Tool executed successfully |
| `tool_rejected` | `tool_use_id`, `tool_name` | Tool call was rejected by the user |
| `message` | `content` | Final assistant response |
| `done` | — | Stream complete |
| `error` | `content` | Unexpected error |

## Available Tools

| Tool | Description |
|------|-------------|
| `calculate` | Evaluate a math expression (`2 + 3`, `math.sqrt(16)`) |
| `get_weather` | Mock weather for London, New York, Tokyo, Paris, Sydney |
| `search_web` | Mock web search returning a stub result |

## Tests

```bash
pytest -v
```
