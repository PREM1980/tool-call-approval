from __future__ import annotations

from typing import Protocol

from app.domain.user import User


class SessionOwnershipRepository(Protocol):
    def record_session_owner(self, user_id: str, session_id: str) -> None: ...
    def user_owns_session(self, user_id: str, session_id: str) -> bool: ...
    def get_session_ids_for_user(self, user_id: str) -> list[str]: ...
    def get_all_session_ids(self) -> list[str]: ...
    def delete_session_owner(self, user_id: str, session_id: str) -> None: ...


class SessionOwnershipService:
    def __init__(self, repository: SessionOwnershipRepository) -> None:
        self._repository = repository

    def record_owner(self, user: User, session_id: str) -> None:
        self._repository.record_session_owner(user.id, session_id)

    def user_owns_session(self, user: User, session_id: str) -> bool:
        return self._repository.user_owns_session(user.id, session_id)

    def get_session_ids_for_user(self, user: User) -> list[str]:
        return self._repository.get_session_ids_for_user(user.id)

    def get_visible_session_ids(self, user: User) -> list[str]:
        if user.is_admin:
            return self._repository.get_all_session_ids()
        return self.get_session_ids_for_user(user)

    def can_view_session(self, user: User, session_id: str) -> bool:
        return user.is_admin or self.user_owns_session(user, session_id)

    def delete_owner(self, user: User, session_id: str) -> None:
        self._repository.delete_session_owner(user.id, session_id)

    def require_owner(self, user: User, session_id: str) -> None:
        if not self.user_owns_session(user, session_id):
            raise PermissionError("Session not found")
