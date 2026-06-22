from __future__ import annotations

from typing import Protocol

from app.domain.user import User, UserRole
from app.security.passwords import PasswordHasher


class UserRepository(Protocol):
    def create_user(self, username: str, password_hash: str, role: UserRole) -> User: ...
    def list_users(self) -> list[User]: ...


class UserService:
    def __init__(self, repository: UserRepository, password_hasher: PasswordHasher) -> None:
        self._repository = repository
        self._password_hasher = password_hasher

    def create_user(self, username: str, password: str, role: str) -> User:
        normalized_username = username.strip()
        if not normalized_username:
            raise ValueError("Username is required")
        if not password:
            raise ValueError("Password is required")
        if role not in {"admin", "user"}:
            raise ValueError("Role must be admin or user")
        return self._repository.create_user(
            normalized_username,
            self._password_hasher.hash_password(password),
            role,
        )

    def list_users(self) -> list[User]:
        return self._repository.list_users()
