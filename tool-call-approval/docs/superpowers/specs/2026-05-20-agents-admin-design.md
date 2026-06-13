# Agents Admin Panel Design

## Goal

Add an **Agents** section to the Admin panel that lets users deploy Docker containers as Kubernetes Deployments and manage them (view, scale, restart, delete) — all through the existing web UI.

## Architecture

A new dedicated FastAPI service (`tool-call-k8s`) runs in its own Docker container and owns all `kubectl` operations. The Angular UI gains an Agents section under Admin. `tool-call-api` proxies `/api/agents/*` to `tool-call-k8s`. The existing `tool-call-agent` service is untouched.

```text
Angular UI (/admin/agents)
    ↓  /api/agents/*
tool-call-api  (new proxy block)
    ↓  /agents/*
tool-call-k8s  (new container, port 8001)
    ↓  kubectl
minikube / K8s cluster
```

## Naming Convention

All K8s Deployments created through this UI are named `{user-input}-ui-agents`. The View tab filters to only show Deployments whose name ends in `-ui-agents`. This ensures clear ownership and prevents accidental management of unrelated cluster resources.

## New Service: `tool-call-k8s`

### Files

| File | Responsibility |
| ---- | -------------- |
| `tool-call-k8s/main.py` | FastAPI app, mounts the agents router |
| `tool-call-k8s/k8s_service.py` | All `kubectl` subprocess calls |
| `tool-call-k8s/models.py` | Pydantic request/response models |
| `tool-call-k8s/Dockerfile` | `python:3.12-slim` + kubectl binary |
| `tool-call-k8s/requirements.txt` | `fastapi`, `uvicorn`, `python-dotenv`, `python-json-logger` |
| `tool-call-k8s/logging_config.py` | JSON structured logging (same pattern as other services) |

### API Endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/kubeconfig` | Store kubeconfig to a mounted volume file |
| `POST` | `/agents` | Create a K8s Deployment named `{name}-ui-agents` |
| `GET` | `/agents` | List all Deployments ending in `-ui-agents` |
| `DELETE` | `/agents/{name}` | Delete the Deployment and its pods |
| `POST` | `/agents/{name}/restart` | `kubectl rollout restart deployment/{name}` |
| `PATCH` | `/agents/{name}/scale` | Set replica count |

### Kubeconfig Storage

On startup, `k8s_service.py` looks for a kubeconfig file at `/data/kubeconfig.yaml` (Docker volume mount). When `POST /kubeconfig` is called, it writes the kubeconfig to that path. `kubectl` commands use `--kubeconfig /data/kubeconfig.yaml`. The volume persists across container restarts.

### kubectl Execution

`k8s_service.py` shells out to `kubectl` using `subprocess.run` with `capture_output=True`. All commands include `--kubeconfig /data/kubeconfig.yaml` and `--output json` where applicable. Stderr is captured and surfaced as error detail in HTTP 500 responses. The `_run_kubectl` pattern mirrors what already exists in `tool-call-agent/tools.py`.

### Deployment Creation

`POST /agents` body:

```json
{
  "name": "my-agent",
  "image": "my-org/my-agent:latest",
  "namespace": "default",
  "replicas": 1,
  "env": [{"key": "API_KEY", "value": "abc123"}]
}
```

Shells out to:

```bash
kubectl create deployment my-agent-ui-agents \
  --image=my-org/my-agent:latest \
  --replicas=1 \
  --namespace=default
kubectl set env deployment/my-agent-ui-agents API_KEY=abc123 --namespace=default
```

### List Response

`GET /agents` returns:

```json
[
  {
    "name": "my-agent-ui-agents",
    "namespace": "default",
    "image": "my-org/my-agent:latest",
    "replicas": 1,
    "ready_replicas": 1,
    "status": "Running"
  }
]
```

Status is derived from `deployment.status.readyReplicas` vs `deployment.spec.replicas`:

- `Running` — ready == desired
- `Pending` — ready < desired
- `Failed` — readyReplicas is 0 and conditions contain `Available=False`

## Changes to Existing Services

### `tool-call-api/main.py`

New proxy block added alongside existing `/api/sessions/*` and `/api/admin/*` blocks:

```python
@app.api_route("/api/agents/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def agents_proxy(path: str, request: Request) -> JSONResponse:
    ...forwards to K8S_BACKEND/agents/{path}...
```

`K8S_BACKEND` read from env var `K8S_BACKEND_URL` (default `http://localhost:8001`).

A second proxy block handles kubeconfig delivery:

```python
@app.post("/api/k8s-config")
async def k8s_config_proxy(request: Request) -> JSONResponse:
    ...forwards to K8S_BACKEND/kubeconfig...
```

### `docker-compose.yml`

New `tool-call-k8s` service:

- Image built from `tool-call-k8s/Dockerfile`
- Port `8001:8001`
- Volume `k8s_data:/data` for kubeconfig persistence
- `extra_hosts: host.docker.internal:host-gateway` (same as tool-call-agent, needed for minikube access)

`tool-call-api` gains `K8S_BACKEND_URL: http://tool-call-k8s:8001` in its environment.

## Frontend Changes

### New Files

| File | Responsibility |
| ---- | -------------- |
| `admin/agents/agents.ts` | Component with tab state (deployments / view) |
| `admin/agents/agents.html` | Tab switcher + child component for each tab |
| `admin/agents/agents.css` | Tab styles |
| `admin/agents/deploy-form/deploy-form.ts` | Deployments tab — form to create a new agent |
| `admin/agents/deploy-form/deploy-form.html` | Name, image, namespace, replicas, env var rows |
| `admin/agents/deploy-form/deploy-form.css` | Form styles |
| `admin/agents/agent-list/agent-list.ts` | View tab — table of running -ui-agents deployments |
| `admin/agents/agent-list/agent-list.html` | Table with inline scale, restart, delete |
| `admin/agents/agent-list/agent-list.css` | Table styles |
| `services/agents.service.ts` | HTTP calls to `/api/agents/*` and `/api/k8s-config` |

### `admin.routes.ts`

New route added:

```typescript
{
  path: 'agents',
  loadComponent: () => import('./agents/agents').then(m => m.Agents),
}
```

### `admin-layout.html`

New nav link:

```html
<a routerLink="/admin/agents" routerLinkActive="active" class="nav-item">Agents</a>
```

### Kubeconfig Auto-Sync

When the `Agents` component initialises, `AgentService.syncKubeconfig()` is called:

1. `GET /api/admin/credentials` — reads the kubeconfig already stored in tool-call-agent
2. If kubeconfig is present, `POST /api/k8s-config` — pushes it to `tool-call-k8s`

This means the user never enters the kubeconfig twice. The Credentials page remains the single source of truth.

### Deployments Tab (deploy-form)

- Name field shows a live preview: `my-agent → my-agent-ui-agents`
- Env vars: dynamic list of key/value rows with `+ Add variable` and `✕` remove buttons
- On submit: `POST /api/agents` with the form values; on success, switches to the View tab

### View Tab (agent-list)

- On load: `GET /api/agents` — fetches all `-ui-agents` deployments
- Table columns: Name, Namespace, Image, Replicas (with inline `−` / `+` buttons), Status (colour-coded), Actions
- **Scale**: clicking `+` or `−` calls `PATCH /api/agents/{name}/scale` immediately
- **Restart**: calls `POST /api/agents/{name}/restart`
- **Delete**: confirmation dialog, then `DELETE /api/agents/{name}`; row removed on success
- **Refresh**: polling every 10 seconds while the tab is active to pick up status changes

## Error Handling

- `tool-call-k8s` returns HTTP 400 if the Deployment name already exists (kubectl exit code non-zero)
- `tool-call-k8s` returns HTTP 404 for delete/restart/scale on unknown names
- Angular surfaces errors inline below the form or table row (not full-page)
- If kubeconfig is missing, `tool-call-k8s` returns HTTP 503 with `"kubeconfig not configured"` — Angular shows a banner prompting the user to save credentials first

## Testing

- `tool-call-k8s/tests/test_agents.py` — unit tests mocking `subprocess.run` to verify kubectl commands are constructed correctly for create, list, delete, restart, scale
- `tool-call-api/tests/test_main.py` — add tests for the `/api/agents/*` proxy (same pattern as existing admin proxy tests)
