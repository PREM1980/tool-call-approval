from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from app.domain.user import User, UserRole


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    username: str
    role: UserRole
    expires_at: int


class TokenService:
    def __init__(self, secret_key: str, access_token_minutes: int = 480) -> None:
        if not secret_key:
            raise ValueError("JWT secret key is required")
        self._secret_key = secret_key.encode("utf-8")
        self._access_token_seconds = access_token_minutes * 60

    def create_access_token(self, user: User) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role,
            "exp": int(time.time()) + self._access_token_seconds,
        }
        signing_input = ".".join(
            [
                self._encode_json(header),
                self._encode_json(payload),
            ]
        )
        signature = self._sign(signing_input)
        return f"{signing_input}.{signature}"

    def verify_access_token(self, token: str) -> TokenClaims:
        try:
            header_text, payload_text, signature = token.split(".", 2)
        except ValueError:
            raise ValueError("Invalid token")

        signing_input = f"{header_text}.{payload_text}"
        if not hmac.compare_digest(signature, self._sign(signing_input)):
            raise ValueError("Invalid token")

        payload = self._decode_json(payload_text)
        if payload.get("exp") is None or int(payload["exp"]) < int(time.time()):
            raise ValueError("Token expired")
        role = payload.get("role")
        if role not in {"admin", "user"}:
            raise ValueError("Invalid token")
        user_id = payload.get("sub")
        username = payload.get("username")
        if not isinstance(user_id, str) or not isinstance(username, str):
            raise ValueError("Invalid token")
        return TokenClaims(
            user_id=user_id,
            username=username,
            role=role,
            expires_at=int(payload["exp"]),
        )

    def _sign(self, signing_input: str) -> str:
        digest = hmac.new(self._secret_key, signing_input.encode("ascii"), hashlib.sha256).digest()
        return self._encode_bytes(digest)

    def _encode_json(self, value: dict[str, Any]) -> str:
        raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return self._encode_bytes(raw)

    def _decode_json(self, value: str) -> dict[str, Any]:
        try:
            decoded = self._decode_bytes(value)
            payload = json.loads(decoded)
        except (ValueError, json.JSONDecodeError):
            raise ValueError("Invalid token")
        if not isinstance(payload, dict):
            raise ValueError("Invalid token")
        return payload

    def _encode_bytes(self, value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _decode_bytes(self, value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(f"{value}{padding}")
