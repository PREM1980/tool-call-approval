# tool-call-web

API gateway that sits between `tool-call-ui` and `tool-call-agent`. The Angular UI communicates exclusively with this service; it forwards requests to the agent backend.

## Architecture

```
tool-call-ui (:4200) → tool-call-web (:8080) → tool-call-agent (:8000)
```

## Routes

| Method | Path | Forwards to |
|---|---|---|
| POST | `/api/sessions` | `POST /sessions` |
| POST | `/api/sessions/{id}/chat` | `POST /sessions/{id}/chat` |
| GET | `/api/sessions/{id}/stream` | `GET /sessions/{id}/stream` (SSE) |
| GET | `/api/sessions/{id}/history` | `GET /sessions/{id}/history` |
| POST | `/api/sessions/{id}/approve` | `POST /sessions/{id}/approve` |

## Setup

```bash
cp .env.example .env
pip install -r requirements.txt
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AGENT_BACKEND_URL` | `http://localhost:8000` | URL of the `tool-call-agent` backend |

## Running

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

## Tests

```bash
pytest -v
```

---

## Docker

```bash
# Build
docker build -t tool-call-web:latest .

# Run (forwarding to a local backend)
docker run --rm \
  -e AGENT_BACKEND_URL=http://host.docker.internal:8000 \
  -e CORS_ORIGIN=http://localhost:4200 \
  -p 8080:8080 \
  tool-call-web:latest
```

---

## Kubernetes

```bash
# Apply all manifests
kubectl apply -f ../k8s/tool-call-web/

# For local K8s (minikube/kind): add the ingress host to /etc/hosts
echo "127.0.0.1 tool-call.local" | sudo tee -a /etc/hosts
# Then open http://tool-call.local in a browser
```

---

## Logging

The gateway emits structured JSON logs to stdout. Backend errors (502, 504) are logged at `ERROR` level. When running via Docker Compose, Promtail ships logs to Loki automatically. Query in Grafana at `http://localhost:3001`.
