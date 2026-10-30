from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection

from src.parsers.normalization.descriptions import normalize_supplier_name


async def list_suppliers(conn: AsyncConnection, org_id: UUID | str, search: str | None = None) -> list[dict]:
    filters = ["org_id = %s"]
    values: list = [str(org_id)]
    if search:
        filters.append("(name ILIKE %s OR normalized_name ILIKE %s)")
        like = f"%{search.strip()}%"
        values.extend([like, like])

    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT id, name, normalized_name, tax_id, email, created_at, updated_at
            FROM suppliers
            WHERE {" AND ".join(filters)}
            ORDER BY name ASC
            """,
            values,
        )
        return list(await cur.fetchall())


async def get_supplier(conn: AsyncConnection, org_id: UUID | str, supplier_id: UUID | str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM suppliers WHERE org_id = %s AND id = %s",
            (str(org_id), str(supplier_id)),
        )
        return await cur.fetchone()


async def get_or_create_supplier(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    name: str,
    tax_id: str | None = None,
    email: str | None = None,
) -> dict:
    clean_name = " ".join((name or "").split()) or "Proveedor sin nombre"
    normalized = normalize_supplier_name(clean_name)

    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO suppliers (org_id, name, normalized_name, tax_id, email)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (org_id, normalized_name)
            DO UPDATE SET
                name = EXCLUDED.name,
                tax_id = COALESCE(EXCLUDED.tax_id, suppliers.tax_id),
                email = COALESCE(EXCLUDED.email, suppliers.email)
            RETURNING *
            """,
            (str(org_id), clean_name, normalized, tax_id, email),
        )
        row = await cur.fetchone()
        assert row is not None
        return row
