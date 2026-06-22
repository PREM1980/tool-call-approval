from __future__ import annotations

import logging
import uuid
from urllib.parse import urlparse, urlunparse

import psycopg2
import psycopg2.extensions
import psycopg2.extras
from psycopg2 import sql

from app.domain.user import User, UserRole
from app.security.passwords import PasswordHasher

logger = logging.getLogger(__name__)


def _to_dsn(url: str) -> str:
    return url.replace("postgresql+psycopg2://", "postgresql://")


class RegistrationRepository:
    def __init__(self, url: str, seed_admin: bool = True) -> None:
        self._url = _to_dsn(url)
        self._disabled_error: Exception | None = None
        try:
            self._ensure_database_exists()
            self._create_tables()
            if seed_admin:
                self.seed_admin_user("admin", "admin")
        except Exception as e:
            self._disabled_error = e
            logger.warning("RegistrationRepository: could not initialize registration DB (%s)", e)

    def _connect(self) -> psycopg2.extensions.connection:
        if self._disabled_error is not None:
            raise RuntimeError("Registration database is not available") from self._disabled_error
        return psycopg2.connect(self._url)

    def _ensure_database_exists(self) -> None:
        parsed = urlparse(self._url)
        database_name = parsed.path.lstrip("/") or "registration"
        try:
            conn = psycopg2.connect(self._url)
            conn.close()
            return
        except psycopg2.OperationalError as e:
            if database_name != "registration" or "does not exist" not in str(e):
                raise

        maintenance_url = urlunparse(parsed._replace(path="/postgres"))
        conn = psycopg2.connect(maintenance_url)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (database_name,),
                )
                if cur.fetchone() is None:
                    cur.execute(
                        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)),
                    )
        finally:
            conn.close()

    def _create_tables(self) -> None:
        conn = psycopg2.connect(self._url)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id UUID PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_chat_sessions (
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        session_id TEXT NOT NULL UNIQUE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (user_id, session_id)
                    )
                """)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def seed_admin_user(self, username: str, password: str) -> None:
        if self.get_user_by_username(username) is not None:
            return
        password_hash = PasswordHasher().hash_password(password)
        self.create_user(username, password_hash, "admin")

    def get_user_by_username(self, username: str) -> tuple[User, str] | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, username, password_hash, role, is_active
                    FROM users
                    WHERE username = %s
                    """,
                    (username,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return self._user_from_row(row), row["password_hash"]
        finally:
            conn.close()

    def get_user_by_id(self, user_id: str) -> User | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, username, role, is_active
                    FROM users
                    WHERE id = %s::uuid
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                return self._user_from_row(row) if row else None
        finally:
            conn.close()

    def create_user(self, username: str, password_hash: str, role: UserRole) -> User:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, username, password_hash, role)
                    VALUES (%s::uuid, %s, %s, %s)
                    RETURNING id, username, role, is_active
                    """,
                    (str(uuid.uuid4()), username, password_hash, role),
                )
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("INSERT INTO users returned no row")
            conn.commit()
            return self._user_from_row(row)
        except psycopg2.IntegrityError as e:
            conn.rollback()
            if "users_username_key" in str(e) or "unique" in str(e).lower():
                raise ValueError("Username already exists")
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_users(self) -> list[User]:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, username, role, is_active
                    FROM users
                    ORDER BY created_at ASC, username ASC
                    """
                )
                return [self._user_from_row(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def record_session_owner(self, user_id: str, session_id: str) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_chat_sessions (user_id, session_id)
                    VALUES (%s::uuid, %s)
                    ON CONFLICT (session_id) DO NOTHING
                    """,
                    (user_id, session_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def user_owns_session(self, user_id: str, session_id: str) -> bool:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM user_chat_sessions
                    WHERE user_id = %s::uuid
                      AND session_id = %s
                    """,
                    (user_id, session_id),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()

    def get_session_ids_for_user(self, user_id: str) -> list[str]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT session_id
                    FROM user_chat_sessions
                    WHERE user_id = %s::uuid
                    ORDER BY created_at DESC
                    """,
                    (user_id,),
                )
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def _user_from_row(self, row: dict) -> User:
        return User(
            id=str(row["id"]),
            username=row["username"],
            role=row["role"],
            is_active=bool(row["is_active"]),
        )
