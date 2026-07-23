from __future__ import annotations

import json
import logging
import socket
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class IAgentStorage(ABC):
    @abstractmethod
    def list_sessions(self, session_ids: list[str] | None = None) -> list[dict]: ...
    @abstractmethod
    def create_session_record(self, session_id: str, instance_id: str | None, system_prompt_id: str | None, system_prompt_name: str | None, system_prompt_instructions_snapshot: str) -> None: ...
    @abstractmethod
    def append_session_message(self, session_id: str, role: str, content: str, instance_id: str | None = None, system_prompt_id: str | None = None, system_prompt_name: str | None = None, system_prompt_instructions_snapshot: str | None = None, message: dict[str, Any] | None = None) -> None: ...
    @abstractmethod
    def get_session_history(self, session_id: str) -> list[dict]: ...
    @abstractmethod
    def append_session_event(self, session_id: str, run_id: str | None, event_type: str,
                             payload: dict[str, Any] | None = None) -> dict: ...
    @abstractmethod
    def get_session_events(self, session_id: str, after_sequence: int = 0) -> list[dict]: ...
    @abstractmethod
    def save_report(self, report_id: str, session_id: str, s3_bucket: str, s3_key: str, title: str) -> None: ...
    @abstractmethod
    def delete_session(self, session_id: str) -> None: ...


class PostgresRepository(IAgentStorage):
    def __init__(self, url: str) -> None: self._url = url
    def list_sessions(self, session_ids: list[str] | None = None) -> list[dict]:
        if session_ids == [] or not self._is_reachable(): return []
        try:
            with psycopg2.connect(self._psycopg_url()) as conn:
                self._ensure_session_records_table(conn)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    clause, params = ("AND session_id = ANY(%s)", (session_ids,)) if session_ids is not None else ("", ())
                    cur.execute(f"""SELECT session_id, EXTRACT(EPOCH FROM created_at)::BIGINT AS created_at, EXTRACT(EPOCH FROM updated_at)::BIGINT AS updated_at, system_prompt_id, system_prompt_name, COALESCE((SELECT COUNT(*) FROM jsonb_array_elements(messages) message WHERE message->>'role'='user'), 0) AS turn_count, LEFT((SELECT message->>'content' FROM jsonb_array_elements(messages) message WHERE message->>'role'='user' LIMIT 1), 120) AS first_message FROM ai.session_records WHERE EXISTS (SELECT 1 FROM jsonb_array_elements(messages) message WHERE message->>'role'='user') {clause} ORDER BY updated_at DESC""", params)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as exc: logger.warning("list_sessions failed: %s", exc); return []
    def create_session_record(self, session_id: str, instance_id: str | None, system_prompt_id: str | None, system_prompt_name: str | None, system_prompt_instructions_snapshot: str) -> None:
        self._append(session_id, instance_id, system_prompt_id, system_prompt_name, system_prompt_instructions_snapshot, [])
    def append_session_message(self, session_id: str, role: str, content: str, instance_id: str | None = None, system_prompt_id: str | None = None, system_prompt_name: str | None = None, system_prompt_instructions_snapshot: str | None = None, message: dict[str, Any] | None = None) -> None:
        self._append(session_id, instance_id, system_prompt_id, system_prompt_name, system_prompt_instructions_snapshot, [self._normalize_message(role, content, message)])
    def _append(self, session_id: str, instance_id: str | None, prompt_id: str | None, prompt_name: str | None, snapshot: str | None, messages: list[dict]) -> None:
        if not self._is_reachable(): return
        try:
            with psycopg2.connect(self._psycopg_url()) as conn:
                self._ensure_session_records_table(conn)
                with conn.cursor() as cur: cur.execute("""INSERT INTO ai.session_records (session_id, instance_id, system_prompt_id, system_prompt_name, system_prompt_instructions_snapshot, messages) VALUES (%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (session_id) DO UPDATE SET instance_id=COALESCE(EXCLUDED.instance_id,ai.session_records.instance_id), system_prompt_id=COALESCE(EXCLUDED.system_prompt_id,ai.session_records.system_prompt_id), system_prompt_name=COALESCE(EXCLUDED.system_prompt_name,ai.session_records.system_prompt_name), system_prompt_instructions_snapshot=COALESCE(EXCLUDED.system_prompt_instructions_snapshot,ai.session_records.system_prompt_instructions_snapshot), messages=ai.session_records.messages || EXCLUDED.messages, updated_at=NOW()""", (session_id, instance_id, prompt_id, prompt_name, snapshot, json.dumps(messages)))
        except Exception as exc: logger.warning("session persistence failed: %s", exc)
    def get_session_history(self, session_id: str) -> list[dict]:
        if not self._is_reachable(): return []
        try:
            with psycopg2.connect(self._psycopg_url()) as conn:
                self._ensure_session_records_table(conn)
                with conn.cursor() as cur:
                    cur.execute("SELECT messages FROM ai.session_records WHERE session_id=%s", (session_id,)); row = cur.fetchone()
                    return [self._normalize_message(m.get("role", "user"), m.get("content") or "", m) for m in (row[0] if row else []) if isinstance(m, dict) and m.get("role") in {"user", "assistant"}]
        except Exception as exc: logger.warning("get_session_history failed: %s", exc); return []
    def append_session_event(self, session_id: str, run_id: str | None, event_type: str,
                             payload: dict[str, Any] | None = None) -> dict:
        """Append a durable, ordered debugging event and return its public form."""
        if not self._is_reachable():
            return {}
        try:
            with psycopg2.connect(self._psycopg_url()) as conn:
                self._ensure_session_events_table(conn)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """INSERT INTO ai.session_events (session_id, run_id, event_type, payload)
                           VALUES (%s, %s, %s, %s::jsonb)
                           RETURNING id AS sequence, run_id, event_type, payload, occurred_at""",
                        (session_id, run_id, event_type, json.dumps(payload or {})),
                    )
                    return self._event_dict(cur.fetchone())
        except Exception as exc:
            logger.warning("event persistence failed: %s", exc)
            return {}
    def get_session_events(self, session_id: str, after_sequence: int = 0) -> list[dict]:
        if not self._is_reachable():
            return []
        try:
            with psycopg2.connect(self._psycopg_url()) as conn:
                self._ensure_session_events_table(conn)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """SELECT id AS sequence, run_id, event_type, payload, occurred_at
                           FROM ai.session_events
                           WHERE session_id=%s AND id>%s ORDER BY id ASC""",
                        (session_id, max(after_sequence, 0)),
                    )
                    return [self._event_dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.warning("get_session_events failed: %s", exc)
            return []
    def save_report(self, report_id: str, session_id: str, s3_bucket: str, s3_key: str, title: str) -> None:
        if not self._is_reachable():
            return
        try:
            with psycopg2.connect(self._psycopg_url()) as conn:
                with conn.cursor() as cur:
                    cur.execute("""CREATE TABLE IF NOT EXISTS ai.reports (
                        id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                        s3_bucket TEXT NOT NULL, s3_key TEXT NOT NULL,
                        title TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )""")
                    cur.execute(
                        "INSERT INTO ai.reports (id, session_id, s3_bucket, s3_key, title) VALUES (%s, %s, %s, %s, %s)",
                        (report_id, session_id, s3_bucket, s3_key, title),
                    )
        except Exception as exc:
            logger.warning("save_report failed: %s", exc)
    def delete_session(self, session_id: str) -> None:
        if not self._is_reachable():
            raise RuntimeError("Session storage is unavailable")
        try:
            with psycopg2.connect(self._psycopg_url()) as conn:
                self._ensure_session_records_table(conn)
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM ai.session_records WHERE session_id=%s", (session_id,))
                    self._ensure_session_events_table(conn)
                    cur.execute("DELETE FROM ai.session_events WHERE session_id=%s", (session_id,))
                    cur.execute("SELECT to_regclass('ai.reports')")
                    if cur.fetchone()[0] is not None:
                        cur.execute("DELETE FROM ai.reports WHERE session_id=%s", (session_id,))
        except Exception as exc:
            logger.warning("delete_session failed: %s", exc)
            raise
    def _ensure_session_records_table(self, conn: Any) -> None:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS ai"); cur.execute("""CREATE TABLE IF NOT EXISTS ai.session_records (session_id TEXT PRIMARY KEY, instance_id TEXT, system_prompt_id TEXT, system_prompt_name TEXT, system_prompt_instructions_snapshot TEXT, messages JSONB NOT NULL DEFAULT '[]', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    def _ensure_session_events_table(self, conn: Any) -> None:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS ai")
            cur.execute("""CREATE TABLE IF NOT EXISTS ai.session_events (
                id BIGSERIAL PRIMARY KEY, session_id TEXT NOT NULL, run_id TEXT,
                event_type TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}',
                occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
            cur.execute("CREATE INDEX IF NOT EXISTS session_events_session_id_id_idx ON ai.session_events (session_id, id)")
    def _event_dict(self, row: Any) -> dict:
        if not row:
            return {}
        value = dict(row)
        occurred_at = value.get("occurred_at")
        if occurred_at:
            value["occurred_at"] = occurred_at.isoformat()
        return value
    def _normalize_message(self, role: str, content: str, message: dict[str, Any] | None = None) -> dict[str, Any]:
        source = message if isinstance(message, dict) else {}; normalized_role = source.get("role") if source.get("role") in {"user", "assistant"} else role
        result = {"role": normalized_role, "content": source.get("content", content), "data": self._data(source.get("data")), "timestamp": source.get("timestamp") or datetime.now(timezone.utc).isoformat(), "user": source.get("user") if "user" in source else None, "agent": source.get("agent") if "agent" in source else None}
        if normalized_role == "user": result.update({"platform_context": source.get("platform_context") or {"k8s_namespace": None, "duplo_base_url": None, "duplo_token": None, "tenant_name": None, "aws_credentials": None, "kubeconfig": None}, "ambient_context": source.get("ambient_context") or {"user_terminal_cmds": []}})
        return result
    def _data(self, value: Any) -> dict[str, list]:
        value = value if isinstance(value, dict) else {}; return {key: [dict(item) if isinstance(item, dict) else item for item in value.get(key, [])] for key in ("cmds", "executed_cmds", "url_configs", "user_file_uploads")}
    def _psycopg_url(self) -> str: return self._url.replace("postgresql+psycopg2://", "postgresql://")
    def _is_reachable(self) -> bool:
        parsed = urlparse(self._url)
        try:
            with socket.create_connection((parsed.hostname or "localhost", parsed.port or 5432), timeout=2): return True
        except OSError: return False
