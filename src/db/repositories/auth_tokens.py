from __future__ import annotations

from datetime import datetime
from uuid import UUID

from psycopg import AsyncConnection


async def create_auth_token(
    conn: AsyncConnection,
    *,
    user_id: UUID | str,
    token_type: str,
    token_hash: str,
    expires_at: datetime,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO auth_tokens (user_id, token_type, token_hash, expires_at)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (str(user_id), token_type, token_hash, expires_at),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def invalidate_auth_tokens(
    conn: AsyncConnection,
    *,
    user_id: UUID | str,
    token_type: str,
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE auth_tokens
            SET consumed_at = now()
            WHERE user_id = %s AND token_type = %s AND consumed_at IS NULL
            """,
            (str(user_id), token_type),
        )


async def get_auth_token(
    conn: AsyncConnection,
    *,
    token_hash: str,
    token_type: str,
) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT t.*, u.email, u.name, u.active
            FROM auth_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token_hash = %s
              AND t.token_type = %s
              AND t.consumed_at IS NULL
              AND t.expires_at > now()
            """,
            (token_hash, token_type),
        )
        return await cur.fetchone()


async def consume_auth_token(conn: AsyncConnection, token_id: UUID | str) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE auth_tokens SET consumed_at = now() WHERE id = %s AND consumed_at IS NULL",
            (str(token_id),),
        )
