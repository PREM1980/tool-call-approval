import asyncio
import json
import uuid

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent import Session, run_agent
from models import ApprovalRequest, ChatRequest, SessionResponse

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
async def create_session() -> SessionResponse:
    session_id = str(uuid.uuid4())
    sessions[session_id] = Session(id=session_id)
    return SessionResponse(session_id=session_id)


# ── SSE endpoints ──────────────────────────────────────────────────────────────

@app.post("/sessions/{session_id}/chat")
async def chat(session_id: str, request: ChatRequest) -> dict:
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    asyncio.create_task(run_agent(session, request.message))
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
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.approval_result = request.approved
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
                asyncio.create_task(run_agent(session, data["message"]))
            elif data.get("type") == "approve":
                session.approval_result = data["approved"]
                session.approval_event.set()
    except WebSocketDisconnect:
        send_task.cancel()
