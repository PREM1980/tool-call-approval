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

_BACKEND = os.getenv("AGENT_BACKEND_URL", "http://localhost:8000")
_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _client
    _client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=500, max_keepalive_connections=500),
        timeout=None,
    )
    yield
    await _client.aclose()


app = FastAPI(title="Tool Call Web", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
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
        raise HTTPException(status_code=502, detail="Backend unreachable")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Backend timeout")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=resp.json().get("detail", "Not found"))
    resp.raise_for_status()
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.post("/api/sessions")
async def create_session() -> JSONResponse:
    return await _proxy(
        _get_client().post(f"{_BACKEND}/sessions", timeout=30.0)
    )


@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, request: Request) -> JSONResponse:
    body = await request.body()
    return await _proxy(
        _get_client().post(
            f"{_BACKEND}/sessions/{session_id}/chat",
            content=body,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
    )


@app.get("/api/sessions/{session_id}/history")
async def history(session_id: str) -> JSONResponse:
    return await _proxy(
        _get_client().get(f"{_BACKEND}/sessions/{session_id}/history", timeout=30.0)
    )


@app.post("/api/sessions/{session_id}/approve")
async def approve(session_id: str, request: Request) -> JSONResponse:
    body = await request.body()
    return await _proxy(
        _get_client().post(
            f"{_BACKEND}/sessions/{session_id}/approve",
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
