# Agents Admin Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Admin > Agents section with Deployments and View tabs, backed by a new `tool-call-k8s` FastAPI service that wraps `kubectl` to create and manage Kubernetes Deployments named `*-ui-agents`.

**Architecture:** A new `tool-call-k8s` container (port 8001) owns all kubectl operations; `tool-call-api` proxies `/api/agents/*` and `/api/k8s-config` to it; Angular's Agents component auto-syncs the kubeconfig from existing Credentials on load, then lets users deploy containers and manage running agents.

**Tech Stack:** Python 3.12 / FastAPI / subprocess kubectl (backend), Angular 19 standalone components (frontend), Docker Compose.

---

## File Map

**New — `tool-call-k8s/`**
- `Dockerfile` — python:3.12-slim + kubectl binary
- `requirements.txt` — fastapi, uvicorn, python-dotenv, python-json-logger, pytest, httpx
- `pytest.ini` — asyncio_mode = auto
- `logging_config.py` — copy of the shared JSON logging module
- `models.py` — Pydantic models: KubeconfigRequest, EnvVar, DeployRequest, ScaleRequest, AgentResponse
- `k8s_service.py` — kubectl subprocess calls (write_kubeconfig, create/list/delete/restart/scale)
- `main.py` — FastAPI routes for /kubeconfig and /agents/*
- `tests/__init__.py` — empty
- `tests/test_k8s_service.py` — unit tests mocking subprocess.run
- `tests/test_main.py` — API tests via TestClient

**Modified**
- `docker-compose.yml` — add `tool-call-k8s` service + `k8s_data` volume; add `K8S_BACKEND_URL` to tool-call-api
- `tool-call-api/main.py` — add `_K8S_BACKEND`, `/api/agents/*` proxy, `/api/k8s-config` proxy
- `tool-call-api/tests/test_main.py` — add tests for the two new proxy routes

**New — Angular**
- `tool-call-ui/src/app/services/agents.service.ts`
- `tool-call-ui/src/app/admin/agents/agents.ts` + `.html` + `.css`
- `tool-call-ui/src/app/admin/agents/deploy-form/deploy-form.ts` + `.html` + `.css`
- `tool-call-ui/src/app/admin/agents/agent-list/agent-list.ts` + `.html` + `.agent-list.css`

**Modified — Angular**
- `tool-call-ui/src/app/admin/admin.routes.ts` — add agents route
- `tool-call-ui/src/app/admin/admin-layout/admin-layout.html` — add Agents nav link

---

### Task 1: Scaffold `tool-call-k8s`

**Files:**
- Create: `tool-call-k8s/Dockerfile`
- Create: `tool-call-k8s/requirements.txt`
- Create: `tool-call-k8s/pytest.ini`
- Create: `tool-call-k8s/logging_config.py`
- Create: `tool-call-k8s/tests/__init__.py`

- [ ] **Step 1: Create the directory and Dockerfile**

```bash
mkdir -p tool-call-k8s/tests
```

Create `tool-call-k8s/Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl ca-certificates && \
    curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && \
    rm kubectl && \
    rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

- [ ] **Step 2: Create requirements.txt and pytest.ini**

Create `tool-call-k8s/requirements.txt`:

```
fastapi==0.115.12
uvicorn[standard]==0.34.2
python-dotenv==1.1.0
pytest==8.3.5
pytest-asyncio==0.25.3
httpx==0.28.1
python-json-logger==2.0.7
```

Create `tool-call-k8s/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 3: Copy logging_config.py from tool-call-agent (it's identical)**

```bash
cp tool-call-agent/logging_config.py tool-call-k8s/logging_config.py
```

Then edit the two boto/httpx suppression lines — tool-call-k8s has neither, so remove them. Final `tool-call-k8s/logging_config.py`:

```python
import logging
import sys

from pythonjsonlogger import jsonlogger


class _ServiceFilter(logging.Filter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service
        return True


def _make_handler(service: str) -> logging.StreamHandler:
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(service)s %(message)s",
        rename_fields={
            "levelname": "level",
            "asctime": "timestamp",
            "name": "logger",
        },
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(_ServiceFilter(service))
    return handler


def setup_logging(service: str) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(_make_handler(service))
    root.setLevel(logging.INFO)


def reconfigure_uvicorn_loggers(service: str) -> None:
    handler = _make_handler(service)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        lgr = logging.getLogger(name)
        lgr.handlers.clear()
        lgr.addHandler(handler)
        lgr.setLevel(logging.INFO)
        lgr.propagate = False
```

- [ ] **Step 4: Create empty tests/__init__.py**

```bash
touch tool-call-k8s/tests/__init__.py
```

- [ ] **Step 5: Commit scaffold**

```bash
git add tool-call-k8s/
git commit -m "feat(k8s): scaffold tool-call-k8s service"
```

---

### Task 2: `tool-call-k8s` — Pydantic models (TDD)

**Files:**
- Create: `tool-call-k8s/models.py`
- Create: `tool-call-k8s/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tool-call-k8s/tests/test_models.py`:

```python
from models import AgentResponse, DeployRequest, EnvVar, KubeconfigRequest, ScaleRequest


def test_kubeconfig_request():
    r = KubeconfigRequest(content="apiVersion: v1")
    assert r.content == "apiVersion: v1"


def test_deploy_request_defaults():
    r = DeployRequest(name="my-agent", image="img:latest")
    assert r.namespace == "default"
    assert r.replicas == 1
    assert r.env == []


def test_deploy_request_with_env():
    r = DeployRequest(name="x", image="y", env=[{"key": "K", "value": "V"}])
    assert r.env[0].key == "K"


def test_scale_request():
    r = ScaleRequest(replicas=3)
    assert r.replicas == 3


def test_agent_response():
    r = AgentResponse(
        name="x-ui-agents",
        namespace="default",
        image="img:latest",
        replicas=2,
        ready_replicas=2,
        status="Running",
    )
    assert r.status == "Running"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd tool-call-k8s && pip install -r requirements.txt -q && pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: Create models.py**

Create `tool-call-k8s/models.py`:

```python
from pydantic import BaseModel


class KubeconfigRequest(BaseModel):
    content: str


class EnvVar(BaseModel):
    key: str
    value: str


class DeployRequest(BaseModel):
    name: str
    image: str
    namespace: str = "default"
    replicas: int = 1
    env: list[EnvVar] = []


class ScaleRequest(BaseModel):
    replicas: int


class AgentResponse(BaseModel):
    name: str
    namespace: str
    image: str
    replicas: int
    ready_replicas: int
    status: str
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add tool-call-k8s/models.py tool-call-k8s/tests/test_models.py
git commit -m "feat(k8s): add Pydantic models"
```

---

### Task 3: `tool-call-k8s` — k8s_service.py (TDD)

**Files:**
- Create: `tool-call-k8s/k8s_service.py`
- Create: `tool-call-k8s/tests/test_k8s_service.py`

- [ ] **Step 1: Write the failing tests**

Create `tool-call-k8s/tests/test_k8s_service.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import k8s_service


@pytest.fixture(autouse=True)
def patch_kubeconfig_path(tmp_path, monkeypatch):
    monkeypatch.setattr(k8s_service, "_KUBECONFIG_PATH", str(tmp_path / "kubeconfig.yaml"))


def _make_proc(stdout: str, returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = ""
    return m


def _existing_kubeconfig():
    Path(k8s_service._KUBECONFIG_PATH).write_text("apiVersion: v1")


def _dep_json(name: str, image: str = "img:latest", replicas: int = 1, ready: int = 1) -> dict:
    return {
        "metadata": {"name": name, "namespace": "default"},
        "spec": {
            "replicas": replicas,
            "template": {"spec": {"containers": [{"image": image}]}},
        },
        "status": {"readyReplicas": ready},
    }


# ── write_kubeconfig ────────────────────────────────────────────────────────

def test_write_kubeconfig_creates_file():
    k8s_service.write_kubeconfig("apiVersion: v1")
    assert Path(k8s_service._KUBECONFIG_PATH).read_text() == "apiVersion: v1"


def test_write_kubeconfig_creates_parent_dirs(tmp_path, monkeypatch):
    deep = str(tmp_path / "a" / "b" / "kubeconfig.yaml")
    monkeypatch.setattr(k8s_service, "_KUBECONFIG_PATH", deep)
    k8s_service.write_kubeconfig("apiVersion: v1")
    assert Path(deep).exists()


# ── _run guards ─────────────────────────────────────────────────────────────

def test_run_raises_when_no_kubeconfig():
    with pytest.raises(RuntimeError, match="kubeconfig not configured"):
        k8s_service._run(["get", "pods"])


def test_run_raises_on_nonzero_exit():
    _existing_kubeconfig()
    with patch("subprocess.run", return_value=_make_proc("", returncode=1, )):
        with pytest.raises(RuntimeError):
            k8s_service._run(["get", "pods"])


# ── create_deployment ────────────────────────────────────────────────────────

def test_create_deployment_uses_ui_agents_suffix():
    _existing_kubeconfig()
    dep = _dep_json("my-agent-ui-agents")
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _make_proc(json.dumps(dep) if "get" in cmd else "created")
    with patch("subprocess.run", side_effect=fake_run):
        result = k8s_service.create_deployment("my-agent", "img:latest", "default", 1, [])
    create_cmd = next(c for c in calls if "create" in c)
    assert "my-agent-ui-agents" in create_cmd
    assert result["name"] == "my-agent-ui-agents"
    assert result["status"] == "Running"


def test_create_deployment_sets_env_vars():
    _existing_kubeconfig()
    dep = _dep_json("x-ui-agents")
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _make_proc(json.dumps(dep) if "get" in cmd else "ok")
    with patch("subprocess.run", side_effect=fake_run):
        k8s_service.create_deployment("x", "img", "default", 1, [{"key": "FOO", "value": "bar"}])
    set_cmd = next(c for c in calls if "set" in c)
    assert "FOO=bar" in set_cmd


def test_create_deployment_skips_set_env_when_no_env():
    _existing_kubeconfig()
    dep = _dep_json("x-ui-agents")
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _make_proc(json.dumps(dep) if "get" in cmd else "ok")
    with patch("subprocess.run", side_effect=fake_run):
        k8s_service.create_deployment("x", "img", "default", 1, [])
    assert not any("set" in c for c in calls)


# ── list_deployments ─────────────────────────────────────────────────────────

def test_list_deployments_filters_by_suffix():
    _existing_kubeconfig()
    items = {
        "items": [
            _dep_json("my-agent-ui-agents"),
            _dep_json("unrelated-deployment"),
        ]
    }
    with patch("subprocess.run", return_value=_make_proc(json.dumps(items))):
        result = k8s_service.list_deployments()
    assert len(result) == 1
    assert result[0]["name"] == "my-agent-ui-agents"


def test_list_deployments_empty():
    _existing_kubeconfig()
    with patch("subprocess.run", return_value=_make_proc(json.dumps({"items": []}))):
        assert k8s_service.list_deployments() == []


# ── delete_deployment ────────────────────────────────────────────────────────

def test_delete_deployment_calls_kubectl_delete():
    _existing_kubeconfig()
    with patch("subprocess.run", return_value=_make_proc("deleted")) as mock:
        k8s_service.delete_deployment("my-agent-ui-agents", "default")
    cmd = mock.call_args[0][0]
    assert "delete" in cmd
    assert "my-agent-ui-agents" in cmd
    assert "--namespace" in cmd


# ── restart_deployment ────────────────────────────────────────────────────────

def test_restart_deployment_calls_rollout_restart():
    _existing_kubeconfig()
    with patch("subprocess.run", return_value=_make_proc("restarted")) as mock:
        k8s_service.restart_deployment("my-agent-ui-agents", "default")
    cmd = mock.call_args[0][0]
    assert "rollout" in cmd
    assert "restart" in cmd
    assert "deployment/my-agent-ui-agents" in cmd


# ── scale_deployment ─────────────────────────────────────────────────────────

def test_scale_deployment_calls_kubectl_scale():
    _existing_kubeconfig()
    with patch("subprocess.run", return_value=_make_proc("scaled")) as mock:
        k8s_service.scale_deployment("my-agent-ui-agents", "default", 3)
    cmd = mock.call_args[0][0]
    assert "scale" in cmd
    assert "--replicas=3" in cmd
    assert "my-agent-ui-agents" in cmd


# ── status derivation ────────────────────────────────────────────────────────

def test_status_running():
    dep = _dep_json("x-ui-agents", replicas=2, ready=2)
    assert k8s_service._derive_status(dep) == "Running"


def test_status_pending():
    dep = _dep_json("x-ui-agents", replicas=2, ready=0)
    assert k8s_service._derive_status(dep) == "Pending"


def test_status_failed():
    dep = _dep_json("x-ui-agents", replicas=1, ready=0)
    dep["status"]["conditions"] = [{"type": "Available", "status": "False"}]
    assert k8s_service._derive_status(dep) == "Failed"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_k8s_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'k8s_service'`

- [ ] **Step 3: Create k8s_service.py**

Create `tool-call-k8s/k8s_service.py`:

```python
import json
import os
import subprocess
from pathlib import Path

_KUBECONFIG_PATH = os.getenv("KUBECONFIG_PATH", "/data/kubeconfig.yaml")
_KUBECTL_TIMEOUT = 30
_SUFFIX = "-ui-agents"


def write_kubeconfig(content: str) -> None:
    path = Path(_KUBECONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _kubeconfig_exists() -> bool:
    return Path(_KUBECONFIG_PATH).exists()


def _run(args: list[str]) -> str:
    if not _kubeconfig_exists():
        raise RuntimeError("kubeconfig not configured")
    result = subprocess.run(
        ["kubectl", "--kubeconfig", _KUBECONFIG_PATH] + args,
        capture_output=True,
        text=True,
        timeout=_KUBECTL_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"exit {result.returncode}")
    return result.stdout.strip()


def _derive_status(dep: dict) -> str:
    spec_replicas = dep.get("spec", {}).get("replicas", 1)
    ready = dep.get("status", {}).get("readyReplicas") or 0
    if ready >= spec_replicas:
        return "Running"
    conditions = dep.get("status", {}).get("conditions", [])
    for c in conditions:
        if c.get("type") == "Available" and c.get("status") == "False":
            return "Failed"
    return "Pending"


def _parse_deployment(dep: dict) -> dict:
    containers = (
        dep.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    return {
        "name": dep["metadata"]["name"],
        "namespace": dep["metadata"].get("namespace", "default"),
        "image": containers[0]["image"] if containers else "",
        "replicas": dep.get("spec", {}).get("replicas", 1),
        "ready_replicas": dep.get("status", {}).get("readyReplicas") or 0,
        "status": _derive_status(dep),
    }


def create_deployment(
    name: str, image: str, namespace: str, replicas: int, env: list[dict]
) -> dict:
    full_name = f"{name}{_SUFFIX}"
    _run([
        "create", "deployment", full_name,
        f"--image={image}",
        f"--replicas={replicas}",
        f"--namespace={namespace}",
    ])
    if env:
        env_args = [f"{e['key']}={e['value']}" for e in env]
        _run(["set", "env", f"deployment/{full_name}", "--namespace", namespace] + env_args)
    raw = _run(["get", "deployment", full_name, "--namespace", namespace, "-o", "json"])
    return _parse_deployment(json.loads(raw))


def list_deployments() -> list[dict]:
    raw = _run(["get", "deployments", "--all-namespaces", "-o", "json"])
    data = json.loads(raw)
    return [
        _parse_deployment(dep)
        for dep in data.get("items", [])
        if dep["metadata"]["name"].endswith(_SUFFIX)
    ]


def delete_deployment(name: str, namespace: str) -> None:
    _run(["delete", "deployment", name, "--namespace", namespace])


def restart_deployment(name: str, namespace: str) -> None:
    _run(["rollout", "restart", f"deployment/{name}", "--namespace", namespace])


def scale_deployment(name: str, namespace: str, replicas: int) -> None:
    _run(["scale", "deployment", name, f"--replicas={replicas}", "--namespace", namespace])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_k8s_service.py -v
```

Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add tool-call-k8s/k8s_service.py tool-call-k8s/tests/test_k8s_service.py
git commit -m "feat(k8s): implement kubectl service with TDD"
```

---

### Task 4: `tool-call-k8s` — FastAPI app (TDD)

**Files:**
- Create: `tool-call-k8s/main.py`
- Create: `tool-call-k8s/tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

Create `tool-call-k8s/tests/test_main.py`:

```python
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _agent(name: str = "my-agent-ui-agents") -> dict:
    return {
        "name": name,
        "namespace": "default",
        "image": "img:latest",
        "replicas": 1,
        "ready_replicas": 1,
        "status": "Running",
    }


# ── POST /kubeconfig ─────────────────────────────────────────────────────────

def test_save_kubeconfig_calls_write():
    with patch("k8s_service.write_kubeconfig") as mock:
        resp = client.post("/kubeconfig", json={"content": "apiVersion: v1"})
    assert resp.status_code == 200
    mock.assert_called_once_with("apiVersion: v1")


def test_save_kubeconfig_propagates_error():
    with patch("k8s_service.write_kubeconfig", side_effect=OSError("permission denied")):
        resp = client.post("/kubeconfig", json={"content": "x"})
    assert resp.status_code == 500


# ── POST /agents ─────────────────────────────────────────────────────────────

def test_create_agent_returns_201():
    with patch("k8s_service.create_deployment", return_value=_agent()):
        resp = client.post("/agents", json={
            "name": "my-agent", "image": "img:latest",
            "namespace": "default", "replicas": 1, "env": [],
        })
    assert resp.status_code == 201
    assert resp.json()["name"] == "my-agent-ui-agents"


def test_create_agent_already_exists_returns_400():
    with patch("k8s_service.create_deployment", side_effect=RuntimeError("already exists")):
        resp = client.post("/agents", json={"name": "x", "image": "img"})
    assert resp.status_code == 400


def test_create_agent_no_kubeconfig_returns_503():
    with patch("k8s_service.create_deployment", side_effect=RuntimeError("kubeconfig not configured")):
        resp = client.post("/agents", json={"name": "x", "image": "img"})
    assert resp.status_code == 503


# ── GET /agents ───────────────────────────────────────────────────────────────

def test_list_agents():
    with patch("k8s_service.list_deployments", return_value=[_agent()]):
        resp = client.get("/agents")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "Running"


def test_list_agents_no_kubeconfig_returns_503():
    with patch("k8s_service.list_deployments", side_effect=RuntimeError("kubeconfig not configured")):
        resp = client.get("/agents")
    assert resp.status_code == 503


# ── DELETE /agents/{name} ────────────────────────────────────────────────────

def test_delete_agent():
    with patch("k8s_service.delete_deployment") as mock:
        resp = client.delete("/agents/my-agent-ui-agents")
    assert resp.status_code == 200
    mock.assert_called_once_with("my-agent-ui-agents", "default")


def test_delete_agent_not_found_returns_404():
    with patch("k8s_service.delete_deployment", side_effect=RuntimeError("not found")):
        resp = client.delete("/agents/missing-ui-agents")
    assert resp.status_code == 404


# ── POST /agents/{name}/restart ───────────────────────────────────────────────

def test_restart_agent():
    with patch("k8s_service.restart_deployment") as mock:
        resp = client.post("/agents/my-agent-ui-agents/restart")
    assert resp.status_code == 200
    mock.assert_called_once_with("my-agent-ui-agents", "default")


def test_restart_agent_not_found_returns_404():
    with patch("k8s_service.restart_deployment", side_effect=RuntimeError("not found")):
        resp = client.post("/agents/missing-ui-agents/restart")
    assert resp.status_code == 404


# ── PATCH /agents/{name}/scale ───────────────────────────────────────────────

def test_scale_agent():
    with patch("k8s_service.scale_deployment") as mock:
        resp = client.patch("/agents/my-agent-ui-agents/scale", json={"replicas": 3})
    assert resp.status_code == 200
    mock.assert_called_once_with("my-agent-ui-agents", "default", 3)


def test_scale_agent_not_found_returns_404():
    with patch("k8s_service.scale_deployment", side_effect=RuntimeError("not found")):
        resp = client.patch("/agents/missing-ui-agents/scale", json={"replicas": 2})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```

Expected: `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Create main.py**

Create `tool-call-k8s/main.py`:

```python
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import k8s_service
from logging_config import reconfigure_uvicorn_loggers, setup_logging
from models import AgentResponse, DeployRequest, KubeconfigRequest, ScaleRequest

setup_logging("tool-call-k8s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    reconfigure_uvicorn_loggers("tool-call-k8s")
    yield


app = FastAPI(title="K8s Manager", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/kubeconfig")
async def save_kubeconfig(request: KubeconfigRequest) -> dict:
    try:
        k8s_service.write_kubeconfig(request.content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "ok"}


@app.post("/agents", response_model=AgentResponse, status_code=201)
async def create_agent(request: DeployRequest) -> AgentResponse:
    try:
        result = k8s_service.create_deployment(
            name=request.name,
            image=request.image,
            namespace=request.namespace,
            replicas=request.replicas,
            env=[e.model_dump() for e in request.env],
        )
    except RuntimeError as exc:
        msg = str(exc)
        if "already exists" in msg:
            raise HTTPException(status_code=400, detail=msg)
        if "kubeconfig not configured" in msg:
            raise HTTPException(status_code=503, detail="kubeconfig not configured")
        raise HTTPException(status_code=500, detail=msg)
    return AgentResponse(**result)


@app.get("/agents", response_model=list[AgentResponse])
async def list_agents() -> list[AgentResponse]:
    try:
        items = k8s_service.list_deployments()
    except RuntimeError as exc:
        msg = str(exc)
        if "kubeconfig not configured" in msg:
            raise HTTPException(status_code=503, detail="kubeconfig not configured")
        raise HTTPException(status_code=500, detail=msg)
    return [AgentResponse(**item) for item in items]


@app.delete("/agents/{name}")
async def delete_agent(name: str, namespace: str = "default") -> dict:
    try:
        k8s_service.delete_deployment(name, namespace)
    except RuntimeError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=f"Deployment {name} not found")
        raise HTTPException(status_code=500, detail=msg)
    return {"status": "ok"}


@app.post("/agents/{name}/restart")
async def restart_agent(name: str, namespace: str = "default") -> dict:
    try:
        k8s_service.restart_deployment(name, namespace)
    except RuntimeError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=f"Deployment {name} not found")
        raise HTTPException(status_code=500, detail=msg)
    return {"status": "ok"}


@app.patch("/agents/{name}/scale")
async def scale_agent(name: str, request: ScaleRequest, namespace: str = "default") -> dict:
    try:
        k8s_service.scale_deployment(name, namespace, request.replicas)
    except RuntimeError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=f"Deployment {name} not found")
        raise HTTPException(status_code=500, detail=msg)
    return {"status": "ok"}
```

- [ ] **Step 4: Run all tool-call-k8s tests**

```bash
pytest -v
```

Expected: all tests pass (models + k8s_service + main)

- [ ] **Step 5: Commit**

```bash
git add tool-call-k8s/main.py tool-call-k8s/tests/test_main.py
git commit -m "feat(k8s): add FastAPI routes with TDD"
```

---

### Task 5: Wire `tool-call-k8s` into docker-compose

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add the tool-call-k8s service and k8s_data volume**

In `docker-compose.yml`, add after the `tool-call-api` block and before `loki`:

```yaml
  tool-call-k8s:
    build:
      context: ./tool-call-k8s
    image: tool-call-k8s:latest
    ports:
      - "8001:8001"
    volumes:
      - k8s_data:/data
    depends_on:
      - tool-call-api
```

In the `tool-call-api` environment block, add:

```yaml
      K8S_BACKEND_URL: http://tool-call-k8s:8001
```

In the `volumes:` section at the bottom, add:

```yaml
  k8s_data:
```

- [ ] **Step 2: Build and start the new service**

```bash
docker compose build tool-call-k8s
docker compose up -d tool-call-k8s
```

- [ ] **Step 3: Verify it starts healthy**

```bash
docker compose ps tool-call-k8s
curl http://localhost:8001/agents  # expect 503 (kubeconfig not configured)
```

Expected: HTTP 503 with `{"detail": "kubeconfig not configured"}`

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(k8s): add tool-call-k8s to docker-compose"
```

---

### Task 6: `tool-call-api` — proxy routes for k8s service (TDD)

**Files:**
- Modify: `tool-call-api/main.py`
- Modify: `tool-call-api/tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

In `tool-call-api/tests/test_main.py`, append after the last test:

```python
async def test_agents_get_proxied(ac):
    mock_client = AsyncMock()
    mock_client.request.return_value = _resp(200, [{"name": "x-ui-agents", "namespace": "default",
        "image": "img", "replicas": 1, "ready_replicas": 1, "status": "Running"}])
    with patch("main._client", mock_client):
        resp = await ac.get("/api/agents")
    assert resp.status_code == 200
    call = mock_client.request.call_args
    assert call.args[0] == "GET"
    assert "localhost:8001/agents" in call.args[1]


async def test_agents_post_proxied(ac):
    mock_client = AsyncMock()
    mock_client.request.return_value = _resp(201, {"name": "x-ui-agents", "namespace": "default",
        "image": "img", "replicas": 1, "ready_replicas": 0, "status": "Pending"})
    with patch("main._client", mock_client):
        resp = await ac.post("/api/agents", json={"name": "x", "image": "img"})
    assert resp.status_code == 201
    call = mock_client.request.call_args
    assert call.args[0] == "POST"
    assert "localhost:8001/agents" in call.args[1]


async def test_k8s_config_proxied(ac):
    mock_client = AsyncMock()
    mock_client.post.return_value = _resp(200, {"status": "ok"})
    with patch("main._client", mock_client):
        resp = await ac.post("/api/k8s-config", json={"content": "apiVersion: v1"})
    assert resp.status_code == 200
    mock_client.post.assert_called_once()
    assert "localhost:8001/kubeconfig" in mock_client.post.call_args.args[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd tool-call-api && pytest tests/test_main.py -v -k "agents or k8s_config"
```

Expected: 3 failures with `404 Not Found`

- [ ] **Step 3: Add the proxy routes to main.py**

In `tool-call-api/main.py`, after the existing `_BACKEND` line, add:

```python
_K8S_BACKEND = os.getenv("K8S_BACKEND_URL", "http://localhost:8001")
```

Then add these two route handlers (place them before the `stream_events` route):

```python
@app.api_route("/api/agents/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def agents_proxy(path: str, request: Request) -> JSONResponse:
    body = await request.body()
    headers = {}
    if ct := request.headers.get("content-type"):
        headers["Content-Type"] = ct
    return await _proxy(
        _get_client().request(
            request.method,
            f"{_K8S_BACKEND}/agents/{path}",
            content=body or None,
            headers=headers if headers else None,
            params=dict(request.query_params),
            timeout=30.0,
        )
    )


@app.post("/api/k8s-config")
async def k8s_config_proxy(request: Request) -> JSONResponse:
    body = await request.body()
    return await _proxy(
        _get_client().post(
            f"{_K8S_BACKEND}/kubeconfig",
            content=body,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
    )
```

- [ ] **Step 4: Run all tool-call-api tests**

```bash
pytest tests/test_main.py -v
```

Expected: all 14 tests pass

- [ ] **Step 5: Rebuild tool-call-api and redeploy**

```bash
cd .. && docker compose build tool-call-api && docker compose up -d tool-call-api
```

- [ ] **Step 6: Commit**

```bash
git add tool-call-api/main.py tool-call-api/tests/test_main.py
git commit -m "feat(web): proxy /api/agents/* and /api/k8s-config to tool-call-k8s"
```

---

### Task 7: Angular — AgentsService

**Files:**
- Create: `tool-call-ui/src/app/services/agents.service.ts`

- [ ] **Step 1: Create agents.service.ts**

Create `tool-call-ui/src/app/services/agents.service.ts`:

```typescript
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { AdminService } from './admin.service';

const API = 'http://localhost:8080/api';

export interface EnvVar {
  key: string;
  value: string;
}

export interface DeployRequest {
  name: string;
  image: string;
  namespace: string;
  replicas: number;
  env: EnvVar[];
}

export interface AgentDeployment {
  name: string;
  namespace: string;
  image: string;
  replicas: number;
  ready_replicas: number;
  status: string;
}

@Injectable({ providedIn: 'root' })
export class AgentsService {
  constructor(private http: HttpClient, private adminService: AdminService) {}

  async syncKubeconfig(): Promise<void> {
    const creds = await this.adminService.getCredentials();
    if (creds?.kubeconfig) {
      await firstValueFrom(
        this.http.post(`${API}/k8s-config`, { content: creds.kubeconfig })
      );
    }
  }

  deploy(req: DeployRequest) {
    return firstValueFrom(this.http.post<AgentDeployment>(`${API}/agents`, req));
  }

  list() {
    return firstValueFrom(this.http.get<AgentDeployment[]>(`${API}/agents`));
  }

  delete(name: string, namespace: string) {
    return firstValueFrom(
      this.http.delete(`${API}/agents/${name}?namespace=${namespace}`)
    );
  }

  restart(name: string, namespace: string) {
    return firstValueFrom(
      this.http.post(`${API}/agents/${name}/restart?namespace=${namespace}`, {})
    );
  }

  scale(name: string, namespace: string, replicas: number) {
    return firstValueFrom(
      this.http.patch(`${API}/agents/${name}/scale?namespace=${namespace}`, { replicas })
    );
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd tool-call-ui && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add tool-call-ui/src/app/services/agents.service.ts
git commit -m "feat(ui): add AgentsService"
```

---

### Task 8: Angular — Agents parent component (tab switcher)

**Files:**
- Create: `tool-call-ui/src/app/admin/agents/agents.ts`
- Create: `tool-call-ui/src/app/admin/agents/agents.html`
- Create: `tool-call-ui/src/app/admin/agents/agents.css`

Note: The child components `DeployForm` and `AgentList` are created in Tasks 9 and 10. For now, stub them with placeholders so the parent compiles.

- [ ] **Step 1: Create stub child component directories**

```bash
mkdir -p tool-call-ui/src/app/admin/agents/deploy-form
mkdir -p tool-call-ui/src/app/admin/agents/agent-list
```

Create `tool-call-ui/src/app/admin/agents/deploy-form/deploy-form.ts` (temporary stub):

```typescript
import { Component, EventEmitter, Output } from '@angular/core';
@Component({ selector: 'app-deploy-form', standalone: true, template: '<p>Deployments</p>' })
export class DeployForm {
  @Output() deployed = new EventEmitter<void>();
}
```

Create `tool-call-ui/src/app/admin/agents/agent-list/agent-list.ts` (temporary stub):

```typescript
import { Component } from '@angular/core';
@Component({ selector: 'app-agent-list', standalone: true, template: '<p>View</p>' })
export class AgentList {}
```

- [ ] **Step 2: Create agents.ts**

Create `tool-call-ui/src/app/admin/agents/agents.ts`:

```typescript
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AgentsService } from '../../services/agents.service';
import { DeployForm } from './deploy-form/deploy-form';
import { AgentList } from './agent-list/agent-list';

@Component({
  selector: 'app-agents',
  standalone: true,
  imports: [CommonModule, DeployForm, AgentList],
  templateUrl: './agents.html',
  styleUrl: './agents.css',
})
export class Agents implements OnInit {
  tab: 'deployments' | 'view' = 'deployments';
  kubeconfigError = '';

  constructor(private agentsService: AgentsService) {}

  async ngOnInit() {
    try {
      await this.agentsService.syncKubeconfig();
    } catch {
      this.kubeconfigError = 'Kubeconfig not configured. Save credentials first.';
    }
  }

  onDeployed() {
    this.tab = 'view';
  }
}
```

- [ ] **Step 3: Create agents.html**

Create `tool-call-ui/src/app/admin/agents/agents.html`:

```html
<h2>Agents</h2>

@if (kubeconfigError) {
  <div class="banner">{{ kubeconfigError }}</div>
}

<div class="tabs">
  <button class="tab" [class.active]="tab === 'deployments'" (click)="tab = 'deployments'">
    Deployments
  </button>
  <button class="tab" [class.active]="tab === 'view'" (click)="tab = 'view'">
    View
  </button>
</div>

@if (tab === 'deployments') {
  <app-deploy-form (deployed)="onDeployed()" />
}
@if (tab === 'view') {
  <app-agent-list />
}
```

- [ ] **Step 4: Create agents.css**

Create `tool-call-ui/src/app/admin/agents/agents.css`:

```css
h2 { font-size: 18px; font-weight: 600; margin-bottom: 20px; color: #e6edf3; }

.banner {
  background: #3d1f1f;
  border: 1px solid #f85149;
  border-radius: 6px;
  color: #f85149;
  font-size: 13px;
  margin-bottom: 16px;
  padding: 10px 14px;
}

.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  border-bottom: 1px solid #30363d;
  padding-bottom: 0;
}

.tab {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #8b949e;
  cursor: pointer;
  font-size: 14px;
  margin-bottom: -1px;
  padding: 8px 16px;
  transition: color 0.15s, border-color 0.15s;
}

.tab:hover { color: #e6edf3; }

.tab.active {
  border-bottom-color: #58a6ff;
  color: #58a6ff;
}
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 6: Commit stubs + parent**

```bash
git add tool-call-ui/src/app/admin/agents/
git commit -m "feat(ui): add Agents parent component with tab switcher"
```

---

### Task 9: Angular — DeployForm component

**Files:**
- Modify: `tool-call-ui/src/app/admin/agents/deploy-form/deploy-form.ts` (replace stub)
- Create: `tool-call-ui/src/app/admin/agents/deploy-form/deploy-form.html`
- Create: `tool-call-ui/src/app/admin/agents/deploy-form/deploy-form.css`

- [ ] **Step 1: Replace the stub with the real deploy-form.ts**

Overwrite `tool-call-ui/src/app/admin/agents/deploy-form/deploy-form.ts`:

```typescript
import { Component, EventEmitter, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AgentsService, EnvVar } from '../../../services/agents.service';

@Component({
  selector: 'app-deploy-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './deploy-form.html',
  styleUrl: './deploy-form.css',
})
export class DeployForm {
  @Output() deployed = new EventEmitter<void>();

  form = { name: '', image: '', namespace: 'default', replicas: 1 };
  env: EnvVar[] = [];
  deploying = false;
  error = '';

  get fullName(): string {
    return this.form.name ? `${this.form.name}-ui-agents` : '';
  }

  constructor(private agentsService: AgentsService) {}

  addEnvVar() {
    this.env.push({ key: '', value: '' });
  }

  removeEnvVar(i: number) {
    this.env.splice(i, 1);
  }

  async deploy() {
    this.deploying = true;
    this.error = '';
    try {
      await this.agentsService.deploy({
        name: this.form.name,
        image: this.form.image,
        namespace: this.form.namespace,
        replicas: this.form.replicas,
        env: this.env.filter(e => e.key.trim() !== ''),
      });
      this.deployed.emit();
    } catch (e: any) {
      this.error = e?.error?.detail ?? 'Deployment failed';
    } finally {
      this.deploying = false;
    }
  }
}
```

- [ ] **Step 2: Create deploy-form.html**

Create `tool-call-ui/src/app/admin/agents/deploy-form/deploy-form.html`:

```html
<div class="form">
  <div class="row">
    <div class="field">
      <label>Name</label>
      <input type="text" [(ngModel)]="form.name" placeholder="my-agent" />
      @if (fullName) {
        <span class="preview">→ {{ fullName }}</span>
      }
    </div>
    <div class="field">
      <label>Docker Image</label>
      <input type="text" [(ngModel)]="form.image" placeholder="my-org/my-agent:latest" />
    </div>
  </div>

  <div class="row">
    <div class="field">
      <label>Namespace</label>
      <input type="text" [(ngModel)]="form.namespace" />
    </div>
    <div class="field">
      <label>Replicas</label>
      <input type="number" [(ngModel)]="form.replicas" min="1" />
    </div>
  </div>

  <div class="field">
    <label>Environment Variables</label>
    @for (ev of env; track $index) {
      <div class="env-row">
        <input type="text" [(ngModel)]="ev.key" placeholder="KEY" />
        <input type="text" [(ngModel)]="ev.value" placeholder="value" />
        <button class="btn-remove" (click)="removeEnvVar($index)">✕</button>
      </div>
    }
    <button class="btn-add" (click)="addEnvVar()">+ Add variable</button>
  </div>

  <div class="actions">
    <button (click)="deploy()" [disabled]="deploying || !form.name || !form.image">
      {{ deploying ? 'Deploying…' : 'Deploy' }}
    </button>
    @if (error) {
      <span class="error">{{ error }}</span>
    }
  </div>
</div>
```

- [ ] **Step 3: Create deploy-form.css**

Create `tool-call-ui/src/app/admin/agents/deploy-form/deploy-form.css`:

```css
.form { display: flex; flex-direction: column; gap: 20px; max-width: 640px; }

.row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.field { display: flex; flex-direction: column; gap: 6px; }

label {
  color: #8b949e;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

input[type="text"],
input[type="number"] {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 6px;
  color: #e6edf3;
  font-size: 14px;
  padding: 8px 12px;
  outline: none;
}

input:focus { border-color: #58a6ff; }

.preview { color: #58a6ff; font-size: 12px; }

.env-row { display: flex; gap: 8px; margin-bottom: 6px; }

.env-row input { flex: 1; }

.btn-remove {
  background: none;
  border: 1px solid #f85149;
  border-radius: 6px;
  color: #f85149;
  cursor: pointer;
  padding: 4px 10px;
}

.btn-add {
  background: none;
  border: none;
  color: #58a6ff;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
  text-align: left;
}

.actions { display: flex; align-items: center; gap: 12px; }

button[disabled] { opacity: 0.6; cursor: not-allowed; }

button:not(.btn-remove):not(.btn-add) {
  background: #238636;
  border: 1px solid #2ea043;
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
  font-size: 14px;
  padding: 8px 20px;
}

button:not(.btn-remove):not(.btn-add):hover:not(:disabled) { background: #2ea043; }

.error { color: #f85149; font-size: 14px; }
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add tool-call-ui/src/app/admin/agents/deploy-form/
git commit -m "feat(ui): implement DeployForm component"
```

---

### Task 10: Angular — AgentList component

**Files:**
- Modify: `tool-call-ui/src/app/admin/agents/agent-list/agent-list.ts` (replace stub)
- Create: `tool-call-ui/src/app/admin/agents/agent-list/agent-list.html`
- Create: `tool-call-ui/src/app/admin/agents/agent-list/agent-list.css`

- [ ] **Step 1: Replace the stub with the real agent-list.ts**

Overwrite `tool-call-ui/src/app/admin/agents/agent-list/agent-list.ts`:

```typescript
import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AgentsService, AgentDeployment } from '../../../services/agents.service';

@Component({
  selector: 'app-agent-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './agent-list.html',
  styleUrl: './agent-list.css',
})
export class AgentList implements OnInit, OnDestroy {
  agents: AgentDeployment[] = [];
  loading = true;
  error = '';
  private _poll: ReturnType<typeof setInterval> | null = null;

  constructor(private agentsService: AgentsService) {}

  ngOnInit() {
    this.load();
    this._poll = setInterval(() => this.load(), 10_000);
  }

  ngOnDestroy() {
    if (this._poll) clearInterval(this._poll);
  }

  async load() {
    try {
      this.agents = await this.agentsService.list();
      this.error = '';
    } catch (e: any) {
      this.error = e?.error?.detail ?? 'Failed to load agents';
    } finally {
      this.loading = false;
    }
  }

  async scale(agent: AgentDeployment, delta: number) {
    const next = Math.max(0, agent.replicas + delta);
    try {
      await this.agentsService.scale(agent.name, agent.namespace, next);
      agent.replicas = next;
    } catch (e: any) {
      alert(e?.error?.detail ?? 'Scale failed');
    }
  }

  async restart(agent: AgentDeployment) {
    try {
      await this.agentsService.restart(agent.name, agent.namespace);
    } catch (e: any) {
      alert(e?.error?.detail ?? 'Restart failed');
    }
  }

  async delete(agent: AgentDeployment) {
    if (!confirm(`Delete ${agent.name}?`)) return;
    try {
      await this.agentsService.delete(agent.name, agent.namespace);
      this.agents = this.agents.filter(a => a.name !== agent.name);
    } catch (e: any) {
      alert(e?.error?.detail ?? 'Delete failed');
    }
  }
}
```

- [ ] **Step 2: Create agent-list.html**

Create `tool-call-ui/src/app/admin/agents/agent-list/agent-list.html`:

```html
@if (loading) {
  <p class="muted">Loading…</p>
}
@if (error) {
  <p class="error">{{ error }}</p>
}
@if (!loading && !error && agents.length === 0) {
  <p class="muted">No agents deployed yet.</p>
}
@if (agents.length > 0) {
  <table>
    <thead>
      <tr>
        <th>Name</th>
        <th>Namespace</th>
        <th>Image</th>
        <th>Replicas</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      @for (a of agents; track a.name) {
        <tr>
          <td>{{ a.name }}</td>
          <td class="muted">{{ a.namespace }}</td>
          <td class="muted img">{{ a.image }}</td>
          <td>
            <span class="scale-cell">
              {{ a.replicas }}
              <span class="scale-btns">
                <button (click)="scale(a, -1)">−</button>
                <button (click)="scale(a, 1)">+</button>
              </span>
            </span>
          </td>
          <td><span class="status" [attr.data-status]="a.status">{{ a.status }}</span></td>
          <td class="action-cell">
            <button class="btn-restart" (click)="restart(a)">Restart</button>
            <button class="btn-delete" (click)="delete(a)">Delete</button>
          </td>
        </tr>
      }
    </tbody>
  </table>
}
```

- [ ] **Step 3: Create agent-list.css**

Create `tool-call-ui/src/app/admin/agents/agent-list/agent-list.css`:

```css
.muted { color: #8b949e; font-size: 14px; }
.error { color: #f85149; font-size: 14px; }

table {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
}

th {
  border-bottom: 1px solid #30363d;
  color: #8b949e;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.07em;
  padding: 6px 12px;
  text-align: left;
  text-transform: uppercase;
}

td {
  border-bottom: 1px solid #1c2128;
  color: #e6edf3;
  padding: 10px 12px;
  vertical-align: middle;
}

td.muted { color: #8b949e; }
td.img { font-family: monospace; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.scale-cell { align-items: center; display: flex; gap: 8px; }

.scale-btns { display: flex; gap: 3px; }

.scale-btns button {
  background: none;
  border: 1px solid #30363d;
  border-radius: 4px;
  color: #58a6ff;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  padding: 2px 7px;
}

.scale-btns button:hover { border-color: #58a6ff; }

.status[data-status="Running"] { color: #3fb950; }
.status[data-status="Pending"] { color: #d29922; }
.status[data-status="Failed"]  { color: #f85149; }

.action-cell { display: flex; gap: 6px; }

.btn-restart, .btn-delete {
  border-radius: 5px;
  cursor: pointer;
  font-size: 12px;
  padding: 4px 10px;
}

.btn-restart {
  background: none;
  border: 1px solid #d29922;
  color: #d29922;
}

.btn-restart:hover { background: #2d2209; }

.btn-delete {
  background: none;
  border: 1px solid #f85149;
  color: #f85149;
}

.btn-delete:hover { background: #3d1f1f; }
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add tool-call-ui/src/app/admin/agents/agent-list/
git commit -m "feat(ui): implement AgentList component with scale, restart, delete"
```

---

### Task 11: Wire routing and navigation

**Files:**
- Modify: `tool-call-ui/src/app/admin/admin.routes.ts`
- Modify: `tool-call-ui/src/app/admin/admin-layout/admin-layout.html`

- [ ] **Step 1: Add the agents route**

In `tool-call-ui/src/app/admin/admin.routes.ts`, add after the `persona` route:

```typescript
  {
    path: 'agents',
    loadComponent: () =>
      import('./agents/agents').then((m) => m.Agents),
  },
```

- [ ] **Step 2: Add the Agents nav link**

In `tool-call-ui/src/app/admin/admin-layout/admin-layout.html`, add after the Credentials link:

```html
    <a routerLink="/admin/agents" routerLinkActive="active" class="nav-item">Agents</a>
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add tool-call-ui/src/app/admin/admin.routes.ts \
        tool-call-ui/src/app/admin/admin-layout/admin-layout.html
git commit -m "feat(ui): wire Agents route and sidebar nav link"
```

---

### Task 12: End-to-end smoke test

- [ ] **Step 1: Ensure all Docker services are running**

```bash
docker compose up -d
docker compose ps
```

Expected: tool-call-agent, tool-call-api, tool-call-k8s all Up

- [ ] **Step 2: Start Angular dev server**

```bash
cd tool-call-ui && ng serve
```

Open http://localhost:4200

- [ ] **Step 3: Save kubeconfig in Credentials**

- Navigate to Admin → Credentials
- Paste the kubeconfig from `kubectl config view --minify --context=minikube --flatten | sed 's/https:\/\/localhost:/https:\/\/host.docker.internal:/g'` with `insecure-skip-tls-verify: true` replacing `certificate-authority-data`
- Click Save

- [ ] **Step 4: Deploy a test agent**

- Navigate to Admin → Agents (sidebar)
- Confirm no kubeconfig banner appears (kubeconfig synced on load)
- Enter name: `test`, image: `nginx:latest`, namespace: `default`, replicas: 1
- Click Deploy
- UI should switch to View tab automatically

- [ ] **Step 5: Verify in View tab**

- Deployment `test-ui-agents` should appear with status Running or Pending
- Click `+` to scale to 2 — replicas column updates
- Click Restart — no error
- Click Delete → confirm → row disappears

- [ ] **Step 6: Verify via kubectl from host**

```bash
kubectl get deployments --all-namespaces | grep ui-agents
```

Expected: row for `test-ui-agents` (or absent if you deleted it)

- [ ] **Step 7: Final commit**

```bash
git add -p  # stage any last tweaks
git commit -m "feat: Agents admin panel — deploy and manage K8s agents via UI"
```
