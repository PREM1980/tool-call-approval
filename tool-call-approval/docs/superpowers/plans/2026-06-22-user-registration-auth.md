# User Registration Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add JWT login, admin-managed users, and per-user chat-session visibility backed by a separate `registration` PostgreSQL database.

**Architecture:** The existing `POSTGRES_URL` database remains the source for Agno state and UI session records. A new registration domain stores users, password hashes, roles, and `user_id <-> session_id` ownership mappings through `REGISTRATION_DATABASE_URL`. FastAPI dependencies enforce auth and ownership; Angular guards and an interceptor make the UI authenticated.

**Tech Stack:** FastAPI, Pydantic, psycopg2, HMAC/PBKDF2 password hashing, standard-library JWT-compatible HMAC tokens, Angular standalone components, Bootstrap/custom SCSS, pytest, Jasmine/Karma.

---

## File Structure

- Create `tool-call-agent/app/domain/user.py`: typed user entity.
- Create `tool-call-agent/app/security/passwords.py`: PBKDF2 password hashing and verification.
- Create `tool-call-agent/app/security/tokens.py`: signed bearer token creation and verification.
- Create `tool-call-agent/app/security/dependencies.py`: FastAPI dependencies for `current_user` and `require_admin`.
- Create `tool-call-agent/app/repositories/registration_repository.py`: registration DB creation, user CRUD, and session ownership queries.
- Create `tool-call-agent/app/services/auth_service.py`: login/current-user behavior.
- Create `tool-call-agent/app/services/user_service.py`: admin user creation/listing.
- Create `tool-call-agent/app/services/session_ownership_service.py`: session ownership checks.
- Create `tool-call-agent/app/schemas/auth.py`: auth/user request and response models.
- Create `tool-call-agent/app/api/auth_router.py`: `/auth/login` and `/auth/me`.
- Modify `tool-call-agent/app/api/admin_router.py`: add `/admin/users` endpoints with role checks.
- Modify `tool-call-agent/app/api/main.py`: wire auth services and protect session routes.
- Modify `tool-call-agent/app/repositories/agent_repository.py`: add owner-filtered `list_sessions(session_ids=...)`.
- Modify tests under `tool-call-agent/tests/`: add focused auth and session ownership tests.
- Modify `tool-call-api/main.py`: forward `Authorization` headers and add `/api/auth/*` proxying.
- Modify Angular app config/routes/services/components for login, auth guard, role guard, interceptor, topbar state, and users UI.
- Update `.env.example`, Docker Compose, and Kubernetes config with registration/JWT variables.

## Tasks

### Task 1: Backend Auth Domain

**Files:**
- Create: `tool-call-approval/tool-call-agent/tests/test_auth.py`
- Create: `tool-call-approval/tool-call-agent/app/domain/user.py`
- Create: `tool-call-approval/tool-call-agent/app/security/passwords.py`
- Create: `tool-call-approval/tool-call-agent/app/security/tokens.py`
- Create: `tool-call-approval/tool-call-agent/app/repositories/registration_repository.py`
- Create: `tool-call-approval/tool-call-agent/app/services/auth_service.py`
- Create: `tool-call-approval/tool-call-agent/app/services/user_service.py`
- Create: `tool-call-approval/tool-call-agent/app/services/session_ownership_service.py`
- Create: `tool-call-approval/tool-call-agent/app/schemas/auth.py`
- Create: `tool-call-approval/tool-call-agent/app/security/__init__.py`

- [ ] Write failing tests for password hashing, token roundtrip, admin seed, user creation, duplicate username, and ownership mapping.
- [ ] Run `cd tool-call-approval/tool-call-agent && /private/tmp/tool-call-approval-venv/bin/python -m pytest tests/test_auth.py -q`; expect import/test failures because the new modules do not exist.
- [ ] Implement the auth domain with PBKDF2 hashes, signed tokens, registration tables, and services.
- [ ] Re-run the focused auth tests; expect pass.

### Task 2: Protect Agent Session APIs

**Files:**
- Modify: `tool-call-approval/tool-call-agent/tests/test_main.py`
- Modify: `tool-call-approval/tool-call-agent/tests/test_sessions.py`
- Modify: `tool-call-approval/tool-call-agent/app/api/main.py`
- Modify: `tool-call-approval/tool-call-agent/app/repositories/agent_repository.py`
- Modify: `tool-call-approval/tool-call-agent/app/repositories/__init__.py`

- [ ] Write failing API tests for missing token, creating session with ownership, owned session listing, unowned history returning `404`, and legacy unowned rows hidden.
- [ ] Run the focused tests and confirm they fail for missing auth/ownership.
- [ ] Wire `RegistrationRepository`, `AuthService`, `TokenService`, and `SessionOwnershipService` into `app/api/main.py`.
- [ ] Add `session_ids` filtering to `PostgresRepository.list_sessions`.
- [ ] Re-run focused backend session/auth tests; expect pass.

### Task 3: Add Auth And User Routes

**Files:**
- Create: `tool-call-approval/tool-call-agent/app/api/auth_router.py`
- Modify: `tool-call-approval/tool-call-agent/app/api/admin_router.py`
- Modify: `tool-call-approval/tool-call-agent/tests/test_main.py`
- Create: `tool-call-approval/tool-call-agent/tests/test_user_admin_api.py`

- [ ] Write failing route tests for `/auth/login`, `/auth/me`, `/admin/users` admin success, `/admin/users` non-admin `403`, and duplicate username `409`.
- [ ] Run the focused route tests and confirm failure.
- [ ] Implement auth router and real-admin user endpoints.
- [ ] Re-run route tests; expect pass.

### Task 4: Proxy Auth Through `tool-call-api`

**Files:**
- Modify: `tool-call-approval/tool-call-api/main.py`
- Modify: `tool-call-approval/tool-call-api/tests/test_main.py`

- [ ] Write failing proxy tests that `/api/auth/login` forwards to `/auth/login` and protected `/api/sessions` forwards the `Authorization` header.
- [ ] Run `cd tool-call-approval/tool-call-api && /private/tmp/tool-call-approval-venv/bin/python -m pytest tests/test_main.py -q`; expect failures.
- [ ] Add auth proxying and authorization-header forwarding.
- [ ] Re-run proxy tests; expect pass.

### Task 5: Angular Auth Flow

**Files:**
- Create: `tool-call-approval/tool-call-ui/src/app/services/auth.service.ts`
- Create: `tool-call-approval/tool-call-ui/src/app/services/auth.interceptor.ts`
- Create: `tool-call-approval/tool-call-ui/src/app/guards/auth.guard.ts`
- Create: `tool-call-approval/tool-call-ui/src/app/guards/admin.guard.ts`
- Create: `tool-call-approval/tool-call-ui/src/app/login/login.ts`
- Create: `tool-call-approval/tool-call-ui/src/app/login/login.html`
- Create: `tool-call-approval/tool-call-ui/src/app/login/login.css`
- Modify: `tool-call-approval/tool-call-ui/src/app/app.config.ts`
- Modify: `tool-call-approval/tool-call-ui/src/app/app.routes.ts`
- Modify: `tool-call-approval/tool-call-ui/src/app/app-shell/app-shell.ts`
- Modify: `tool-call-approval/tool-call-ui/src/app/app-shell/app-shell.html`
- Modify: `tool-call-approval/tool-call-ui/src/app/app-shell/app-shell.css`
- Modify/Create tests for auth service, guards, and login component.

- [ ] Write failing Angular tests for login storing token/current user, interceptor adding bearer token, auth guard redirecting, and admin guard blocking users.
- [ ] Run targeted Angular tests; expect failures.
- [ ] Implement service, interceptor, guards, login route, topbar username/logout, and protected routes.
- [ ] Re-run targeted Angular tests; expect pass.

### Task 6: Angular Admin Users Page

**Files:**
- Create: `tool-call-approval/tool-call-ui/src/app/admin-users/admin-users.ts`
- Create: `tool-call-approval/tool-call-ui/src/app/admin-users/admin-users.html`
- Create: `tool-call-approval/tool-call-ui/src/app/admin-users/admin-users.css`
- Modify: `tool-call-approval/tool-call-ui/src/app/services/admin.service.ts`
- Modify: `tool-call-approval/tool-call-ui/src/app/app.routes.ts`
- Create: `tool-call-approval/tool-call-ui/src/app/admin-users/admin-users.spec.ts`

- [ ] Write failing Angular tests that admins can submit username/password/role and list users.
- [ ] Run the focused tests; expect failures.
- [ ] Implement Bootstrap-based admin users UI with custom bold styling.
- [ ] Re-run focused tests; expect pass.

### Task 7: Configuration And Verification

**Files:**
- Modify: `tool-call-approval/tool-call-agent/.env.example`
- Modify: `tool-call-approval/docker-compose.yml`
- Modify: `tool-call-approval/k8s/tool-call-agent/configmap.yaml`
- Modify: `tool-call-approval/README.md`

- [ ] Add `REGISTRATION_DATABASE_URL`, `JWT_SECRET_KEY`, and `JWT_ACCESS_TOKEN_MINUTES` examples.
- [ ] Run backend test suites for changed services.
- [ ] Run `cd tool-call-approval/tool-call-ui && npm run build`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: This plan covers separate registration DB, seeded admin user, JWT login, admin-only user creation, per-user session ownership, frontend login/admin users UI, proxy forwarding, configuration, and verification.
- Placeholder scan: No `TBD` or unspecified behavior remains; each task names exact files and verification commands.
- Type consistency: Backend uses `role` values `admin` and `user`; frontend uses the same role strings; session ownership maps by `session_id`.
