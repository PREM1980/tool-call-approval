import asyncio
import json
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from admin_repository import AdminRepository
from admin_router import init_router, router as admin_router
from agent_service import AgentService
from models import ApprovalRequest, ChatRequest, SessionResponse
from repository import PostgresRepository

app = FastAPI(title="Tool Call Approval API")

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

service = AgentService(repository=_repository)
app.include_router(admin_router, prefix="/admin", tags=["admin"])


@app.post("/sessions", response_model=SessionResponse)
async def create_session() -> SessionResponse:
    session = service.create_session()
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
    return {"status": "ok"}
