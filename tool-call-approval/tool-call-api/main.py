from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Awaitable

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

load_dotenv()

from logging_config import reconfigure_uvicorn_loggers, setup_logging  # noqa: E402
from models import ApprovalRequest, ChatRequest, CreateSessionRequest, MessageEnvelope  # noqa: E402

setup_logging("tool-call-api")

logger = logging.getLogger(__name__)

_BACKEND = os.getenv("AGENT_BACKEND_URL", "http://localhost:8000")
_K8S_BACKEND = os.getenv("K8S_BACKEND_URL", "http://localhost:8001")
_CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:4200")
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    reconfigure_uvicorn_loggers("tool-call-api")
    global _client
    _client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=500, max_keepalive_connections=500),
        timeout=None,
    )
    yield
    await _client.aclose()


app = FastAPI(title="Tool Call API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialised")
    return _client


async def _proxy(coro: Awaitable[httpx.Response]) -> JSONResponse:
    try:
        resp = await coro
    except httpx.ConnectError:
        logger.error("backend unreachable")
        raise HTTPException(status_code=502, detail="Backend unreachable")
    except httpx.TimeoutException:
        logger.error("backend timeout")
        raise HTTPException(status_code=504, detail="Backend timeout")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


def _payload(request: MessageEnvelope) -> dict:
    return request.model_dump(mode="json")


@app.get("/api/sessions")
async def list_sessions() -> JSONResponse:
    return await _proxy(
        _get_client().get(f"{_BACKEND}/sessions", timeout=30.0)
    )


@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest) -> JSONResponse:
    return await _proxy(
        _get_client().post(
            f"{_BACKEND}/sessions",
            json=_payload(request),
            timeout=30.0,
        )
    )


@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, request: ChatRequest) -> JSONResponse:
    return await _proxy(
        _get_client().post(
            f"{_BACKEND}/sessions/{session_id}/chat",
            json=_payload(request),
            timeout=30.0,
        )
    )


@app.get("/api/sessions/{session_id}/history")
async def history(session_id: str) -> JSONResponse:
    return await _proxy(
        _get_client().get(f"{_BACKEND}/sessions/{session_id}/history", timeout=30.0)
    )


@app.post("/api/sessions/{session_id}/approve")
async def approve(session_id: str, request: ApprovalRequest) -> JSONResponse:
    return await _proxy(
        _get_client().post(
            f"{_BACKEND}/sessions/{session_id}/approve",
            json=_payload(request),
            timeout=30.0,
        )
    )


@app.api_route("/api/admin/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def admin_proxy(path: str, request: Request) -> JSONResponse:
    body = await request.body()
    headers = {}
    if ct := request.headers.get("content-type"):
        headers["Content-Type"] = ct
    return await _proxy(
        _get_client().request(
            request.method,
            f"{_BACKEND}/admin/{path}",
            content=body or None,
            headers=headers if headers else None,
            params=dict(request.query_params),
            timeout=30.0,
        )
    )


@app.api_route("/api/agents{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def agents_proxy(path: str, request: Request) -> JSONResponse:
    body = await request.body()
    headers = {}
    if ct := request.headers.get("content-type"):
        headers["Content-Type"] = ct
    return await _proxy(
        _get_client().request(
            request.method,
            f"{_K8S_BACKEND}/agents{path}",
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


@app.get("/api/sessions/{session_id}/stream")
async def stream_events(session_id: str) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        async with _get_client().stream(
            "GET", f"{_BACKEND}/sessions/{session_id}/stream"
        ) as resp:
            async for chunk in resp.aiter_text():
                yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_ui(full_path: str) -> FileResponse:
    static_root = _STATIC_DIR.resolve()
    requested = (static_root / full_path).resolve()
    try:
        requested.relative_to(static_root)
    except ValueError:
        requested = static_root / "index.html"
    if requested.is_file():
        return FileResponse(requested)
    return FileResponse(static_root / "index.html")
