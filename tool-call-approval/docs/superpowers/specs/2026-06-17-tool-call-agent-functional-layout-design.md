# Tool Call Agent Functional Layout Design

## Goal

Reorganize `tool-call-agent` from a flat collection of Python modules into functionality-based folders while preserving the existing Docker and uvicorn entrypoints.

## Current State

Most runtime modules currently live directly under `tool-call-agent/`:

- FastAPI entrypoints and routes: `main.py`, `main_mock.py`, `main_websocket.py`, `admin_router.py`
- Schemas: `models.py`, `admin_models.py`
- Services and domain logic: `agent_service.py`, `mock_agent.py`, `session.py`
- Persistence: `repository.py`, `admin_repository.py`
- Tools and config: `tools.py`, `logging_config.py`, `system_prompt_defaults.py`
- Tests import many of these modules by their root names.

The existing deployment runs `uvicorn main:app`, so a safe refactor should not require deployment command changes.

## Proposed Layout

Create an internal `app/` package with folders named by responsibility:

```text
tool-call-agent/
  main.py
  main_mock.py
  main_websocket.py
  client.py
  evals.py
  app/
    __init__.py
    api/
      __init__.py
      main.py
      mock.py
      websocket.py
      admin_router.py
    schemas/
      __init__.py
      messages.py
      admin.py
    services/
      __init__.py
      agent_service.py
      mock_agent.py
    repositories/
      __init__.py
      agent_repository.py
      admin_repository.py
    domain/
      __init__.py
      session.py
    tools/
      __init__.py
      registry.py
    core/
      __init__.py
      logging_config.py
      system_prompts.py
      system_prompts_old.py
```

Root `main.py`, `main_mock.py`, and `main_websocket.py` remain as tiny compatibility entrypoints:

```python
from app.api.main import app
```

That keeps Docker, compose, and local commands such as `uvicorn main:app` working.

## Module Mapping

Move modules as follows:

| Current file | New file |
| --- | --- |
| `admin_router.py` | `app/api/admin_router.py` |
| `main.py` | `app/api/main.py` plus root wrapper |
| `main_mock.py` | `app/api/mock.py` plus root wrapper |
| `main_websocket.py` | `app/api/websocket.py` plus root wrapper |
| `models.py` | `app/schemas/messages.py` |
| `admin_models.py` | `app/schemas/admin.py` |
| `agent_service.py` | `app/services/agent_service.py` |
| `mock_agent.py` | `app/services/mock_agent.py` |
| `repository.py` | `app/repositories/agent_repository.py` |
| `admin_repository.py` | `app/repositories/admin_repository.py` |
| `session.py` | `app/domain/session.py` |
| `tools.py` | `app/tools/registry.py` |
| `logging_config.py` | `app/core/logging_config.py` |
| `system_prompt_defaults.py` | `app/core/system_prompts.py` |
| `system_prompt_defaults_old.py` | `app/core/system_prompts_old.py` |

`client.py` and `evals.py` can remain at the root because they are command-line helper scripts rather than application modules.

## Import Strategy

Use absolute imports from the new `app` package inside runtime code:

```python
from app.services.agent_service import AgentService
from app.schemas.messages import ChatRequest
from app.repositories.agent_repository import PostgresRepository
```

Tests should import from the new package paths where possible. Tests that need the deployed app can continue importing root `main.app`, because the root wrapper preserves the public entrypoint.

## Backward Compatibility

The root entrypoint files keep these commands working:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
uvicorn main_mock:app --reload
uvicorn main_websocket:app --reload
```

No Dockerfile `CMD` change is required for the main agent service.

## Error Handling

This refactor should not change runtime behavior. It only changes module locations and imports. Route validation, message envelope behavior, tool approval behavior, repository behavior, and streaming behavior must remain identical.

Import errors are the primary risk. The implementation should update all runtime imports and test imports in one pass, then run focused and broad tests before redeploying.

## Testing

Run these checks after the move:

```bash
cd tool-call-agent
/private/tmp/tool-call-approval-venv/bin/python -m pytest tests/test_main.py -q
/private/tmp/tool-call-approval-venv/bin/python -m pytest -q
```

Then rebuild the agent container and check service startup:

```bash
cd ..
docker compose up -d --build --no-deps tool-calling-k8s-agent tool-call-api
docker compose ps
```

Finally, smoke-test the route surface:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8080/api/sessions
```

## Out Of Scope

- Changing the message envelope schema.
- Changing agent behavior, tools, or provider selection.
- Changing database schema.
- Refactoring `tool-call-api` or `tool-call-ui`.
- Renaming Docker services or deployed API paths.
