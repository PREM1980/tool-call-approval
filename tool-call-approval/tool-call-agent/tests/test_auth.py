from __future__ import annotations

import pytest

from app.domain.user import User
from app.security.passwords import PasswordHasher
from app.security.tokens import TokenService
from app.services.auth_service import AuthService
from app.services.session_ownership_service import SessionOwnershipService
from app.services.user_service import UserService


class FakeRegistrationRepository:
    def __init__(self) -> None:
        self.users_by_id: dict[str, User] = {}
        self.passwords_by_username: dict[str, str] = {}
        self.owned_sessions: dict[str, list[str]] = {}

    def add_user(self, user: User, password_hash: str) -> None:
        self.users_by_id[user.id] = user
        self.passwords_by_username[user.username] = password_hash

    def get_user_by_username(self, username: str) -> tuple[User, str] | None:
        for user in self.users_by_id.values():
            if user.username == username:
                return user, self.passwords_by_username[username]
        return None

    def get_user_by_id(self, user_id: str) -> User | None:
        return self.users_by_id.get(user_id)

    def create_user(self, username: str, password_hash: str, role: str) -> User:
        if username in self.passwords_by_username:
            raise ValueError("Username already exists")
        user = User(id=f"user-{len(self.users_by_id) + 1}", username=username, role=role)
        self.add_user(user, password_hash)
        return user

    def list_users(self) -> list[User]:
        return list(self.users_by_id.values())

    def record_session_owner(self, user_id: str, session_id: str) -> None:
        self.owned_sessions.setdefault(user_id, []).append(session_id)

    def user_owns_session(self, user_id: str, session_id: str) -> bool:
        return session_id in self.owned_sessions.get(user_id, [])

    def get_session_ids_for_user(self, user_id: str) -> list[str]:
        return self.owned_sessions.get(user_id, [])


def test_password_hasher_verifies_matching_password_and_rejects_wrong_password():
    hasher = PasswordHasher()

    password_hash = hasher.hash_password("admin")

    assert password_hash != "admin"
    assert hasher.verify_password("admin", password_hash) is True
    assert hasher.verify_password("wrong", password_hash) is False


def test_token_service_round_trips_user_claims():
    user = User(id="user-1", username="admin", role="admin")
    token_service = TokenService(secret_key="test-secret", access_token_minutes=60)

    token = token_service.create_access_token(user)
    claims = token_service.verify_access_token(token)

    assert claims.user_id == "user-1"
    assert claims.username == "admin"
    assert claims.role == "admin"


def test_token_service_rejects_tampered_token():
    user = User(id="user-1", username="admin", role="admin")
    token_service = TokenService(secret_key="test-secret", access_token_minutes=60)
    token = token_service.create_access_token(user)

    with pytest.raises(ValueError, match="Invalid token"):
        token_service.verify_access_token(f"{token}tampered")


def test_auth_service_login_returns_access_token_for_valid_credentials():
    repo = FakeRegistrationRepository()
    hasher = PasswordHasher()
    repo.add_user(
        User(id="admin-id", username="admin", role="admin"),
        hasher.hash_password("admin"),
    )
    token_service = TokenService(secret_key="test-secret", access_token_minutes=60)
    service = AuthService(repo, hasher, token_service)

    result = service.login("admin", "admin")

    assert result.token_type == "bearer"
    assert result.user.username == "admin"
    assert result.user.role == "admin"
    assert token_service.verify_access_token(result.access_token).user_id == "admin-id"


def test_auth_service_rejects_invalid_credentials():
    repo = FakeRegistrationRepository()
    hasher = PasswordHasher()
    repo.add_user(
        User(id="admin-id", username="admin", role="admin"),
        hasher.hash_password("admin"),
    )
    service = AuthService(repo, hasher, TokenService(secret_key="test-secret"))

    with pytest.raises(PermissionError, match="Invalid username or password"):
        service.login("admin", "wrong")


def test_user_service_creates_users_with_hashed_passwords_and_valid_roles():
    repo = FakeRegistrationRepository()
    hasher = PasswordHasher()
    service = UserService(repo, hasher)

    user = service.create_user("alice", "shared-password", "user")

    assert user.username == "alice"
    assert user.role == "user"
    stored = repo.get_user_by_username("alice")
    assert stored is not None
    _, password_hash = stored
    assert password_hash != "shared-password"
    assert hasher.verify_password("shared-password", password_hash) is True


def test_user_service_rejects_invalid_roles():
    service = UserService(FakeRegistrationRepository(), PasswordHasher())

    with pytest.raises(ValueError, match="Role must be admin or user"):
        service.create_user("alice", "password", "owner")


def test_session_ownership_service_records_and_checks_owned_sessions():
    repo = FakeRegistrationRepository()
    service = SessionOwnershipService(repo)
    user = User(id="user-1", username="alice", role="user")

    service.record_owner(user, "session-123")

    assert service.user_owns_session(user, "session-123") is True
    assert service.user_owns_session(user, "other-session") is False
    assert service.get_session_ids_for_user(user) == ["session-123"]
