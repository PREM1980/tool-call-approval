from pydantic import BaseModel


class PlatformContext(BaseModel):
    kubeconfig: str | None = None


class ChatRequest(BaseModel):
    message: str
    platform_context: PlatformContext | None = None


class ApprovalRequest(BaseModel):
    approved: bool
    tool_use_id: str | None = None


class SessionResponse(BaseModel):
    session_id: str


class CreateSessionRequest(BaseModel):
    instance_id: str | None = None
    system_prompt_id: str | None = None
    model_id: str | None = None
    provider: str | None = None


class SessionSummaryResponse(BaseModel):
    session_id: str
    created_at: int
    updated_at: int | None
    turn_count: int
    first_message: str | None = None
    system_prompt_id: str | None = None
    system_prompt_name: str | None = None
