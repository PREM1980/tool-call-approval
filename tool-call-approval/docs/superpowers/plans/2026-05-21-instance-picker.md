# Instance Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dropdown to the AI-Engg chat page that lists all agent instances; picking one creates a session with the instance's persona skills loaded into the Agno agent via `LocalSkills`.

**Architecture:** `POST /sessions` accepts an optional `instance_id`; the backend looks up the instance → persona → skill content, writes each skill to a temp directory as `{skill_name}/SKILL.md`, and builds the Agno `Agent` with `Skills(loaders=[LocalSkills(tmpdir)])`. The frontend fetches all instances on init and passes the selected `instance_id` when creating each session. Switching the dropdown resets the session.

**Tech Stack:** Python 3.11, FastAPI, Agno (`agno.skills.Skills`, `agno.skills.LocalSkills`), PostgreSQL, Angular 17, Jasmine/Karma.

---

## File Map

| File | Change |
|---|---|
| `tool-call-agent/session.py` | Add `tmpdir: str \| None = None` field |
| `tool-call-agent/admin_repository.py` | Add `get_all_agent_instances`, `get_agent_instance`, `get_persona`, `get_skill_content` |
| `tool-call-agent/admin_router.py` | Make `agent_name` optional on `GET /agent-instances` |
| `tool-call-agent/models.py` | Add `CreateSessionRequest` |
| `tool-call-agent/agent_service.py` | Accept `admin_repository`; wire instance → skills; clean up tmpdir |
| `tool-call-agent/main.py` | Accept `CreateSessionRequest` body on `POST /sessions`; pass `admin_repository` to service |
| `tool-call-agent/tests/test_admin.py` | Tests for 4 new repo methods + router `GET /agent-instances` without filter |
| `tool-call-agent/tests/test_agent.py` | Update fixture; add `tmpdir` default test; add instance-wiring tests |
| `tool-call-agent/tests/test_main.py` | Tests for `POST /sessions` with and without `instance_id` |
| `tool-call-ui/src/app/services/admin.service.ts` | Add `getAllAgentInstances()` |
| `tool-call-ui/src/app/services/chat.service.ts` | `createSession(instanceId?)` |
| `tool-call-ui/src/app/services/websocket-chat.service.ts` | `createSession(instanceId?)` |
| `tool-call-ui/src/app/components/chat/chat.ts` | Instance picker state; load on init; wire to session creation |
| `tool-call-ui/src/app/components/chat/chat.html` | Add `<select>` between header and message list |
| `tool-call-ui/src/app/components/chat/chat.css` | Add `.instance-bar`, `.instance-label`, `.instance-select` |
| `tool-call-ui/src/app/components/chat/chat.spec.ts` | Mock `AdminService`; add instance picker tests |

---

## Task 1: Add `tmpdir` field to `Session`

**Files:**
- Modify: `tool-call-agent/session.py`
- Modify: `tool-call-agent/tests/test_agent.py` (line ~33, `test_session_defaults`)

- [ ] **Step 1.1: Write the failing test**

  In `tool-call-agent/tests/test_agent.py`, update `test_session_defaults`:

  ```python
  def test_session_defaults():
      session = Session(id="abc-123")
      assert session.id == "abc-123"
      assert session.queue.empty()
      assert not session.approval_event.is_set()
      assert session.approval_result is False
      assert session.tmpdir is None
  ```

- [ ] **Step 1.2: Run test to confirm it fails**

  ```bash
  cd tool-call-agent && pytest tests/test_agent.py::test_session_defaults -v
  ```

  Expected: `FAILED` — `Session` has no attribute `tmpdir`.

- [ ] **Step 1.3: Add `tmpdir` to `Session`**

  Replace the full content of `tool-call-agent/session.py`:

  ```python
  import asyncio
  from dataclasses import dataclass, field


  @dataclass
  class Session:
      id: str
      queue: asyncio.Queue = field(default_factory=asyncio.Queue)
      approval_event: asyncio.Event = field(default_factory=asyncio.Event)
      approval_result: bool = False
      kubeconfig: str | None = None
      tmpdir: str | None = None
  ```

- [ ] **Step 1.4: Run test to confirm it passes**

  ```bash
  cd tool-call-agent && pytest tests/test_agent.py::test_session_defaults -v
  ```

  Expected: `PASSED`.

- [ ] **Step 1.5: Commit**

  ```bash
  git add tool-call-agent/session.py tool-call-agent/tests/test_agent.py
  git commit -m "feat(agent): add tmpdir field to Session for skill cleanup"
  ```

---

## Task 2: `AdminRepository` — four new methods

**Files:**
- Modify: `tool-call-agent/admin_repository.py`
- Modify: `tool-call-agent/tests/test_admin.py`

- [ ] **Step 2.1: Write the failing tests**

  Append to `tool-call-agent/tests/test_admin.py`:

  ```python
  # ── get_all_agent_instances ────────────────────────────────────────────────

  def test_get_all_agent_instances_empty(repo):
      assert repo.get_all_agent_instances() == []


  def test_get_all_agent_instances_returns_all(repo):
      repo.create_agent_instance("agent-a", "inst-1", None, [])
      repo.create_agent_instance("agent-b", "inst-2", None, [])
      rows = repo.get_all_agent_instances()
      names = [r["instance_name"] for r in rows]
      assert "inst-1" in names
      assert "inst-2" in names


  def test_get_all_agent_instances_sorted(repo):
      repo.create_agent_instance("zebra", "z-inst", None, [])
      repo.create_agent_instance("alpha", "a-inst", None, [])
      rows = repo.get_all_agent_instances()
      agent_names = [r["agent_name"] for r in rows]
      assert agent_names == sorted(agent_names)


  # ── get_agent_instance ────────────────────────────────────────────────────

  def test_get_agent_instance_returns_none_for_unknown(repo):
      import uuid
      assert repo.get_agent_instance(str(uuid.uuid4())) is None


  def test_get_agent_instance_returns_row(repo):
      created = repo.create_agent_instance("agent-a", "my-inst", None, [1, 2])
      fetched = repo.get_agent_instance(str(created["id"]))
      assert fetched is not None
      assert fetched["instance_name"] == "my-inst"
      assert fetched["mcp_positions"] == [1, 2]


  # ── get_persona ───────────────────────────────────────────────────────────

  def test_get_persona_returns_none_for_unknown(repo):
      import uuid
      assert repo.get_persona(str(uuid.uuid4())) is None


  def test_get_persona_returns_row(repo):
      created = repo.create_persona("My Persona", ["skill-1"])
      fetched = repo.get_persona(str(created["id"]))
      assert fetched is not None
      assert fetched["name"] == "My Persona"
      assert fetched["skill_ids"] == ["skill-1"]


  # ── get_skill_content ─────────────────────────────────────────────────────

  def test_get_skill_content_returns_none_for_unknown(repo):
      import uuid
      assert repo.get_skill_content(str(uuid.uuid4())) is None


  def test_get_skill_content_returns_filename_and_content(repo):
      skill_id = repo.save_skill("my-skill.md", "# My Skill\nDo things.")
      result = repo.get_skill_content(skill_id)
      assert result is not None
      filename, content = result
      assert filename == "my-skill.md"
      assert content == "# My Skill\nDo things."
  ```

- [ ] **Step 2.2: Run tests to confirm they fail**

  ```bash
  cd tool-call-agent && pytest tests/test_admin.py -k "get_all_agent_instances or get_agent_instance or get_persona or get_skill_content" -v
  ```

  Expected: all `FAILED` — methods do not exist yet.

- [ ] **Step 2.3: Add the four methods to `AdminRepository`**

  In `tool-call-agent/admin_repository.py`, append inside the `AdminRepository` class after `get_agent_instances`:

  ```python
      def get_all_agent_instances(self) -> list[dict]:
          conn = self._connect()
          try:
              with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                  cur.execute(
                      "SELECT * FROM admin_agent_instances ORDER BY agent_name, instance_name"
                  )
                  return [dict(r) for r in cur.fetchall()]
          finally:
              conn.close()

      def get_agent_instance(self, instance_id: str) -> dict | None:
          conn = self._connect()
          try:
              with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                  cur.execute(
                      "SELECT * FROM admin_agent_instances WHERE id = %s::uuid",
                      (instance_id,),
                  )
                  row = cur.fetchone()
                  return dict(row) if row else None
          finally:
              conn.close()

      def get_persona(self, persona_id: str) -> dict | None:
          conn = self._connect()
          try:
              with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                  cur.execute(
                      "SELECT * FROM admin_personas WHERE id = %s::uuid",
                      (persona_id,),
                  )
                  row = cur.fetchone()
                  return dict(row) if row else None
          finally:
              conn.close()

      def get_skill_content(self, skill_id: str) -> tuple[str, str] | None:
          conn = self._connect()
          try:
              with conn.cursor() as cur:
                  cur.execute(
                      "SELECT filename, content FROM admin_skills WHERE id = %s::uuid",
                      (skill_id,),
                  )
                  row = cur.fetchone()
                  return (row[0], row[1]) if row else None
          finally:
              conn.close()
  ```

- [ ] **Step 2.4: Run tests to confirm they pass**

  ```bash
  cd tool-call-agent && pytest tests/test_admin.py -k "get_all_agent_instances or get_agent_instance or get_persona or get_skill_content" -v
  ```

  Expected: all `PASSED`.

- [ ] **Step 2.5: Run the full test suite to confirm no regressions**

  ```bash
  cd tool-call-agent && pytest -v
  ```

  Expected: all previously-passing tests still `PASSED`.

- [ ] **Step 2.6: Commit**

  ```bash
  git add tool-call-agent/admin_repository.py tool-call-agent/tests/test_admin.py
  git commit -m "feat(admin): add get_all_agent_instances, get_agent_instance, get_persona, get_skill_content"
  ```

---

## Task 3: Admin router — make `agent_name` optional; add `CreateSessionRequest`; update `POST /sessions`

**Files:**
- Modify: `tool-call-agent/admin_router.py`
- Modify: `tool-call-agent/models.py`
- Modify: `tool-call-agent/main.py`
- Modify: `tool-call-agent/tests/test_main.py`

- [ ] **Step 3.1: Write failing tests**

  Append to `tool-call-agent/tests/test_main.py`:

  ```python
  def test_get_all_agent_instances_no_filter():
      """GET /admin/agent-instances without agent_name returns 200."""
      response = client.get("/admin/agent-instances")
      assert response.status_code == 200
      assert isinstance(response.json(), list)


  def test_create_session_with_null_instance_id():
      response = client.post("/sessions", json={"instance_id": None})
      assert response.status_code == 200
      assert "session_id" in response.json()


  def test_create_session_with_instance_id_string():
      import uuid
      response = client.post("/sessions", json={"instance_id": str(uuid.uuid4())})
      # instance lookup will find nothing and fall back to default — still 200
      assert response.status_code == 200
      assert "session_id" in response.json()


  def test_create_session_no_body_still_works():
      """Existing callers that send no body must not break."""
      response = client.post("/sessions")
      assert response.status_code == 200
      assert "session_id" in response.json()
  ```

- [ ] **Step 3.2: Run tests to confirm they fail**

  ```bash
  cd tool-call-agent && pytest tests/test_main.py::test_get_all_agent_instances_no_filter tests/test_main.py::test_create_session_with_null_instance_id tests/test_main.py::test_create_session_with_instance_id_string tests/test_main.py::test_create_session_no_body_still_works -v
  ```

  Expected: some `FAILED` or `ERROR`.

- [ ] **Step 3.3: Make `agent_name` optional on the router**

  In `tool-call-agent/admin_router.py`, replace the `get_agent_instances` handler:

  ```python
  @router.get("/agent-instances", response_model=list[AgentInstanceResponse])
  async def get_agent_instances(agent_name: str | None = None):
      if agent_name:
          return _get_repo().get_agent_instances(agent_name)
      return _get_repo().get_all_agent_instances()
  ```

- [ ] **Step 3.4: Add `CreateSessionRequest` to `models.py`**

  In `tool-call-agent/models.py`, append:

  ```python
  class CreateSessionRequest(BaseModel):
      instance_id: str | None = None
  ```

- [ ] **Step 3.5: Update `POST /sessions` in `main.py`**

  At the top of `tool-call-agent/main.py`, add `Body` to the FastAPI imports:

  ```python
  from fastapi import Body, FastAPI, HTTPException
  ```

  Add `CreateSessionRequest` to the models import line:

  ```python
  from models import ApprovalRequest, ChatRequest, CreateSessionRequest, SessionResponse
  ```

  Replace the `create_session` route:

  ```python
  @app.post("/sessions", response_model=SessionResponse)
  async def create_session(
      request: CreateSessionRequest = Body(CreateSessionRequest()),
  ) -> SessionResponse:
      session = service.create_session(request.instance_id)
      logger.info(
          "session created",
          extra={"session_id": session.id, "instance_id": request.instance_id},
      )
      return SessionResponse(session_id=session.id)
  ```

  Note: `AgentService.create_session` now accepts `instance_id` — that change happens in Task 4. For now the call `service.create_session(request.instance_id)` will fail at runtime but the tests mock the agent, so the tests will pass.

- [ ] **Step 3.6: Run the new tests**

  ```bash
  cd tool-call-agent && pytest tests/test_main.py -v
  ```

  Expected: all `PASSED` (the `create_session` calls in test_main go through the mocked service which patches Agent/AwsBedrock).

  If `AgentService.create_session` doesn't yet accept `instance_id`, you'll get a `TypeError`. In that case, temporarily add `instance_id: str | None = None` to the existing `create_session` signature in `agent_service.py` (no logic change yet) to unblock the tests, then revert that when Task 4 is complete.

- [ ] **Step 3.7: Run full suite**

  ```bash
  cd tool-call-agent && pytest -v
  ```

  Expected: all `PASSED`.

- [ ] **Step 3.8: Commit**

  ```bash
  git add tool-call-agent/admin_router.py tool-call-agent/models.py tool-call-agent/main.py tool-call-agent/tests/test_main.py
  git commit -m "feat(api): make agent_name optional on GET /agent-instances; accept instance_id on POST /sessions"
  ```

---

## Task 4: `AgentService` — wire instance → persona → skills → `LocalSkills`

**Files:**
- Modify: `tool-call-agent/agent_service.py`
- Modify: `tool-call-agent/main.py` (pass `admin_repository` to service)
- Modify: `tool-call-agent/tests/test_agent.py`

- [ ] **Step 4.1: Write failing tests**

  In `tool-call-agent/tests/test_agent.py`, replace the `MockStorage` class and `service` fixture, and add new tests:

  ```python
  class MockStorage(IAgentStorage):
      def get_db(self):
          return MagicMock()


  class MockAdminRepo:
      def get_agent_instance(self, instance_id):
          return None

      def get_persona(self, persona_id):
          return None

      def get_skill_content(self, skill_id):
          return None

      def get_all_agent_instances(self):
          return []


  @pytest.fixture
  def service():
      with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
          svc = AgentService(repository=MockStorage(), admin_repository=MockAdminRepo())
      return svc
  ```

  Then append these new test functions (after the existing `test_run_tool_rejected`):

  ```python
  def test_create_session_no_instance_has_no_tmpdir(service):
      with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
          session = service.create_session(instance_id=None)
      assert session.tmpdir is None


  def test_create_session_with_unknown_instance_has_no_tmpdir(service):
      # MockAdminRepo.get_agent_instance returns None → no tmpdir
      with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
          session = service.create_session(instance_id="nonexistent-uuid")
      assert session.tmpdir is None


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

      with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"), \
           patch("agent_service.Skills"), patch("agent_service.LocalSkills"), \
           patch("agent_service.tempfile.mkdtemp", return_value=str(tmp_path)):
          session = service.create_session(instance_id="inst-uuid")

      assert session.tmpdir == str(tmp_path)
      skill_file = tmp_path / "my-skill" / "SKILL.md"
      assert skill_file.exists()
      assert skill_file.read_text() == "# My Skill\nDo things."


  def test_remove_session_deletes_tmpdir(service, tmp_path):
      with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
          session = service.create_session()
      session.tmpdir = str(tmp_path)
      # tmp_path exists now; _remove_session should delete it
      service._remove_session(session.id)
      assert not tmp_path.exists()


  def test_create_session_skips_missing_skill(service, tmp_path):
      instance = {"id": "i", "persona_id": "p", "mcp_positions": []}
      persona = {"id": "p", "name": "P", "skill_ids": ["missing-skill"]}

      service._admin_repository.get_agent_instance = MagicMock(return_value=instance)
      service._admin_repository.get_persona = MagicMock(return_value=persona)
      service._admin_repository.get_skill_content = MagicMock(return_value=None)

      with patch("agent_service.Agent"), patch("agent_service.AwsBedrock"):
          session = service.create_session(instance_id="i")

      # No skills loaded → tmpdir cleaned up → None
      assert session.tmpdir is None
  ```

- [ ] **Step 4.2: Run tests to confirm they fail**

  ```bash
  cd tool-call-agent && pytest tests/test_agent.py -k "tmpdir or instance or remove_session_deletes or missing_skill" -v
  ```

  Expected: `FAILED` — `AgentService.__init__` doesn't accept `admin_repository`.

- [ ] **Step 4.3: Rewrite `agent_service.py`**

  Replace the full content of `tool-call-agent/agent_service.py`:

  ```python
  import asyncio
  import shutil
  import tempfile
  from pathlib import Path
  from typing import Any
  from uuid import uuid4

  from agno.agent import Agent
  from agno.models.aws.bedrock import AwsBedrock
  from agno.run.agent import (
      RunCompletedEvent,
      RunContentEvent,
      RunErrorEvent,
      RunPausedEvent,
      ToolCallCompletedEvent,
  )
  from agno.skills import LocalSkills, Skills
  from agno.tools import tool
  from langfuse.decorators import langfuse_context, observe

  from admin_repository import AdminRepository
  from repository import IAgentStorage
  from session import Session
  from tools import execute_tool, reset_kubeconfig, set_kubeconfig

  _MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
  _THROTTLE_MAX_RETRIES = 3
  _THROTTLE_BASE_DELAY = 5  # seconds; backoff: 5s, 10s, 20s

  _DEFAULT_INSTRUCTIONS = (
      "<agent>\n"
      "  <identity>\n"
      "    You are a Kubernetes operations agent. Your sole purpose is to help users\n"
      "    manage, debug, and operate Kubernetes clusters.\n"
      "  </identity>\n"
      "\n"
      "  <scope>\n"
      "    <allowed>\n"
      "      Pods, Deployments, StatefulSets, DaemonSets, ReplicaSets, Jobs, CronJobs,\n"
      "      Services, Ingress, NetworkPolicies, ConfigMaps, Secrets, PersistentVolumes,\n"
      "      PersistentVolumeClaims, StorageClasses, Namespaces, Nodes, ResourceQuotas,\n"
      "      LimitRanges, HorizontalPodAutoscalers, ClusterRoles, Roles, RoleBindings,\n"
      "      ServiceAccounts, CustomResourceDefinitions, Helm charts, kubeconfig,\n"
      "      kubectl commands, cluster upgrades, and Kubernetes troubleshooting.\n"
      "    </allowed>\n"
      "    <context_resolution>\n"
      "      Before deciding a request is off-topic, check the conversation history.\n"
      "      Short or ambiguous messages ('can you diagnose it', 'check it', 'fix it')\n"
      "      almost always refer to the Kubernetes resource or issue discussed just above.\n"
      "      Resolve 'it' / 'that' / 'this' from context and proceed — do not refuse.\n"
      "    </context_resolution>\n"
      "    <prohibited>\n"
      "      Only refuse when the request is unambiguously unrelated to Kubernetes\n"
      "      (e.g. 'write me a poem', 'what is the weather', 'solve 2+2').\n"
      "      When refusing, respond only with: 'I am a Kubernetes agent and cannot help with that.'\n"
      "    </prohibited>\n"
      "    <allowed_commands>\n"
      "      Only the following kubectl subcommands are permitted. Any other command\n"
      "      will be rejected by the system — do NOT attempt unlisted ones:\n"
      "      Read/inspect: get, describe, logs, top, explain, version, cluster-info,\n"
      "        api-resources, api-versions, config, events\n"
      "      Mutating (developer-safe): apply, create, delete, edit, patch, replace,\n"
      "        rollout, scale, autoscale, set, run, expose, label, annotate\n"
      "      Interaction: exec, port-forward, cp, debug\n"
      "      Other: diff, wait\n"
      "      Exception: 'cluster-info dump' is blocked even though 'cluster-info' is allowed.\n"
      "      Node management (drain, cordon, uncordon, taint) and cluster-admin\n"
      "      operations are reserved for infrastructure engineers.\n"
      "      When a user requests a blocked operation, explain the restriction and\n"
      "      suggest a read-only alternative where one exists.\n"
      "    </allowed_commands>\n"
      "  </scope>\n"
      "\n"
      "  <tool_usage>\n"
      "    <rule>Always call the relevant tool before composing your response.</rule>\n"
      "    <rule>When the user asks about multiple Kubernetes resources, call the tool\n"
      "      once for EACH resource before writing your final answer.</rule>\n"
      "    <rule>Never assume, skip, or fabricate tool results.</rule>\n"
      "    <rule>If a tool call is approved and returns a result, immediately call the\n"
      "      tool for the next item if more items remain.</rule>\n"
      "  </tool_usage>\n"
      "\n"
      "  <response_style>\n"
      "    <rule>Be concise and precise. Kubernetes operators value accuracy over verbosity.</rule>\n"
      "    <rule>Prefer kubectl command examples when explaining operations.</rule>\n"
      "    <rule>When diagnosing issues, state the likely root cause first, then remediation steps.</rule>\n"
      "  </response_style>\n"
      "</agent>"
  )


  @tool(requires_confirmation=True)
  def calculate(expression: str) -> str:
      """Evaluate a mathematical expression. Use math.sqrt(), math.pi, etc. for math functions."""
      return execute_tool("calculate", {"expression": expression})


  @tool(requires_confirmation=True)
  def get_weather(city: str) -> str:
      """Get current weather conditions for a city."""
      return execute_tool("get_weather", {"city": city})


  @tool(requires_confirmation=True)
  def search_web(query: str) -> str:
      """Search the web for information on a topic."""
      return execute_tool("search_web", {"query": query})


  @tool(requires_confirmation=True)
  def kubectl(args: str) -> str:
      """Execute a kubectl command. Provide arguments after 'kubectl', e.g. 'get pods -n default'."""
      return execute_tool("kubectl", {"args": args})


  class AgentService:
      def __init__(self, repository: IAgentStorage, admin_repository: AdminRepository) -> None:
          self._repository = repository
          self._admin_repository = admin_repository
          self._sessions: dict[str, tuple[Session, Agent]] = {}
          self._handlers: dict[type, Any] = {
              RunPausedEvent: self._on_paused,
              RunContentEvent: self._on_content,
              RunCompletedEvent: self._on_completed,
              RunErrorEvent: self._on_error,
              ToolCallCompletedEvent: self._on_tool_completed,
          }

      # ── Session lifecycle ──────────────────────────────────────────────────

      def create_session(self, instance_id: str | None = None) -> Session:
          session = Session(id=str(uuid4()))
          agent, tmpdir = self._build_agent(session.id, instance_id)
          session.tmpdir = tmpdir
          self._sessions[session.id] = (session, agent)
          return session

      def get_session(self, session_id: str) -> Session | None:
          pair = self._sessions.get(session_id)
          return pair[0] if pair else None

      def approve(self, session: Session, approved: bool) -> None:
          session.approval_result = approved
          session.approval_event.set()

      # ── Factory ───────────────────────────────────────────────────────────

      def _build_agent(self, session_id: str, instance_id: str | None = None) -> tuple[Agent, str | None]:
          tmpdir, skills_obj = (
              self._load_instance_skills(instance_id)
              if instance_id
              else (None, None)
          )
          agent = Agent(
              model=AwsBedrock(id=_MODEL_ID),
              tools=[calculate, get_weather, search_web, kubectl],
              skills=skills_obj,
              instructions=_DEFAULT_INSTRUCTIONS,
              stream=True,
              session_id=session_id,
              user_id=session_id,
              db=self._repository.get_db(),
          )
          return agent, tmpdir

      def _load_instance_skills(self, instance_id: str) -> tuple[str | None, Any]:
          """Resolve instance → persona → skills; write to tmpdir. Returns (tmpdir, Skills) or (None, None)."""
          instance = self._admin_repository.get_agent_instance(instance_id)
          if not instance or not instance.get("persona_id"):
              return None, None

          persona = self._admin_repository.get_persona(str(instance["persona_id"]))
          if not persona or not persona.get("skill_ids"):
              return None, None

          tmpdir = tempfile.mkdtemp(prefix="agno_skills_")
          loaded = 0
          for skill_id in persona["skill_ids"]:
              result = self._admin_repository.get_skill_content(skill_id)
              if not result:
                  continue
              filename, content = result
              skill_name = Path(filename).stem
              skill_dir = Path(tmpdir) / skill_name
              skill_dir.mkdir(parents=True, exist_ok=True)
              (skill_dir / "SKILL.md").write_text(content)
              loaded += 1

          if loaded == 0:
              shutil.rmtree(tmpdir, ignore_errors=True)
              return None, None

          return tmpdir, Skills(loaders=[LocalSkills(tmpdir)])

      def get_history(self, session_id: str) -> list[dict]:
          db = self._repository.get_db()
          agent_session = db.get_session(session_id)
          if agent_session is None:
              return []
          return [
              {"role": msg.role, "content": msg.content or ""}
              for msg in agent_session.get_chat_history()
          ]

      def _get_agent(self, session_id: str) -> Agent | None:
          pair = self._sessions.get(session_id)
          return pair[1] if pair else None

      def _remove_session(self, session_id: str) -> None:
          pair = self._sessions.pop(session_id, None)
          if pair:
              session = pair[0]
              if session.tmpdir:
                  shutil.rmtree(session.tmpdir, ignore_errors=True)

      # ── Run loop ──────────────────────────────────────────────────────────

      @observe(name="agent-run", capture_input=False, capture_output=False)
      async def run(self, session: Session, message: str) -> None:
          agent = self._get_agent(session.id)
          if agent is None:
              return

          kubeconfig_token = set_kubeconfig(session.kubeconfig)
          try:
              await self._run_inner(session, agent, message)
          finally:
              reset_kubeconfig(kubeconfig_token)

      async def _run_inner(self, session: Session, agent: Any, message: str) -> None:
          langfuse_context.update_current_trace(
              user_id=session.id,
              tags=["tool-call-approval"],
          )
          langfuse_context.update_current_observation(input=message)
          await session.queue.put({"type": "thinking", "content": "Thinking..."})

          tool_spans: list = []
          response_parts: list = []

          for attempt in range(_THROTTLE_MAX_RETRIES + 1):
              tool_spans = []
              response_parts = []
              try:
                  async for event in agent.arun(
                      message,
                      stream=True,
                      stream_events=True,
                      yield_run_output=True,
                  ):
                      done = await self._dispatch(session, event, tool_spans, response_parts)
                      if done and isinstance(event, RunCompletedEvent):
                          break
                  break
              except Exception as e:
                  error_str = str(e)
                  if "ThrottlingException" in error_str and attempt < _THROTTLE_MAX_RETRIES:
                      await asyncio.sleep(_THROTTLE_BASE_DELAY * (2 ** attempt))
                      continue
                  langfuse_context.update_current_observation(level="ERROR", status_message=error_str)
                  await session.queue.put({"type": "error", "content": f"Unexpected error: {error_str}"})
                  await session.queue.put({"type": "done"})
                  self._remove_session(session.id)
                  return

          final_output = "".join(response_parts)
          langfuse_context.update_current_observation(
              output=final_output,
              metadata={"tool_calls": tool_spans},
          )
          langfuse_context.update_current_trace(output=final_output)

      # ── Strategy dispatch ─────────────────────────────────────────────────

      async def _dispatch(
          self, session: Session, event: Any, tool_spans: list, response_parts: list
      ) -> bool:
          handler = self._handlers.get(type(event))
          if handler:
              return await handler(session, event, tool_spans, response_parts)
          return False

      async def _on_paused(
          self, session: Session, event: RunPausedEvent, tool_spans: list, response_parts: list
      ) -> bool:
          requirements = event.requirements or []
          requirement = next((r for r in requirements if r.needs_confirmation), None)
          if requirement is None or requirement.tool_execution is None:
              return False

          tool_execution = requirement.tool_execution
          await session.queue.put({
              "type": "tool_call_pending",
              "tool_use_id": tool_execution.tool_call_id,
              "tool_name": tool_execution.tool_name,
              "tool_input": tool_execution.tool_args or {},
          })

          session.approval_event.clear()
          await session.approval_event.wait()

          if not session.approval_result:
              requirement.reject()
              await session.queue.put({
                  "type": "tool_rejected",
                  "tool_use_id": tool_execution.tool_call_id,
                  "tool_name": tool_execution.tool_name,
              })
              return False

          requirement.confirm()
          agent = self._get_agent(session.id)
          if agent is None:
              return False

          async for resumed_event in agent.acontinue_run(
              run_id=event.run_id,
              requirements=[requirement],
              stream=True,
              stream_events=True,
              yield_run_output=True,
          ):
              if isinstance(resumed_event, ToolCallCompletedEvent) and resumed_event.tool:
                  result = str(resumed_event.content)
                  tool_spans.append({"tool": tool_execution.tool_name, "result": result})
                  await session.queue.put({
                      "type": "tool_result",
                      "tool_use_id": resumed_event.tool.tool_call_id,
                      "tool_name": resumed_event.tool.tool_name,
                      "result": result,
                  })
              else:
                  done = await self._dispatch(session, resumed_event, tool_spans, response_parts)
                  if done:
                      return True

          return True

      async def _on_content(
          self, session: Session, event: RunContentEvent, tool_spans: list, response_parts: list
      ) -> bool:
          if event.content:
              response_parts.append(str(event.content))
              await session.queue.put({"type": "message", "content": str(event.content)})
          return False

      async def _on_completed(
          self, session: Session, event: RunCompletedEvent, tool_spans: list, response_parts: list
      ) -> bool:
          await session.queue.put({"type": "done"})
          return True

      async def _on_error(
          self, session: Session, event: RunErrorEvent, tool_spans: list, response_parts: list
      ) -> bool:
          await session.queue.put({"type": "error", "content": f"Agent error: {event.content}"})
          await session.queue.put({"type": "done"})
          self._remove_session(session.id)
          return True

      async def _on_tool_completed(
          self, session: Session, event: ToolCallCompletedEvent, tool_spans: list, response_parts: list
      ) -> bool:
          if event.tool:
              await session.queue.put({
                  "type": "tool_result",
                  "tool_use_id": event.tool.tool_call_id,
                  "tool_name": event.tool.tool_name,
                  "result": str(event.content),
              })
          return False
  ```

- [ ] **Step 4.4: Pass `admin_repository` to `AgentService` in `main.py`**

  In `tool-call-agent/main.py`, replace:

  ```python
  service = AgentService(repository=_repository)
  ```

  with:

  ```python
  service = AgentService(repository=_repository, admin_repository=_admin_repository)
  ```

- [ ] **Step 4.5: Run the new agent tests**

  ```bash
  cd tool-call-agent && pytest tests/test_agent.py -v
  ```

  Expected: all `PASSED`.

- [ ] **Step 4.6: Run full suite**

  ```bash
  cd tool-call-agent && pytest -v
  ```

  Expected: all `PASSED`.

- [ ] **Step 4.7: Commit**

  ```bash
  git add tool-call-agent/agent_service.py tool-call-agent/main.py tool-call-agent/tests/test_agent.py
  git commit -m "feat(agent): wire instance persona skills into AgentService via LocalSkills"
  ```

---

## Task 5: Frontend service layer

**Files:**
- Modify: `tool-call-ui/src/app/services/admin.service.ts`
- Modify: `tool-call-ui/src/app/services/chat.service.ts`
- Modify: `tool-call-ui/src/app/services/websocket-chat.service.ts`

No dedicated Angular unit tests exist for services (they're tested via the component spec). Changes here are verified in Task 6.

- [ ] **Step 5.1: Add `getAllAgentInstances` to `AdminService`**

  In `tool-call-ui/src/app/services/admin.service.ts`, add after `getAgentInstances`:

  ```typescript
  getAllAgentInstances() {
    return firstValueFrom(this.http.get<AgentInstance[]>(`${API}/agent-instances`));
  }
  ```

- [ ] **Step 5.2: Update `ChatService.createSession`**

  In `tool-call-ui/src/app/services/chat.service.ts`, replace `createSession`:

  ```typescript
  async createSession(instanceId?: string | null): Promise<void> {
    const body = instanceId ? { instance_id: instanceId } : {};
    const res = await firstValueFrom(
      this.http.post<{ session_id: string }>(`${API_URL}/sessions`, body)
    );
    this.sessionId = res.session_id;
  }
  ```

- [ ] **Step 5.3: Update `WebsocketChatService.createSession`**

  In `tool-call-ui/src/app/services/websocket-chat.service.ts`, replace `createSession`:

  ```typescript
  async createSession(instanceId?: string | null): Promise<void> {
    const body = instanceId ? { instance_id: instanceId } : {};
    const res = await firstValueFrom(
      this.http.post<{ session_id: string }>(`${API_URL}/sessions`, body)
    );
    this.sessionId = res.session_id;
  }
  ```

- [ ] **Step 5.4: Verify TypeScript compiles**

  ```bash
  cd tool-call-ui && npx tsc --noEmit
  ```

  Expected: no errors.

- [ ] **Step 5.5: Commit**

  ```bash
  git add tool-call-ui/src/app/services/admin.service.ts tool-call-ui/src/app/services/chat.service.ts tool-call-ui/src/app/services/websocket-chat.service.ts
  git commit -m "feat(ui): add getAllAgentInstances and forward instanceId to createSession"
  ```

---

## Task 6: Chat component — instance picker UI + tests

**Files:**
- Modify: `tool-call-ui/src/app/components/chat/chat.ts`
- Modify: `tool-call-ui/src/app/components/chat/chat.html`
- Modify: `tool-call-ui/src/app/components/chat/chat.css`
- Modify: `tool-call-ui/src/app/components/chat/chat.spec.ts`

- [ ] **Step 6.1: Write failing tests**

  Replace the full content of `tool-call-ui/src/app/components/chat/chat.spec.ts`:

  ```typescript
  import { ComponentFixture, TestBed } from '@angular/core/testing';
  import { Chat } from './chat';
  import { ChatService } from '../../services/chat.service';
  import { AdminService, AgentInstance } from '../../services/admin.service';
  import { provideHttpClientTesting } from '@angular/common/http/testing';
  import { provideHttpClient } from '@angular/common/http';
  import { Subject } from 'rxjs';
  import { SseEvent } from '../../models/types';

  describe('Chat', () => {
    let component: Chat;
    let fixture: ComponentFixture<Chat>;
    let chatService: jasmine.SpyObj<ChatService>;
    let adminService: jasmine.SpyObj<AdminService>;
    let sseSubject: Subject<SseEvent>;

    beforeEach(async () => {
      sseSubject = new Subject<SseEvent>();
      chatService = jasmine.createSpyObj(
        'ChatService',
        ['createSession', 'connectStream', 'sendMessage', 'approveTool', 'closeStream'],
        { sseEvents$: sseSubject }
      );
      chatService.createSession.and.returnValue(Promise.resolve());
      chatService.sendMessage.and.returnValue(Promise.resolve());
      chatService.approveTool.and.returnValue(Promise.resolve());

      adminService = jasmine.createSpyObj('AdminService', [
        'getAllAgentInstances',
        'getCredentials',
      ]);
      adminService.getAllAgentInstances.and.returnValue(Promise.resolve([]));
      adminService.getCredentials.and.returnValue(Promise.resolve(null));

      await TestBed.configureTestingModule({
        imports: [Chat],
        providers: [
          provideHttpClient(),
          provideHttpClientTesting(),
          { provide: ChatService, useValue: chatService },
          { provide: AdminService, useValue: adminService },
        ],
      }).compileComponents();

      fixture = TestBed.createComponent(Chat);
      component = fixture.componentInstance;
      fixture.detectChanges();
    });

    it('should create', () => {
      expect(component).toBeTruthy();
    });

    it('should initialize a session on init', () => {
      expect(chatService.createSession).toHaveBeenCalled();
    });

    it('should fetch all agent instances on init', () => {
      expect(adminService.getAllAgentInstances).toHaveBeenCalled();
    });

    it('should populate instances and select first on init', async () => {
      const instances: AgentInstance[] = [
        {
          id: 'inst-1',
          agent_name: 'agent-a',
          instance_name: 'one',
          persona_id: null,
          mcp_positions: [],
          created_at: '',
          updated_at: '',
        },
      ];
      adminService.getAllAgentInstances.and.returnValue(Promise.resolve(instances));
      await component.ngOnInit();
      expect(component.instances).toEqual(instances);
      expect(component.selectedInstanceId).toBe('inst-1');
    });

    it('should set selectedInstanceId to null when no instances exist', async () => {
      adminService.getAllAgentInstances.and.returnValue(Promise.resolve([]));
      await component.ngOnInit();
      expect(component.selectedInstanceId).toBeNull();
    });

    it('should call newSession when onInstanceChange is called', async () => {
      spyOn(component, 'newSession').and.returnValue(Promise.resolve());
      await component.onInstanceChange();
      expect(component.newSession).toHaveBeenCalled();
    });

    it('should pass selectedInstanceId to createSession', async () => {
      component.selectedInstanceId = 'inst-42';
      await component.newSession();
      expect(chatService.createSession).toHaveBeenCalledWith('inst-42');
    });

    it('should pass undefined to createSession when selectedInstanceId is null', async () => {
      component.selectedInstanceId = null;
      await component.newSession();
      expect(chatService.createSession).toHaveBeenCalledWith(undefined);
    });

    it('should add a user message when sendMessage is called', async () => {
      component.userInput = 'Hello';
      await component.sendMessage();
      const userMsg = component.messages.find((m) => m.role === 'user');
      expect(userMsg?.content).toBe('Hello');
      expect(component.userInput).toBe('');
    });

    it('should not send empty messages', async () => {
      component.userInput = '   ';
      await component.sendMessage();
      expect(chatService.sendMessage).not.toHaveBeenCalled();
    });

    it('should add assistant message on SSE message event', () => {
      sseSubject.next({ type: 'message', content: 'Hi there!' });
      fixture.detectChanges();
      const assistantMsg = component.messages.find((m) => m.role === 'assistant');
      expect(assistantMsg?.content).toBe('Hi there!');
    });

    it('should set pendingToolCall on tool_call_pending event', () => {
      sseSubject.next({
        type: 'tool_call_pending',
        tool_use_id: 'abc',
        tool_name: 'calculate',
        tool_input: { expression: '2+2' },
      });
      fixture.detectChanges();
      expect(component.pendingToolCall).not.toBeNull();
      expect(component.pendingToolCall?.tool_name).toBe('calculate');
    });

    it('should clear pendingToolCall after approval', async () => {
      component.pendingToolCall = {
        tool_use_id: 'abc',
        tool_name: 'calculate',
        tool_input: { expression: '2+2' },
      };
      await component.handleApproval(true);
      expect(chatService.approveTool).toHaveBeenCalledWith(true);
      expect(component.pendingToolCall).toBeNull();
    });
  });
  ```

- [ ] **Step 6.2: Run tests to confirm they fail**

  ```bash
  cd tool-call-ui && npx ng test --include="**/chat.spec.ts" --watch=false
  ```

  Expected: several `FAILED` — `instances`, `selectedInstanceId`, `onInstanceChange` don't exist on `Chat`.

- [ ] **Step 6.3: Update `chat.ts`**

  Replace the full content of `tool-call-ui/src/app/components/chat/chat.ts`:

  ```typescript
  import {
    ChangeDetectorRef,
    Component,
    OnInit,
    OnDestroy,
    ViewChild,
    ElementRef,
    AfterViewChecked,
  } from '@angular/core';
  import { CommonModule } from '@angular/common';
  import { FormsModule } from '@angular/forms';
  import { Subscription } from 'rxjs';
  import { AdminService, AgentInstance } from '../../services/admin.service';
  import { ChatService } from '../../services/chat.service';
  import { WebsocketChatService } from '../../services/websocket-chat.service';
  import { ToolApproval } from '../tool-approval/tool-approval';
  import { Message, ToolCall } from '../../models/types';

  export type ConnectionMode = 'sse' | 'websocket';

  @Component({
    selector: 'app-chat',
    standalone: true,
    imports: [CommonModule, FormsModule, ToolApproval],
    templateUrl: './chat.html',
    styleUrl: './chat.css',
  })
  export class Chat implements OnInit, OnDestroy, AfterViewChecked {
    @ViewChild('messageList') private messageListRef!: ElementRef;

    messages: Message[] = [];
    userInput = '';
    pendingToolCall: ToolCall | null = null;
    isWaiting = false;
    mode: ConnectionMode = 'sse';
    isSwitching = false;
    instances: AgentInstance[] = [];
    selectedInstanceId: string | null = null;

    private sseSubscription!: Subscription;
    private shouldScrollToBottom = false;
    private kubeconfig: string | null = null;

    constructor(
      private chatService: ChatService,
      private wsChatService: WebsocketChatService,
      private adminService: AdminService,
      private cdr: ChangeDetectorRef
    ) {}

    private get activeService(): ChatService | WebsocketChatService {
      return this.mode === 'sse' ? this.chatService : this.wsChatService;
    }

    async ngOnInit(): Promise<void> {
      const [creds, instances] = await Promise.all([
        this.adminService.getCredentials().catch(() => null),
        this.adminService.getAllAgentInstances().catch(() => []),
      ]);
      this.kubeconfig = creds?.kubeconfig ?? null;
      this.instances = instances;
      this.selectedInstanceId = instances[0]?.id ?? null;
      await this.initConnection();
    }

    ngAfterViewChecked(): void {
      if (this.shouldScrollToBottom) {
        this.scrollToBottom();
        this.shouldScrollToBottom = false;
      }
    }

    ngOnDestroy(): void {
      this.sseSubscription?.unsubscribe();
      this.activeService.closeStream();
    }

    async newSession(): Promise<void> {
      if (this.isSwitching) return;
      this.isSwitching = true;
      this.sseSubscription?.unsubscribe();
      this.activeService.closeStream();
      this.messages = [];
      this.pendingToolCall = null;
      this.isWaiting = false;
      await this.initConnection();
      this.isSwitching = false;
    }

    async onInstanceChange(): Promise<void> {
      await this.newSession();
    }

    async switchMode(newMode: ConnectionMode): Promise<void> {
      if (newMode === this.mode || this.isSwitching) return;
      this.isSwitching = true;
      this.sseSubscription?.unsubscribe();
      this.activeService.closeStream();
      this.messages = [];
      this.pendingToolCall = null;
      this.isWaiting = false;
      this.mode = newMode;
      await this.initConnection();
      this.isSwitching = false;
    }

    async sendMessage(): Promise<void> {
      const text = this.userInput.trim();
      if (!text) return;
      this.userInput = '';
      this.addMessage('user', text);
      this.isWaiting = true;
      const platformContext = this.kubeconfig ? { kubeconfig: this.kubeconfig } : undefined;
      await this.activeService.sendMessage(text, platformContext);
    }

    async handleApproval(approved: boolean): Promise<void> {
      this.pendingToolCall = null;
      this.isWaiting = true;
      await this.activeService.approveTool(approved);
    }

    private async initConnection(): Promise<void> {
      await this.activeService.createSession(this.selectedInstanceId ?? undefined);
      this.activeService.connectStream();
      this.sseSubscription = this.activeService.sseEvents$.subscribe((event) => {
        switch (event.type) {
          case 'thinking':
            this.isWaiting = true;
            break;
          case 'tool_call_pending':
            this.isWaiting = false;
            this.pendingToolCall = {
              tool_use_id: event.tool_use_id!,
              tool_name: event.tool_name!,
              tool_input: event.tool_input ?? {},
            };
            break;
          case 'tool_result':
            this.addSystemMessage(
              `Tool "${event.tool_name}" returned: ${event.result}`
            );
            break;
          case 'tool_rejected':
            this.addSystemMessage(`Tool "${event.tool_name}" was rejected.`);
            break;
          case 'message':
            this.isWaiting = false;
            this.appendAssistantMessage(event.content ?? '');
            break;
          case 'done':
            this.isWaiting = false;
            if (this.mode === 'sse') {
              this.activeService.connectStream();
            }
            break;
          case 'error':
            this.isWaiting = false;
            this.addSystemMessage(`Error: ${event.content}`);
            break;
        }
        this.shouldScrollToBottom = true;
        this.cdr.detectChanges();
      });
    }

    private appendAssistantMessage(content: string): void {
      const last = this.messages.at(-1);
      if (last?.role === 'assistant') {
        last.content += content;
      } else {
        this.addMessage('assistant', content);
      }
    }

    private addMessage(role: 'user' | 'assistant', content: string): void {
      this.messages.push({
        id: crypto.randomUUID(),
        role,
        content,
        timestamp: new Date(),
      });
    }

    private addSystemMessage(content: string): void {
      this.messages.push({
        id: crypto.randomUUID(),
        role: 'system',
        content,
        timestamp: new Date(),
      });
    }

    private scrollToBottom(): void {
      try {
        const el = this.messageListRef?.nativeElement;
        if (el) el.scrollTop = el.scrollHeight;
      } catch {
        // ignore scroll errors in test env
      }
    }
  }
  ```

- [ ] **Step 6.4: Update `chat.html` — add the instance bar**

  In `tool-call-ui/src/app/components/chat/chat.html`, add the instance bar between `</header>` and `<div class="message-list"`:

  ```html
  <div class="chat-container">
    <header class="chat-header">
      <span class="header-icon">🤖</span>
      <div class="header-text">
        <h1>Tool Call Approval</h1>
        <span class="subtitle">Claude agent with human-in-the-loop</span>
      </div>

      <button
        type="button"
        class="new-session-btn"
        [disabled]="isSwitching || isWaiting"
        (click)="newSession()"
        title="New session"
      >+ New</button>

      <div class="mode-toggle">
        <button
          type="button"
          class="mode-btn"
          [class.active]="mode === 'sse'"
          [disabled]="isSwitching"
          (click)="switchMode('sse')"
        >
          <span class="mode-dot"></span>
          SSE
        </button>
        <button
          type="button"
          class="mode-btn"
          [class.active]="mode === 'websocket'"
          [disabled]="isSwitching"
          (click)="switchMode('websocket')"
        >
          <span class="mode-dot"></span>
          WebSocket
        </button>
      </div>
    </header>

    @if (instances.length > 0) {
      <div class="instance-bar">
        <label class="instance-label">Agent instance</label>
        <select
          class="instance-select"
          [(ngModel)]="selectedInstanceId"
          (ngModelChange)="onInstanceChange()"
          name="instanceSelect"
        >
          <option [ngValue]="null">— none —</option>
          @for (inst of instances; track inst.id) {
            <option [ngValue]="inst.id">{{ inst.agent_name }} / {{ inst.instance_name }}</option>
          }
        </select>
      </div>
    }

    <div class="message-list" #messageList>
      @if (messages.length === 0) {
        <div class="empty-state">
          <p>Try asking:</p>
          <ul>
            <li>"What is 1234 × 5678?"</li>
            <li>"What's the weather in London?"</li>
            <li>"Search for information about black holes"</li>
          </ul>
        </div>
      }

      @for (message of messages; track message.id) {
        <div class="message" [ngClass]="message.role">
          <div class="bubble">{{ message.content }}</div>
          <span class="timestamp">{{ message.timestamp | date: 'HH:mm' }}</span>
        </div>
      }

      @if (pendingToolCall) {
        <app-tool-approval
          [toolCall]="pendingToolCall"
          [disabled]="isWaiting"
          (approved)="handleApproval($event)"
        />
      }

      @if (isWaiting && !pendingToolCall) {
        <div class="thinking">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
      }
    </div>

    <form class="input-area" (ngSubmit)="sendMessage()">
      <input
        class="input-field"
        type="text"
        [(ngModel)]="userInput"
        name="userInput"
        placeholder="Ask the agent something..."
        [disabled]="isWaiting || !!pendingToolCall"
        autocomplete="off"
      />
      <button
        class="send-btn"
        type="submit"
        [disabled]="isWaiting || !!pendingToolCall || !userInput.trim()"
      >
        Send
      </button>
    </form>
  </div>
  ```

- [ ] **Step 6.5: Add `.instance-bar` styles to `chat.css`**

  Append to `tool-call-ui/src/app/components/chat/chat.css`:

  ```css
  .instance-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 24px;
    background: #1e2433;
    border-bottom: 1px solid #334155;
  }

  .instance-label {
    font-size: 0.8rem;
    color: #94a3b8;
    white-space: nowrap;
  }

  .instance-select {
    font-size: 0.85rem;
    padding: 4px 8px;
    border: 1px solid #334155;
    border-radius: 6px;
    background: #0f172a;
    color: #f1f5f9;
    cursor: pointer;
  }
  ```

- [ ] **Step 6.6: Run the component tests**

  ```bash
  cd tool-call-ui && npx ng test --include="**/chat.spec.ts" --watch=false
  ```

  Expected: all `PASSED`.

- [ ] **Step 6.7: Run full TypeScript check**

  ```bash
  cd tool-call-ui && npx tsc --noEmit
  ```

  Expected: no errors.

- [ ] **Step 6.8: Commit**

  ```bash
  git add tool-call-ui/src/app/components/chat/chat.ts tool-call-ui/src/app/components/chat/chat.html tool-call-ui/src/app/components/chat/chat.css tool-call-ui/src/app/components/chat/chat.spec.ts
  git commit -m "feat(ui): add agent instance picker to AI-Engg chat page"
  ```

---

## Self-Review Checklist

- **Spec coverage:**
  - `GET /admin/agent-instances` without filter → Task 3 ✓
  - `CreateSessionRequest` with `instance_id` → Task 3 ✓
  - `Session.tmpdir` → Task 1 ✓
  - `AdminRepository` new methods → Task 2 ✓
  - `AgentService` instance → skills wiring → Task 4 ✓
  - tmpdir cleanup on session removal → Task 4 ✓
  - Skip missing skills gracefully → Task 4 (test `test_create_session_skips_missing_skill`) ✓
  - `getAllAgentInstances` in `AdminService` → Task 5 ✓
  - `createSession(instanceId?)` in both chat services → Task 5 ✓
  - Instance picker dropdown in chat component → Task 6 ✓
  - `onInstanceChange()` resets session → Task 6 ✓
  - Error handling (no instances → dropdown hidden) → Task 6 (`.instance-bar` inside `@if (instances.length > 0)`) ✓
  - WebSocket service updated → Task 5 ✓

- **Type consistency:** `AgentInstance` imported from `admin.service.ts` in both `chat.ts` and `chat.spec.ts`. `selectedInstanceId: string | null` matches `[ngValue]="null"` and `[ngValue]="inst.id"` in template.

- **No placeholders:** All steps contain complete code. ✓
