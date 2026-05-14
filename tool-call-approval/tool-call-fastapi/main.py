import asyncio
import json
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent import Session, run_agent
from models import ApprovalRequest, ChatRequest, SessionResponse

app = FastAPI(title="Tool Call Approval API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
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
