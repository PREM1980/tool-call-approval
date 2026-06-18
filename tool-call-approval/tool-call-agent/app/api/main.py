from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.core.logging_config import reconfigure_uvicorn_loggers, setup_logging  # noqa: E402

setup_logging("tool-calling-k8s-agent")

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from app.api.admin_router import init_router, router as admin_router
from app.repositories.admin_repository import AdminRepository
from app.repositories.agent_repository import PostgresRepository
from app.schemas.messages import (
    ApprovalRequest,
    ChatRequest,
    CreateSessionRequest,
    SessionResponse,
    SessionSummaryResponse,
)
from app.services.agent_service import AgentService


def _validate_route_session(session_id: str, request_session_id: str | None) -> None:
    if request_session_id and request_session_id != session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")


def _latest_user_content(request: ChatRequest) -> str:
    message = request.latest_user_message()
    if message is None or not message.content.strip():
        raise HTTPException(status_code=422, detail="At least one user message is required")
    return message.content


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    reconfigure_uvicorn_loggers("tool-calling-k8s-agent")
    yield


app = FastAPI(title="Tool Call Approval API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_postgres_url = os.getenv("POSTGRES_URL", "postgresql+psycopg2://localhost:5432/postgres")
_repository = PostgresRepository(url=_postgres_url)
_admin_repository = AdminRepository(_postgres_url)
init_router(_admin_repository)

service = AgentService(repository=_repository, admin_repository=_admin_repository)
app.include_router(admin_router, prefix="/admin", tags=["admin"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/sessions", response_model=list[SessionSummaryResponse])
async def list_sessions() -> list[dict]:
    return _repository.list_sessions()


@app.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest) -> SessionResponse:
    session_context = request.session
    session = service.create_session(
        session_context.instance_id,
        session_context.persona_id,
        session_context.persona_ids,
        session_context.system_prompt_id,
        session_context.model_id,
        session_context.provider,
    )
    logger.info(
        "session created",
        extra={
            "session_id": session.id,
            "instance_id": session_context.instance_id,
            "persona_id": session_context.persona_id,
            "persona_ids": session_context.persona_ids,
            "system_prompt_id": session_context.system_prompt_id,
            "model_id": session_context.model_id,
            "provider": session_context.provider,
        },
    )
    return SessionResponse(session_id=session.id)


@app.post("/sessions/{session_id}/chat")
async def chat(session_id: str, request: ChatRequest) -> dict:
    _validate_route_session(session_id, request.session.session_id)
    user_message = request.latest_user_message()
    message_content = _latest_user_content(request)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if user_message and user_message.platform_context:
        session.kubeconfig = user_message.platform_context.kubeconfig
    service.record_user_message(
        session,
        message_content,
        user_message.model_dump(mode="json") if user_message else None,
    )
    asyncio.create_task(service.run(session, message_content))
    return {"status": "processing"}


@app.get("/sessions/{session_id}/stream")
async def stream_events(session_id: str) -> StreamingResponse:
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        while True:
            event = await session.queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "done":
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/sessions/{session_id}/history")
async def get_history(session_id: str) -> list[dict]:
    return service.get_history(session_id)


@app.get("/sessions/{session_id}/reports/{report_id}")
async def get_report(session_id: str, report_id: str) -> FileResponse:
    session = service.get_session(session_id)
    if not session or not session.tmpdir:
        raise HTTPException(status_code=404, detail="Session not found")
    path = Path(session.tmpdir) / f"{report_id}.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(path, media_type="application/pdf", filename=f"{report_id}.pdf")


@app.post("/sessions/{session_id}/approve")
async def approve_tool(session_id: str, request: ApprovalRequest) -> dict:
    _validate_route_session(session_id, request.session.session_id)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if request.approval is None:
        raise HTTPException(status_code=422, detail="Approval details are required")
    service.approve(session, request.approval.tool_use_id, request.approval.approved)
    logger.info(
        "tool approval received",
        extra={
            "session_id": session_id,
            "tool_use_id": request.approval.tool_use_id,
            "approved": request.approval.approved,
        },
    )
    return {"status": "ok"}
