# Tool Call Approval - Real Agent Mode

This guide runs the real Kubernetes operations agent locally with the Angular UI.
The local stack is:

```text
tool-call-ui (:4200) -> tool-call-api (:8080) -> tool-call-agent (:8000)
```

Use real agent mode when you want the app to call an actual LLM provider
(AWS Bedrock, GCP Vertex AI, or a local OpenAI-compatible endpoint) and require
human approval before tools run.

## Prerequisites

- Python 3.12+
- Node.js/npm compatible with Angular 20
- Docker + Docker Compose
- `kubectl` on your PATH if you want the Kubernetes tool to run locally
- AWS Bedrock, GCP Vertex AI, or local OpenAI-compatible endpoint credentials

## 1. Start Postgres and Langfuse

From this directory:

```bash
docker compose up -d postgres clickhouse minio redis langfuse-web langfuse-worker
docker compose ps
```

Langfuse runs at `http://localhost:3000`.

Local login:

```text
admin@local.dev / admin1234
```

The compose file exposes Postgres to your host on port `5433`. Services inside
Docker use port `5432`, but local Python processes should use `localhost:5433`.

## 2. Install Python Dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r tool-call-agent/requirements.txt -r tool-call-api/requirements.txt
```

## 3. Configure the Agent

Create the agent env file:

```bash
cp tool-call-agent/.env.example tool-call-agent/.env
```

Edit `tool-call-agent/.env` and set the provider credentials you want to use.

For AWS Bedrock:

```env
LLM_PROVIDER=AWS
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
POSTGRES_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/postgres
LANGFUSE_PUBLIC_KEY=pk-lf-local-tool-call-approval
LANGFUSE_SECRET_KEY=sk-lf-local-tool-call-approval
LANGFUSE_HOST=http://localhost:3000
```

For GCP Vertex AI:

```env
LLM_PROVIDER=GCP
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-east5
POSTGRES_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/postgres
LANGFUSE_PUBLIC_KEY=pk-lf-local-tool-call-approval
LANGFUSE_SECRET_KEY=sk-lf-local-tool-call-approval
LANGFUSE_HOST=http://localhost:3000
```

For the local/AIP OpenAI-compatible endpoint:

```env
LLM_PROVIDER=LOCAL
OPENAI_API_KEY=sk-your-local-endpoint-key
MODEL_ID=nemotron-3-super
BASE_URL=https://models.k8s.aip.mitre.org/v1
LOCAL_VERIFY_SSL=false
POSTGRES_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/postgres
LANGFUSE_PUBLIC_KEY=pk-lf-local-tool-call-approval
LANGFUSE_SECRET_KEY=sk-lf-local-tool-call-approval
LANGFUSE_HOST=http://localhost:3000
```

The Admin credentials page stores app settings such as kubeconfig, but the real
LLM credentials must still be available to the agent process through `.env` or
your normal cloud SDK environment.

## 4. Run the Agent API

In terminal 1:

```bash
source .venv/bin/activate
cd tool-call-agent
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

## 5. Run the Web Gateway

In terminal 2:

```bash
source .venv/bin/activate
cd tool-call-api
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Gateway defaults:

```env
AGENT_BACKEND_URL=http://localhost:8000
CORS_ORIGIN=http://localhost:4200
```

## 6. Run the Angular UI

In terminal 3:

```bash
cd tool-call-ui
npm install
npm start
```

Open:

```text
http://localhost:4200
```

Use the `SSE` mode in the chat UI for real agent mode. The WebSocket toggle is
for the mock/direct backend path and is not the normal real-agent path.

## Kubernetes Access

For Kubernetes questions, the agent executes `kubectl` after you approve the
tool call. You can provide cluster access in either of these ways:

```bash
# Option 1: rely on your shell's kubectl config
kubectl get pods
```

Or use the UI:

```text
Admin -> Credentials -> paste kubeconfig -> Save
```

When kubeconfig is saved in the UI, the chat sends it to the agent for the
current session.

## Optional Services

The `tool-call-k8s` service powers Kubernetes deployment management screens.
It is not required for basic real-agent chat, but you can run it separately:

```bash
source .venv/bin/activate
pip install -r tool-call-k8s/requirements.txt
cd tool-call-k8s
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Grafana/Loki logging is also defined in `docker-compose.yml` and can be started
when needed:

```bash
docker compose up -d loki grafana promtail
```

Grafana runs at `http://localhost:3001`.

## Stop the Stack

```bash
docker compose down
```

To remove local Docker data too:

```bash
docker compose down -v
```
