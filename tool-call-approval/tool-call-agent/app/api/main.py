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

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.admin_router import init_router, router as admin_router
from app.domain.user import User
from app.repositories.admin_repository import AdminRepository
from app.repositories.agent_repository import PostgresRepository
from app.repositories.registration_repository import RegistrationRepository
from app.schemas.auth import CreateUserRequest, LoginRequest, TokenResponse, UserResponse
from app.schemas.messages import (
    ApprovalRequest,
    ChatRequest,
    CreateSessionRequest,
    SessionResponse,
    SessionSummaryResponse,
)
from app.security.passwords import PasswordHasher
from app.security.tokens import TokenService
from app.services.agent_service import AgentService
from app.services.auth_service import AuthService
from app.services.session_ownership_service import SessionOwnershipService
from app.services.user_service import UserService


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
_registration_url = os.getenv(
    "REGISTRATION_DATABASE_URL",
    "postgresql+psycopg2://localhost:5432/registration",
)
_repository = PostgresRepository(url=_postgres_url)
_admin_repository = AdminRepository(_postgres_url)
init_router(_admin_repository)

service = AgentService(repository=_repository, admin_repository=_admin_repository)
_password_hasher = PasswordHasher()
_token_service = TokenService(
    secret_key=os.getenv("JWT_SECRET_KEY", "local-development-secret"),
    access_token_minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "480")),
)
_registration_repository = RegistrationRepository(_registration_url)
_auth_service = AuthService(_registration_repository, _password_hasher, _token_service)
_user_service = UserService(_registration_repository, _password_hasher)
_session_ownership_service = SessionOwnershipService(_registration_repository)
_bearer = HTTPBearer(auto_error=False)
app.include_router(admin_router, prefix="/admin", tags=["admin"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, username=user.username, role=user.role)


def _current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    access_token: str | None = Query(default=None),
) -> User:
    token = credentials.credentials if credentials else access_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    try:
        return _auth_service.get_current_user(token)
    except (PermissionError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


def _require_admin(user: User = Depends(_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def _require_session_owner(user: User, session_id: str) -> None:
    if not _session_ownership_service.user_owns_session(user, session_id):
        raise HTTPException(status_code=404, detail="Session not found")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    try:
        result = _auth_service.login(request.username, request.password)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        user=_user_response(result.user),
    )


@app.get("/auth/me", response_model=UserResponse)
async def me(current_user: User = Depends(_current_user)) -> UserResponse:
    return _user_response(current_user)


@app.get("/admin/users", response_model=list[UserResponse])
async def list_users(_: User = Depends(_require_admin)) -> list[UserResponse]:
    return [_user_response(user) for user in _user_service.list_users()]


@app.post("/admin/users", response_model=UserResponse, status_code=201)
async def create_user(
    request: CreateUserRequest,
    _: User = Depends(_require_admin),
) -> UserResponse:
    try:
        user = _user_service.create_user(request.username, request.password, request.role)
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=409, detail="Username already exists")
        raise HTTPException(status_code=422, detail=str(e))
    return _user_response(user)


@app.get("/sessions", response_model=list[SessionSummaryResponse])
async def list_sessions(current_user: User = Depends(_current_user)) -> list[dict]:
    session_ids = _session_ownership_service.get_session_ids_for_user(current_user)
    return _repository.list_sessions(session_ids)


@app.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(_current_user),
) -> SessionResponse:
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
    _session_ownership_service.record_owner(current_user, session.id)
    return SessionResponse(session_id=session.id)


@app.post("/sessions/{session_id}/chat")
async def chat(
    session_id: str,
    request: ChatRequest,
    current_user: User = Depends(_current_user),
) -> dict:
    _validate_route_session(session_id, request.session.session_id)
    _require_session_owner(current_user, session_id)
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
async def stream_events(
    session_id: str,
    current_user: User = Depends(_current_user),
) -> StreamingResponse:
    _require_session_owner(current_user, session_id)
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
async def get_history(
    session_id: str,
    current_user: User = Depends(_current_user),
) -> list[dict]:
    _require_session_owner(current_user, session_id)
    return service.get_history(session_id)


@app.get("/sessions/{session_id}/reports/{report_id}")
async def get_report(
    session_id: str,
    report_id: str,
    current_user: User = Depends(_current_user),
) -> FileResponse:
    _require_session_owner(current_user, session_id)
    session = service.get_session(session_id)
    if not session or not session.tmpdir:
        raise HTTPException(status_code=404, detail="Session not found")
    path = Path(session.tmpdir) / f"{report_id}.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(path, media_type="application/pdf", filename=f"{report_id}.pdf")


@app.post("/sessions/{session_id}/approve")
async def approve_tool(
    session_id: str,
    request: ApprovalRequest,
    current_user: User = Depends(_current_user),
) -> dict:
    _validate_route_session(session_id, request.session.session_id)
    _require_session_owner(current_user, session_id)
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
