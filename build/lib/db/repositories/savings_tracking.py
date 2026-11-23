from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb


async def record_savings_tracking(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    opportunity_key: str,
    status: str = "identified",
    realized_amount: Decimal | float | int = 0,
    currency: str = "CLP",
    notes: str | None = None,
    title: str | None = None,
    sku: str | None = None,
    product: str | None = None,
    supplier_before: str | None = None,
    supplier_after: str | None = None,
    document_before_id: UUID | str | None = None,
    document_after_id: UUID | str | None = None,
    unit_price_before: Decimal | float | None = None,
    unit_price_after: Decimal | float | None = None,
    quantity: Decimal | float | None = None,
    evidence: dict | None = None,
) -> dict:
    status = status if status in {"identified", "contacted", "negotiated", "realized", "dismissed"} else "identified"
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'savings_tracking'
                  AND column_name = 'evidence'
            ) AS extended
            """
        )
        extended = bool((await cur.fetchone() or {}).get("extended"))
        if not extended:
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

        await cur.execute(
            """
            INSERT INTO savings_tracking (
                org_id, opportunity_key, status, realized_amount, currency, notes,
                title, sku, product, supplier_before, supplier_after,
                document_before_id, document_after_id, unit_price_before, unit_price_after,
                quantity, evidence, realized_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s = 'realized' THEN now() ELSE NULL END)
            ON CONFLICT (org_id, opportunity_key) DO UPDATE SET
                status = EXCLUDED.status,
                realized_amount = EXCLUDED.realized_amount,
                currency = EXCLUDED.currency,
                notes = COALESCE(EXCLUDED.notes, savings_tracking.notes),
                title = COALESCE(EXCLUDED.title, savings_tracking.title),
                sku = COALESCE(EXCLUDED.sku, savings_tracking.sku),
                product = COALESCE(EXCLUDED.product, savings_tracking.product),
                supplier_before = COALESCE(EXCLUDED.supplier_before, savings_tracking.supplier_before),
                supplier_after = COALESCE(EXCLUDED.supplier_after, savings_tracking.supplier_after),
                document_before_id = COALESCE(EXCLUDED.document_before_id, savings_tracking.document_before_id),
                document_after_id = COALESCE(EXCLUDED.document_after_id, savings_tracking.document_after_id),
                unit_price_before = COALESCE(EXCLUDED.unit_price_before, savings_tracking.unit_price_before),
                unit_price_after = COALESCE(EXCLUDED.unit_price_after, savings_tracking.unit_price_after),
                quantity = COALESCE(EXCLUDED.quantity, savings_tracking.quantity),
                evidence = COALESCE(EXCLUDED.evidence, savings_tracking.evidence),
                realized_at = CASE
                    WHEN EXCLUDED.status = 'realized' THEN COALESCE(savings_tracking.realized_at, now())
                    ELSE savings_tracking.realized_at
                END,
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
                title,
                sku,
                product,
                supplier_before,
                supplier_after,
                str(document_before_id) if document_before_id else None,
                str(document_after_id) if document_after_id else None,
                unit_price_before,
                unit_price_after,
                quantity,
                Jsonb(evidence or {}),
                status,
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


async def list_verified_savings(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    month: str | None = None,
) -> list[dict]:
    filters = ["org_id = %s", "status = 'realized'"]
    values: list = [str(org_id)]
    if month:
        filters.append("to_char(coalesce(realized_at, updated_at), 'YYYY-MM') = %s")
        values.append(month)
    where = " AND ".join(filters)
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'savings_tracking'
                  AND column_name = 'realized_at'
            ) AS extended
            """
        )
        has_realized_at = bool((await cur.fetchone() or {}).get("extended"))
        if has_realized_at:
            order_column = "coalesce(realized_at, updated_at)"
        else:
            order_column = "updated_at"
            if month:
                filters = ["org_id = %s", "status = 'realized'"]
                filters.append("to_char(updated_at, 'YYYY-MM') = %s")
                where = " AND ".join(filters)
        await cur.execute(
            f"""
            SELECT * FROM savings_tracking
            WHERE {where}
            ORDER BY {order_column} DESC, created_at DESC
            """,
            values,
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