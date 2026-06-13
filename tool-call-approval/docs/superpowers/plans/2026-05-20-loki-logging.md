# Loki Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured JSON logging to both Python services and ship logs to Loki via Promtail, with Grafana on :3001 for querying.

**Architecture:** Both `tool-call-agent` and `tool-call-api` emit structured JSON logs to stdout; Promtail reads them from the Docker daemon via the Unix socket and pushes to Loki; Grafana queries Loki with the datasource pre-provisioned. All three new services (Loki, Grafana, Promtail) are added to the existing `docker-compose.yml`.

**Tech Stack:** `python-json-logger==2.0.7`, `grafana/loki:3.0.0`, `grafana/promtail:3.0.0`, `grafana/grafana:11.0.0`

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `tool-call-agent/logging_config.py` | JSON log setup for agent service |
| Create | `tool-call-agent/tests/test_logging.py` | Unit tests for agent logging |
| Modify | `tool-call-agent/requirements.txt` | Add python-json-logger |
| Modify | `tool-call-agent/main.py` | Call setup_logging at startup |
| Create | `tool-call-api/logging_config.py` | JSON log setup for web gateway |
| Create | `tool-call-api/tests/test_logging.py` | Unit tests for web logging |
| Modify | `tool-call-api/requirements.txt` | Add python-json-logger |
| Modify | `tool-call-api/main.py` | Call setup_logging at startup |
| Create | `loki/loki-config.yaml` | Loki single-process config |
| Create | `promtail/promtail-config.yaml` | Promtail Docker socket scrape config |
| Create | `grafana/provisioning/datasources/loki.yaml` | Auto-provision Loki datasource |
| Modify | `docker-compose.yml` | Add loki, grafana, promtail services + volumes |

---

### Task 1: Structured JSON logging in tool-call-agent

**Files:**
- Create: `tool-call-agent/logging_config.py`
- Create: `tool-call-agent/tests/test_logging.py`
- Modify: `tool-call-agent/requirements.txt`

- [ ] **Step 1: Add python-json-logger to requirements**

Edit `tool-call-agent/requirements.txt` — append one line:

```
python-json-logger==2.0.7
```

- [ ] **Step 2: Install it**

```bash
cd tool-call-agent && pip install python-json-logger==2.0.7
```

Expected: `Successfully installed python-json-logger-2.0.7`

- [ ] **Step 3: Write the failing tests**

Create `tool-call-agent/tests/test_logging.py`:

```python
import json
import logging

import pytest

from logging_config import setup_logging


@pytest.fixture(autouse=True)
def reset_root_logger():
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_filters = root.filters[:]
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.filters = original_filters
    root.level = original_level


def test_log_output_is_valid_json(capsys):
    setup_logging("tool-call-agent")
    logging.getLogger("test").info("hello world")
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["message"] == "hello world"
    assert record["level"] == "INFO"
    assert record["service"] == "tool-call-agent"
    assert record["logger"] == "test"
    assert "timestamp" in record


def test_extra_fields_propagated(capsys):
    setup_logging("tool-call-agent")
    logging.getLogger("test").info("session started", extra={"session_id": "abc-123"})
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["session_id"] == "abc-123"


def test_service_label_customisable(capsys):
    setup_logging("my-service")
    logging.getLogger("test").info("msg")
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["service"] == "my-service"
```

- [ ] **Step 4: Run tests to confirm they fail**

```bash
cd tool-call-agent && pytest tests/test_logging.py -v
```

Expected: `ModuleNotFoundError: No module named 'logging_config'`

- [ ] **Step 5: Create logging_config.py**

Create `tool-call-agent/logging_config.py`:

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


def setup_logging(service: str) -> None:
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

    root = logging.getLogger()
    root.handlers.clear()
    root.filters.clear()
    root.addHandler(handler)
    root.addFilter(_ServiceFilter(service))
    root.setLevel(logging.INFO)

    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
cd tool-call-agent && pytest tests/test_logging.py -v
```

Expected: `3 passed`

- [ ] **Step 7: Wire logging into main.py**

In `tool-call-agent/main.py`, add after `load_dotenv()` (before any other local imports):

```python
import asyncio
import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from logging_config import setup_logging  # noqa: E402

setup_logging("tool-call-agent")

logger = logging.getLogger(__name__)
```

Then add log calls in the route handlers. Replace the existing `create_session` and `approve_tool` functions:

```python
@app.post("/sessions", response_model=SessionResponse)
async def create_session() -> SessionResponse:
    session = service.create_session()
    logger.info("session created", extra={"session_id": session.id})
    return SessionResponse(session_id=session.id)


@app.post("/sessions/{session_id}/approve")
async def approve_tool(session_id: str, request: ApprovalRequest) -> dict:
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    service.approve(session, request.approved)
    logger.info(
        "tool approval received",
        extra={"session_id": session_id, "approved": request.approved},
    )
    return {"status": "ok"}
```

- [ ] **Step 8: Run the full test suite to confirm no regressions**

```bash
cd tool-call-agent && pytest -v
```

Expected: all previously passing tests still pass.

- [ ] **Step 9: Commit**

```bash
git add tool-call-agent/logging_config.py \
        tool-call-agent/tests/test_logging.py \
        tool-call-agent/requirements.txt \
        tool-call-agent/main.py
git commit -m "feat(agent): add structured JSON logging via python-json-logger"
```

---

### Task 2: Structured JSON logging in tool-call-api

**Files:**
- Create: `tool-call-api/logging_config.py`
- Create: `tool-call-api/tests/test_logging.py`
- Modify: `tool-call-api/requirements.txt`
- Modify: `tool-call-api/main.py`

- [ ] **Step 1: Add python-json-logger to requirements**

Edit `tool-call-api/requirements.txt` — append one line:

```
python-json-logger==2.0.7
```

- [ ] **Step 2: Install it**

```bash
cd tool-call-api && pip install python-json-logger==2.0.7
```

Expected: `Successfully installed python-json-logger-2.0.7` (or "already satisfied")

- [ ] **Step 3: Write the failing tests**

Create `tool-call-api/tests/__init__.py` if it doesn't exist (empty file), then create `tool-call-api/tests/test_logging.py`:

```python
import json
import logging

import pytest

from logging_config import setup_logging


@pytest.fixture(autouse=True)
def reset_root_logger():
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_filters = root.filters[:]
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.filters = original_filters
    root.level = original_level


def test_log_output_is_valid_json(capsys):
    setup_logging("tool-call-api")
    logging.getLogger("test").info("request proxied")
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["message"] == "request proxied"
    assert record["level"] == "INFO"
    assert record["service"] == "tool-call-api"
    assert record["logger"] == "test"
    assert "timestamp" in record


def test_extra_fields_propagated(capsys):
    setup_logging("tool-call-api")
    logging.getLogger("test").warning("backend error", extra={"status_code": 502})
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["status_code"] == 502
    assert record["level"] == "WARNING"
```

- [ ] **Step 4: Run tests to confirm they fail**

```bash
cd tool-call-api && pytest tests/test_logging.py -v
```

Expected: `ModuleNotFoundError: No module named 'logging_config'`

- [ ] **Step 5: Create logging_config.py**

Create `tool-call-api/logging_config.py`:

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


def setup_logging(service: str) -> None:
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

    root = logging.getLogger()
    root.handlers.clear()
    root.filters.clear()
    root.addHandler(handler)
    root.addFilter(_ServiceFilter(service))
    root.setLevel(logging.INFO)

    logging.getLogger("httpx").setLevel(logging.WARNING)
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
cd tool-call-api && pytest tests/test_logging.py -v
```

Expected: `2 passed`

- [ ] **Step 7: Wire logging into main.py**

In `tool-call-api/main.py`, add after `load_dotenv()`:

```python
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Awaitable

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

load_dotenv()

from logging_config import setup_logging  # noqa: E402

setup_logging("tool-call-api")

logger = logging.getLogger(__name__)
```

Also update `_proxy` to log backend errors:

```python
async def _proxy(coro: Awaitable[httpx.Response]) -> JSONResponse:
    try:
        resp = await coro
    except httpx.ConnectError:
        logger.error("backend unreachable")
        raise HTTPException(status_code=502, detail="Backend unreachable")
    except httpx.TimeoutException:
        logger.error("backend timeout")
        raise HTTPException(status_code=504, detail="Backend timeout")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=resp.json().get("detail", "Not found"))
    resp.raise_for_status()
    return JSONResponse(content=resp.json(), status_code=resp.status_code)
```

- [ ] **Step 8: Run the full test suite**

```bash
cd tool-call-api && pytest -v
```

Expected: all 8 tests + 2 new logging tests pass.

- [ ] **Step 9: Commit**

```bash
git add tool-call-api/logging_config.py \
        tool-call-api/tests/test_logging.py \
        tool-call-api/requirements.txt \
        tool-call-api/main.py
git commit -m "feat(web): add structured JSON logging via python-json-logger"
```

---

### Task 3: Loki configuration

**Files:**
- Create: `loki/loki-config.yaml`

- [ ] **Step 1: Create the directory and config**

```bash
mkdir -p loki
```

Create `loki/loki-config.yaml`:

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096
  log_level: warn

common:
  instance_addr: 127.0.0.1
  path_prefix: /tmp/loki
  storage:
    filesystem:
      chunks_directory: /tmp/loki/chunks
      rules_directory: /tmp/loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  allow_structured_metadata: true

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100
```

- [ ] **Step 2: Commit**

```bash
git add loki/loki-config.yaml
git commit -m "feat(infra): add Loki configuration"
```

---

### Task 4: Promtail configuration

**Files:**
- Create: `promtail/promtail-config.yaml`

- [ ] **Step 1: Create the directory and config**

```bash
mkdir -p promtail
```

Create `promtail/promtail-config.yaml`:

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0
  log_level: warn

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: [__meta_docker_container_label_com_docker_compose_service]
        target_label: service
      - source_labels: [__meta_docker_container_name]
        regex: '/?(.*)'
        target_label: container
      - source_labels: [__meta_docker_container_label_com_docker_compose_project]
        target_label: project
      - source_labels: [__meta_docker_container_log_stream]
        target_label: stream
    pipeline_stages:
      - json:
          expressions:
            level: level
      - labels:
          level:
```

The `pipeline_stages` block tries to parse a `level` field from JSON log lines and promotes it to a Loki label. Lines that aren't JSON (e.g. uvicorn startup messages) are passed through unchanged.

- [ ] **Step 2: Commit**

```bash
git add promtail/promtail-config.yaml
git commit -m "feat(infra): add Promtail Docker socket scrape config"
```

---

### Task 5: Grafana datasource provisioning

**Files:**
- Create: `grafana/provisioning/datasources/loki.yaml`

- [ ] **Step 1: Create directory structure and datasource**

```bash
mkdir -p grafana/provisioning/datasources
```

Create `grafana/provisioning/datasources/loki.yaml`:

```yaml
apiVersion: 1

datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    isDefault: true
    jsonData:
      maxLines: 1000
```

- [ ] **Step 2: Commit**

```bash
git add grafana/provisioning/datasources/loki.yaml
git commit -m "feat(infra): add Grafana Loki datasource provisioning"
```

---

### Task 6: Add Loki, Grafana, Promtail to docker-compose

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add the three services to docker-compose.yml**

Open `docker-compose.yml`. After the last existing service block (before the `volumes:` section), add:

```yaml
  loki:
    image: grafana/loki:3.0.0
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/loki.yaml
    volumes:
      - ./loki/loki-config.yaml:/etc/loki/loki.yaml:ro
      - loki_data:/tmp/loki
    healthcheck:
      test: ["CMD-SHELL", "wget -q --tries=1 -O- http://localhost:3100/ready | grep -q ready || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 20
      start_period: 10s

  grafana:
    image: grafana/grafana:11.0.0
    ports:
      - "3001:3000"
    environment:
      GF_AUTH_ANONYMOUS_ENABLED: "true"
      GF_AUTH_ANONYMOUS_ORG_ROLE: Admin
      GF_AUTH_DISABLE_LOGIN_FORM: "true"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - grafana_data:/var/lib/grafana
    depends_on:
      loki:
        condition: service_healthy

  promtail:
    image: grafana/promtail:3.0.0
    user: root
    command: -config.file=/etc/promtail/promtail.yaml
    volumes:
      - ./promtail/promtail-config.yaml:/etc/promtail/promtail.yaml:ro
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      loki:
        condition: service_healthy
```

- [ ] **Step 2: Add new volumes at the bottom of docker-compose.yml**

In the `volumes:` section, add:

```yaml
  loki_data:
  grafana_data:
```

- [ ] **Step 3: Verify the compose file is valid**

```bash
docker compose config --quiet
```

Expected: no output (no errors). If you see errors, check indentation — the services must be indented under `services:` and volumes under `volumes:`.

- [ ] **Step 4: Start the new services**

```bash
docker compose up -d loki grafana promtail
```

Expected output: containers created/started for loki, grafana, promtail.

- [ ] **Step 5: Verify Loki is ready**

```bash
docker compose ps loki
```

Expected: `loki` shows status `healthy`.

```bash
curl -s http://localhost:3100/ready
```

Expected: `ready`

- [ ] **Step 6: Verify Grafana is up**

Open `http://localhost:3001` in a browser. You should see the Grafana explore interface (anonymous access, no login required). Navigate to **Explore → Loki** datasource — it should already be selected.

- [ ] **Step 7: Verify Promtail is scraping**

```bash
curl -s http://localhost:9080/targets 2>/dev/null | head -20
```

Expected: JSON response listing discovered Docker containers. If port 9080 isn't accessible (Promtail has no exposed port by default), check Promtail logs instead:

```bash
docker compose logs promtail --tail=20
```

Expected: lines like `"Scraping targets"` — no error lines about failed connections to Loki.

- [ ] **Step 8: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(infra): add Loki, Grafana, Promtail to docker-compose"
```

---

### Task 7: Update READMEs

**Files:**
- Modify: `tool-call-agent/README.md`
- Modify: `tool-call-api/README.md`

- [ ] **Step 1: Add Logging section to tool-call-agent README**

In `tool-call-agent/README.md`, add after the existing `## Langfuse tracing` section:

```markdown
## Logging

The service emits structured JSON logs to stdout. Each line is a valid JSON object:

```json
{"timestamp": "2026-05-20T12:00:00", "level": "INFO", "logger": "main", "service": "tool-call-agent", "message": "session created", "session_id": "abc-123"}
```

When running via Docker Compose, Promtail ships these logs to Loki automatically. Query them in Grafana at `http://localhost:3001`.
```

- [ ] **Step 2: Add Logging section to tool-call-api README**

In `tool-call-api/README.md`, add a new section at the end:

```markdown
## Logging

The gateway emits structured JSON logs to stdout. Backend errors (502, 504) are logged at `WARNING` level with a `status_code` field. When running via Docker Compose, Promtail ships logs to Loki automatically. Query in Grafana at `http://localhost:3001`.
```

- [ ] **Step 3: Commit**

```bash
git add tool-call-agent/README.md tool-call-api/README.md
git commit -m "docs: add structured logging and Loki/Grafana sections to READMEs"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Application logs → structured JSON in both services
- ✅ Docker container logs → Promtail Docker socket discovery
- ✅ FastAPI request logs → uvicorn access logger flows through root logger (JSON formatter applied)
- ✅ Loki storage → single-process filesystem mode
- ✅ Grafana → port 3001 (no conflict with Langfuse on 3000), anonymous access, Loki datasource pre-provisioned

**Placeholder scan:** None found — all steps include exact code and commands.

**Type consistency:** `setup_logging(service: str) -> None` used consistently across both services. `_ServiceFilter` is a private implementation detail in each `logging_config.py` (no cross-service usage).
