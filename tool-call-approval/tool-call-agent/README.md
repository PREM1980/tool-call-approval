# tool-call-agent

FastAPI backend for the tool-call-approval demo. Runs a Claude agent (via AWS Bedrock) with human-in-the-loop tool approval, streaming events over SSE and WebSocket. Includes Langfuse tracing and a mock mode that requires no API keys.

---

## Prerequisites

- Python 3.12+
- AWS account with Bedrock access (for the real agent)
- Docker + Docker Compose (for Langfuse)

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# AWS Bedrock (required for real agent)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# Langfuse (auto-set if using docker compose)
LANGFUSE_PUBLIC_KEY=pk-lf-local-tool-call-approval
LANGFUSE_SECRET_KEY=sk-lf-local-tool-call-approval
LANGFUSE_HOST=http://localhost:3000
```

### 3. Start Langfuse

Langfuse runs as a set of Docker containers (Postgres, ClickHouse, Redis, MinIO). Start it from the **project root**:

```bash
cd ..                        # go to tool-call-approval/
docker compose up -d
```

First boot takes ~30 seconds while the database initialises. Check readiness:

```bash
docker compose ps            # all services should show "healthy"
```

Langfuse UI: `http://localhost:3000`
Login: `admin@local.dev` / `admin`
Project: **tool-call-approval** (auto-created, no manual setup needed)

To stop Langfuse:

```bash
docker compose down          # keeps data volumes
docker compose down -v       # also removes all data
```

### 4. Start the server

**With real AWS Bedrock + Langfuse:**

```bash
uvicorn main_websocket:app --reload
```

**Mock mode (no API key required):**

```bash
uvicorn main_mock:app --reload
```

Server starts on `http://localhost:8000`.

---

## Running the Python client

A minimal SSE client for testing without the Angular frontend:

```bash
# default question (no tool call triggered)
python client.py

# custom message
python client.py "Explain the difference between TCP and UDP"
```

The client prints streamed output to the terminal and auto-approves any tool calls. After each run, the trace appears in Langfuse at `http://localhost:3000`.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions` | Create a new agent session |
| POST | `/sessions/{id}/chat` | Send a user message (SSE mode) |
| GET  | `/sessions/{id}/stream` | SSE stream of agent events |
| POST | `/sessions/{id}/approve` | Approve or reject a pending tool call (SSE mode) |
| WS   | `/sessions/{id}/ws` | WebSocket connection (chat + approval in one connection) |

### WebSocket message format

#### Client → Server

```json
{ "type": "chat", "message": "What is 1234 × 5678?" }
{ "type": "approve", "approved": true }
```

#### Server → Client

Same event shapes as SSE (see table below).

---

## SSE / WebSocket event types

| `type` | Additional fields | Description |
|--------|-------------------|-------------|
| `thinking` | `content` | Agent is processing |
| `tool_call_pending` | `tool_use_id`, `tool_name`, `tool_input` | Agent wants to call a tool — awaits approval |
| `tool_result` | `tool_use_id`, `tool_name`, `result` | Tool executed successfully |
| `tool_rejected` | `tool_use_id`, `tool_name` | Tool call was rejected |
| `message` | `content` | Assistant response chunk |
| `done` | — | Turn complete |
| `error` | `content` | Unexpected error |

---

## Available tools

All tools require human approval before execution.

| Tool | Description |
|------|-------------|
| `calculate` | Evaluate a math expression (`2 + 3`, `math.sqrt(16)`) |
| `get_weather` | Weather for a city |
| `search_web` | Web search |

---

## Mock mode trigger keywords

The mock agent matches these keywords to simulate tool calls:

| Keyword | Tool simulated |
|---------|----------------|
| `calculate`, `math`, `×`, `*`, `sqrt` | `calculate` |
| `weather`, `temperature`, `forecast` | `get_weather` |
| `search`, `find`, `look up` | `search_web` |

Any other message returns a plain text fallback.

---

## Langfuse tracing

Every real agent run creates a trace in Langfuse with:

- **Input** — user message
- **Output** — final assistant response
- **Tool spans** — one span per tool call, with arguments, approval status, and result
- **User ID** — session ID
- **Tags** — `tool-call-approval`

View traces at `http://localhost:3000` → **tool-call-approval** project → **Traces**.

---

## Logging

The service emits structured JSON logs to stdout. Each line is a valid JSON object:

```json
{"timestamp": "2026-05-20T12:00:00", "level": "INFO", "logger": "main", "service": "tool-call-agent", "message": "session created", "session_id": "abc-123"}
```

When running via Docker Compose, Promtail ships these logs to Loki automatically. Query them in Grafana at `http://localhost:3001` → **Explore** → select **Loki** datasource.

---

## Project files

| File | Description |
|------|-------------|
| `main_websocket.py` | FastAPI app with SSE + WebSocket endpoints |
| `main_mock.py` | Same but uses mock agent (no API key needed) |
| `agent.py` | Agent definition, event processing, Langfuse tracing |
| `mock_agent.py` | Mock agent with canned responses |
| `tools.py` | Tool implementations |
| `models.py` | Pydantic request/response models |
| `client.py` | CLI client for testing via SSE |

---

## Tests

```bash
pytest -v
```

---

## Docker

```bash
# Build
docker build -t tool-call-agent:latest .

# Run (point at host Postgres and Langfuse)
docker run --rm \
  -e AWS_DEFAULT_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  -e POSTGRES_URL=postgresql+psycopg2://postgres:postgres@host.docker.internal:5432/postgres \
  -e LANGFUSE_PUBLIC_KEY=pk-lf-local-tool-call-approval \
  -e LANGFUSE_SECRET_KEY=sk-lf-local-tool-call-approval \
  -e LANGFUSE_HOST=http://host.docker.internal:3000 \
  -p 8000:8000 \
  tool-call-agent:latest
```

---

## Kubernetes

```bash
# Copy and fill in secret values (base64-encode each value)
cp ../k8s/tool-call-agent/secret.yaml.example ../k8s/tool-call-agent/secret.yaml
# Edit secret.yaml with your real base64-encoded credentials

# Apply all manifests
kubectl apply -f ../k8s/tool-call-agent/
```
