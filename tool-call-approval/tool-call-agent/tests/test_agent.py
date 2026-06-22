import asyncio
import pytest
from unittest.mock import MagicMock, patch

from app.core.system_prompts import DEFAULT_INSTRUCTIONS
from app.repositories.agent_repository import IAgentStorage, PostgresRepository

EMPTY_DATA = {
    "cmds": [],
    "executed_cmds": [],
    "url_configs": [],
    "user_file_uploads": [],
}
EMPTY_PLATFORM_CONTEXT = {
    "k8s_namespace": None,
    "duplo_base_url": None,
    "duplo_token": None,
    "tenant_name": None,
    "aws_credentials": None,
    "kubeconfig": None,
}
EMPTY_AMBIENT_CONTEXT = {"user_terminal_cmds": []}
EMPTY_AGENT_METADATA = {
    "session_id": None,
    "instance_id": None,
    "persona_id": None,
    "persona_ids": [],
    "persona_name": None,
    "persona_names": [],
    "skill_ids": [],
    "system_prompt_id": None,
    "system_prompt_name": None,
    "model_id": None,
    "provider": None,
}


def test_kubernetes_prompt_maps_cluster_health_to_cluster_status_commands():
    instructions = " ".join(DEFAULT_INSTRUCTIONS.lower().split())
    assert "cluster health" in instructions
    assert "same intent" in instructions
    assert "same command set" in instructions
    assert "cluster-info, get nodes -o wide, get namespaces" in DEFAULT_INSTRUCTIONS


def test_postgres_repository_is_lazy():
    repo = PostgresRepository(url="postgresql+psycopg2://localhost:9999/postgres")
    assert repo._db is None


def test_postgres_repository_returns_none_when_unreachable():
    repo = PostgresRepository(url="postgresql+psycopg2://localhost:9999/postgres")
    assert repo.get_db() is None


def test_postgres_repository_singleton():
    repo = PostgresRepository(url="postgresql+psycopg2://localhost:5432/postgres")
    with patch("app.repositories.agent_repository.socket.create_connection"), \
         patch("app.repositories.agent_repository.PostgresDb") as MockDb:
        MockDb.return_value = MagicMock()
        db1 = repo.get_db()
        db2 = repo.get_db()
        assert db1 is db2
        assert MockDb.call_count == 1


def test_get_session_history_preserves_agent_message_metadata():
    repo = PostgresRepository(url="postgresql+psycopg2://localhost:5432/postgres")
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = ([
        {
            "role": "user",
            "content": "hello",
            "timestamp": "2026-06-17T09:59:00+00:00",
        },
        {
            "role": "assistant",
            "content": "hi",
            "timestamp": "2026-06-17T10:00:00+00:00",
            "agent": {"session_id": "session-1"},
        },
    ],)

    with patch.object(repo, "_is_reachable", return_value=True), \
         patch("app.repositories.agent_repository.psycopg2.connect", return_value=mock_conn):
        history = repo.get_session_history("session-1")

    assert history == [
        {
            "role": "user",
            "content": "hello",
            "data": EMPTY_DATA,
            "timestamp": "2026-06-17T09:59:00+00:00",
            "user": None,
            "agent": None,
            "platform_context": EMPTY_PLATFORM_CONTEXT,
            "ambient_context": EMPTY_AMBIENT_CONTEXT,
        },
        {
            "role": "assistant",
            "content": "hi",
            "data": EMPTY_DATA,
            "timestamp": "2026-06-17T10:00:00+00:00",
            "user": None,
            "agent": {**EMPTY_AGENT_METADATA, "session_id": "session-1"},
        },
    ]


from app.domain.session import Session


def test_session_defaults():
    session = Session(id="abc-123")
    assert session.id == "abc-123"
    assert session.queue.empty()
    assert session.pending_approvals == {}
    assert session.approval_results == {}
    assert session.tmpdir is None


from agno.models.response import ToolExecution
from agno.run.agent import RunCompletedEvent, RunContentEvent, RunErrorEvent, RunPausedEvent, ToolCallCompletedEvent
from agno.run.requirement import RunRequirement

from app.services.agent_service import AgentService, _build_model


def test_build_model_uses_local_openai_like_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "LOCAL")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test")
    monkeypatch.setenv("LOCAL_MODEL_ID", "nemotron-3-super")
    monkeypatch.setenv("LOCAL_BASE_URL", "https://models.k8s.aip.mitre.org/v1")
    monkeypatch.delenv("LOCAL_VERIFY_SSL", raising=False)
    monkeypatch.delenv("LOCAL_CA_BUNDLE", raising=False)

    with patch("agno.models.openai.OpenAILike") as MockOpenAILike:
        model = _build_model()

    MockOpenAILike.assert_called_once_with(
        id="nemotron-3-super",
        api_key="sk-local-test",
        base_url="https://models.k8s.aip.mitre.org/v1",
    )
    assert model is MockOpenAILike.return_value


def test_build_model_uses_local_model_id_and_base_url_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "LOCAL")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test")
    monkeypatch.setenv("MODEL_ID", "custom-local-model")
    monkeypatch.setenv("BASE_URL", "https://local-models.example/v1")
    monkeypatch.delenv("LOCAL_MODEL_ID", raising=False)
    monkeypatch.delenv("LOCAL_BASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_VERIFY_SSL", raising=False)
    monkeypatch.delenv("LOCAL_CA_BUNDLE", raising=False)

    with patch("agno.models.openai.OpenAILike") as MockOpenAILike:
        model = _build_model()

    MockOpenAILike.assert_called_once_with(
        id="custom-local-model",
        api_key="sk-local-test",
        base_url="https://local-models.example/v1",
    )
    assert model is MockOpenAILike.return_value


def test_build_model_can_disable_local_tls_verification(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "LOCAL")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test")
    monkeypatch.setenv("LOCAL_VERIFY_SSL", "false")

    with patch("agno.models.openai.OpenAILike") as MockOpenAILike, \
         patch("app.services.agent_service.httpx.AsyncClient") as MockAsyncClient:
        model = _build_model()

    MockAsyncClient.assert_called_once_with(verify=False)
    MockOpenAILike.assert_called_once_with(
        id="nemotron-3-super",
        api_key="sk-local-test",
        base_url="https://models.k8s.aip.mitre.org/v1",
        http_client=MockAsyncClient.return_value,
    )
    assert model is MockOpenAILike.return_value


def test_build_model_rejects_invalid_local_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "LOCAL")
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-sk-key")

    with pytest.raises(EnvironmentError, match="must start with 'sk-'"):
        _build_model()


class MockStorage(IAgentStorage):
    def __init__(self):
        self.session_records = []
        self.messages = []

    def get_db(self):
        return MagicMock()

    def list_sessions(self):
        return []

    def create_session_record(
        self,
        session_id,
        instance_id,
        system_prompt_id,
        system_prompt_name,
        system_prompt_instructions_snapshot,
    ):
        self.session_records.append({
            "session_id": session_id,
            "instance_id": instance_id,
            "system_prompt_id": system_prompt_id,
            "system_prompt_name": system_prompt_name,
            "system_prompt_instructions_snapshot": system_prompt_instructions_snapshot,
        })

    def append_session_message(
        self,
        session_id,
        role,
        content,
        instance_id=None,
        system_prompt_id=None,
        system_prompt_name=None,
        system_prompt_instructions_snapshot=None,
        message=None,
    ):
        self.messages.append({
            "session_id": session_id,
            "role": role,
            "content": content,
            "instance_id": instance_id,
            "system_prompt_id": system_prompt_id,
            "system_prompt_name": system_prompt_name,
            "system_prompt_instructions_snapshot": system_prompt_instructions_snapshot,
            "message": message,
        })

    def get_session_history(self, session_id):
        return []

    def save_report(self, report_id, session_id, s3_bucket, s3_key, title):
        pass


class MockAdminRepo:
    def get_agent_instance(self, instance_id):
        return None

    def get_persona(self, persona_id):
        if persona_id == "persona-1":
            return {"id": "persona-1", "name": "ops_persona", "skill_ids": ["skill-1"]}
        if persona_id == "persona-2":
            return {"id": "persona-2", "name": "security_persona", "skill_ids": ["skill-2", "skill-1"]}
        return None

    def get_skill_content(self, skill_id):
        if skill_id == "skill-1":
            return (
                "ops.md",
                "---\nname: ops\ndescription: Ops skill\n---\n# Ops\nUse safe commands.",
            )
        if skill_id == "skill-2":
            return (
                "security.md",
                "---\nname: security\ndescription: Security skill\n---\n# Security\nCheck policy.",
            )
        return None

    def get_all_agent_instances(self):
        return []


@pytest.fixture
def service():
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        svc = AgentService(repository=MockStorage(), admin_repository=MockAdminRepo())
    return svc


def test_create_session_returns_session_with_id(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()
    assert session.id is not None
    assert len(session.id) == 36  # UUID


def test_create_session_uses_selected_system_prompt(service):
    service._admin_repository.get_system_prompt = MagicMock(return_value={
        "id": "prompt-1",
        "name": "default_agent",
        "instructions": "selected instructions",
    })
    service._admin_repository.get_active_system_prompt = MagicMock(
        return_value="active instructions"
    )

    with patch("app.services.agent_service.Agent") as MockAgent, patch("app.services.agent_service.AwsBedrock"):
        service.create_session(system_prompt_id="prompt-1")

    assert MockAgent.call_args.kwargs["instructions"] == "selected instructions"
    service._admin_repository.get_system_prompt.assert_called_once_with("prompt-1")


def test_create_session_defers_prompt_metadata_until_first_message(service):
    service._admin_repository.get_system_prompt = MagicMock(return_value={
        "id": "prompt-1",
        "name": "default_agent",
        "instructions": "selected instructions",
    })

    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        service.create_session(instance_id="inst-1", system_prompt_id="prompt-1")

    assert service._repository.session_records == []
    assert service._repository.messages == []


def test_create_session_loads_direct_persona_skills(service):
    with patch("app.services.agent_service.Agent") as MockAgent, \
         patch("app.services.agent_service.AwsBedrock"), \
         patch("app.services.agent_service.Skills") as MockSkills, \
         patch("app.services.agent_service.LocalSkills") as MockLocalSkills:
        session = service.create_session(persona_id="persona-1")

    assert session.persona_id == "persona-1"
    assert session.persona_name == "ops_persona"
    assert session.skill_ids == ["skill-1"]
    assert MockAgent.call_args.kwargs["skills"] is MockSkills.return_value
    MockLocalSkills.assert_called_once()


def test_create_session_loads_multiple_persona_skills(service):
    with patch("app.services.agent_service.Agent") as MockAgent, \
         patch("app.services.agent_service.AwsBedrock"), \
         patch("app.services.agent_service.Skills") as MockSkills, \
         patch("app.services.agent_service.LocalSkills") as MockLocalSkills:
        session = service.create_session(
            persona_id="persona-1",
            persona_ids=["persona-1", "persona-2"],
        )

    assert session.persona_id == "persona-1"
    assert session.persona_ids == ["persona-1", "persona-2"]
    assert session.persona_name == "ops_persona"
    assert session.persona_names == ["ops_persona", "security_persona"]
    assert session.skill_ids == ["skill-1", "skill-2"]
    assert MockAgent.call_args.kwargs["skills"] is MockSkills.return_value
    MockLocalSkills.assert_called_once()


def test_load_persona_skill_uses_frontmatter_name_for_directory(service, tmp_path):
    service._admin_repository.get_persona = MagicMock(return_value={
        "id": "persona-3",
        "name": "report_persona",
        "skill_ids": ["skill-3"],
    })
    service._admin_repository.get_skill_content = MagicMock(return_value=(
        "SKILL.md",
        "---\nname: kubernetes-report-formatter\ndescription: Format reports\n---\n# Reports\nFormat reports.",
    ))

    with patch("app.services.agent_service.Skills"), \
         patch("app.services.agent_service.LocalSkills"), \
         patch("app.services.agent_service.tempfile.mkdtemp", return_value=str(tmp_path)):
        service._load_personas_skills(["persona-3"])

    skill_file = tmp_path / "kubernetes-report-formatter" / "SKILL.md"
    assert skill_file.exists()
    assert skill_file.read_text() == (
        "---\nname: kubernetes-report-formatter\ndescription: Format reports\n---\n# Reports\nFormat reports."
    )


def test_agent_message_metadata_includes_persona_snapshot(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session(persona_id="persona-1")

    service.record_agent_message(session, "hello")

    agent = service._repository.messages[-1]["message"]["agent"]
    assert agent["persona_id"] == "persona-1"
    assert agent["persona_ids"] == ["persona-1"]
    assert agent["persona_name"] == "ops_persona"
    assert agent["persona_names"] == ["ops_persona"]
    assert agent["skill_ids"] == ["skill-1"]


def test_agent_message_metadata_includes_multiple_persona_snapshot(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session(
            persona_id="persona-1",
            persona_ids=["persona-1", "persona-2"],
        )

    service.record_agent_message(session, "hello")

    agent = service._repository.messages[-1]["message"]["agent"]
    assert agent["persona_id"] == "persona-1"
    assert agent["persona_ids"] == ["persona-1", "persona-2"]
    assert agent["persona_name"] == "ops_persona"
    assert agent["persona_names"] == ["ops_persona", "security_persona"]
    assert agent["skill_ids"] == ["skill-1", "skill-2"]


def test_record_user_message_persists_prompt_metadata_with_first_message(service):
    service._admin_repository.get_system_prompt = MagicMock(return_value={
        "id": "prompt-1",
        "name": "default_agent",
        "instructions": "selected instructions",
    })

    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session(instance_id="inst-1", system_prompt_id="prompt-1")

    service.record_user_message(session, "hello")

    assert service._repository.messages == [{
        "session_id": session.id,
        "role": "user",
        "content": "hello",
        "instance_id": "inst-1",
        "system_prompt_id": "prompt-1",
        "system_prompt_name": "default_agent",
        "system_prompt_instructions_snapshot": "selected instructions",
        "message": None,
    }]


def test_get_session_returns_none_for_unknown(service):
    assert service.get_session("nonexistent") is None


def test_get_session_returns_session(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()
    assert service.get_session(session.id) is session


def test_approve_sets_result_and_fires_event(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()
    session.pending_approvals["tool-1"] = asyncio.Event()
    service.approve(session, "tool-1", True)
    assert session.approval_results["tool-1"] is True
    assert session.pending_approvals["tool-1"].is_set()


async def test_on_content_puts_message_on_queue(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()
    event = RunContentEvent(content="Hello!")
    await service._on_content(session, event, [], [])
    item = await session.queue.get()
    assert item == {"type": "message", "content": "Hello!"}


async def test_on_completed_puts_done_and_removes_session(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()
    session_id = session.id
    await service._on_completed(session, RunCompletedEvent(), [], [])
    item = await session.queue.get()
    assert item == {"type": "done"}
    # Session is kept alive across turns — only removed on error
    assert service.get_session(session_id) is not None


async def test_on_error_puts_error_and_done(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()
    event = RunErrorEvent(content="boom")
    await service._on_error(session, event, [], [])
    items = []
    while not session.queue.empty():
        items.append(await session.queue.get())
    types = [i["type"] for i in items]
    assert "error" in types
    assert "done" in types


async def test_on_error_probes_unknown_local_model_error(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session(model_id="nemotron-3-super", provider="LOCAL")
    event = RunErrorEvent(content="Unknown model error")

    with patch(
        "app.services.agent_service._probe_local_model_error",
        return_value="Model backend error for LOCAL/nemotron-3-super (HTTP 500): no existing backendRef provided",
    ) as probe:
        await service._on_error(session, event, [], [])

    items = []
    while not session.queue.empty():
        items.append(await session.queue.get())

    probe.assert_called_once_with(session)
    assert items == [
        {
            "type": "error",
            "content": "Model backend error for LOCAL/nemotron-3-super (HTTP 500): no existing backendRef provided",
        },
        {"type": "done"},
    ]


async def test_dispatch_ignores_unknown_event(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()
    result = await service._dispatch(session, object(), [], [])
    assert result is False


async def test_run_happy_path(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()

    mock_agent = MagicMock()

    async def fake_arun(*args, **kwargs):
        yield RunContentEvent(content="Hello!")
        yield RunCompletedEvent()

    mock_agent.arun = fake_arun
    service._sessions[session.id] = (session, mock_agent)

    with patch("app.services.agent_service.langfuse_context"):
        await service.run(session, "Hi")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "thinking" in types
    assert "message" in types
    assert "done" in types
    assert service._repository.messages[-1] == {
        "session_id": session.id,
        "role": "assistant",
        "content": "Hello!",
        "instance_id": None,
        "system_prompt_id": None,
        "system_prompt_name": None,
        "system_prompt_instructions_snapshot": None,
        "message": {
            "role": "assistant",
            "content": "Hello!",
            "data": EMPTY_DATA,
            "timestamp": service._repository.messages[-1]["message"]["timestamp"],
            "user": None,
            "agent": {
                "session_id": session.id,
                "instance_id": None,
                "persona_id": None,
                "persona_ids": [],
                "persona_name": None,
                "persona_names": [],
                "skill_ids": [],
                "system_prompt_id": None,
                "system_prompt_name": "kubernetes_agent",
                "model_id": None,
                "provider": None,
            },
        },
    }
    assert service._repository.messages[-1]["message"]["timestamp"]


async def test_run_tool_approved(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()

    tool_exec = ToolExecution(
        tool_call_id="tool_123",
        tool_name="calculate",
        tool_args={"expression": "2 + 2"},
        requires_confirmation=True,
    )
    requirement = RunRequirement(tool_execution=tool_exec)
    paused_event = RunPausedEvent(tools=[tool_exec], requirements=[requirement], run_id="run-1")

    mock_agent = MagicMock()

    async def fake_arun(*args, **kwargs):
        yield paused_event

    async def fake_acontinue_run(*args, **kwargs):
        yield ToolCallCompletedEvent(tool=tool_exec, content="4")
        yield RunContentEvent(content="The answer is 4.")
        yield RunCompletedEvent()

    mock_agent.arun = fake_arun
    mock_agent.acontinue_run = fake_acontinue_run
    service._sessions[session.id] = (session, mock_agent)

    async def approve_after_delay():
        await asyncio.sleep(0.05)
        service.approve(session, "tool_123", True)

    asyncio.create_task(approve_after_delay())

    with patch("app.services.agent_service.langfuse_context"):
        await service.run(session, "What is 2+2?")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "tool_call_pending" in types
    assert "tool_result" in types
    assert "message" in types


async def test_run_persists_approved_kubectl_command_data(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()

    tool_exec = ToolExecution(
        tool_call_id="tool_kubectl",
        tool_name="kubectl",
        tool_args={"args": "get namespaces"},
        requires_confirmation=True,
    )
    requirement = RunRequirement(tool_execution=tool_exec)
    paused_event = RunPausedEvent(tools=[tool_exec], requirements=[requirement], run_id="run-k")

    mock_agent = MagicMock()

    async def fake_arun(*args, **kwargs):
        yield paused_event

    async def fake_acontinue_run(*args, **kwargs):
        yield ToolCallCompletedEvent(
            tool=tool_exec,
            content="kubectl(args=get namespaces) completed in 0.25s",
        )
        yield RunContentEvent(content="Namespaces listed.")
        yield RunCompletedEvent()

    mock_agent.arun = fake_arun
    mock_agent.acontinue_run = fake_acontinue_run
    service._sessions[session.id] = (session, mock_agent)

    async def approve_after_delay():
        await asyncio.sleep(0.05)
        service.approve(session, "tool_kubectl", True)

    asyncio.create_task(approve_after_delay())

    with patch("app.services.agent_service.langfuse_context"):
        await service.run(session, "get namespaces")

    assert service._repository.messages[-1]["message"]["data"] == {
        "cmds": [{"command": "kubectl get namespaces", "execute": True}],
        "executed_cmds": [{
            "command": "kubectl get namespaces",
            "output": "kubectl(args=get namespaces) completed in 0.25s",
        }],
        "url_configs": [],
        "user_file_uploads": [],
    }


async def test_run_stops_original_stream_after_resumed_tool_run_completes(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()

    tool_exec = ToolExecution(
        tool_call_id="tool_nodes",
        tool_name="kubectl",
        tool_args={"args": "get nodes -o wide"},
        requires_confirmation=True,
    )
    requirement = RunRequirement(tool_execution=tool_exec)
    paused_event = RunPausedEvent(tools=[tool_exec], requirements=[requirement], run_id="run-nodes")

    mock_agent = MagicMock()

    async def fake_arun(*args, **kwargs):
        yield paused_event
        raise AssertionError("original stream continued after resumed run completed")

    async def fake_acontinue_run(*args, **kwargs):
        yield ToolCallCompletedEvent(
            tool=tool_exec,
            content="kubectl(args=get nodes -o wide) completed in 0.23s",
        )
        yield RunContentEvent(content="Nodes listed.")
        yield RunCompletedEvent()

    mock_agent.arun = fake_arun
    mock_agent.acontinue_run = fake_acontinue_run
    service._sessions[session.id] = (session, mock_agent)

    async def approve_after_delay():
        await asyncio.sleep(0.05)
        service.approve(session, "tool_nodes", True)

    asyncio.create_task(approve_after_delay())

    with patch("app.services.agent_service.langfuse_context"):
        final_output = await service._run_agent(session, mock_agent, "get all nodes")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    assert final_output == "Nodes listed."
    assert [event["type"] for event in events].count("tool_call_pending") == 1
    assert not any(event["type"] == "error" for event in events)


async def test_run_agent_reports_root_level_upstream_model_error(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session(model_id="nemotron-3-super", provider="LOCAL")

    class FakeResponse:
        status_code = 503

        def json(self):
            return {
                "message": "failure to get a peer from the ring-balancer",
                "request_id": "req-123",
            }

    class FakeApiStatusError(Exception):
        response = FakeResponse()

    mock_agent = MagicMock()

    async def fake_arun(*args, **kwargs):
        raise RuntimeError("Unknown model error") from FakeApiStatusError()
        yield

    mock_agent.arun = fake_arun

    with patch("app.services.agent_service.langfuse_context"):
        final_output = await service._run_agent(session, mock_agent, "hello")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    assert final_output == ""
    assert events == [
        {
            "type": "error",
            "content": (
                "Unexpected error: Model backend error for LOCAL/nemotron-3-super "
                "(HTTP 503): failure to get a peer from the ring-balancer "
                "(request_id: req-123)"
            ),
        },
        {"type": "done"},
    ]


async def test_run_tool_rejected(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()

    tool_exec = ToolExecution(
        tool_call_id="tool_456",
        tool_name="get_weather",
        tool_args={"city": "London"},
        requires_confirmation=True,
    )
    requirement = RunRequirement(tool_execution=tool_exec)
    paused_event = RunPausedEvent(tools=[tool_exec], requirements=[requirement], run_id="run-2")

    mock_agent = MagicMock()

    async def fake_arun(*args, **kwargs):
        yield paused_event

    async def fake_acontinue_run(*args, **kwargs):
        yield RunCompletedEvent()

    mock_agent.arun = fake_arun
    mock_agent.acontinue_run = fake_acontinue_run
    service._sessions[session.id] = (session, mock_agent)

    async def reject_after_delay():
        await asyncio.sleep(0.05)
        service.approve(session, "tool_456", False)

    asyncio.create_task(reject_after_delay())

    with patch("app.services.agent_service.langfuse_context"):
        await service.run(session, "What's the weather?")

    events = []
    while not session.queue.empty():
        events.append(await session.queue.get())

    types = [e["type"] for e in events]
    assert "tool_call_pending" in types
    assert "tool_rejected" in types


async def test_run_persists_rejected_kubectl_command_data(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()

    tool_exec = ToolExecution(
        tool_call_id="tool_reject",
        tool_name="kubectl",
        tool_args={"args": "delete namespace prod"},
        requires_confirmation=True,
    )
    requirement = RunRequirement(tool_execution=tool_exec)
    paused_event = RunPausedEvent(tools=[tool_exec], requirements=[requirement], run_id="run-r")

    mock_agent = MagicMock()

    async def fake_arun(*args, **kwargs):
        yield paused_event

    async def fake_acontinue_run(*args, **kwargs):
        yield RunContentEvent(content="I did not run that command.")
        yield RunCompletedEvent()

    mock_agent.arun = fake_arun
    mock_agent.acontinue_run = fake_acontinue_run
    service._sessions[session.id] = (session, mock_agent)

    async def reject_after_delay():
        await asyncio.sleep(0.05)
        service.approve(session, "tool_reject", False)

    asyncio.create_task(reject_after_delay())

    with patch("app.services.agent_service.langfuse_context"):
        await service.run(session, "delete namespace prod")

    assert service._repository.messages[-1]["message"]["data"] == {
        "cmds": [{
            "command": "kubectl delete namespace prod",
            "execute": False,
            "rejection_reason": "User rejected tool call",
        }],
        "executed_cmds": [],
        "url_configs": [],
        "user_file_uploads": [],
    }


def test_create_session_no_instance_has_tmpdir(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session(instance_id=None)
    assert session.tmpdir is not None


def test_create_session_with_unknown_instance_has_tmpdir(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session(instance_id="nonexistent-uuid")
    assert session.tmpdir is not None


def test_create_session_with_instance_writes_skills(service, tmp_path):
    instance = {
        "id": "inst-uuid",
        "agent_name": "my-agent",
        "instance_name": "test-instance",
        "persona_id": "persona-uuid",
        "mcp_positions": [],
    }
    persona = {"id": "persona-uuid", "name": "Test Persona", "skill_ids": ["skill-1"]}
    skill_data = ("my-skill.md", "# My Skill\nDo things.")

    service._admin_repository.get_agent_instance = MagicMock(return_value=instance)
    service._admin_repository.get_persona = MagicMock(return_value=persona)
    service._admin_repository.get_skill_content = MagicMock(return_value=skill_data)

    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"), \
         patch("app.services.agent_service.Skills"), patch("app.services.agent_service.LocalSkills"), \
         patch("app.services.agent_service.tempfile.mkdtemp", return_value=str(tmp_path)):
        session = service.create_session(instance_id="inst-uuid")

    assert session.tmpdir == str(tmp_path)
    skill_file = tmp_path / "my-skill" / "SKILL.md"
    assert skill_file.exists()
    assert skill_file.read_text() == "# My Skill\nDo things."


def test_remove_session_deletes_tmpdir(service, tmp_path):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session()
    session.tmpdir = str(tmp_path)
    service._remove_session(session.id)
    assert not tmp_path.exists()


def test_create_session_skips_missing_skill(service, tmp_path):
    instance = {"id": "i", "persona_id": "p", "mcp_positions": []}
    persona = {"id": "p", "name": "P", "skill_ids": ["missing-skill"]}

    service._admin_repository.get_agent_instance = MagicMock(return_value=instance)
    service._admin_repository.get_persona = MagicMock(return_value=persona)
    service._admin_repository.get_skill_content = MagicMock(return_value=None)

    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session(instance_id="i")

    assert session.tmpdir is not None
