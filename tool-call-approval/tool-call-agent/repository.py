import socket
from abc import ABC, abstractmethod
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

from agno.db.postgres.postgres import PostgresDb


class IAgentStorage(ABC):
    @abstractmethod
    def get_db(self) -> PostgresDb: ...


class PostgresRepository(IAgentStorage):
    def __init__(self, url: str) -> None:
        self._url = url
        self._db: PostgresDb | None = None

    def get_db(self) -> PostgresDb:
        if self._db is None:
            self._check_reachable()
            self._db = PostgresDb(db_url=self._url)
        return self._db

    def list_sessions(self) -> list[dict]:
        url = self._url.replace("postgresql+psycopg2://", "postgresql://")
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

    def _check_reachable(self) -> None:
        parsed = urlparse(self._url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        try:
            with socket.create_connection((host, port), timeout=2):
                pass
        except OSError:
            raise RuntimeError(
                f"Postgres is not reachable at {host}:{port}. "
                "Please ensure it is running."
            )
