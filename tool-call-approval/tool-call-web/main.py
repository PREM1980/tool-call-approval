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
