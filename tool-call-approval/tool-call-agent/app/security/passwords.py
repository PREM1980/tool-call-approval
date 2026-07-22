from __future__ import annotations

import base64
import hashlib
import hmac
import os


class PasswordHasher:
    def __init__(self, iterations: int = 260_000) -> None:
        self._iterations = iterations

    def hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        digest = self._derive(password, salt, self._iterations)
        return "$".join(
            [
                "pbkdf2_sha256",
                str(self._iterations),
                self._encode(salt),
                self._encode(digest),
            ]
        )

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            algorithm, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            iterations = int(iterations_text)
            salt = self._decode(salt_text)
            expected = self._decode(digest_text)
        except (ValueError, TypeError):
            return False
        actual = self._derive(password, salt, iterations)
        return hmac.compare_digest(actual, expected)

    def _derive(self, password: str, salt: bytes, iterations: int) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)

    def _encode(self, value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _decode(self, value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(f"{value}{padding}")
