from pydantic import BaseModel


class KubeconfigRequest(BaseModel):
    content: str


class EnvVar(BaseModel):
    key: str
    value: str


class DeployRequest(BaseModel):
    name: str
    image: str
    namespace: str = "default"
    replicas: int = 1
    env: list[EnvVar] = []


class ScaleRequest(BaseModel):
    replicas: int


class AgentResponse(BaseModel):
    name: str
    namespace: str
    image: str
    replicas: int
    ready_replicas: int
    status: str
