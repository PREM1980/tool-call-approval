# User Registration And Session Isolation Design

## Goal

Add application login, real admin-managed user registration, and per-user chat session visibility to the tool-call app.

The existing agent/session database must remain structurally untouched. A new PostgreSQL database named `registration` will own users, roles, password hashes, and the mapping between users and chat session IDs.

## Current State

The app has three main pieces:

- `tool-call-agent`: FastAPI backend that creates chat sessions, streams events, stores session history through Agno/Postgres, and exposes existing configuration/admin APIs.
- `tool-call-api`: FastAPI proxy and static UI host. It forwards `/api/*` calls to the agent backend.
- `tool-call-ui`: Angular frontend with chat, session history, and existing configuration/admin pages.

Session persistence currently uses `POSTGRES_URL` and writes under the existing `ai.session_records` table. Session list/history endpoints are global today because no authenticated user boundary exists.

## Decisions

- Use a separate PostgreSQL database named `registration`.
- Configure it with `REGISTRATION_DATABASE_URL`.
- Seed the first admin user as username `admin`, password `admin`, role `admin`.
- Use JWT bearer tokens for browser-to-API authentication.
- Store password hashes only; never return plaintext passwords.
- Store chat ownership in the `registration` database by mapping `user_id` to the existing chat `session_id`.
- Hide legacy unowned sessions after login is introduced.
- Keep the existing configuration/admin pages conceptually separate from the new real-admin user management page.
- Build the login and user management UI with Bootstrap plus custom SCSS for a polished, bold, non-stock look.

## Database Boundary

`POSTGRES_URL` remains the existing agent/session database. The implementation must not add columns, tables, constraints, or migrations to that database for this feature.

`REGISTRATION_DATABASE_URL` points to the new `registration` database, for example:

```text
postgresql+psycopg2://postgres:postgres@postgres:5432/registration
```

On startup, the registration repository should attempt to ensure the target database exists when using a PostgreSQL role with permission to create databases. If database creation is not permitted, startup should fail with a clear error telling the operator to create the `registration` database manually. After connecting to `registration`, the repository creates its own tables there.

## Registration Schema

Create the following tables in the `registration` database:

```sql
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_chat_sessions (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, session_id)
);
```

If `gen_random_uuid()` is unavailable, the repository should enable `pgcrypto` in `registration` or generate UUIDs in Python. This extension must not be created in the existing agent/session database.

## Backend Architecture

Add a focused auth/user domain to `tool-call-agent`:

- `RegistrationRepository`: owns all SQL for the `registration` database, table creation, admin seeding, users, and chat ownership rows.
- `PasswordHasher`: hashes and verifies passwords.
- `TokenService`: creates and verifies JWT access tokens with `sub`, `username`, `role`, and expiry.
- `AuthService`: handles login and current-user lookup.
- `UserService`: creates users and enforces role validation.
- `SessionOwnershipService`: records ownership when sessions are created and checks ownership before session operations.

These classes should be injected into routers instead of using global helper logic. Route dependencies should expose `current_user` and `require_admin` for consistent authorization.

## Backend API

Add auth endpoints:

```text
POST /auth/login
GET  /auth/me
```

`POST /auth/login` accepts username and password and returns:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": "<uuid>",
    "username": "admin",
    "role": "admin"
  }
}
```

Add real-admin user management endpoints:

```text
GET  /admin/users
POST /admin/users
```

Only role `admin` can call these endpoints. `POST /admin/users` accepts username, password, and role `admin` or `user`.

Protect session endpoints:

```text
GET  /sessions
POST /sessions
POST /sessions/{session_id}/chat
GET  /sessions/{session_id}/stream
GET  /sessions/{session_id}/history
GET  /sessions/{session_id}/reports/{report_id}
POST /sessions/{session_id}/approve
```

`POST /sessions` creates the normal chat session through `AgentService`, then records `current_user.id` and the generated `session_id` in `registration.user_chat_sessions`.

For reads and mutations on a session ID, the API checks ownership through `SessionOwnershipService` before loading the in-memory session or existing database history. If the current user does not own the session, return `404` so session existence is not leaked.

## How Agno Sessions Relate To Users

Agno sessions remain identified by their existing `session_id`. The Agno/session table does not need a user column.

The application links a user to an Agno session through the new database:

```text
registration.user_chat_sessions.user_id    -> registration.users.id
registration.user_chat_sessions.session_id -> existing Agno/chat session_id
```

When listing sessions, the API first loads the current user's owned session IDs from `registration`, then asks the existing repository for summaries for those IDs only. Legacy session rows without an ownership mapping are hidden.

## Repository Changes

Extend the existing session repository interface with owner-filtered read methods rather than changing the existing database schema:

- `list_sessions(session_ids: list[str] | None = None)`
- `get_session_history(session_id: str)`

When `session_ids` is an empty list, return no sessions. When it is populated, query `ai.session_records WHERE session_id = ANY(%s)` and preserve the current ordering by `updated_at DESC`.

This changes read filtering only. It does not write ownership into the existing database.

## JWT And Security

Use a new `JWT_SECRET_KEY` environment variable. Development may default to a clearly named local secret, but production/deployment docs should instruct operators to provide a strong secret.

Recommended token payload:

```json
{
  "sub": "<user-id>",
  "username": "admin",
  "role": "admin",
  "exp": 1782119735
}
```

Use an access token expiry such as eight hours. The Angular app stores the token and sends:

```text
Authorization: Bearer <token>
```

Password hashing should use a standard library already available or added to requirements, such as `passlib[bcrypt]`. If adding a dependency, update `requirements.txt` and keep tests deterministic.

## Frontend Design

Add an Angular auth flow:

- `/login`: public login page.
- Auth guard: redirects unauthenticated users to `/login`.
- Role guard: exposes the new real-admin user page only for `role === 'admin'`.
- Auth service: login, logout, token storage, current user state, and bearer-token attachment.
- HTTP interceptor: attaches JWT to API calls.
- Top bar: shows current username, logout, and a Users link only for real admins.
- User management page: create users with username, password, and role, and list existing users.

The chat and sessions views remain familiar but become authenticated. Their service calls should not need user IDs because the backend derives identity from the JWT.

## Visual Direction

Use Bootstrap forms, buttons, grid, and utility classes as the foundation, with custom SCSS for an exceptional interface:

- bold headings and strong font weights
- polished login layout
- clean user creation form
- readable user table
- confident primary actions
- responsive desktop and mobile layout
- no stock-looking default Bootstrap pages

The UI should feel like an admin-grade product console rather than a temporary internal form.

## Proxy/API Host Changes

`tool-call-api` should forward auth headers to the agent backend for protected routes. The proxy needs endpoints or generic forwarding for:

```text
/api/auth/*
/api/admin/users
/api/sessions*
```

The Angular dev proxy already forwards `/api`; the UI should continue using `/api` paths.

## Configuration

Update examples and deployment config with:

```text
REGISTRATION_DATABASE_URL=postgresql+psycopg2://localhost:5432/registration
JWT_SECRET_KEY=local-development-secret
JWT_ACCESS_TOKEN_MINUTES=480
```

For Docker Compose, set `REGISTRATION_DATABASE_URL` for `tool-calling-k8s-agent` to the same Postgres service but database `registration`. The app can attempt database creation on startup, or the compose setup can include an initialization path if startup creation is not reliable in the target environment.

For Kubernetes, add the same registration URL and JWT settings to the agent config/secret manifests without changing `POSTGRES_URL`.

## Error Handling

- Duplicate username: `409 Conflict`.
- Invalid login credentials: `401 Unauthorized`.
- Missing or invalid token: `401 Unauthorized`.
- Non-admin user management attempt: `403 Forbidden`.
- Access to another user's session: `404 Not Found`.
- Missing `registration` database and no permission to create it: fail startup clearly.
- Registration DB unavailable during requests: return a clear server error and do not allow unauthenticated access.
- Password hashes and JWT secrets must never be returned from APIs.

## Testing

Backend tests:

- `admin/admin` is seeded in the `registration` database.
- Password hashing verifies correct passwords and rejects incorrect ones.
- Login returns a JWT and current user data.
- `GET /auth/me` resolves the current user from a JWT.
- Admin can create users with role `admin` or `user`.
- Non-admin cannot create users.
- Duplicate usernames return `409`.
- Authenticated session creation records ownership.
- Session list returns only owned sessions.
- Session history for another user's session returns `404`.
- Legacy unowned sessions are hidden.

Frontend tests:

- Login form calls auth service and navigates into the app.
- Auth guard blocks unauthenticated routes.
- Role guard blocks non-admin users from the real-admin users page.
- Users page submits username, password, and role.
- Top bar shows user identity and logout state.

Verification should include focused backend tests, Angular tests for the new auth pieces, and a UI build.

## Out Of Scope

- Password reset or self-service password change.
- Refresh tokens.
- Deleting or disabling users, unless needed as a small admin-table convenience.
- Migrating legacy unowned sessions.
- Modifying the existing Agno/session database schema.
- Reworking the existing configuration/admin pages beyond adding auth-aware navigation.
