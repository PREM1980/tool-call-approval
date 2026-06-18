from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FileObject(StrictBaseModel):
    file_path: str
    file_content: str
    refers_persistent_file: str | None = None


class Command(StrictBaseModel):
    command: str
    execute: bool = False
    rejection_reason: str | None = None
    files: list[FileObject] | None = None


class ExecutedCommand(StrictBaseModel):
    command: str
    output: str


class URLConfig(StrictBaseModel):
    url: HttpUrl
    description: str


class PlatformContext(StrictBaseModel):
    k8s_namespace: str | None
    duplo_base_url: str | None
    duplo_token: str | None
    tenant_name: str | None
    aws_credentials: dict[str, Any] | None
    kubeconfig: str | None


class AmbientContext(StrictBaseModel):
    user_terminal_cmds: list[ExecutedCommand]


class Data(StrictBaseModel):
    cmds: list[Command]
    executed_cmds: list[ExecutedCommand]
    url_configs: list[URLConfig]
    user_file_uploads: list[FileObject]


class Message(StrictBaseModel):
    role: Literal["user", "assistant"]
    content: str
    data: Data
    timestamp: datetime | None
    user: str | dict[str, Any] | None
    agent: str | dict[str, Any] | None


class UserMessage(Message):
    role: Literal["user"] = "user"
    platform_context: PlatformContext
    ambient_context: AmbientContext


class AgentMessage(Message):
    role: Literal["assistant"] = "assistant"


class SessionContext(StrictBaseModel):
    session_id: str | None
    instance_id: str | None
    persona_id: str | None
    persona_ids: list[str] = Field(default_factory=list)
    system_prompt_id: str | None
    model_id: str | None
    provider: str | None


class ApprovalContext(StrictBaseModel):
    approved: bool
    tool_use_id: str | None = None


class MessageEnvelope(StrictBaseModel):
    session: SessionContext
    messages: list[UserMessage | AgentMessage]
    approval: ApprovalContext | None


class CreateSessionRequest(MessageEnvelope):
    pass


class ChatRequest(MessageEnvelope):
    pass


class ApprovalRequest(MessageEnvelope):
    pass
