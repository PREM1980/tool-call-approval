import asyncio
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.core.system_prompts import DEFAULT_INSTRUCTIONS
from app.domain.session import Session
from app.repositories.agent_repository import IAgentStorage, PostgresRepository
from app.services.agent_service import AgentService


class MockStorage(IAgentStorage):
    def __init__(self):
        self.messages = []

    def list_sessions(self, session_ids=None): return []
    def create_session_record(self, *args): pass
    def append_session_message(self, session_id, role, content, instance_id=None,
                               system_prompt_id=None, system_prompt_name=None,
                               system_prompt_instructions_snapshot=None, message=None):
        self.messages.append({"session_id": session_id, "role": role, "content": content, "message": message})
    def get_session_history(self, session_id): return []
    def save_report(self, *args): pass


class MockAdminRepo:
    def get_agent_instance(self, instance_id): return None
    def get_active_system_prompt(self): return None
    def get_persona(self, persona_id):
        return {"id": persona_id, "name": "ops", "skill_ids": ["skill-1"]} if persona_id else None
    def get_skill_content(self, skill_id):
        return ("ops.md", "---\nname: ops\n---\nUse safe commands.")


class TextModel:
    def bind_tools(self, tools): return self
    async def ainvoke(self, messages): return AIMessage(content="Hello from LangGraph.")


@pytest.fixture
def service():
    return AgentService(MockStorage(), MockAdminRepo())


def test_kubernetes_prompt_is_retained():
    assert "cluster health" in " ".join(DEFAULT_INSTRUCTIONS.lower().split())


def test_postgres_repository_has_no_agno_database_adapter():
    repo = PostgresRepository("postgresql+psycopg2://localhost:9999/postgres")
    assert not hasattr(repo, "get_db")


def test_session_defaults():
    session = Session(id="abc-123")
    assert session.pending_approvals == {}
    assert session.queue.empty()


def test_create_session_builds_a_langgraph_runtime(service):
    with patch("app.services.agent_service._build_model", return_value=TextModel()):
        session = service.create_session(persona_id="persona-1")
    runtime = service._sessions[session.id][1]
    assert hasattr(runtime.graph, "ainvoke")
    assert session.persona_ids == ["persona-1"]
    assert session.skill_ids == ["skill-1"]


async def test_run_uses_graph_and_persists_final_response(service):
    with patch("app.services.agent_service._build_model", return_value=TextModel()):
        session = service.create_session()
        await service.run(session, "Hi")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())
    assert [event["type"] for event in events] == ["thinking", "message", "done"]
    assert service._repository.messages[-1]["content"] == "Hello from LangGraph."


def test_approve_validates_edited_tool_parameters(service):
    session = Session(id="session")
    session.pending_approvals["tool-1"] = asyncio.Event()
    session.pending_tool_inputs["tool-1"] = {"expression": "2 + 2"}
    service.approve(session, "tool-1", True, {"expression": "3 + 3"})
    assert session.approval_inputs["tool-1"] == {"expression": "3 + 3"}
    with pytest.raises(ValueError, match="existing tool parameters"):
        service.approve(session, "tool-1", True, {"unexpected": "value"})
