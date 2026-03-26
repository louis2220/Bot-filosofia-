"""
utils/db.py
Camada de acesso ao PostgreSQL via asyncpg.
Todas as tabelas são criadas automaticamente ao inicializar.
Uso: await Database.connect()  — chamar no setup_hook do bot.
"""

import asyncpg
import os
import logging
from typing import Any

log = logging.getLogger("filosofia.db")


class Database:
    pool: asyncpg.Pool | None = None

    @classmethod
    async def connect(cls):
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("Variável de ambiente DATABASE_URL não definida.")
        cls.pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        await cls._create_tables()
        log.info("[DB] PostgreSQL conectado e tabelas verificadas.")

    @classmethod
    async def _create_tables(cls):
        async with cls.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id     BIGINT NOT NULL,
                    namespace    TEXT   NOT NULL,
                    key          TEXT   NOT NULL,
                    value        JSONB  NOT NULL DEFAULT '{}',
                    PRIMARY KEY  (guild_id, namespace, key)
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS warns (
                    id           SERIAL PRIMARY KEY,
                    guild_id     BIGINT NOT NULL,
                    user_id      BIGINT NOT NULL,
                    moderator_id BIGINT NOT NULL,
                    reason       TEXT   NOT NULL,
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id           SERIAL PRIMARY KEY,
                    guild_id     BIGINT NOT NULL,
                    channel_id   BIGINT NOT NULL UNIQUE,
                    user_id      BIGINT NOT NULL,
                    category     TEXT   NOT NULL DEFAULT 'geral',
                    reason       TEXT,
                    attendant_id BIGINT,
                    status       TEXT   NOT NULL DEFAULT 'open',
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    closed_at    TIMESTAMPTZ
                );
            """)
            # Garante que colunas novas existam mesmo se a tabela foi criada pelo outro bot
            await conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'open';")
            await conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'geral';")
            await conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS reason TEXT;")
            await conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS attendant_id BIGINT;")
            await conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;")

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS security_log (
                    id           SERIAL PRIMARY KEY,
                    guild_id     BIGINT NOT NULL,
                    user_id      BIGINT NOT NULL,
                    action       TEXT   NOT NULL,
                    detail       TEXT,
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS warns_guild_user
                    ON warns (guild_id, user_id);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS tickets_guild
                    ON tickets (guild_id, status);
            """)

    # ── Config por guild ──────────────────────────────────────────────────────

    @classmethod
    async def guild_get(cls, guild_id: int, namespace: str, key: str) -> Any:
        row = await cls.pool.fetchrow(
            "SELECT value FROM guild_config WHERE guild_id=$1 AND namespace=$2 AND key=$3",
            guild_id, namespace, key,
        )
        return row["value"] if row else None

    @classmethod
    async def guild_set(cls, guild_id: int, namespace: str, key: str, value: Any):
        import json
        await cls.pool.execute("""
            INSERT INTO guild_config (guild_id, namespace, key, value)
            VALUES ($1, $2, $3, $4::jsonb)
            ON CONFLICT (guild_id, namespace, key)
            DO UPDATE SET value = EXCLUDED.value
        """, guild_id, namespace, key, json.dumps(value))

    @classmethod
    async def guild_delete(cls, guild_id: int, namespace: str, key: str):
        await cls.pool.execute(
            "DELETE FROM guild_config WHERE guild_id=$1 AND namespace=$2 AND key=$3",
            guild_id, namespace, key,
        )

    # ── Warns ─────────────────────────────────────────────────────────────────

    @classmethod
    async def add_warn(cls, guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
        row = await cls.pool.fetchrow("""
            INSERT INTO warns (guild_id, user_id, moderator_id, reason)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, guild_id, user_id, moderator_id, reason)
        count = await cls.pool.fetchval(
            "SELECT COUNT(*) FROM warns WHERE guild_id=$1 AND user_id=$2",
            guild_id, user_id,
        )
        return int(count)

    @classmethod
    async def get_warns(cls, guild_id: int, user_id: int) -> list[asyncpg.Record]:
        return await cls.pool.fetch(
            "SELECT * FROM warns WHERE guild_id=$1 AND user_id=$2 ORDER BY created_at DESC",
            guild_id, user_id,
        )

    @classmethod
    async def clear_warns(cls, guild_id: int, user_id: int):
        await cls.pool.execute(
            "DELETE FROM warns WHERE guild_id=$1 AND user_id=$2",
            guild_id, user_id,
        )

    @classmethod
    async def count_warns(cls, guild_id: int, user_id: int) -> int:
        return int(await cls.pool.fetchval(
            "SELECT COUNT(*) FROM warns WHERE guild_id=$1 AND user_id=$2",
            guild_id, user_id,
        ))

    # ── Tickets ───────────────────────────────────────────────────────────────

    @classmethod
    async def open_ticket(cls, guild_id: int, channel_id: int, user_id: int,
                           category: str, reason: str) -> asyncpg.Record:
        return await cls.pool.fetchrow("""
            INSERT INTO tickets (guild_id, channel_id, user_id, category, reason)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """, guild_id, channel_id, user_id, category, reason)

    @classmethod
    async def get_ticket(cls, channel_id: int) -> asyncpg.Record | None:
        return await cls.pool.fetchrow(
            "SELECT * FROM tickets WHERE channel_id=$1", channel_id)

    @classmethod
    async def get_open_ticket_by_user(cls, guild_id: int, user_id: int) -> asyncpg.Record | None:
        return await cls.pool.fetchrow(
            "SELECT * FROM tickets WHERE guild_id=$1 AND user_id=$2 AND status='open'",
            guild_id, user_id,
        )

    @classmethod
    async def list_open_tickets(cls, guild_id: int) -> list[asyncpg.Record]:
        return await cls.pool.fetch(
            "SELECT * FROM tickets WHERE guild_id=$1 AND status='open' ORDER BY created_at",
            guild_id,
        )

    @classmethod
    async def set_attendant(cls, channel_id: int, attendant_id: int):
        await cls.pool.execute(
            "UPDATE tickets SET attendant_id=$1 WHERE channel_id=$2",
            attendant_id, channel_id,
        )

    @classmethod
    async def close_ticket(cls, channel_id: int):
        await cls.pool.execute("""
            UPDATE tickets SET status='closed', closed_at=NOW()
            WHERE channel_id=$1
        """, channel_id)

    # ── Log de segurança ──────────────────────────────────────────────────────

    @classmethod
    async def log_security(cls, guild_id: int, user_id: int, action: str, detail: str = ""):
        await cls.pool.execute("""
            INSERT INTO security_log (guild_id, user_id, action, detail)
            VALUES ($1, $2, $3, $4)
        """, guild_id, user_id, action, detail)
