import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from logging_config import reconfigure_uvicorn_loggers, setup_logging  # noqa: E402

setup_logging("tool-call-agent")

logger = logging.getLogger(__name__)

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from admin_repository import AdminRepository
from admin_router import init_router, router as admin_router
from agent_service import AgentService
from models import ApprovalRequest, ChatRequest, CreateSessionRequest, SessionResponse, SessionSummaryResponse
from repository import PostgresRepository

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    reconfigure_uvicorn_loggers("tool-call-agent")
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


@app.get("/sessions", response_model=list[SessionSummaryResponse])
async def list_sessions() -> list[dict]:
    return _repository.list_sessions()


@app.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest = Body(CreateSessionRequest()),
) -> SessionResponse:
    session = service.create_session(request.instance_id)
    logger.info(
        "session created",
        extra={"session_id": session.id, "instance_id": request.instance_id},
    )
    return SessionResponse(session_id=session.id)


@app.post("/sessions/{session_id}/chat")
async def chat(session_id: str, request: ChatRequest) -> dict:
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if request.platform_context:
        session.kubeconfig = request.platform_context.kubeconfig
    asyncio.create_task(service.run(session, request.message))
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
