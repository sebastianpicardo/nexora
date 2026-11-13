from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from psycopg import AsyncConnection


async def record_savings_tracking(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    opportunity_key: str,
    status: str = "identified",
    realized_amount: Decimal | float | int = 0,
    currency: str = "CLP",
    notes: str | None = None,
) -> dict:
    status = status if status in {"identified", "contacted", "negotiated", "realized", "dismissed"} else "identified"
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO savings_tracking (
                org_id, opportunity_key, status, realized_amount, currency, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (org_id, opportunity_key) DO UPDATE SET
                status = EXCLUDED.status,
                realized_amount = EXCLUDED.realized_amount,
                currency = EXCLUDED.currency,
                notes = COALESCE(EXCLUDED.notes, savings_tracking.notes),
                updated_at = now()
            RETURNING *
            """,
            (
                str(org_id),
                opportunity_key,
                status,
                max(float(realized_amount or 0), 0.0),
                (currency or "CLP").strip().upper(),
                notes,
            ),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def list_savings_tracking(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    filters = ["org_id = %s"]
    values: list = [str(org_id)]
    if status:
        filters.append("status = %s")
        values.append(status)
    where = " AND ".join(filters)
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT * FROM savings_tracking
            WHERE {where}
            ORDER BY updated_at DESC, created_at DESC
            LIMIT %s
            """,
            [*values, limit],
        )
        return list(await cur.fetchall())


async def summarize_savings_tracking(conn: AsyncConnection, org_id: UUID | str) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                count(*) AS total,
                count(*) FILTER (WHERE status = 'realized') AS realized,
                COALESCE(SUM(realized_amount) FILTER (WHERE status = 'realized'), 0) AS realized_amount,
                count(*) FILTER (WHERE status = 'identified') AS identified
            FROM savings_tracking
            WHERE org_id = %s
            """,
            (str(org_id),),
        )
        row = await cur.fetchone() or {}
    return {
        "total": int(row.get("total") or 0),
        "identified": int(row.get("identified") or 0),
        "realized": int(row.get("realized") or 0),
        "realized_amount": float(row.get("realized_amount") or 0),
    }