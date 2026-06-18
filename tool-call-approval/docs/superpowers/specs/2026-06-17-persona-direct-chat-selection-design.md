# Persona Direct Chat Selection Design

## Goal

Move chat session configuration from selecting an agent instance to selecting a persona directly. A persona already owns a list of skill IDs, so the chat flow should send `persona_id` in the message envelope and the backend should load that persona's skills onto the agent for the session.

## Current State

The chat page currently loads agent instances and sends `instance_id` when creating a session. The agent then resolves skills indirectly:

```text
instance_id -> persona_id -> skill_ids -> SKILL.md content
```

This makes the chat page depend on instance configuration even when the user only needs to choose a persona and its skills.

## Proposed Contract

Add `persona_id` to `SessionContext` while keeping `instance_id` nullable for backward compatibility:

```json
{
  "session": {
    "session_id": null,
    "instance_id": null,
    "persona_id": "persona-1",
    "system_prompt_id": "prompt-1",
    "model_id": "nemotron-3-super",
    "provider": "LOCAL"
  },
  "messages": [],
  "approval": null
}
```

The complete-envelope rule still applies: every session key is present, and absent values are explicit `null`.

## Backend Design

Session creation accepts `persona_id` in both the API gateway schema and the agent schema. `AgentService.create_session()` receives both `instance_id` and `persona_id`.

Skill loading precedence:

1. If `persona_id` is provided, load skills directly from that persona.
2. If `persona_id` is absent and `instance_id` is provided, keep the current fallback path through the instance.
3. If neither resolves skills, create the agent without a skills object.

The session object should retain `persona_id`, `persona_name`, and the selected `skill_ids` for history snapshots. Assistant message agent metadata should include:

```json
{
  "session_id": "session-1",
  "instance_id": null,
  "persona_id": "persona-1",
  "persona_name": "kubernetes_operator",
  "skill_ids": ["skill-1", "skill-2"],
  "system_prompt_id": "prompt-1",
  "system_prompt_name": "kubernetes_agent",
  "model_id": "nemotron-3-super",
  "provider": "LOCAL"
}
```

Repository history normalization should include those agent metadata fields with `null` or empty-array defaults where absent.

## UI Design

The chat page should load personas and skills from the existing admin endpoints:

- `GET /api/admin/personas`
- `GET /api/admin/skills`

Replace the chat page's agent instance selector with a Persona list box. The list should show persona names. A compact skills summary can be displayed beside or under the selected persona using the skill filenames already available from the skills endpoint.

When a persona changes, the chat page starts a new session, matching the current behavior for instance/provider/model changes. `ChatService.createSession()` and `WebsocketChatService.createSession()` should accept `personaId` and include it in the normalized envelope.

The admin agent instance screens can stay as they are. This change only removes instances from the chat session path.

## Compatibility

Existing clients that still send `instance_id` continue to work because the backend falls back to the current instance-to-persona resolution path.

Existing stored history remains readable. Missing `persona_id`, `persona_name`, and `skill_ids` are normalized as `null`, `null`, and `[]`.

## Testing

Backend tests should cover:

- `SessionContext` accepts and forwards `persona_id`.
- Creating a session with `persona_id` loads the persona's skills directly.
- Creating a session with only `instance_id` still loads skills through the instance fallback.
- Agent message metadata includes persona and skill snapshot fields.

UI tests should cover:

- Chat initialization loads personas and skills.
- The chat page selects the first persona by default when available.
- Changing persona starts a new session.
- Session creation sends `persona_id` and keeps `instance_id: null`.
- Envelope normalization includes `persona_id` on chat and approval requests after session creation.
