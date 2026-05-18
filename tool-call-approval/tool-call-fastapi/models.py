from pydantic import BaseModel


class PlatformContext(BaseModel):
    kubeconfig: str | None = None


class ChatRequest(BaseModel):
    message: str
    platform_context: PlatformContext | None = None


class ApprovalRequest(BaseModel):
    approved: bool


class SessionResponse(BaseModel):
    session_id: str
