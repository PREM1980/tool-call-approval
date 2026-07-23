import asyncio
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk

from app.core.system_prompts import DEFAULT_INSTRUCTIONS
from app.domain.session import Session
from app.repositories.agent_repository import IAgentStorage, PostgresRepository
from app.services.agent_service import AgentService, _normalize_tool_args


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
    def append_session_event(self, session_id, run_id, event_type, payload=None): return {}
    def get_session_events(self, session_id, after_sequence=0): return []
    def save_report(self, *args): pass
    def delete_session(self, session_id): pass


class MockAdminRepo:
    def get_agent_instance(self, instance_id): return None
    def get_active_system_prompt(self): return None
    def get_persona(self, persona_id):
        return {"id": persona_id, "name": "ops", "skill_ids": ["skill-1"]} if persona_id else None
    def get_skill_content(self, skill_id):
        return ("ops.md", "---\nname: ops\n---\nUse safe commands.")


class TextModel:
    def bind_tools(self, tools, **kwargs): return self
    async def ainvoke(self, messages): return AIMessage(content="Hello from LangGraph.")
    async def astream(self, messages):
        yield AIMessageChunk(content="Hello from ")
        yield AIMessageChunk(content="LangGraph.")


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
    assert session.k8s_namespace is None
    assert session.pending_namespace_command is None


def test_kubectl_uses_active_namespace_when_command_has_none():
    assert _normalize_tool_args("kubectl", {"command": "get pods"}, "demo") == {
        "command": "get pods -n demo"
    }


def test_explicit_kubectl_namespace_overrides_active_namespace():
    assert _normalize_tool_args("kubectl", {"command": "get pods -n kube-system"}, "demo") == {
        "command": "get pods -n kube-system"
    }


def test_kubectl_uses_all_namespaces_scope_when_selected():
    assert _normalize_tool_args("kubectl", {"command": "get pods"}, "__all__") == {
        "command": "get pods --all-namespaces"
    }


def test_explicit_all_namespaces_scope_overrides_active_namespace():
    assert _normalize_tool_args("kubectl", {"command": "get pods -A"}, "demo") == {
        "command": "get pods -A"
    }


def test_namespace_list_is_formatted_as_markdown_table():
    output = "NAME STATUS AGE\ndefault Active 41d\nkube-system Active 41d"

    assert AgentService._format_namespace_list(output) == (
        "| Namespace | Status | Age |\n"
        "| --- | --- | --- |\n"
        "| default | Active | 41d |\n"
        "| kube-system | Active | 41d |"
    )


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
    assert [event["type"] for event in events] == [
        "run_started", "thinking", "model_request", "model_response",
        "model_request", "message_delta", "message_delta", "model_response",
        "message", "run_completed", "done",
    ]
    assert service._repository.messages[-1]["content"] == "Hello from LangGraph."


def test_approve_validates_edited_tool_parameters(service):
    session = Session(id="session")
    session.pending_approvals["tool-1"] = asyncio.Event()
    session.pending_tool_inputs["tool-1"] = {"expression": "2 + 2"}
    service.approve(session, "tool-1", True, {"expression": "3 + 3"})
    assert session.approval_inputs["tool-1"] == {"expression": "3 + 3"}
    with pytest.raises(ValueError, match="existing tool parameters"):
        service.approve(session, "tool-1", True, {"unexpected": "value"})
