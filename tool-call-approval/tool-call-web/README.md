# tool-call-web

API gateway that sits between `tool-call-ui` and `tool-call-fastapi`. The Angular UI communicates exclusively with this service; it forwards requests to the agent backend.

## Architecture

```
tool-call-ui (:4200) → tool-call-web (:8080) → tool-call-fastapi (:8000)
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
| `AGENT_BACKEND_URL` | `http://localhost:8000` | URL of the `tool-call-fastapi` backend |

## Running

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

## Tests

```bash
pytest -v
```
