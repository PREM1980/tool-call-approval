# Tool Call Agent Functional Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `tool-call-agent` internals into functionality-based folders while keeping existing root uvicorn entrypoints working.

**Architecture:** Create an internal `app/` package under `tool-call-agent` and move modules by responsibility: `api`, `schemas`, `services`, `repositories`, `domain`, `tools`, and `core`. Keep root `main.py`, `main_mock.py`, and `main_websocket.py` as thin wrappers so Docker and local `uvicorn main:app` commands do not change.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, Docker Compose.

---

## File Structure

Create:

- `tool-call-agent/app/__init__.py`: package marker.
- `tool-call-agent/app/api/__init__.py`: API package marker.
- `tool-call-agent/app/schemas/__init__.py`: schema package marker.
- `tool-call-agent/app/services/__init__.py`: service package marker.
- `tool-call-agent/app/repositories/__init__.py`: repository package marker.
- `tool-call-agent/app/domain/__init__.py`: domain package marker.
- `tool-call-agent/app/tools/__init__.py`: tools package marker.
- `tool-call-agent/app/core/__init__.py`: core package marker.

Move:

- `tool-call-agent/admin_router.py` -> `tool-call-agent/app/api/admin_router.py`
- `tool-call-agent/main.py` -> `tool-call-agent/app/api/main.py`
- `tool-call-agent/main_mock.py` -> `tool-call-agent/app/api/mock.py`
- `tool-call-agent/main_websocket.py` -> `tool-call-agent/app/api/websocket.py`
- `tool-call-agent/models.py` -> `tool-call-agent/app/schemas/messages.py`
- `tool-call-agent/admin_models.py` -> `tool-call-agent/app/schemas/admin.py`
- `tool-call-agent/agent_service.py` -> `tool-call-agent/app/services/agent_service.py`
- `tool-call-agent/mock_agent.py` -> `tool-call-agent/app/services/mock_agent.py`
- `tool-call-agent/repository.py` -> `tool-call-agent/app/repositories/agent_repository.py`
- `tool-call-agent/admin_repository.py` -> `tool-call-agent/app/repositories/admin_repository.py`
- `tool-call-agent/session.py` -> `tool-call-agent/app/domain/session.py`
- `tool-call-agent/tools.py` -> `tool-call-agent/app/tools/registry.py`
- `tool-call-agent/logging_config.py` -> `tool-call-agent/app/core/logging_config.py`
- `tool-call-agent/system_prompt_defaults.py` -> `tool-call-agent/app/core/system_prompts.py`
- `tool-call-agent/system_prompt_defaults_old.py` -> `tool-call-agent/app/core/system_prompts_old.py`

Modify:

- `tool-call-agent/main.py`: root compatibility wrapper for `app.api.main`.
- `tool-call-agent/main_mock.py`: root compatibility wrapper for `app.api.mock`.
- `tool-call-agent/main_websocket.py`: root compatibility wrapper for `app.api.websocket`.
- `tool-call-agent/client.py`: no module import changes; it currently uses only standard library and `httpx`.
- `tool-call-agent/evals.py`: no module import changes; it currently uses only standard library, `dotenv`, `agno`, and `fpdf`.
- `tool-call-agent/tests/*.py`: update imports to new package paths where tests target internals; keep `from main import app` for route tests that intentionally test the deployment entrypoint.
- `tool-call-agent/README.md`: update code layout notes and local entrypoint guidance.

---

### Task 1: Baseline And Package Scaffold

**Files:**
- Create: `tool-call-agent/app/__init__.py`
- Create: `tool-call-agent/app/api/__init__.py`
- Create: `tool-call-agent/app/schemas/__init__.py`
- Create: `tool-call-agent/app/services/__init__.py`
- Create: `tool-call-agent/app/repositories/__init__.py`
- Create: `tool-call-agent/app/domain/__init__.py`
- Create: `tool-call-agent/app/tools/__init__.py`
- Create: `tool-call-agent/app/core/__init__.py`

- [ ] **Step 1: Run focused baseline tests before moving files**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval/tool-call-agent
/private/tmp/tool-call-approval-venv/bin/python -m pytest tests/test_main.py -q
```

Expected: `15 passed`.

- [ ] **Step 2: Create package folders**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval/tool-call-agent
mkdir -p app/api app/schemas app/services app/repositories app/domain app/tools app/core
```

Expected: command exits `0`.

- [ ] **Step 3: Add package marker files**

Use `apply_patch` to add these exact files with one-line package comments:

```python
# Package marker for tool-call-agent internals.
```

Files:

```text
tool-call-agent/app/__init__.py
tool-call-agent/app/api/__init__.py
tool-call-agent/app/schemas/__init__.py
tool-call-agent/app/services/__init__.py
tool-call-agent/app/repositories/__init__.py
tool-call-agent/app/domain/__init__.py
tool-call-agent/app/tools/__init__.py
tool-call-agent/app/core/__init__.py
```

- [ ] **Step 4: Verify the empty package imports**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval/tool-call-agent
/private/tmp/tool-call-approval-venv/bin/python -c "import app, app.api, app.schemas, app.services, app.repositories, app.domain, app.tools, app.core; print('ok')"
```

Expected: prints `ok`.

---

### Task 2: Move Schema, Domain, Core, Repository, Service, And Tool Modules

**Files:**
- Move: all module paths listed in the File Structure section.
- Modify: moved files only for imports.

- [ ] **Step 1: Move files with git-aware commands**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval
git mv tool-call-agent/admin_router.py tool-call-agent/app/api/admin_router.py
git mv tool-call-agent/main.py tool-call-agent/app/api/main.py
git mv tool-call-agent/main_mock.py tool-call-agent/app/api/mock.py
git mv tool-call-agent/main_websocket.py tool-call-agent/app/api/websocket.py
git mv tool-call-agent/models.py tool-call-agent/app/schemas/messages.py
git mv tool-call-agent/admin_models.py tool-call-agent/app/schemas/admin.py
git mv tool-call-agent/agent_service.py tool-call-agent/app/services/agent_service.py
git mv tool-call-agent/mock_agent.py tool-call-agent/app/services/mock_agent.py
git mv tool-call-agent/repository.py tool-call-agent/app/repositories/agent_repository.py
git mv tool-call-agent/admin_repository.py tool-call-agent/app/repositories/admin_repository.py
git mv tool-call-agent/session.py tool-call-agent/app/domain/session.py
git mv tool-call-agent/tools.py tool-call-agent/app/tools/registry.py
git mv tool-call-agent/logging_config.py tool-call-agent/app/core/logging_config.py
git mv tool-call-agent/system_prompt_defaults.py tool-call-agent/app/core/system_prompts.py
git mv tool-call-agent/system_prompt_defaults_old.py tool-call-agent/app/core/system_prompts_old.py
```

Expected: each `git mv` exits `0`.

- [ ] **Step 2: Update imports in `app/api/main.py`**

Replace the local imports in `tool-call-agent/app/api/main.py` with:

```python
from app.core.logging_config import reconfigure_uvicorn_loggers, setup_logging  # noqa: E402
from app.repositories.admin_repository import AdminRepository
from app.api.admin_router import init_router, router as admin_router
from app.services.agent_service import AgentService
from app.schemas.messages import ApprovalRequest, ChatRequest, CreateSessionRequest, SessionResponse, SessionSummaryResponse
from app.repositories.agent_repository import PostgresRepository
```

- [ ] **Step 3: Update imports in `app/api/admin_router.py`**

Replace the local imports in `tool-call-agent/app/api/admin_router.py` with:

```python
from app.schemas.admin import (
    AgentInstanceCreate,
    AgentInstanceResponse,
    AgentInstanceUpdate,
    AgentResponse,
    CredentialsRequest,
    CredentialsResponse,
    PersonaCreate,
    PersonaResponse,
    PersonaUpdate,
    SkillCreate,
    SkillResponse,
    SkillUpdate,
    SystemPromptCreate,
    SystemPromptResponse,
    SystemPromptUpdate,
)
from app.repositories.admin_repository import AdminRepository
```

- [ ] **Step 4: Update imports in `app/api/mock.py`**

Replace the local imports in `tool-call-agent/app/api/mock.py` with:

```python
from app.services.mock_agent import Session, run_agent
from app.schemas.messages import ApprovalRequest, ChatRequest, CreateSessionRequest, SessionResponse
```

- [ ] **Step 5: Update imports in `app/api/websocket.py`**

Replace the local imports in `tool-call-agent/app/api/websocket.py` with:

```python
from app.services.agent_service import AgentService
from app.repositories.agent_repository import PostgresRepository
from app.domain.session import Session
from app.schemas.messages import ApprovalRequest, ChatRequest, CreateSessionRequest, SessionResponse
```

- [ ] **Step 6: Update imports in `app/services/agent_service.py`**

Replace the local imports in `tool-call-agent/app/services/agent_service.py` with:

```python
from app.repositories.admin_repository import AdminRepository
from app.repositories.agent_repository import IAgentStorage
from app.domain.session import Session
from app.core.system_prompts import (
    DEFAULT_INSTRUCTIONS as _DEFAULT_INSTRUCTIONS,
    DEFAULT_SYSTEM_PROMPT_NAME as _DEFAULT_SYSTEM_PROMPT_NAME,
)
from app.tools.registry import execute_tool, reset_kubeconfig, set_kubeconfig
```

- [ ] **Step 7: Update imports in `app/repositories/admin_repository.py`**

Replace the local prompt defaults import in `tool-call-agent/app/repositories/admin_repository.py` with:

```python
from app.core.system_prompts import DEFAULT_INSTRUCTIONS, DEFAULT_SYSTEM_PROMPT_NAME, SEEDED_SYSTEM_PROMPTS
```

- [ ] **Step 8: Verify moved internals import directly**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval/tool-call-agent
/private/tmp/tool-call-approval-venv/bin/python -c "from app.schemas.messages import ChatRequest; from app.services.agent_service import AgentService; from app.repositories.agent_repository import PostgresRepository; from app.tools.registry import execute_tool; print('ok')"
```

Expected: prints `ok`.

---

### Task 3: Restore Root Entrypoint Compatibility Wrappers

**Files:**
- Create: `tool-call-agent/main.py`
- Create: `tool-call-agent/main_mock.py`
- Create: `tool-call-agent/main_websocket.py`

- [ ] **Step 1: Create root `main.py` wrapper**

Use `apply_patch` to create `tool-call-agent/main.py`:

```python
from app.api.main import app

__all__ = ["app"]
```

- [ ] **Step 2: Create root `main_mock.py` wrapper**

Use `apply_patch` to create `tool-call-agent/main_mock.py`:

```python
from app.api.mock import app

__all__ = ["app"]
```

- [ ] **Step 3: Create root `main_websocket.py` wrapper**

Use `apply_patch` to create `tool-call-agent/main_websocket.py`:

```python
from app.api.websocket import app

__all__ = ["app"]
```

- [ ] **Step 4: Verify uvicorn-visible imports**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval/tool-call-agent
/private/tmp/tool-call-approval-venv/bin/python -c "import main, main_mock, main_websocket; print(main.app.title); print(main_mock.app.title); print(main_websocket.app.title)"
```

Expected: prints three FastAPI app titles without import errors.

---

### Task 4: Update Tests To New Functionality Paths

**Files:**
- Modify: `tool-call-agent/tests/test_main.py`
- Modify: `tool-call-agent/tests/test_admin.py`
- Modify: `tool-call-agent/tests/test_agent.py`
- Modify: `tool-call-agent/tests/test_logging.py`
- Modify: `tool-call-agent/tests/test_report.py`
- Modify: `tool-call-agent/tests/test_sessions.py`
- Modify: `tool-call-agent/tests/test_tools.py`

- [ ] **Step 1: Update route test internals in `tests/test_main.py`**

Replace the top-level test imports:

```python
import main
from main import app
from session import Session
```

with:

```python
import app.api.main as main_app
from app.domain.session import Session
from main import app
```

Replace every internal patch target that points at the root wrapper:

```python
patch.object(main.service, "create_session", ...)
patch.object(main.service, "get_session", ...)
patch.object(main.service, "run", ...)
patch.object(main.service, "record_user_message", ...)
patch.object(main._admin_repository, "get_all_agent_instances", ...)
patch("main.asyncio.create_task")
```

with implementation-module targets:

```python
patch.object(main_app.service, "create_session", ...)
patch.object(main_app.service, "get_session", ...)
patch.object(main_app.service, "run", ...)
patch.object(main_app.service, "record_user_message", ...)
patch.object(main_app._admin_repository, "get_all_agent_instances", ...)
patch("app.api.main.asyncio.create_task")
```

- [ ] **Step 2: Update admin tests**

In `tool-call-agent/tests/test_admin.py`, replace:

```python
from admin_repository import AdminRepository
from system_prompt_defaults import DEFAULT_INSTRUCTIONS
from main import app
```

with:

```python
from app.repositories.admin_repository import AdminRepository
from app.core.system_prompts import DEFAULT_INSTRUCTIONS
from main import app
```

- [ ] **Step 3: Update agent service tests**

In `tool-call-agent/tests/test_agent.py`, replace:

```python
from repository import IAgentStorage, PostgresRepository
from session import Session
from agent_service import AgentService, _build_model
```

with:

```python
from app.repositories.agent_repository import IAgentStorage, PostgresRepository
from app.domain.session import Session
from app.services.agent_service import AgentService, _build_model
```

- [ ] **Step 4: Update logging tests**

In `tool-call-agent/tests/test_logging.py`, replace:

```python
from logging_config import reconfigure_uvicorn_loggers, setup_logging
```

with:

```python
from app.core.logging_config import reconfigure_uvicorn_loggers, setup_logging
```

- [ ] **Step 5: Update report tests**

In `tool-call-agent/tests/test_report.py`, replace:

```python
from agent_service import _build_pdf, AgentService
```

with:

```python
from app.services.agent_service import _build_pdf, AgentService
```

- [ ] **Step 6: Update session route tests**

In `tool-call-agent/tests/test_sessions.py`, keep:

```python
from main import app
```

because this test covers the public deployment entrypoint.

- [ ] **Step 7: Update tool tests**

In `tool-call-agent/tests/test_tools.py`, replace:

```python
from tools import execute_tool, TOOL_DEFINITIONS, _is_allowed
```

with:

```python
from app.tools.registry import execute_tool, TOOL_DEFINITIONS, _is_allowed
```

- [ ] **Step 8: Run focused route tests**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval/tool-call-agent
/private/tmp/tool-call-approval-venv/bin/python -m pytest tests/test_main.py -q
```

Expected: `15 passed`.

---

### Task 5: Update Stale Import Scan And Docs

**Files:**
- Modify: `tool-call-agent/README.md`

- [ ] **Step 1: Check command-line scripts for stale imports**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval
rg "from (models|admin_models|repository|admin_repository|agent_service|mock_agent|session|tools|logging_config|system_prompt_defaults)|import (models|admin_models|repository|admin_repository|agent_service|mock_agent|session|tools|logging_config|system_prompt_defaults)" tool-call-agent -g '*.py'
```

Expected before docs changes: stale imports appear only in files that will be updated in Tasks 2 and 4. `tool-call-agent/client.py` and `tool-call-agent/evals.py` do not require import edits.

- [ ] **Step 2: Leave `client.py` unchanged**

Confirm this command returns only standard library and `httpx` imports for `client.py`:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval
rg -n "^(from|import) " tool-call-agent/client.py
```

Expected:

```text
tool-call-agent/client.py:2:import json
tool-call-agent/client.py:3:import sys
tool-call-agent/client.py:4:import httpx
```

- [ ] **Step 3: Leave `evals.py` unchanged**

Confirm this command returns no imports from moved tool-call-agent modules:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval
rg -n "from (models|admin_models|repository|admin_repository|agent_service|mock_agent|session|tools|logging_config|system_prompt_defaults)|import (models|admin_models|repository|admin_repository|agent_service|mock_agent|session|tools|logging_config|system_prompt_defaults)" tool-call-agent/evals.py
```

Expected: no output.

- [ ] **Step 4: Add layout section to `README.md`**

Add this section near the setup or endpoint documentation:

```markdown
## Code Layout

Runtime code is organized under `app/` by functionality:

- `app/api/` contains FastAPI route modules and app entrypoints.
- `app/schemas/` contains Pydantic request and response models.
- `app/services/` contains agent orchestration and mock agent behavior.
- `app/repositories/` contains persistence adapters.
- `app/domain/` contains core runtime objects such as `Session`.
- `app/tools/` contains tool execution and allowlist logic.
- `app/core/` contains logging and system prompt defaults.

The root `main.py`, `main_mock.py`, and `main_websocket.py` files are compatibility wrappers so existing `uvicorn main:app` commands continue to work.
```

- [ ] **Step 5: Run stale import search again**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval
rg "from (models|admin_models|repository|admin_repository|agent_service|mock_agent|session|tools|logging_config|system_prompt_defaults)|import (models|admin_models|repository|admin_repository|agent_service|mock_agent|session|tools|logging_config|system_prompt_defaults)" tool-call-agent -g '*.py'
```

Expected: no stale imports in runtime or test files.

---

### Task 6: Full Verification And Container Redeploy

**Files:**
- Verify only, no source changes expected.

- [ ] **Step 1: Run focused route and internal import tests**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval/tool-call-agent
/private/tmp/tool-call-approval-venv/bin/python -m pytest tests/test_main.py -q
/private/tmp/tool-call-approval-venv/bin/python -c "import main, main_mock, main_websocket; from app.services.agent_service import AgentService; from app.repositories.admin_repository import AdminRepository; from app.tools.registry import execute_tool; print('ok')"
```

Expected: `15 passed` from pytest, then `ok` from the import check.

- [ ] **Step 2: Run optional broader test collection**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval/tool-call-agent
/private/tmp/tool-call-approval-venv/bin/python -m pytest --collect-only -q
```

Expected: collection completes without import errors. Database-dependent test execution is not required for this refactor verification unless the local Postgres test database is configured.

- [ ] **Step 3: Run whitespace diff check**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 4: Rebuild redeployed agent and API containers**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval
docker compose up -d --build --no-deps tool-calling-k8s-agent tool-call-api
```

Expected: `tool-calling-k8s-agent` and `tool-call-api` rebuild and start.

- [ ] **Step 5: Check compose status**

Run:

```bash
cd /Users/plakshmanan/Documents/python/tool-call-approval/tool-call-approval
docker compose ps
```

Expected: `postgres`, `tool-calling-k8s-agent`, `tool-call-api`, and `tool-call-k8s` are `Up`.

- [ ] **Step 6: Smoke-test public route compatibility**

Run:

```bash
curl -sS -i http://127.0.0.1:8000/health
curl -sS -i http://127.0.0.1:8080/api/sessions
```

Expected:

```text
HTTP/1.1 200 OK
```

for the agent health route, and `HTTP/1.1 200 OK` with a JSON list for API sessions.

- [ ] **Step 7: Smoke-test new schema through the redeployed gateway**

Run:

```bash
curl -sS -i \
  -H 'Content-Type: application/json' \
  -d '{"session":{},"messages":[]}' \
  http://127.0.0.1:8080/api/sessions
```

Expected:

```text
HTTP/1.1 200 OK
```

with a response containing `session_id`.

- [ ] **Step 8: Summarize results**

Report:

- Which files moved.
- Whether root entrypoints still import.
- Test command outputs.
- Docker redeploy status.
- Any remaining unrelated environmental blockers such as external LLM credentials.
