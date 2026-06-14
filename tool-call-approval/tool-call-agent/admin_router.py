from fastapi import APIRouter, HTTPException, UploadFile, File

from admin_models import (
    AgentInstanceRequest,
    AgentInstanceResponse,
    AgentInstanceUpdateRequest,
    CredentialsRequest,
    CredentialsResponse,
    McpServerRequest,
    McpServerResponse,
    PersonaRequest,
    PersonaResponse,
    SkillResponse,
    SystemPromptRequest,
    SystemPromptUpdateRequest,
    SystemPromptResponse,
)
from admin_repository import AdminRepository

router = APIRouter()
_repo: AdminRepository | None = None


def init_router(repo: AdminRepository) -> None:
    global _repo
    _repo = repo


def _get_repo() -> AdminRepository:
    if _repo is None:
        raise RuntimeError("AdminRepository not initialised")
    return _repo


# ── Credentials ────────────────────────────────────────────────────────────

@router.get("/credentials", response_model=CredentialsResponse | None)
async def get_credentials():
    creds = _get_repo().get_credentials()
    if not creds:
        return None
    creds["aws_secret_access_key"] = "***"
    return CredentialsResponse(**creds)


@router.post("/credentials")
async def save_credentials(request: CredentialsRequest):
    _get_repo().upsert_credentials(
        request.aws_access_key_id,
        request.aws_secret_access_key,
        request.aws_region,
        request.kubeconfig,
    )
    return {"status": "ok"}


# ── MCP Servers ────────────────────────────────────────────────────────────

@router.get("/mcp-servers", response_model=list[McpServerResponse])
async def get_mcp_servers():
    return _get_repo().get_mcp_servers()


@router.post("/mcp-servers/{position}")
async def save_mcp_server(position: int, request: McpServerRequest):
    if not 1 <= position <= 5:
        raise HTTPException(status_code=422, detail="Position must be between 1 and 5")
    _get_repo().upsert_mcp_server(position, request.name, request.config)
    return {"status": "ok"}


@router.delete("/mcp-servers/{position}")
async def delete_mcp_server(position: int):
    if not _get_repo().delete_mcp_server(position):
        raise HTTPException(status_code=404, detail="MCP server not found")
    return {"status": "ok"}


# ── Skills ─────────────────────────────────────────────────────────────────

@router.get("/skills", response_model=list[SkillResponse])
async def get_skills():
    return _get_repo().get_skills()


@router.post("/skills", response_model=SkillResponse)
async def upload_skill(file: UploadFile = File(...)):
    content = await file.read()
    skill_id = _get_repo().save_skill(
        file.filename or "upload", content.decode("utf-8", errors="replace")
    )
    skill = next(s for s in _get_repo().get_skills() if str(s["id"]) == skill_id)
    return skill


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str):
    if not _get_repo().delete_skill(skill_id):
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"status": "ok"}


# ── Personas ───────────────────────────────────────────────────────────────

@router.get("/personas", response_model=list[PersonaResponse])
async def get_personas():
    return _get_repo().get_personas()


@router.post("/personas", response_model=PersonaResponse, status_code=201)
async def create_persona(request: PersonaRequest):
    try:
        return _get_repo().create_persona(request.name, request.skill_ids)
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Persona name already exists")
        raise


@router.put("/personas/{persona_id}", response_model=PersonaResponse)
async def update_persona(persona_id: str, request: PersonaRequest):
    persona = _get_repo().update_persona(persona_id, request.name, request.skill_ids)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.delete("/personas/{persona_id}")
async def delete_persona(persona_id: str):
    if not _get_repo().delete_persona(persona_id):
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"status": "ok"}


# ── Agent Instances ────────────────────────────────────────────────────────

@router.get("/agent-instances", response_model=list[AgentInstanceResponse])
async def get_agent_instances(agent_name: str | None = None):
    if agent_name:
        return _get_repo().get_agent_instances(agent_name)
    return _get_repo().get_all_agent_instances()


@router.post("/agent-instances", response_model=AgentInstanceResponse, status_code=201)
async def create_agent_instance(request: AgentInstanceRequest):
    try:
        return _get_repo().create_agent_instance(
            request.agent_name,
            request.instance_name,
            str(request.persona_id) if request.persona_id else None,
            request.mcp_positions,
        )
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail="Instance name already exists for this agent",
            )
        raise


@router.put("/agent-instances/{instance_id}", response_model=AgentInstanceResponse)
async def update_agent_instance(instance_id: str, request: AgentInstanceUpdateRequest):
    instance = _get_repo().update_agent_instance(
        instance_id,
        request.instance_name,
        str(request.persona_id) if request.persona_id else None,
        request.mcp_positions,
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Agent instance not found")
    return instance


@router.delete("/agent-instances/{instance_id}")
async def delete_agent_instance(instance_id: str):
    if not _get_repo().delete_agent_instance(instance_id):
        raise HTTPException(status_code=404, detail="Agent instance not found")
    return {"status": "ok"}


# ── System Prompts ──────────────────────────────────────────────────────────

@router.get("/system-prompts", response_model=list[SystemPromptResponse])
async def list_system_prompts():
    return _get_repo().list_system_prompts()


@router.post("/system-prompts", response_model=SystemPromptResponse, status_code=201)
async def create_system_prompt(request: SystemPromptRequest):
    try:
        return _get_repo().create_system_prompt(request.name, request.instructions)
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Prompt name already exists")
        raise


@router.put("/system-prompts/{prompt_id}", response_model=SystemPromptResponse)
async def update_system_prompt(prompt_id: str, request: SystemPromptUpdateRequest):
    prompt = _get_repo().update_system_prompt(prompt_id, request.name, request.instructions)
    if not prompt:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return prompt


@router.delete("/system-prompts/{prompt_id}")
async def delete_system_prompt(prompt_id: str):
    if not _get_repo().delete_system_prompt(prompt_id):
        raise HTTPException(status_code=404, detail="System prompt not found")
    return {"status": "ok"}


@router.post("/system-prompts/{prompt_id}/activate", response_model=SystemPromptResponse)
async def activate_system_prompt(prompt_id: str):
    prompt = _get_repo().activate_system_prompt(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return prompt
