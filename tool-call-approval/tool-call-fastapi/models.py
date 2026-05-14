from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ApprovalRequest(BaseModel):
    approved: bool


class SessionResponse(BaseModel):
    session_id: str
