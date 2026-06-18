# Persona Direct Chat Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let chat sessions select a persona directly and load that persona's skills without requiring an agent instance.

**Architecture:** Add `persona_id` to the full `MessageEnvelope.session` contract, keep `instance_id` as a nullable backward-compatible field, and teach `AgentService` to load skills directly from a persona before falling back to the existing instance path. Replace the chat page's agent instance selector with a persona selector that sends `persona_id` through both SSE and WebSocket chat services.

**Tech Stack:** FastAPI, Pydantic, Python dataclasses, Agno `Skills`/`LocalSkills`, Angular standalone components, Jasmine/Karma, Docker Compose.

---

## File Structure

- Modify `tool-call-api/models.py`: add `persona_id` to `SessionContext`.
- Modify `tool-call-agent/app/schemas/messages.py`: add `persona_id` to `SessionContext`.
- Modify `tool-call-agent/app/domain/session.py`: store `persona_id`, `persona_name`, and `skill_ids` on a session.
- Modify `tool-call-agent/app/api/main.py`: pass `persona_id` into `AgentService.create_session()`.
- Modify `tool-call-agent/app/services/agent_service.py`: resolve skills from direct persona selection and include persona snapshot metadata in assistant messages.
- Modify `tool-call-agent/app/repositories/agent_repository.py`: normalize agent metadata with `persona_id`, `persona_name`, and `skill_ids`.
- Modify `tool-call-ui/src/app/models/types.ts`: add `persona_id` to `SessionContext`.
- Modify `tool-call-ui/src/app/services/envelope.ts`: include `persona_id` in normalized session contexts.
- Modify `tool-call-ui/src/app/services/chat.service.ts`: accept and persist `personaId` during session creation.
- Modify `tool-call-ui/src/app/services/websocket-chat.service.ts`: mirror `ChatService` persona handling.
- Modify `tool-call-ui/src/app/components/chat/chat.ts`: load personas and skills, select persona, and create sessions with `persona_id`.
- Modify `tool-call-ui/src/app/components/chat/chat.html`: replace the instance selector with a persona selector and skill summary.
- Modify tests in `tool-call-api/tests/test_main.py`, `tool-call-agent/tests/test_main.py`, `tool-call-agent/tests/test_agent.py`, `tool-call-ui/src/app/services/chat.service.spec.ts`, and `tool-call-ui/src/app/components/chat/chat.spec.ts`.

---

### Task 1: Schema Contract

**Files:**
- Modify: `tool-call-api/models.py`
- Modify: `tool-call-agent/app/schemas/messages.py`
- Modify: `tool-call-ui/src/app/models/types.ts`
- Modify: `tool-call-ui/src/app/services/envelope.ts`
- Test: `tool-call-api/tests/test_main.py`
- Test: `tool-call-ui/src/app/services/chat.service.spec.ts`

- [ ] **Step 1: Write failing API proxy expectation**

In `tool-call-api/tests/test_main.py`, update `EMPTY_SESSION`:

```python
EMPTY_SESSION = {
    "session_id": None,
    "instance_id": None,
    "persona_id": None,
    "system_prompt_id": None,
    "model_id": None,
    "provider": None,
}
```

Add a create-session assertion that sends and forwards a persona:

```python
async def test_create_session_forwards_selected_persona(ac):
    mock_client = AsyncMock()
    mock_client.post.return_value = _resp(200, {"session_id": "abc-123"})

    with patch("main._client", mock_client):
        resp = await ac.post(
            "/api/sessions",
            json=_session_envelope(instance_id=None, persona_id="persona-1"),
        )

    assert resp.status_code == 200
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["session"]["instance_id"] is None
    assert payload["session"]["persona_id"] == "persona-1"
```

- [ ] **Step 2: Write failing UI service expectation**

In `tool-call-ui/src/app/services/chat.service.spec.ts`, update `EMPTY_SESSION` with `persona_id: null`, then call:

```typescript
const promise = service.createSession(
  null,
  'persona-1',
  'prompt-1',
  'nemotron-3-super',
  'LOCAL',
);
```

Expected body:

```typescript
expect(req.request.body.session).toEqual({
  session_id: null,
  instance_id: null,
  persona_id: 'persona-1',
  system_prompt_id: 'prompt-1',
  model_id: 'nemotron-3-super',
  provider: 'LOCAL',
});
```

- [ ] **Step 3: Verify red tests**

Run focused checks:

```bash
npm test -- --watch=false --browsers=ChromeHeadless --include src/app/services/chat.service.spec.ts
```

Expected: UI service test fails because `persona_id` is not sent.

For API, run in the rebuilt/container path used by this repo:

```bash
docker compose build tool-call-api
docker create --name tca-api-persona-test tool-call-api:latest pytest tests/test_main.py::test_create_session_forwards_selected_persona
docker cp tool-call-api/tests tca-api-persona-test:/app/tests
docker start -a tca-api-persona-test
docker rm tca-api-persona-test
```

Expected: API schema rejects or drops `persona_id`.

- [ ] **Step 4: Implement schema changes**

Add `persona_id` to both Python `SessionContext` classes:

```python
class SessionContext(StrictBaseModel):
    session_id: str | None
    instance_id: str | None
    persona_id: str | None
    system_prompt_id: str | None
    model_id: str | None
    provider: str | None
```

Add `persona_id` to TypeScript `SessionContext`:

```typescript
export interface SessionContext {
  session_id?: string | null;
  instance_id?: string | null;
  persona_id?: string | null;
  system_prompt_id?: string | null;
  model_id?: string | null;
  provider?: string | null;
}
```

Update `emptySessionContext()`:

```typescript
export function emptySessionContext(): SessionContext {
  return {
    session_id: null,
    instance_id: null,
    persona_id: null,
    system_prompt_id: null,
    model_id: null,
    provider: null,
  };
}
```

- [ ] **Step 5: Verify green tests**

Run the same focused UI and API tests. Expected: both pass.

---

### Task 2: Backend Persona Skill Resolution

**Files:**
- Modify: `tool-call-agent/app/domain/session.py`
- Modify: `tool-call-agent/app/api/main.py`
- Modify: `tool-call-agent/app/services/agent_service.py`
- Modify: `tool-call-agent/app/repositories/agent_repository.py`
- Test: `tool-call-agent/tests/test_main.py`
- Test: `tool-call-agent/tests/test_agent.py`

- [ ] **Step 1: Write failing route test**

In `tool-call-agent/tests/test_main.py`, update `EMPTY_SESSION` with `persona_id: None` and add:

```python
def test_create_session_passes_persona_id_to_service():
    with patch.object(
        main_app.service,
        "create_session",
        return_value=SimpleNamespace(id="session-123"),
    ) as create_session:
        response = client.post(
            "/sessions",
            json=_session_envelope(
                instance_id=None,
                persona_id="persona-1",
                system_prompt_id="prompt-1",
                model_id="nemotron-3-super",
                provider="LOCAL",
            ),
        )

    assert response.status_code == 200
    create_session.assert_called_once_with(
        None,
        "persona-1",
        "prompt-1",
        "nemotron-3-super",
        "LOCAL",
    )
```

- [ ] **Step 2: Write failing service tests**

In `tool-call-agent/tests/test_agent.py`, extend `MockAdminRepo`:

```python
def get_persona(self, persona_id):
    if persona_id == "persona-1":
        return {"id": "persona-1", "name": "ops_persona", "skill_ids": ["skill-1"]}
    return None

def get_skill_content(self, skill_id):
    if skill_id == "skill-1":
        return ("ops.md", "# Ops\nUse safe commands.")
    return None
```

Add test:

```python
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
```

Add metadata test:

```python
def test_agent_message_metadata_includes_persona_snapshot(service):
    with patch("app.services.agent_service.Agent"), patch("app.services.agent_service.AwsBedrock"):
        session = service.create_session(persona_id="persona-1")

    service.record_agent_message(session, "hello")

    agent = service._repository.messages[-1]["message"]["agent"]
    assert agent["persona_id"] == "persona-1"
    assert agent["persona_name"] == "ops_persona"
    assert agent["skill_ids"] == ["skill-1"]
```

- [ ] **Step 3: Verify red tests**

```bash
docker compose build tool-calling-k8s-agent
docker create --name tca-agent-persona-test tool-calling-k8s-agent:latest pytest tests/test_main.py::test_create_session_passes_persona_id_to_service tests/test_agent.py::test_create_session_loads_direct_persona_skills tests/test_agent.py::test_agent_message_metadata_includes_persona_snapshot
docker cp tool-call-agent/tests tca-agent-persona-test:/app/tests
docker start -a tca-agent-persona-test
docker rm tca-agent-persona-test
```

Expected: tests fail because `persona_id` is not accepted or stored.

- [ ] **Step 4: Implement backend changes**

Add fields to `Session`:

```python
persona_id: str | None = None
persona_name: str | None = None
skill_ids: list[str] = field(default_factory=list)
```

Change `AgentService.create_session()` signature:

```python
def create_session(
    self,
    instance_id: str | None = None,
    persona_id: str | None = None,
    system_prompt_id: str | None = None,
    model_id: str | None = None,
    provider: str | None = None,
) -> Session:
```

Pass `persona_id` from API:

```python
session = service.create_session(
    session_context.instance_id,
    session_context.persona_id,
    session_context.system_prompt_id,
    session_context.model_id,
    session_context.provider,
)
```

Add direct persona loader:

```python
def _load_persona_skills(self, persona_id: str) -> tuple[str | None, Any, dict[str, Any] | None]:
    persona = self._admin_repository.get_persona(persona_id)
    if not persona or not persona.get("skill_ids"):
        return None, None, persona
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
        return None, None, persona
    return tmpdir, Skills(loaders=[LocalSkills(tmpdir)]), persona
```

Set session fields after loading:

```python
session.persona_id = str(persona["id"]) if persona else None
session.persona_name = persona.get("name") if persona else None
session.skill_ids = list(persona.get("skill_ids") or []) if persona else []
```

Extend `_agent_message_metadata()`:

```python
"persona_id": session.persona_id,
"persona_name": session.persona_name,
"skill_ids": session.skill_ids,
```

Extend repository `_normalize_agent()`:

```python
"persona_id": agent.get("persona_id"),
"persona_name": agent.get("persona_name"),
"skill_ids": agent.get("skill_ids") if isinstance(agent.get("skill_ids"), list) else [],
```

- [ ] **Step 5: Verify green tests**

Run the focused agent tests again. Expected: all pass.

---

### Task 3: Chat UI Persona Selector

**Files:**
- Modify: `tool-call-ui/src/app/components/chat/chat.ts`
- Modify: `tool-call-ui/src/app/components/chat/chat.html`
- Modify: `tool-call-ui/src/app/services/chat.service.ts`
- Modify: `tool-call-ui/src/app/services/websocket-chat.service.ts`
- Test: `tool-call-ui/src/app/components/chat/chat.spec.ts`
- Test: `tool-call-ui/src/app/services/chat.service.spec.ts`

- [ ] **Step 1: Write failing component tests**

Update Chat spec imports to use `PersonaData` and `Skill`. Extend the admin service spy with `getPersonas` and `getSkills`.

Add:

```typescript
it('should populate personas and select first on init', async () => {
  const personas: PersonaData[] = [{
    id: 'persona-1',
    name: 'ops_persona',
    skill_ids: ['skill-1'],
    created_at: '',
    updated_at: '',
  }];
  adminService.getPersonas.and.returnValue(Promise.resolve(personas));
  adminService.getSkills.and.returnValue(Promise.resolve([]));

  await component.ngOnInit();

  expect(component.personas).toEqual(personas);
  expect(component.selectedPersonaId).toBe('persona-1');
});
```

Add session creation expectation:

```typescript
it('should pass selectedPersonaId to createSession', async () => {
  component.selectedPersonaId = 'persona-42';
  component.selectedSystemPromptId = 'prompt-42';

  await component.newSession();

  expect(chatService.createSession).toHaveBeenCalledWith(
    null,
    'persona-42',
    'prompt-42',
    'nemotron-3-super',
    'LOCAL',
  );
});
```

- [ ] **Step 2: Write failing service tests**

Update `ChatService.createSession()` tests to call the new signature:

```typescript
service.createSession(null, 'persona-1', 'prompt-1', 'nemotron-3-super', 'LOCAL');
```

Expected request session includes:

```typescript
instance_id: null,
persona_id: 'persona-1',
```

- [ ] **Step 3: Verify red UI tests**

```bash
npm test -- --watch=false --browsers=ChromeHeadless --include src/app/components/chat/chat.spec.ts
npm test -- --watch=false --browsers=ChromeHeadless --include src/app/services/chat.service.spec.ts
```

Expected: tests fail because chat still uses instances.

- [ ] **Step 4: Implement UI service changes**

Change `createSession()` signatures:

```typescript
async createSession(
  instanceId?: string | null,
  personaId?: string | null,
  systemPromptId?: string | null,
  modelId?: string | null,
  provider?: string | null,
): Promise<void>
```

Set session:

```typescript
const session: SessionContext = normalizeSessionContext({
  session_id: null,
  instance_id: instanceId ?? null,
  persona_id: personaId ?? null,
  system_prompt_id: systemPromptId ?? null,
  model_id: modelId ?? null,
  provider: provider ?? null,
});
```

Apply the same signature and session construction in `WebsocketChatService`.

- [ ] **Step 5: Implement Chat component changes**

Replace instance state with persona state:

```typescript
personas: PersonaData[] = [];
skills: Skill[] = [];
selectedPersonaId: string | null = null;
```

Load personas and skills:

```typescript
const [creds, personas, skills, systemPrompts] = await Promise.all([
  this.adminService.getCredentials().catch(() => null),
  this.adminService.getPersonas().catch(() => []),
  this.adminService.getSkills().catch(() => []),
  this.adminService.listSystemPrompts().catch(() => []),
]);
this.personas = personas;
this.skills = skills;
this.selectedPersonaId = personas[0]?.id ?? null;
```

Add persona change handler:

```typescript
async onPersonaChange(): Promise<void> {
  await this.newSession();
}
```

Create sessions with persona:

```typescript
await this.activeService.createSession(
  null,
  this.selectedPersonaId ?? undefined,
  this.selectedSystemPromptId ?? undefined,
  this.selectedProvider === 'LOCAL' ? this.selectedModelId || undefined : undefined,
  this.selectedProvider,
);
```

Add skill summary helper:

```typescript
selectedPersonaSkillSummary(): string {
  const persona = this.personas.find(p => p.id === this.selectedPersonaId);
  if (!persona || persona.skill_ids.length === 0) return 'No skills';
  return persona.skill_ids
    .map(id => this.skills.find(skill => skill.id === id)?.filename ?? id)
    .join(', ');
}
```

- [ ] **Step 6: Implement template changes**

Replace the instance picker block with:

```html
@if (personas.length > 0) {
  <div class="instance-picker">
    <label class="context-label" for="personaSelect">Persona</label>
    <select class="instance-select"
      id="personaSelect"
      [(ngModel)]="selectedPersonaId"
      (ngModelChange)="onPersonaChange()"
      name="personaSelect"
      title="Persona">
      <option [ngValue]="null">— none —</option>
      @for (persona of personas; track persona.id) {
        <option [ngValue]="persona.id">{{ persona.name }}</option>
      }
    </select>
    <span class="context-hint">{{ selectedPersonaSkillSummary() }}</span>
  </div>
}
```

Update the context bar condition to:

```html
@if (systemPrompts.length > 0 || personas.length > 0) {
```

- [ ] **Step 7: Verify green UI tests**

Run the focused component and service tests. Expected: all pass.

---

### Task 4: Verification and Redeploy

**Files:**
- No source changes unless verification exposes a defect.

- [ ] **Step 1: Run full UI tests**

```bash
npm test -- --watch=false --browsers=ChromeHeadless
```

Expected: `TOTAL: 46 SUCCESS` or the updated count with zero failures.

- [ ] **Step 2: Run UI build**

```bash
npm run build
```

Expected: build succeeds. Existing CSS budget warning is acceptable unless a new error appears.

- [ ] **Step 3: Run API tests in container**

```bash
docker compose build tool-call-api
docker create --name tca-api-persona-full tool-call-api:latest pytest tests
docker cp tool-call-api/tests tca-api-persona-full:/app/tests
docker start -a tca-api-persona-full
docker rm tca-api-persona-full
```

Expected: API tests pass.

- [ ] **Step 4: Run focused agent tests in container**

```bash
docker compose build tool-calling-k8s-agent
docker create --name tca-agent-persona-focused tool-calling-k8s-agent:latest pytest tests/test_main.py::test_create_session_passes_persona_id_to_service tests/test_agent.py::test_create_session_loads_direct_persona_skills tests/test_agent.py::test_agent_message_metadata_includes_persona_snapshot
docker cp tool-call-agent/tests tca-agent-persona-focused:/app/tests
docker start -a tca-agent-persona-focused
docker rm tca-agent-persona-focused
```

Expected: focused agent tests pass.

- [ ] **Step 5: Redeploy updated containers**

```bash
docker compose up -d --no-deps tool-calling-k8s-agent tool-call-api
```

Expected: both containers are recreated and started.

- [ ] **Step 6: Smoke test live endpoints**

```bash
curl -sS http://localhost:8000/health
curl -sS -H 'Content-Type: application/json' -d '{"session":{"session_id":null,"instance_id":null,"persona_id":null,"system_prompt_id":null,"model_id":null,"provider":null},"messages":[],"approval":null}' http://localhost:8080/api/sessions
```

Expected: health returns `{"status":"ok"}` and session creation returns a `session_id`.

---

## Self-Review

- Spec coverage: schema contract, backend direct persona resolution, UI list box, compatibility fallback, metadata snapshot, and tests are covered.
- Placeholder scan: no TBD/TODO placeholders are present.
- Type consistency: `persona_id`, `personaId`, `persona_name`, and `skill_ids` names are consistent with existing persona models and JSON style.
