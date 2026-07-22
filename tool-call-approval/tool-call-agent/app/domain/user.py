from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

UserRole = Literal["admin", "user"]


@dataclass(frozen=True)
class User:
    id: str
    username: str
    role: UserRole
    is_active: bool = True

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
