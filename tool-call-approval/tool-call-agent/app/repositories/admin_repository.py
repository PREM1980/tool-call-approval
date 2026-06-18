from __future__ import annotations

import json
import logging
import psycopg2
import psycopg2.extensions
import psycopg2.extras

from app.core.system_prompts import DEFAULT_INSTRUCTIONS, DEFAULT_SYSTEM_PROMPT_NAME, SEEDED_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


def _to_dsn(url: str) -> str:
    return url.replace("postgresql+psycopg2://", "postgresql://")


class AdminRepository:
    def __init__(self, url: str) -> None:
        self._url = _to_dsn(url)
        try:
            self._create_tables()
        except Exception as e:
            logger.warning("AdminRepository: could not initialize tables (%s) — admin features disabled", e)

    def _connect(self) -> psycopg2.extensions.connection:
        return psycopg2.connect(self._url)

    def _create_tables(self) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS admin_credentials (
                        id INTEGER PRIMARY KEY DEFAULT 1,
                        aws_access_key_id TEXT,
                        aws_secret_access_key TEXT,
                        aws_region TEXT NOT NULL DEFAULT 'us-east-1',
                        kubeconfig TEXT,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        CONSTRAINT single_row CHECK (id = 1)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS admin_mcp_servers (
                        position INTEGER PRIMARY KEY CHECK (position BETWEEN 1 AND 5),
                        name TEXT NOT NULL,
                        config JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS admin_skills (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        filename TEXT NOT NULL,
                        content TEXT NOT NULL,
                        uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS admin_personas (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name TEXT NOT NULL UNIQUE,
                        skill_ids JSONB NOT NULL DEFAULT '[]',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS admin_agent_instances (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        agent_name TEXT NOT NULL,
                        instance_name TEXT NOT NULL,
                        persona_id UUID,
                        mcp_positions JSONB NOT NULL DEFAULT '[]',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE (agent_name, instance_name)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS admin_system_prompts (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name TEXT NOT NULL UNIQUE,
                        instructions TEXT NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                self._seed_default_system_prompt(cur)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _seed_default_system_prompt(self, cur: psycopg2.extensions.cursor) -> None:
        for name, instructions in SEEDED_SYSTEM_PROMPTS:
            cur.execute(
                """
                INSERT INTO admin_system_prompts (name, instructions, is_active)
                VALUES (%s, %s, FALSE)
                ON CONFLICT (name) DO UPDATE SET
                    instructions = EXCLUDED.instructions,
                    updated_at   = NOW()
                """,
                (name, instructions),
            )
        cur.execute(
            """
            UPDATE admin_system_prompts
            SET is_active = TRUE, updated_at = NOW()
            WHERE name = %s
              AND is_active = FALSE
              AND NOT EXISTS (
                  SELECT 1 FROM admin_system_prompts WHERE is_active = TRUE
              )
            """,
            (DEFAULT_SYSTEM_PROMPT_NAME,),
        )

    # ── Credentials ────────────────────────────────────────────────────────

    def get_credentials(self) -> dict | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM admin_credentials WHERE id = 1")
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def upsert_credentials(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        aws_region: str,
        kubeconfig: str | None,
    ) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO admin_credentials
                        (id, aws_access_key_id, aws_secret_access_key, aws_region, kubeconfig, updated_at)
                    VALUES (1, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        aws_access_key_id     = EXCLUDED.aws_access_key_id,
                        aws_secret_access_key = EXCLUDED.aws_secret_access_key,
                        aws_region            = EXCLUDED.aws_region,
                        kubeconfig            = EXCLUDED.kubeconfig,
                        updated_at            = NOW()
                """, (aws_access_key_id, aws_secret_access_key, aws_region, kubeconfig))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── MCP Servers ────────────────────────────────────────────────────────

    def get_mcp_servers(self) -> list[dict]:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM admin_mcp_servers ORDER BY position")
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def upsert_mcp_server(self, position: int, name: str, config: dict) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO admin_mcp_servers (position, name, config, updated_at)
                    VALUES (%s, %s, %s::jsonb, NOW())
                    ON CONFLICT (position) DO UPDATE SET
                        name       = EXCLUDED.name,
                        config     = EXCLUDED.config,
                        updated_at = NOW()
                """, (position, name, json.dumps(config)))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_mcp_server(self, position: int) -> bool:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM admin_mcp_servers WHERE position = %s", (position,))
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Skills ─────────────────────────────────────────────────────────────

    def get_skills(self) -> list[dict]:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, filename, uploaded_at FROM admin_skills ORDER BY uploaded_at DESC"
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def save_skill(self, filename: str, content: str) -> str:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO admin_skills (filename, content) VALUES (%s, %s) RETURNING id",
                    (filename, content),
                )
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("INSERT INTO admin_skills returned no row")
                skill_id = str(row[0])
            conn.commit()
            return skill_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_skill(self, skill_id: str) -> bool:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM admin_skills WHERE id = %s::uuid", (skill_id,))
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Personas ───────────────────────────────────────────────────────────

    def get_personas(self) -> list[dict]:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM admin_personas ORDER BY created_at")
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def create_persona(self, name: str, skill_ids: list[str]) -> dict:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO admin_personas (name, skill_ids) VALUES (%s, %s::jsonb) RETURNING *",
                    (name, json.dumps(skill_ids)),
                )
                row = dict(cur.fetchone())
            conn.commit()
            return row
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_persona(self, persona_id: str, name: str, skill_ids: list[str]) -> dict | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    UPDATE admin_personas
                    SET name = %s, skill_ids = %s::jsonb, updated_at = NOW()
                    WHERE id = %s::uuid
                    RETURNING *
                """, (name, json.dumps(skill_ids), persona_id))
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_persona(self, persona_id: str) -> bool:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM admin_personas WHERE id = %s::uuid", (persona_id,))
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Agent Instances ────────────────────────────────────────────────────

    def get_agent_instances(self, agent_name: str) -> list[dict]:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM admin_agent_instances WHERE agent_name = %s ORDER BY created_at",
                    (agent_name,),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def create_agent_instance(
        self,
        agent_name: str,
        instance_name: str,
        persona_id: str | None,
        mcp_positions: list[int],
    ) -> dict:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO admin_agent_instances
                           (agent_name, instance_name, persona_id, mcp_positions)
                       VALUES (%s, %s, %s::uuid, %s::jsonb) RETURNING *""",
                    (agent_name, instance_name, persona_id, json.dumps(mcp_positions)),
                )
                row = dict(cur.fetchone())
            conn.commit()
            return row
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_agent_instance(
        self,
        instance_id: str,
        instance_name: str,
        persona_id: str | None,
        mcp_positions: list[int],
    ) -> dict | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """UPDATE admin_agent_instances
                       SET instance_name = %s,
                           persona_id    = %s::uuid,
                           mcp_positions = %s::jsonb,
                           updated_at    = NOW()
                       WHERE id = %s::uuid
                       RETURNING *""",
                    (instance_name, persona_id, json.dumps(mcp_positions), instance_id),
                )
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_all_agent_instances(self) -> list[dict]:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM admin_agent_instances ORDER BY agent_name, instance_name"
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_agent_instance(self, instance_id: str) -> dict | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM admin_agent_instances WHERE id = %s::uuid",
                    (instance_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def get_persona(self, persona_id: str) -> dict | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM admin_personas WHERE id = %s::uuid",
                    (persona_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def get_skill_content(self, skill_id: str) -> tuple[str, str] | None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT filename, content FROM admin_skills WHERE id = %s::uuid",
                    (skill_id,),
                )
                row = cur.fetchone()
                return (row[0], row[1]) if row else None
        finally:
            conn.close()

    def delete_agent_instance(self, instance_id: str) -> bool:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM admin_agent_instances WHERE id = %s::uuid", (instance_id,)
                )
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── System Prompts ─────────────────────────────────────────────────────

    def list_system_prompts(self) -> list[dict]:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM admin_system_prompts ORDER BY created_at")
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def create_system_prompt(self, name: str, instructions: str) -> dict:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO admin_system_prompts (name, instructions) VALUES (%s, %s) RETURNING *",
                    (name, instructions),
                )
                row = dict(cur.fetchone())
            conn.commit()
            return row
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_system_prompt(self, prompt_id: str, name: str, instructions: str) -> dict | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    UPDATE admin_system_prompts
                    SET name = %s, instructions = %s, updated_at = NOW()
                    WHERE id = %s::uuid
                    RETURNING *
                """, (name, instructions, prompt_id))
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_system_prompt(self, prompt_id: str) -> bool:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM admin_system_prompts WHERE id = %s::uuid", (prompt_id,))
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def activate_system_prompt(self, prompt_id: str) -> dict | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("UPDATE admin_system_prompts SET is_active = FALSE")
                cur.execute("""
                    UPDATE admin_system_prompts SET is_active = TRUE, updated_at = NOW()
                    WHERE id = %s::uuid RETURNING *
                """, (prompt_id,))
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_active_system_prompt(self) -> str | None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT instructions FROM admin_system_prompts WHERE is_active = TRUE LIMIT 1"
                )
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()

    def get_active_system_prompt_record(self) -> dict | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM admin_system_prompts WHERE is_active = TRUE LIMIT 1"
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def get_system_prompt(self, prompt_id: str) -> dict | None:
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM admin_system_prompts WHERE id = %s::uuid",
                    (prompt_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def get_system_prompt_instructions(self, prompt_id: str) -> str | None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT instructions FROM admin_system_prompts WHERE id = %s::uuid",
                    (prompt_id,),
                )
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()
