from __future__ import annotations

import re
import secrets
import unicodedata
from uuid import UUID

from psycopg import AsyncConnection

USER_SELECT = """
    SELECT
        u.id,
        u.org_id,
        u.email,
        u.google_id,
        u.name,
        u.avatar_url,
        u.role,
        u.job_title,
        u.phone,
        u.timezone,
        u.notify_quota,
        u.notify_weekly,
        u.active,
        u.last_login_at,
        u.created_at,
        u.updated_at,
        o.name AS org_name,
        o.slug AS org_slug,
        o.price_spike_threshold_pct,
        o.min_confidence,
        o.default_currency
    FROM users u
    JOIN organizations o ON o.id = u.org_id
"""


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "empresa"


async def get_user_with_org(conn: AsyncConnection, user_id: UUID | str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(f"{USER_SELECT} WHERE u.id = %s", (str(user_id),))
        return await cur.fetchone()


async def get_user_by_email(conn: AsyncConnection, email: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(f"{USER_SELECT} WHERE lower(u.email) = lower(%s)", (email.strip(),))
        return await cur.fetchone()


async def get_user_by_google_id(conn: AsyncConnection, google_id: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(f"{USER_SELECT} WHERE u.google_id = %s", (google_id,))
        return await cur.fetchone()


async def _pending_invitation(conn: AsyncConnection, email: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT *
            FROM team_invitations
            WHERE lower(email) = lower(%s)
              AND status = 'pending'
              AND expires_at > now()
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (email.strip(),),
        )
        return await cur.fetchone()


async def create_user_with_org(
    conn: AsyncConnection,
    *,
    email: str,
    google_id: str,
    name: str,
    avatar_url: str,
    price_spike_threshold_pct: float | None = None,
    min_confidence: float | None = None,
    default_currency: str | None = None,
) -> dict:
    email = email.strip().lower()
    display_name = (name or email.split("@")[0]).strip() or "Usuario"

    invitation = await _pending_invitation(conn, email)
    if invitation is not None:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO users (
                    org_id, email, google_id, name, avatar_url, role, active, last_login_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, now())
                RETURNING id
                """,
                (
                    invitation["org_id"],
                    email,
                    google_id,
                    display_name,
                    avatar_url or "",
                    invitation["role"],
                ),
            )
            user_row = await cur.fetchone()
            assert user_row is not None
            user_id = user_row["id"]

            await cur.execute(
                """
                UPDATE team_invitations
                SET status = 'accepted', accepted_at = now()
                WHERE id = %s
                """,
                (invitation["id"],),
            )

        user = await get_user_with_org(conn, user_id)
        if user is None:
            raise RuntimeError("No se pudo recuperar el usuario invitado")
        return user

    org_name = display_name
    slug = f"{_slugify(org_name)}-{secrets.token_hex(3)}"

    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO organizations (
                name, slug, price_spike_threshold_pct, min_confidence, default_currency
            )
            VALUES (%s, %s, COALESCE(%s, 10.00), COALESCE(%s, 0.750), COALESCE(%s, 'CLP'))
            RETURNING id
            """,
            (org_name, slug, price_spike_threshold_pct, min_confidence, default_currency),
        )
        org_row = await cur.fetchone()
        assert org_row is not None
        org_id = org_row["id"]

        await cur.execute(
            """
            INSERT INTO subscriptions (org_id, plan_id, status)
            VALUES (%s, 'free', 'active')
            ON CONFLICT (org_id) DO NOTHING
            """,
            (org_id,),
        )

        await cur.execute(
            """
            INSERT INTO users (org_id, email, google_id, name, avatar_url, role, active, last_login_at)
            VALUES (%s, %s, %s, %s, %s, 'owner', TRUE, now())
            RETURNING id
            """,
            (org_id, email, google_id, display_name, avatar_url or ""),
        )
        user_row = await cur.fetchone()
        assert user_row is not None
        user_id = user_row["id"]

    user = await get_user_with_org(conn, user_id)
    if user is None:
        raise RuntimeError("No se pudo recuperar el usuario recién creado")
    return user


async def update_google_profile(
    conn: AsyncConnection,
    *,
    user_id: UUID | str,
    google_id: str,
    name: str,
    avatar_url: str,
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE users
            SET google_id = COALESCE(google_id, %s),
                name = CASE WHEN %s <> '' THEN %s ELSE name END,
                avatar_url = CASE WHEN %s <> '' THEN %s ELSE avatar_url END,
                last_login_at = now()
            WHERE id = %s
            """,
            (google_id, name, name, avatar_url, avatar_url, str(user_id)),
        )


async def touch_last_login(conn: AsyncConnection, user_id: UUID | str) -> None:
    async with conn.cursor() as cur:
        await cur.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (str(user_id),))


async def set_user_role(conn: AsyncConnection, user_id: UUID | str, role: str) -> None:
    async with conn.cursor() as cur:
        await cur.execute("UPDATE users SET role = %s WHERE id = %s", (role, str(user_id)))


async def list_users(conn: AsyncConnection, org_id: UUID | str) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, email, name, avatar_url, role, job_title, active, last_login_at, created_at
            FROM users
            WHERE org_id = %s
            ORDER BY created_at ASC
            """,
            (str(org_id),),
        )
        return list(await cur.fetchall())


async def get_member(conn: AsyncConnection, org_id: UUID | str, user_id: UUID | str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, org_id, email, name, avatar_url, role, job_title, active, last_login_at, created_at
            FROM users
            WHERE org_id = %s AND id = %s
            """,
            (str(org_id), str(user_id)),
        )
        return await cur.fetchone()


async def update_member(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    user_id: UUID | str,
    role: str | None,
    active: bool | None,
) -> dict | None:
    updates: list[str] = []
    values: list = []
    if role is not None:
        updates.append("role = %s")
        values.append(role)
    if active is not None:
        updates.append("active = %s")
        values.append(active)
    if not updates:
        return await get_member(conn, org_id, user_id)

    values.extend([str(org_id), str(user_id)])
    async with conn.cursor() as cur:
        await cur.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE org_id = %s AND id = %s RETURNING id",
            values,
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return await get_member(conn, org_id, user_id)


async def count_active_admins(conn: AsyncConnection, org_id: UUID | str) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT count(*) AS total
            FROM users
            WHERE org_id = %s
              AND active = TRUE
              AND role IN ('owner', 'admin', 'super_admin')
            """,
            (str(org_id),),
        )
        row = await cur.fetchone()
        return int(row["total"]) if row else 0


async def update_profile(conn: AsyncConnection, user_id: UUID | str, fields: dict) -> dict | None:
    allowed = {"name", "job_title", "phone", "timezone", "notify_quota", "notify_weekly"}
    updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
    if not updates:
        return await get_user_with_org(conn, user_id)

    assignments = ", ".join(f"{key} = %s" for key in updates)
    values = [*updates.values(), str(user_id)]
    async with conn.cursor() as cur:
        await cur.execute(
            f"UPDATE users SET {assignments} WHERE id = %s RETURNING id",
            values,
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return await get_user_with_org(conn, user_id)
