from __future__ import annotations

import json
from uuid import UUID

from psycopg import AsyncConnection


async def record_audit_event(
    conn: AsyncConnection,
    *,
    org_id: UUID | str | None,
    user_id: UUID | str | None,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO audit_events (
                org_id, user_id, action, entity_type, entity_id, metadata, ip_address
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                str(org_id) if org_id else None,
                str(user_id) if user_id else None,
                action,
                entity_type,
                entity_id,
                json.dumps(metadata or {}, default=str),
                ip_address,
            ),
        )


async def list_audit_events(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    action: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    filters = ["e.org_id = %s"]
    values: list = [str(org_id)]
    if action:
        filters.append("e.action = %s")
        values.append(action)

    where_clause = " AND ".join(filters)
    count_where = where_clause.replace("e.", "")
    offset = (page - 1) * page_size
    async with conn.cursor() as cur:
        await cur.execute(
            f"SELECT count(*) AS total FROM audit_events WHERE {count_where}",
            values,
        )
        count_row = await cur.fetchone()
        total = int(count_row["total"]) if count_row else 0

        await cur.execute(
            f"""
            SELECT e.id, e.org_id, e.user_id, u.name AS user_name, u.email AS user_email,
                   e.action, e.entity_type, e.entity_id, e.metadata, e.ip_address, e.created_at
            FROM audit_events e
            LEFT JOIN users u ON u.id = e.user_id
            WHERE {where_clause}
            ORDER BY e.created_at DESC
            LIMIT %s OFFSET %s
            """,
            [*values, page_size, offset],
        )
        rows = list(await cur.fetchall())
    return {"items": rows, "total": total, "page": page, "page_size": page_size}
