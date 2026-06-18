from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CredentialsRequest(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    kubeconfig: str | None = None


class CredentialsResponse(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    kubeconfig: str | None


class McpServerRequest(BaseModel):
    name: str
    config: dict


class McpServerResponse(BaseModel):
    position: int
    name: str
    config: dict
    updated_at: datetime


class SkillResponse(BaseModel):
    id: UUID
    filename: str
    uploaded_at: datetime


class PersonaRequest(BaseModel):
    name: str
    skill_ids: list[str] = []


class PersonaResponse(BaseModel):
    id: UUID
    name: str
    skill_ids: list[str]
    created_at: datetime
    updated_at: datetime


class AgentInstanceRequest(BaseModel):
    agent_name: str
    instance_name: str
    persona_id: UUID | None = None
    mcp_positions: list[int] = []


class AgentInstanceUpdateRequest(BaseModel):
    instance_name: str
    persona_id: UUID | None = None
    mcp_positions: list[int] = []


class AgentInstanceResponse(BaseModel):
    id: UUID
    agent_name: str
    instance_name: str
    persona_id: UUID | None
    mcp_positions: list[int]
    created_at: datetime
    updated_at: datetime


class SystemPromptRequest(BaseModel):
    name: str
    instructions: str


class SystemPromptUpdateRequest(BaseModel):
    name: str
    instructions: str


class SystemPromptResponse(BaseModel):
    id: UUID
    name: str
    instructions: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
