from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection


async def list_price_catalog(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    active_only: bool = True,
    search: str | None = None,
) -> list[dict]:
    filters = ["org_id = %s"]
    values: list = [str(org_id)]
    if active_only:
        filters.append("active = TRUE")
    if search:
        filters.append("(sku ILIKE %s OR name ILIKE %s OR category ILIKE %s)")
        search_pattern = f"%{search}%"
        values.extend([search_pattern, search_pattern, search_pattern])
    where = " AND ".join(filters)
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT id, sku, name, description, unit, cost_price, sale_price,
                   margin_pct, category, supplier_name, active, created_at, updated_at
            FROM price_catalog
            WHERE {where}
            ORDER BY name ASC
            """,
            values,
        )
        return list(await cur.fetchall())


async def get_price_catalog_item(
    conn: AsyncConnection,
    org_id: UUID | str,
    item_id: UUID | str,
) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, sku, name, description, unit, cost_price, sale_price,
                   margin_pct, category, supplier_name, active, created_at, updated_at
            FROM price_catalog
            WHERE org_id = %s AND id = %s
            """,
            (str(org_id), str(item_id)),
        )
        return await cur.fetchone()


async def create_price_catalog_item(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    sku: str,
    name: str,
    description: str | None = None,
    unit: str = "unidad",
    cost_price: float = 0,
    sale_price: float = 0,
    category: str | None = None,
    supplier_name: str | None = None,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO price_catalog (
                org_id, sku, name, description, unit, cost_price, sale_price,
                category, supplier_name
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, sku, name, description, unit, cost_price, sale_price,
                      margin_pct, category, supplier_name, active, created_at, updated_at
            """,
            (
                str(org_id), sku, name, description, unit,
                cost_price, sale_price, category, supplier_name,
            ),
        )
        return await cur.fetchone()


async def update_price_catalog_item(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    item_id: UUID | str,
    fields: dict,
) -> dict | None:
    allowed = {"name", "description", "unit", "cost_price", "sale_price", "category", "supplier_name", "active"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return await get_price_catalog_item(conn, org_id, item_id)

    assignments = []
    values = []
    for key, value in updates.items():
        assignments.append(f"{key} = %s")
        values.append(value)
    values.extend([str(org_id), str(item_id)])
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            UPDATE price_catalog
            SET {', '.join(assignments)}, updated_at = now()
            WHERE org_id = %s AND id = %s
            RETURNING id, sku, name, description, unit, cost_price, sale_price,
                      margin_pct, category, supplier_name, active, created_at, updated_at
            """,
            values,
        )
        return await cur.fetchone()


async def delete_price_catalog_item(
    conn: AsyncConnection,
    org_id: UUID | str,
    item_id: UUID | str,
) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM price_catalog WHERE org_id = %s AND id = %s",
            (str(org_id), str(item_id)),
        )
        return cur.rowcount > 0
