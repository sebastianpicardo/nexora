from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

EXCEPTION_SELECT = """
    SELECT
        e.*,
        d.original_filename AS document_filename,
        d.doc_type,
        s.name AS supplier_name,
        i.original_description AS item_description,
        i.sku AS item_sku,
        i.original_unit AS item_original_unit,
        i.base_unit AS item_base_unit,
        i.original_unit_price AS item_original_unit_price,
        i.normalized_unit_price AS item_normalized_unit_price,
        i.quantity AS item_quantity,
        i.currency AS item_currency
    FROM exceptions_log e
    JOIN documents_log d ON d.id = e.document_id
    LEFT JOIN suppliers s ON s.id = d.supplier_id
    LEFT JOIN items_history i ON i.id = e.item_id
"""


async def create_exception(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    document_id: UUID | str,
    item_id: UUID | str | None,
    type: str,
    severity: str,
    reason: str,
    evidence: dict,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO exceptions_log (org_id, document_id, item_id, type, severity, reason, evidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                str(org_id),
                str(document_id),
                str(item_id) if item_id else None,
                type,
                severity,
                reason,
                Jsonb(evidence),
            ),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def list_exceptions(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    status: str | None = None,
    type: str | None = None,
    severity: str | None = None,
    document_id: UUID | str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    filters = ["e.org_id = %s"]
    values: list = [str(org_id)]

    if status:
        filters.append("e.status = %s")
        values.append(status)
    if type:
        filters.append("e.type = %s")
        values.append(type)
    if severity:
        filters.append("e.severity = %s")
        values.append(severity)
    if document_id:
        filters.append("e.document_id = %s")
        values.append(str(document_id))

    where_clause = " AND ".join(filters)
    offset = (page - 1) * page_size

    async with conn.cursor() as cur:
        await cur.execute(
            f"SELECT count(*) AS total FROM exceptions_log e WHERE {where_clause}",
            values,
        )
        count_row = await cur.fetchone()
        total = int(count_row["total"]) if count_row else 0

        await cur.execute(
            f"""
            {EXCEPTION_SELECT}
            WHERE {where_clause}
            ORDER BY
                CASE e.severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    ELSE 4
                END,
                e.created_at DESC
            LIMIT %s OFFSET %s
            """,
            [*values, page_size, offset],
        )
        rows = list(await cur.fetchall())

    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def get_exception(conn: AsyncConnection, org_id: UUID | str, exception_id: UUID | str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            f"{EXCEPTION_SELECT} WHERE e.org_id = %s AND e.id = %s",
            (str(org_id), str(exception_id)),
        )
        return await cur.fetchone()


async def resolve_exception(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    exception_id: UUID | str,
    status: str,
    resolution: dict,
    notes: str | None,
    resolved_by: UUID | str,
) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE exceptions_log
            SET status = %s,
                resolution = %s,
                notes = %s,
                resolved_by = %s,
                resolved_at = now()
            WHERE org_id = %s AND id = %s AND status = 'pending'
            RETURNING *
            """,
            (
                status,
                Jsonb(resolution),
                notes,
                str(resolved_by),
                str(org_id),
                str(exception_id),
            ),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return await get_exception(conn, org_id, exception_id)


async def count_open(conn: AsyncConnection, org_id: UUID | str) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) AS total FROM exceptions_log WHERE org_id = %s AND status = 'pending'",
            (str(org_id),),
        )
        row = await cur.fetchone()
        return int(row["total"]) if row else 0
