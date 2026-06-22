from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.user import User
from app.security.passwords import PasswordHasher
from app.security.tokens import TokenService


class AuthRepository(Protocol):
    def get_user_by_username(self, username: str) -> tuple[User, str] | None: ...
    def get_user_by_id(self, user_id: str) -> User | None: ...


@dataclass(frozen=True)
class AuthResult:
    access_token: str
    token_type: str
    user: User


class AuthService:
    def __init__(
        self,
        repository: AuthRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._token_service = token_service

    def login(self, username: str, password: str) -> AuthResult:
        record = self._repository.get_user_by_username(username)
        if record is None:
            raise PermissionError("Invalid username or password")
        user, password_hash = record
        if not user.is_active or not self._password_hasher.verify_password(password, password_hash):
            raise PermissionError("Invalid username or password")
        return AuthResult(
            access_token=self._token_service.create_access_token(user),
            token_type="bearer",
            user=user,
        )

    def get_current_user(self, token: str) -> User:
        claims = self._token_service.verify_access_token(token)
        user = self._repository.get_user_by_id(claims.user_id)
        if user is None or not user.is_active:
            raise PermissionError("Invalid token")
        return user
