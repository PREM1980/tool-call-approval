import socket
from abc import ABC, abstractmethod
from urllib.parse import urlparse

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
