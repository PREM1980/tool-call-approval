# Dockerize & Kubernetes Deployment Design

**Date:** 2026-05-20
**Status:** Approved

## Overview

Containerize `tool-call-fastapi` and `tool-call-api`, then provide plain Kubernetes manifests to deploy both services. `tool-call-api` calls `tool-call-fastapi` by its K8s service DNS name. The Angular UI reaches `tool-call-api` via an Ingress.

```
[browser / tool-call-ui]
        │ HTTP (Ingress)
        ▼
tool-call-api (ClusterIP :8080)
        │ http://tool-call-fastapi:8000
        ▼
tool-call-fastapi (ClusterIP :8000)
        │
        ├─ POSTGRES_URL (Secret)
        ├─ AWS Bedrock (Secret: AWS credentials)
        └─ Langfuse (ConfigMap: LANGFUSE_HOST)
```

## Dockerfiles

Both services use `python:3.12-slim` with the same pattern: install dependencies from `requirements.txt`, copy source, run `uvicorn`.

**`tool-call-fastapi/Dockerfile`** — exposes port 8000.

**`tool-call-api/Dockerfile`** — exposes port 8080.

**`.dockerignore`** (each service) excludes: `__pycache__/`, `.env`, `.pytest_cache/`, `tests/`. This keeps images lean and prevents local secrets from leaking into the build context.

## tool-call-api CORS Change

`tool-call-api/main.py` currently hardcodes `allow_origins=["http://localhost:4200"]`. This is replaced with an env var `CORS_ORIGIN` read at startup, defaulting to `http://localhost:4200` for backward compatibility. This allows the Ingress hostname to be configured without rebuilding the image.

## Kubernetes Manifests

All manifests live under `k8s/` at the repo root, organised by service:

```
k8s/
  tool-call-fastapi/
    deployment.yaml      # 1 replica, port 8000
    service.yaml         # ClusterIP, port 8000
    configmap.yaml       # AWS_DEFAULT_REGION, LANGFUSE_HOST
    secret.yaml.example  # Placeholder template (committed)
    # secret.yaml        # Real values — gitignored, never committed
  tool-call-api/
    deployment.yaml      # 1 replica, port 8080
    service.yaml         # ClusterIP, port 8080
    configmap.yaml       # AGENT_BACKEND_URL, CORS_ORIGIN
    ingress.yaml         # Routes external traffic → tool-call-api:8080
```

### tool-call-fastapi

**ConfigMap** (`tool-call-fastapi-config`):
- `AWS_DEFAULT_REGION` — e.g. `us-east-1`
- `LANGFUSE_HOST` — e.g. `http://langfuse-web:3000` (cluster) or external hostname

**Secret** (`tool-call-fastapi-secret`) — base64-encoded values, never committed:
- `POSTGRES_URL` — full connection string, e.g. `postgresql+psycopg2://user:pass@host:5432/db`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`

**Deployment:**
- Image: `tool-call-fastapi:latest`
- 1 replica
- `envFrom` referencing ConfigMap and Secret
- Port 8000

**Service:**
- Type: `ClusterIP`
- Port 8000 → targetPort 8000
- Selector: `app: tool-call-fastapi`

### tool-call-api

**ConfigMap** (`tool-call-api-config`):
- `AGENT_BACKEND_URL` — `http://tool-call-fastapi:8000`
- `CORS_ORIGIN` — e.g. `http://tool-call.local` (or UI origin in production)

**Deployment:**
- Image: `tool-call-api:latest`
- 1 replica
- `envFrom` referencing ConfigMap
- Port 8080

**Service:**
- Type: `ClusterIP`
- Port 8080 → targetPort 8080
- Selector: `app: tool-call-api`

**Ingress:**
- Ingress class: `nginx`
- Host: `tool-call.local` (override with real domain for cloud)
- Rule: `/*` → `tool-call-api:8080`
- For local K8s: add `127.0.0.1 tool-call.local` to `/etc/hosts`

## Secrets Workflow

Real `secret.yaml` files are gitignored via a `k8s/**/secret.yaml` entry in the root `.gitignore`. A `secret.yaml.example` is committed alongside each service's manifests with documented placeholders:

```yaml
# Copy to secret.yaml and fill in base64-encoded values:
#   echo -n 'value' | base64
apiVersion: v1
kind: Secret
metadata:
  name: tool-call-fastapi-secret
type: Opaque
data:
  POSTGRES_URL: <base64-encoded-value>
  AWS_ACCESS_KEY_ID: <base64-encoded-value>
  AWS_SECRET_ACCESS_KEY: <base64-encoded-value>
  LANGFUSE_PUBLIC_KEY: <base64-encoded-value>
  LANGFUSE_SECRET_KEY: <base64-encoded-value>
```

## Local Dev Workflow

```bash
# 1. Build images
docker build -t tool-call-fastapi:latest ./tool-call-fastapi
docker build -t tool-call-api:latest ./tool-call-api

# 2. Create secrets (once)
cp k8s/tool-call-fastapi/secret.yaml.example k8s/tool-call-fastapi/secret.yaml
# fill in base64 values, then:
kubectl apply -f k8s/tool-call-fastapi/secret.yaml

# 3. Deploy all manifests
kubectl apply -f k8s/tool-call-fastapi/
kubectl apply -f k8s/tool-call-api/

# 4. For local K8s (minikube/kind): add to /etc/hosts
#    127.0.0.1 tool-call.local
```

## What Is Not In Scope

- Postgres K8s deployment (user supplies connection string via Secret)
- Langfuse K8s deployment (stays in existing docker-compose or external)
- TLS / HTTPS on Ingress (can be added with cert-manager later)
- Multiple replicas / HPA (single replica for now)
- CI/CD image build pipeline
- Namespace configuration (deploys to `default` namespace)
