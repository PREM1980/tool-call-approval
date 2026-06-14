import logging
import json
import socket
from abc import ABC, abstractmethod
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

from agno.db.postgres.postgres import PostgresDb

logger = logging.getLogger(__name__)


class IAgentStorage(ABC):
    @abstractmethod
    def get_db(self) -> PostgresDb | None: ...

    @abstractmethod
    def list_sessions(self) -> list[dict]: ...

    @abstractmethod
    def create_session_record(
        self,
        session_id: str,
        instance_id: str | None,
        system_prompt_id: str | None,
        system_prompt_name: str | None,
        system_prompt_instructions_snapshot: str,
    ) -> None: ...

    @abstractmethod
    def append_session_message(
        self,
        session_id: str,
        role: str,
        content: str,
        instance_id: str | None = None,
        system_prompt_id: str | None = None,
        system_prompt_name: str | None = None,
        system_prompt_instructions_snapshot: str | None = None,
    ) -> None: ...

    @abstractmethod
    def get_session_history(self, session_id: str) -> list[dict]: ...

    @abstractmethod
    def save_report(
        self,
        report_id: str,
        session_id: str,
        s3_bucket: str,
        s3_key: str,
        title: str,
    ) -> None: ...


class PostgresRepository(IAgentStorage):
    def __init__(self, url: str) -> None:
        self._url = url
        self._db: PostgresDb | None = None

    def get_db(self) -> PostgresDb | None:
        if self._db is None:
            if not self._is_reachable():
                logger.warning("Postgres unreachable — session persistence disabled")
                return None
            self._db = PostgresDb(db_url=self._url)
        return self._db

    def list_sessions(self) -> list[dict]:
        if not self._is_reachable():
            return []
        url = self._url.replace("postgresql+psycopg2://", "postgresql://")
        try:
            conn = psycopg2.connect(url)
            try:
                self._ensure_session_records_table(conn)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT session_id,
                               EXTRACT(EPOCH FROM created_at)::BIGINT AS created_at,
                               EXTRACT(EPOCH FROM updated_at)::BIGINT AS updated_at,
                               system_prompt_id,
                               system_prompt_name,
                               COALESCE((
                                   SELECT COUNT(*)
                                   FROM jsonb_array_elements(messages) AS message
                                   WHERE message->>'role' = 'user'
                               ), 0) AS turn_count,
                               LEFT((
                                   SELECT message->>'content'
                                   FROM jsonb_array_elements(messages) AS message
                                   WHERE message->>'role' = 'user'
                                   LIMIT 1
                               ), 120) AS first_message
                        FROM ai.session_records
                        WHERE EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements(messages) AS message
                            WHERE message->>'role' = 'user'
                        )
                        ORDER BY updated_at DESC
                    """)
                    return [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()
        except Exception as e:
            logger.warning("list_sessions failed: %s", e)
            return []

    def create_session_record(
        self,
        session_id: str,
        instance_id: str | None,
        system_prompt_id: str | None,
        system_prompt_name: str | None,
        system_prompt_instructions_snapshot: str,
    ) -> None:
        if not self._is_reachable():
            return
        url = self._url.replace("postgresql+psycopg2://", "postgresql://")
        try:
            conn = psycopg2.connect(url)
            try:
                self._ensure_session_records_table(conn)
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO ai.session_records (
                            session_id,
                            instance_id,
                            system_prompt_id,
                            system_prompt_name,
                            system_prompt_instructions_snapshot
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (session_id) DO UPDATE SET
                            instance_id = EXCLUDED.instance_id,
                            system_prompt_id = EXCLUDED.system_prompt_id,
                            system_prompt_name = EXCLUDED.system_prompt_name,
                            system_prompt_instructions_snapshot = EXCLUDED.system_prompt_instructions_snapshot,
                            updated_at = NOW()
                    """, (
                        session_id,
                        instance_id,
                        system_prompt_id,
                        system_prompt_name,
                        system_prompt_instructions_snapshot,
                    ))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        except Exception as e:
            logger.warning("create_session_record failed: %s", e)

    def append_session_message(
        self,
        session_id: str,
        role: str,
        content: str,
        instance_id: str | None = None,
        system_prompt_id: str | None = None,
        system_prompt_name: str | None = None,
        system_prompt_instructions_snapshot: str | None = None,
    ) -> None:
        if not self._is_reachable():
            return
        url = self._url.replace("postgresql+psycopg2://", "postgresql://")
        message = [{"role": role, "content": content}]
        try:
            conn = psycopg2.connect(url)
            try:
                self._ensure_session_records_table(conn)
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO ai.session_records (
                            session_id,
                            instance_id,
                            system_prompt_id,
                            system_prompt_name,
                            system_prompt_instructions_snapshot,
                            messages
                        )
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (session_id) DO UPDATE SET
                            instance_id = COALESCE(EXCLUDED.instance_id, ai.session_records.instance_id),
                            system_prompt_id = COALESCE(EXCLUDED.system_prompt_id, ai.session_records.system_prompt_id),
                            system_prompt_name = COALESCE(EXCLUDED.system_prompt_name, ai.session_records.system_prompt_name),
                            system_prompt_instructions_snapshot = COALESCE(
                                EXCLUDED.system_prompt_instructions_snapshot,
                                ai.session_records.system_prompt_instructions_snapshot
                            ),
                            messages = ai.session_records.messages || EXCLUDED.messages,
                            updated_at = NOW()
                    """, (
                        session_id,
                        instance_id,
                        system_prompt_id,
                        system_prompt_name,
                        system_prompt_instructions_snapshot,
                        json.dumps(message),
                    ))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        except Exception as e:
            logger.warning("append_session_message failed: %s", e)

    def get_session_history(self, session_id: str) -> list[dict]:
        if not self._is_reachable():
            return []
        url = self._url.replace("postgresql+psycopg2://", "postgresql://")
        try:
            conn = psycopg2.connect(url)
            try:
                self._ensure_session_records_table(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT messages FROM ai.session_records WHERE session_id = %s",
                        (session_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return []
                    return [
                        {
                            "role": message.get("role"),
                            "content": message.get("content") or "",
                        }
                        for message in row[0]
                        if message.get("role") in {"user", "assistant"}
                    ]
            finally:
                conn.close()
        except Exception as e:
            logger.warning("get_session_history failed: %s", e)
            return []

    def save_report(
        self,
        report_id: str,
        session_id: str,
        s3_bucket: str,
        s3_key: str,
        title: str,
    ) -> None:
        url = self._url.replace("postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(url)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ai.reports (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        s3_bucket TEXT NOT NULL,
                        s3_key TEXT NOT NULL,
                        title TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute(
                    """
                    INSERT INTO ai.reports (id, session_id, s3_bucket, s3_key, title)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (report_id, session_id, s3_bucket, s3_key, title),
                )
            conn.commit()
        finally:
            conn.close()

    def _ensure_session_records_table(self, conn: psycopg2.extensions.connection) -> None:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS ai")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai.session_records (
                    session_id TEXT PRIMARY KEY,
                    instance_id TEXT,
                    system_prompt_id TEXT,
                    system_prompt_name TEXT,
                    system_prompt_instructions_snapshot TEXT,
                    messages JSONB NOT NULL DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

    def _is_reachable(self) -> bool:
        parsed = urlparse(self._url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            return False
