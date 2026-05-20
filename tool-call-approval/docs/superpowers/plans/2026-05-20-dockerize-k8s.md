# Dockerize & Kubernetes Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Containerize `tool-call-fastapi` and `tool-call-web`, and provide plain Kubernetes manifests so both services can be deployed to any K8s cluster with `kubectl apply -f k8s/`.

**Architecture:** Each service gets a `Dockerfile` + `.dockerignore`. K8s manifests live under `k8s/<service>/` (Deployment, Service, ConfigMap, Secret template, Ingress). `tool-call-web` calls `tool-call-fastapi` by K8s service DNS (`http://tool-call-fastapi:8000`). The CORS origin in `tool-call-web` is made configurable via a `CORS_ORIGIN` env var so it can be set per-environment without rebuilding the image.

**Tech Stack:** Docker (python:3.12-slim base), Kubernetes 1.24+ (apps/v1 Deployment, networking.k8s.io/v1 Ingress), nginx ingress controller.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `tool-call-fastapi/Dockerfile` | Container image for agent backend |
| Create | `tool-call-fastapi/.dockerignore` | Exclude cache, secrets, tests from build |
| Modify | `tool-call-web/main.py:14,31-37` | Read CORS_ORIGIN from env |
| Create | `tool-call-web/Dockerfile` | Container image for API gateway |
| Create | `tool-call-web/.dockerignore` | Exclude cache, secrets, tests from build |
| Create | `k8s/tool-call-fastapi/deployment.yaml` | Run agent backend pod |
| Create | `k8s/tool-call-fastapi/service.yaml` | ClusterIP service on port 8000 |
| Create | `k8s/tool-call-fastapi/configmap.yaml` | AWS_DEFAULT_REGION, LANGFUSE_HOST |
| Create | `k8s/tool-call-fastapi/secret.yaml.example` | Placeholder template for secrets |
| Create | `k8s/tool-call-web/deployment.yaml` | Run gateway pod |
| Create | `k8s/tool-call-web/service.yaml` | ClusterIP service on port 8080 |
| Create | `k8s/tool-call-web/configmap.yaml` | AGENT_BACKEND_URL, CORS_ORIGIN |
| Create | `k8s/tool-call-web/ingress.yaml` | Route external traffic to gateway |
| Modify | `.gitignore` | Add k8s/**/secret.yaml |
| Modify | `tool-call-fastapi/README.md` | Docker + K8s usage |
| Modify | `tool-call-web/README.md` | Docker + K8s usage |

---

## Task 1: Dockerize tool-call-fastapi

**Files:**
- Create: `tool-call-fastapi/Dockerfile`
- Create: `tool-call-fastapi/.dockerignore`

- [ ] **Step 1: Create .dockerignore**

Create `tool-call-fastapi/.dockerignore`:
```
__pycache__/
*.pyc
.env
.pytest_cache/
tests/
```

- [ ] **Step 2: Create Dockerfile**

Create `tool-call-fastapi/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Build the image to verify it works**

```bash
docker build -t tool-call-fastapi:latest ./tool-call-fastapi
```

Expected: image builds successfully, no errors. Final line should be:
```
Successfully tagged tool-call-fastapi:latest
```
(or equivalent BuildKit output ending with the image ID)

- [ ] **Step 4: Verify the image starts**

```bash
docker run --rm -e AWS_DEFAULT_REGION=us-east-1 -e POSTGRES_URL=postgresql+psycopg2://localhost/test -p 8000:8000 tool-call-fastapi:latest &
sleep 3
curl -s http://localhost:8000/docs | grep -q "Tool Call" && echo "OK" || echo "FAIL"
kill %1
```

Expected: `OK` (FastAPI's OpenAPI docs are served).

- [ ] **Step 5: Commit**

```bash
git add tool-call-fastapi/Dockerfile tool-call-fastapi/.dockerignore
git commit -m "feat(tool-call-fastapi): add Dockerfile and .dockerignore"
```

---

## Task 2: Make CORS Origin Configurable in tool-call-web

**Files:**
- Modify: `tool-call-web/main.py:14,31-37`

- [ ] **Step 1: Update main.py to read CORS_ORIGIN from env**

In `tool-call-web/main.py`, change lines 14–15 from:
```python
_BACKEND = os.getenv("AGENT_BACKEND_URL", "http://localhost:8000")
_client: httpx.AsyncClient | None = None
```

To:
```python
_BACKEND = os.getenv("AGENT_BACKEND_URL", "http://localhost:8000")
_CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:4200")
_client: httpx.AsyncClient | None = None
```

Then change lines 31–37 from:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

To:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 2: Run existing tests to confirm nothing broke**

```bash
cd tool-call-web && python -m pytest -v 2>&1 | tail -15
```

Expected: all 8 tests PASS (CORS middleware is not directly tested, so no test changes needed).

- [ ] **Step 3: Update .env.example**

Add `CORS_ORIGIN` to `tool-call-web/.env.example`:
```
AGENT_BACKEND_URL=http://localhost:8000
CORS_ORIGIN=http://localhost:4200
```

- [ ] **Step 4: Commit**

```bash
cd ..
git add tool-call-web/main.py tool-call-web/.env.example
git commit -m "feat(tool-call-web): make CORS origin configurable via CORS_ORIGIN env var"
```

---

## Task 3: Dockerize tool-call-web

**Files:**
- Create: `tool-call-web/Dockerfile`
- Create: `tool-call-web/.dockerignore`

- [ ] **Step 1: Create .dockerignore**

Create `tool-call-web/.dockerignore`:
```
__pycache__/
*.pyc
.env
.pytest_cache/
tests/
```

- [ ] **Step 2: Create Dockerfile**

Create `tool-call-web/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 3: Build the image to verify it works**

```bash
docker build -t tool-call-web:latest ./tool-call-web
```

Expected: image builds successfully.

- [ ] **Step 4: Verify the image starts**

```bash
docker run --rm -e AGENT_BACKEND_URL=http://localhost:8000 -p 8080:8080 tool-call-web:latest &
sleep 3
curl -s http://localhost:8080/docs | grep -q "Tool Call Web" && echo "OK" || echo "FAIL"
kill %1
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add tool-call-web/Dockerfile tool-call-web/.dockerignore
git commit -m "feat(tool-call-web): add Dockerfile and .dockerignore"
```

---

## Task 4: K8s Manifests for tool-call-fastapi

**Files:**
- Create: `k8s/tool-call-fastapi/deployment.yaml`
- Create: `k8s/tool-call-fastapi/service.yaml`
- Create: `k8s/tool-call-fastapi/configmap.yaml`
- Create: `k8s/tool-call-fastapi/secret.yaml.example`

- [ ] **Step 1: Create directory**

```bash
mkdir -p k8s/tool-call-fastapi
```

- [ ] **Step 2: Create configmap.yaml**

Create `k8s/tool-call-fastapi/configmap.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tool-call-fastapi-config
data:
  AWS_DEFAULT_REGION: us-east-1
  LANGFUSE_HOST: http://langfuse-web:3000
```

- [ ] **Step 3: Create secret.yaml.example**

Create `k8s/tool-call-fastapi/secret.yaml.example`:
```yaml
# Copy this file to secret.yaml and fill in base64-encoded values.
# Encode a value:  echo -n 'your-value' | base64
# Apply:           kubectl apply -f k8s/tool-call-fastapi/secret.yaml
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

- [ ] **Step 4: Create service.yaml**

Create `k8s/tool-call-fastapi/service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: tool-call-fastapi
spec:
  selector:
    app: tool-call-fastapi
  ports:
    - port: 8000
      targetPort: 8000
  type: ClusterIP
```

- [ ] **Step 5: Create deployment.yaml**

Create `k8s/tool-call-fastapi/deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tool-call-fastapi
spec:
  replicas: 1
  selector:
    matchLabels:
      app: tool-call-fastapi
  template:
    metadata:
      labels:
        app: tool-call-fastapi
    spec:
      containers:
        - name: tool-call-fastapi
          image: tool-call-fastapi:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: tool-call-fastapi-config
            - secretRef:
                name: tool-call-fastapi-secret
```

- [ ] **Step 6: Validate all manifests with dry-run**

```bash
kubectl apply --dry-run=client -f k8s/tool-call-fastapi/configmap.yaml
kubectl apply --dry-run=client -f k8s/tool-call-fastapi/service.yaml
kubectl apply --dry-run=client -f k8s/tool-call-fastapi/deployment.yaml
```

Expected output (one line per command):
```
configmap/tool-call-fastapi-config created (dry run)
service/tool-call-fastapi created (dry run)
deployment.apps/tool-call-fastapi created (dry run)
```

Note: `secret.yaml.example` has placeholder values so it is not dry-run validated — it is a documentation artifact only.

- [ ] **Step 7: Commit**

```bash
git add k8s/tool-call-fastapi/
git commit -m "feat(k8s): add tool-call-fastapi manifests (deployment, service, configmap, secret template)"
```

---

## Task 5: K8s Manifests for tool-call-web

**Files:**
- Create: `k8s/tool-call-web/deployment.yaml`
- Create: `k8s/tool-call-web/service.yaml`
- Create: `k8s/tool-call-web/configmap.yaml`
- Create: `k8s/tool-call-web/ingress.yaml`

- [ ] **Step 1: Create directory**

```bash
mkdir -p k8s/tool-call-web
```

- [ ] **Step 2: Create configmap.yaml**

Create `k8s/tool-call-web/configmap.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tool-call-web-config
data:
  AGENT_BACKEND_URL: http://tool-call-fastapi:8000
  CORS_ORIGIN: http://tool-call.local
```

- [ ] **Step 3: Create service.yaml**

Create `k8s/tool-call-web/service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: tool-call-web
spec:
  selector:
    app: tool-call-web
  ports:
    - port: 8080
      targetPort: 8080
  type: ClusterIP
```

- [ ] **Step 4: Create deployment.yaml**

Create `k8s/tool-call-web/deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tool-call-web
spec:
  replicas: 1
  selector:
    matchLabels:
      app: tool-call-web
  template:
    metadata:
      labels:
        app: tool-call-web
    spec:
      containers:
        - name: tool-call-web
          image: tool-call-web:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
          envFrom:
            - configMapRef:
                name: tool-call-web-config
```

- [ ] **Step 5: Create ingress.yaml**

Create `k8s/tool-call-web/ingress.yaml`:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tool-call-web
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: tool-call.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: tool-call-web
                port:
                  number: 8080
```

- [ ] **Step 6: Validate all manifests with dry-run**

```bash
kubectl apply --dry-run=client -f k8s/tool-call-web/configmap.yaml
kubectl apply --dry-run=client -f k8s/tool-call-web/service.yaml
kubectl apply --dry-run=client -f k8s/tool-call-web/deployment.yaml
kubectl apply --dry-run=client -f k8s/tool-call-web/ingress.yaml
```

Expected:
```
configmap/tool-call-web-config created (dry run)
service/tool-call-web created (dry run)
deployment.apps/tool-call-web created (dry run)
ingress.networking.k8s.io/tool-call-web created (dry run)
```

- [ ] **Step 7: Commit**

```bash
git add k8s/tool-call-web/
git commit -m "feat(k8s): add tool-call-web manifests (deployment, service, configmap, ingress)"
```

---

## Task 6: Update .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add secret.yaml glob to .gitignore**

Append to `.gitignore`:
```
# K8s secrets — never commit real values
k8s/**/secret.yaml
```

- [ ] **Step 2: Verify secret.yaml.example is still tracked**

```bash
git check-ignore -v k8s/tool-call-fastapi/secret.yaml.example
```

Expected: no output (file is NOT ignored — `.example` suffix is not matched by the glob).

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore k8s secret.yaml files"
```

---

## Task 7: Update READMEs

**Files:**
- Modify: `tool-call-fastapi/README.md`
- Modify: `tool-call-web/README.md`

- [ ] **Step 1: Add Docker & K8s section to tool-call-fastapi/README.md**

Open `tool-call-fastapi/README.md` and append:

```markdown
## Docker

```bash
docker build -t tool-call-fastapi:latest .
docker run --rm \
  -e AWS_DEFAULT_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=... \
  -e AWS_SECRET_ACCESS_KEY=... \
  -e POSTGRES_URL=postgresql+psycopg2://user:pass@host:5432/db \
  -e LANGFUSE_HOST=http://langfuse-web:3000 \
  -p 8000:8000 \
  tool-call-fastapi:latest
```

## Kubernetes

```bash
# 1. Create secret from template
cp k8s/tool-call-fastapi/secret.yaml.example k8s/tool-call-fastapi/secret.yaml
# Fill in base64-encoded values (echo -n 'value' | base64), then:
kubectl apply -f k8s/tool-call-fastapi/secret.yaml

# 2. Apply remaining manifests
kubectl apply -f k8s/tool-call-fastapi/
```
```

- [ ] **Step 2: Add Docker & K8s section to tool-call-web/README.md**

Open `tool-call-web/README.md` and append:

```markdown
## Docker

```bash
docker build -t tool-call-web:latest .
docker run --rm \
  -e AGENT_BACKEND_URL=http://tool-call-fastapi:8000 \
  -e CORS_ORIGIN=http://tool-call.local \
  -p 8080:8080 \
  tool-call-web:latest
```

## Kubernetes

```bash
kubectl apply -f k8s/tool-call-web/
```

For local K8s (minikube/kind), add to `/etc/hosts`:
```
127.0.0.1 tool-call.local
```
```

- [ ] **Step 3: Commit**

```bash
git add tool-call-fastapi/README.md tool-call-web/README.md
git commit -m "docs: add Docker and Kubernetes usage to READMEs"
```

---

## Final Verification

- [ ] **Run both test suites to confirm nothing regressed**

```bash
cd tool-call-web && python -m pytest -v 2>&1 | tail -12
cd ../tool-call-fastapi && python -m pytest -v 2>&1 | tail -5
```

Expected: 8 passed in tool-call-web, 107 passed in tool-call-fastapi.

- [ ] **Verify both images build cleanly from scratch**

```bash
docker build --no-cache -t tool-call-fastapi:latest ./tool-call-fastapi
docker build --no-cache -t tool-call-web:latest ./tool-call-web
```

Expected: both complete without errors.

- [ ] **Dry-run all K8s manifests**

```bash
kubectl apply --dry-run=client -f k8s/tool-call-fastapi/configmap.yaml \
  -f k8s/tool-call-fastapi/service.yaml \
  -f k8s/tool-call-fastapi/deployment.yaml
kubectl apply --dry-run=client -f k8s/tool-call-web/
```

Expected: all resources show `created (dry run)` with no errors.
