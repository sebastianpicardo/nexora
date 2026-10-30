from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg import AsyncConnection, sql
from psycopg.types.json import Jsonb

ITEM_SELECT = """
    SELECT
        i.*,
        s.name AS supplier_name,
        d.original_filename AS document_filename
    FROM items_history i
    LEFT JOIN suppliers s ON s.id = i.supplier_id
    JOIN documents_log d ON d.id = i.document_id
"""


async def insert_item(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    document_id: UUID | str,
    supplier_id: UUID | str | None,
    sku: str | None,
    original_description: str,
    normalized_description: str,
    original_unit: str | None,
    base_unit: str | None,
    unit_factor: Decimal,
    quantity: Decimal | None,
    package_size: Decimal | None,
    original_unit_price: Decimal | None,
    normalized_unit_price: Decimal | None,
    currency: str,
    price_date: date,
    confidence: float,
    review_status: str,
    source_page: int | None,
    source_text: str | None,
    metadata: dict | None = None,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO items_history (
                org_id, document_id, supplier_id, sku, original_description,
                normalized_description, original_unit, base_unit, unit_factor,
                quantity, package_size, original_unit_price, normalized_unit_price,
                currency, price_date, confidence, review_status, source_page,
                source_text, metadata
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s
            )
            RETURNING *
            """,
            (
                str(org_id),
                str(document_id),
                str(supplier_id) if supplier_id else None,
                sku,
                original_description,
                normalized_description,
                original_unit,
                base_unit,
                unit_factor,
                quantity,
                package_size,
                original_unit_price,
                normalized_unit_price,
                currency,
                price_date,
                confidence,
                review_status,
                source_page,
                source_text,
                Jsonb(metadata or {}),
            ),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def list_items(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    supplier_id: UUID | str | None = None,
    document_id: UUID | str | None = None,
    sku: str | None = None,
    review_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    filters = ["i.org_id = %s"]
    values: list = [str(org_id)]

    if supplier_id:
        filters.append("i.supplier_id = %s")
        values.append(str(supplier_id))
    if document_id:
        filters.append("i.document_id = %s")
        values.append(str(document_id))
    if sku:
        filters.append("i.sku = %s")
        values.append(sku)
    if review_status:
        filters.append("i.review_status = %s")
        values.append(review_status)
    if date_from:
        filters.append("i.price_date >= %s")
        values.append(date_from)
    if date_to:
        filters.append("i.price_date <= %s")
        values.append(date_to)
    if search:
        like = f"%{search.strip()}%"
        filters.append("(i.sku ILIKE %s OR i.original_description ILIKE %s OR i.normalized_description ILIKE %s)")
        values.extend([like, like, like])

    where_clause = " AND ".join(filters)
    offset = (page - 1) * page_size

    async with conn.cursor() as cur:
        await cur.execute(
            f"SELECT count(*) AS total FROM items_history i WHERE {where_clause}",
            values,
        )
        count_row = await cur.fetchone()
        total = int(count_row["total"]) if count_row else 0

        await cur.execute(
            f"""
            {ITEM_SELECT}
            WHERE {where_clause}
            ORDER BY i.price_date DESC, i.created_at DESC
            LIMIT %s OFFSET %s
            """,
            [*values, page_size, offset],
        )
        rows = list(await cur.fetchall())

    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def get_item(conn: AsyncConnection, org_id: UUID | str, item_id: UUID | str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            f"{ITEM_SELECT} WHERE i.org_id = %s AND i.id = %s",
            (str(org_id), str(item_id)),
        )
        return await cur.fetchone()


async def update_item_fields(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    item_id: UUID | str,
    fields: dict,
) -> dict | None:
    allowed = {
        "sku",
        "original_description",
        "normalized_description",
        "original_unit",
        "base_unit",
        "unit_factor",
        "quantity",
        "package_size",
        "original_unit_price",
        "normalized_unit_price",
        "currency",
        "price_date",
        "confidence",
        "review_status",
        "metadata",
    }
    updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
    if not updates:
        return await get_item(conn, org_id, item_id)

    assignments = []
    values = []
    for key, value in updates.items():
        assignments.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
        values.append(Jsonb(value) if key == "metadata" else value)

    query = sql.SQL("UPDATE items_history SET {} WHERE org_id = %s AND id = %s RETURNING *").format(
        sql.SQL(", ").join(assignments)
    )
    async with conn.cursor() as cur:
        await cur.execute(query, [*values, str(org_id), str(item_id)])
        row = await cur.fetchone()
    if row is None:
        return None
    return await get_item(conn, org_id, item_id)


async def get_price_history(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    supplier_id: UUID | str | None,
    sku: str | None,
    normalized_description: str,
    base_unit: str | None,
    currency: str,
    before_date: date,
    lookback_days: int,
    exclude_document_id: UUID | str,
    limit: int = 12,
) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, document_id, price_date, normalized_unit_price, currency, quantity,
                   original_description, normalized_description, sku
            FROM items_history
            WHERE org_id = %s::uuid
              AND review_status <> 'rejected'
              AND normalized_unit_price IS NOT NULL
              AND supplier_id IS NOT DISTINCT FROM %s::uuid
              AND base_unit IS NOT DISTINCT FROM %s::text
              AND currency = %s::text
              AND price_date >= (%s::date - (%s * interval '1 day'))
              AND price_date <= %s
              AND document_id <> %s::uuid
              AND (
                  (%s::text IS NOT NULL AND sku = %s::text)
                  OR normalized_description = %s::text
              )
            ORDER BY price_date DESC
            LIMIT %s
            """,
            (
                str(org_id),
                str(supplier_id) if supplier_id else None,
                base_unit,
                currency,
                before_date,
                lookback_days,
                before_date,
                str(exclude_document_id),
                sku,
                sku,
                normalized_description,
                limit,
            ),
        )
        return list(await cur.fetchall())
