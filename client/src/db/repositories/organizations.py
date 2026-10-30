from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection


async def get_organization(conn: AsyncConnection, org_id: UUID | str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute("SELECT * FROM organizations WHERE id = %s", (str(org_id),))
        return await cur.fetchone()


async def update_organization(conn: AsyncConnection, org_id: UUID | str, fields: dict) -> dict | None:
    allowed = {
        "name",
        "price_spike_threshold_pct",
        "min_confidence",
        "default_currency",
    }
    updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
    if not updates:
        return await get_organization(conn, org_id)

    assignments = ", ".join(f"{key} = %s" for key in updates)
    values = [*updates.values(), str(org_id)]
    async with conn.cursor() as cur:
        await cur.execute(
            f"UPDATE organizations SET {assignments} WHERE id = %s RETURNING *",
            values,
        )
        return await cur.fetchone()
