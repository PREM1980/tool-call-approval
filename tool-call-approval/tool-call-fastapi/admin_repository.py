import json
import psycopg2
import psycopg2.extras


def _dsn(url: str) -> str:
    return url.replace("postgresql+psycopg2://", "postgresql://")


class AdminRepository:
    def __init__(self, url: str) -> None:
        self._dsn = _dsn(url)
        self._create_tables()

    def _connect(self):
        return psycopg2.connect(self._dsn)

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
            conn.commit()
        finally:
            conn.close()

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
                skill_id = str(cur.fetchone()[0])
            conn.commit()
            return skill_id
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
        finally:
            conn.close()
