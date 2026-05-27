import logging
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
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT session_id,
                               created_at,
                               updated_at,
                               COALESCE(jsonb_array_length(runs), 0) AS turn_count
                        FROM ai.agno_sessions
                        ORDER BY updated_at DESC NULLS LAST
                    """)
                    return [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()
        except Exception as e:
            logger.warning("list_sessions failed: %s", e)
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

    def _is_reachable(self) -> bool:
        parsed = urlparse(self._url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            return False
