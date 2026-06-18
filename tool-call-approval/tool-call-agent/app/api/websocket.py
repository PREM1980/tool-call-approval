import asyncio
import json
import uuid

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.domain.session import Session
from app.repositories.agent_repository import PostgresRepository
from app.schemas.messages import ApprovalRequest, ChatRequest, CreateSessionRequest, SessionResponse
from app.services.agent_service import AgentService

app = FastAPI(title="Tool Call Approval API")

ALLOWED_ORIGINS = {"http://localhost:4200"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, Session] = {}


@app.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest) -> SessionResponse:
    session_id = str(uuid.uuid4())
    sessions[session_id] = Session(id=session_id)
    return SessionResponse(session_id=session_id)


# ── SSE endpoints ──────────────────────────────────────────────────────────────

@app.post("/sessions/{session_id}/chat")
async def chat(session_id: str, request: ChatRequest) -> dict:
    if request.session.session_id and request.session.session_id != session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    message = request.latest_user_message()
    if message is None or not message.content.strip():
        raise HTTPException(status_code=422, detail="At least one user message is required")
    asyncio.create_task(run_agent(session, message.content))
    return {"status": "processing"}


@app.get("/sessions/{session_id}/stream")
async def stream_events(session_id: str) -> StreamingResponse:
    session = sessions.get(session_id)
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


@app.post("/sessions/{session_id}/approve")
async def approve_tool(session_id: str, request: ApprovalRequest) -> dict:
    if request.session.session_id and request.session.session_id != session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if request.approval is None:
        raise HTTPException(status_code=422, detail="Approval details are required")
    session.approval_result = request.approval.approved
    session.approval_event.set()
    return {"status": "ok"}


# ── WebSocket endpoint ─────────────────────────────────────────────────────────
# Client sends: {"type": "chat", "message": "..."} or {"type": "approve", "approved": true/false}
# Server sends: same event shapes as SSE (thinking, message, tool_call_pending, tool_result, done, error)

@app.websocket("/sessions/{session_id}/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    origin = websocket.headers.get("origin", "")
    if origin not in ALLOWED_ORIGINS:
        await websocket.close(code=1008)
        return

    session = sessions.get(session_id)
    if not session:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    async def send_events() -> None:
        try:
            while True:
                event = await session.queue.get()
                await websocket.send_json(event)
        except Exception:
            pass

    send_task = asyncio.create_task(send_events())

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "chat":
                request = ChatRequest.model_validate(
                    {key: value for key, value in data.items() if key != "type"}
                )
                message = request.latest_user_message()
                if message is not None and message.content.strip():
                    asyncio.create_task(run_agent(session, message.content))
            elif data.get("type") == "approve":
                request = ApprovalRequest.model_validate(
                    {key: value for key, value in data.items() if key != "type"}
                )
                if request.approval is not None:
                    session.approval_result = request.approval.approved
                    session.approval_event.set()
    except WebSocketDisconnect:
        send_task.cancel()
