from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection

DEMO_CATALOG = [
    {
        "sku": "DEMO-TORN-006",
        "name": "Tornillo acero inoxidable 6mm",
        "description": "Producto de prueba para comparar costos y márgenes.",
        "unit": "unidad",
        "cost_price": 120,
        "sale_price": 180,
        "category": "Tornillería",
        "supplier_name": "Ferretería del Norte",
    },
    {
        "sku": "DEMO-PINT-001",
        "name": "Pintura esmalte blanco 1 galón",
        "description": "Producto de prueba para comparar costos y márgenes.",
        "unit": "galón",
        "cost_price": 7900,
        "sale_price": 10900,
        "category": "Pintura",
        "supplier_name": "Color y Decoración",
    },
    {
        "sku": "DEMO-TUB-012",
        "name": "Tubería PVC 1/2 pulgada",
        "description": "Producto de prueba para comparar costos y márgenes.",
        "unit": "metro",
        "cost_price": 1350,
        "sale_price": 1890,
        "category": "Fontanería",
        "supplier_name": "Tuberías Chile",
    },
    {
        "sku": "DEMO-CABLE-025",
        "name": "Cable eléctrico 2.5mm",
        "description": "Producto de prueba para comparar costos y márgenes.",
        "unit": "metro",
        "cost_price": 580,
        "sale_price": 850,
        "category": "Eléctrica",
        "supplier_name": "Voltaje y Cable",
    },
    {
        "sku": "DEMO-CINTA-5M",
        "name": "Cinta métrica 5m",
        "description": "Producto de prueba para comparar costos y márgenes.",
        "unit": "unidad",
        "cost_price": 3900,
        "sale_price": 5900,
        "category": "Ferretería general",
        "supplier_name": "Herramientas SA",
    },
    {
        "sku": "DEMO-LLAVE-8",
        "name": "Llave inglesa 8 pulgadas",
        "description": "Producto de prueba para comparar costos y márgenes.",
        "unit": "unidad",
        "cost_price": 5900,
        "sale_price": 8900,
        "category": "Ferretería general",
        "supplier_name": "Herramientas SA",
    },
    {
        "sku": "DEMO-TALADRO-650",
        "name": "Taladro percutor 650W",
        "description": "Producto de demostración con margen bajo para la auditoría express.",
        "unit": "unidad",
        "cost_price": 12000,
        "sale_price": 10900,
        "category": "Herramientas eléctricas",
        "supplier_name": "Herramientas SA",
    },
    {
        "sku": "DEMO-SIERRA-7",
        "name": "Sierra circular 7 1/4",
        "description": "Producto de demostración con margen delgado para la auditoría express.",
        "unit": "unidad",
        "cost_price": 10000,
        "sale_price": 10400,
        "category": "Herramientas eléctricas",
        "supplier_name": "Ferretería del Norte",
    },
]


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


async def import_from_approved_items(
    conn: AsyncConnection,
    org_id: UUID | str,
) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (btrim(i.sku))
                    btrim(i.sku) AS sku,
                    COALESCE(NULLIF(i.normalized_description, ''), i.original_description)
                        AS name,
                    i.original_description AS description,
                    COALESCE(NULLIF(i.base_unit, ''), 'unidad') AS unit,
                    i.normalized_unit_price AS cost_price,
                    s.name AS supplier_name
                FROM items_history i
                LEFT JOIN suppliers s ON s.id = i.supplier_id
                WHERE i.org_id = %s
                  AND i.review_status IN ('auto_approved', 'approved')
                  AND i.sku IS NOT NULL
                  AND btrim(i.sku) <> ''
                  AND i.normalized_unit_price IS NOT NULL
                  AND i.normalized_unit_price > 0
                ORDER BY btrim(i.sku), i.price_date DESC, i.created_at DESC
            )
            INSERT INTO price_catalog (
                org_id, sku, name, description, unit, cost_price, sale_price,
                category, supplier_name
            )
            SELECT %s, sku, name, description, unit, cost_price, 0, NULL, supplier_name
            FROM latest
            ON CONFLICT (org_id, sku) DO UPDATE SET
                cost_price = EXCLUDED.cost_price,
                supplier_name = COALESCE(EXCLUDED.supplier_name, price_catalog.supplier_name),
                updated_at = now()
            RETURNING sku
            """,
            (str(org_id), str(org_id)),
        )
        rows = await cur.fetchall()
    return len(rows)


async def seed_demo_catalog(
    conn: AsyncConnection,
    org_id: UUID | str,
) -> int:
    inserted = 0
    async with conn.cursor() as cur:
        for item in DEMO_CATALOG:
            await cur.execute(
                """
                INSERT INTO price_catalog (
                    org_id, sku, name, description, unit, cost_price, sale_price,
                    category, supplier_name
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (org_id, sku) DO NOTHING
                """,
                (
                    str(org_id),
                    item["sku"],
                    item["name"],
                    item["description"],
                    item["unit"],
                    item["cost_price"],
                    item["sale_price"],
                    item["category"],
                    item["supplier_name"],
                ),
            )
            inserted += max(cur.rowcount, 0)
    return inserted


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
