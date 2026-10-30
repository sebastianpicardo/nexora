from __future__ import annotations

import secrets
from uuid import UUID

from psycopg import AsyncConnection

INVITATION_SELECT = """
    SELECT id, org_id, email, role, status, token, invited_by, expires_at, accepted_at, created_at
    FROM team_invitations
"""


async def expire_pending_invitations(conn: AsyncConnection, org_id: UUID | str) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE team_invitations
            SET status = 'expired'
            WHERE org_id = %s
              AND status = 'pending'
              AND expires_at <= now()
            """,
            (str(org_id),),
        )


async def list_invitations(conn: AsyncConnection, org_id: UUID | str) -> list[dict]:
    await expire_pending_invitations(conn, org_id)
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            {INVITATION_SELECT}
            WHERE org_id = %s AND status = 'pending'
            ORDER BY created_at DESC
            """,
            (str(org_id),),
        )
        return list(await cur.fetchall())


async def get_pending_by_email(conn: AsyncConnection, org_id: UUID | str, email: str) -> dict | None:
    await expire_pending_invitations(conn, org_id)
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            {INVITATION_SELECT}
            WHERE org_id = %s AND lower(email) = lower(%s) AND status = 'pending'
            """,
            (str(org_id), email.strip()),
        )
        return await cur.fetchone()


async def create_invitation(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    email: str,
    role: str,
    invited_by: UUID | str,
) -> dict:
    token = secrets.token_urlsafe(32)
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO team_invitations (org_id, email, role, token, invited_by)
            VALUES (%s, lower(%s), %s, %s, %s)
            RETURNING *
            """,
            (str(org_id), email.strip(), role, token, str(invited_by)),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def revoke_invitation(conn: AsyncConnection, org_id: UUID | str, invitation_id: UUID | str) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE team_invitations
            SET status = 'revoked'
            WHERE org_id = %s AND id = %s AND status = 'pending'
            RETURNING id
            """,
            (str(org_id), str(invitation_id)),
        )
        return await cur.fetchone() is not None


async def get_invitation_by_token(conn: AsyncConnection, token: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            {INVITATION_SELECT}
            WHERE token = %s
              AND status = 'pending'
              AND expires_at > now()
            """,
            (token,),
        )
        return await cur.fetchone()


async def mark_invitation_accepted(conn: AsyncConnection, invitation_id: UUID | str) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE team_invitations
            SET status = 'accepted', accepted_at = now()
            WHERE id = %s AND status = 'pending'
            """,
            (str(invitation_id),),
        )
