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
