# Message Envelope Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require the new message envelope schema for session creation, chat, and approval payloads.

**Architecture:** Keep the existing HTTP routes, but replace simple request bodies with a shared envelope containing session metadata, messages, platform context, ambient context, data attachments, and approval details where needed. The API gateway validates and forwards the envelope; the agent backend consumes the same shape.

**Tech Stack:** FastAPI, Pydantic, pytest, Angular HttpClient, Jasmine/Karma.

---

### Task 1: Backend And Gateway Contract Tests

**Files:**
- Modify: `tool-call-api/tests/test_main.py`
- Modify: `tool-call-agent/tests/test_main.py`

- [ ] Write tests showing `POST /sessions`, `POST /sessions/{id}/chat`, and `POST /sessions/{id}/approve` reject old bodies and accept the new envelope.
- [ ] Run targeted pytest commands and confirm the new tests fail before implementation.

### Task 2: Python Envelope Schemas

**Files:**
- Create: `tool-call-api/models.py`
- Modify: `tool-call-api/main.py`
- Modify: `tool-call-agent/models.py`
- Modify: `tool-call-agent/main.py`

- [ ] Add strict Pydantic models for file, command, executed command, URL config, platform context, ambient context, data, user/assistant messages, session context, approval context, and message envelope.
- [ ] Update session, chat, and approval handlers to accept only those envelopes.
- [ ] Forward envelope JSON from the API gateway to the agent backend.

### Task 3: Frontend Envelope Payloads

**Files:**
- Modify: `tool-call-ui/src/app/models/types.ts`
- Modify: `tool-call-ui/src/app/services/chat.service.ts`
- Modify: `tool-call-ui/src/app/services/websocket-chat.service.ts`
- Test: `tool-call-ui/src/app/services/chat.service.spec.ts`

- [ ] Add TypeScript interfaces for the envelope.
- [ ] Build create-session, chat, and approval request bodies with the new envelope.
- [ ] Add service tests for the posted JSON.

### Task 4: Verification And Docs

**Files:**
- Modify: `tool-call-api/README.md`

- [ ] Run focused backend and gateway pytest suites.
- [ ] Run the frontend service/component tests that cover the changed payload builders.
- [ ] Document the new envelope payload examples.
