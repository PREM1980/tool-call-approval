# tool-call-approval — Claude Code Guidelines

## Project Overview

FastAPI agent server built on the **Agno** framework with AWS Bedrock (Claude Sonnet 4),
featuring human-in-the-loop tool call approval, Langfuse tracing, and Postgres-backed
session persistence.

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | agno 2.6.6 |
| LLM | AWS Bedrock — `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| API server | FastAPI + uvicorn |
| Session storage | PostgreSQL (local, port 5432) via `PostgresDb` |
| Observability | Langfuse (docker-compose, port 3000) |
| Tests | pytest + pytest-asyncio |

## Key Files

| File | Purpose |
|---|---|
| `tool-call-fastapi/agent.py` | Agent definition, session/db wiring, event processing |
| `tool-call-fastapi/main.py` | FastAPI routes (sessions, chat, stream, approve) |
| `tool-call-fastapi/client.py` | CLI SSE test client |
| `tool-call-fastapi/tools.py` | Tool implementations (calculate, weather, search) |
| `tool-call-fastapi/models.py` | Pydantic request/response models |
| `docker-compose.yml` | Langfuse stack (postgres on 5433, redis, minio, clickhouse) |

## Common Commands

```bash
# Start the API server
cd tool-call-fastapi && uvicorn main:app --reload

# Run the test client
cd tool-call-fastapi && python client.py "your message here"

# Run tests
cd tool-call-fastapi && pytest

# Start Langfuse stack
docker compose up -d

# Check session data in Postgres
psql -h localhost -p 5432 -U postgres -d postgres \
  -c "SELECT session_id, jsonb_array_length(runs) AS turns FROM ai.agno_sessions;"
```

## Code Generation — Principal Engineer Standards

When generating any code, apply these standards:

### Design
- Design for the actual problem, not hypothetical future requirements (YAGNI)
- Prefer simple, direct solutions over clever abstractions
- Each function/class has one clear purpose
- Fail fast with clear error messages at system boundaries

### Python Style
- Type hints on all function signatures
- No mutable default arguments
- Prefer `|` union syntax over `Optional[X]` (Python 3.10+)
- Use dataclasses for simple data containers, Pydantic for API models
- Async all the way — don't mix sync blocking I/O in async paths

### Code Quality
- No comments that repeat what the code says — only document non-obvious WHY
- No dead code, no commented-out blocks
- No bare `except:` — catch specific exceptions
- Keep functions under ~40 lines; if longer, it's doing too much

### Testing
- Every new feature or bugfix gets a test
- Test the behaviour, not the implementation
- Use `pytest-asyncio` for async tests; fixtures over setUp/tearDown

### Documentation
- Update `README.md` whenever you add a feature, flag, or config option
- Keep `.env.example` in sync with any new env vars

## Commit & Push Workflows

- To stage and commit: type **`commit`** → the `commit` skill walks you through per-file approval
- To push: type **`push`** → the `push` skill confirms and pushes to remote
- Commit messages follow Conventional Commits (see `commit-messages` skill)

## Environment

Copy `.env.example` → `.env` and fill in:

```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
POSTGRES_URL=postgresql+psycopg2://localhost:5432/postgres   # optional override
LANGFUSE_PUBLIC_KEY=pk-lf-local-tool-call-approval
LANGFUSE_SECRET_KEY=sk-lf-local-tool-call-approval
LANGFUSE_HOST=http://localhost:3000
```
