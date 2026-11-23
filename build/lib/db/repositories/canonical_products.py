from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection


async def get_or_create_canonical_product(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    name: str,
    normalized_name: str,
    base_unit: str | None = None,
    brand: str | None = None,
    presentation: str | None = None,
) -> dict:
    normalized_name = (normalized_name or name or "").strip().lower()
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT * FROM canonical_products
            WHERE org_id = %s AND normalized_name = %s
              AND COALESCE(base_unit, '') = COALESCE(%s, '')
            """,
            (str(org_id), normalized_name, base_unit),
        )
        row = await cur.fetchone()
        if row is not None:
            return row
        await cur.execute(
            """
            INSERT INTO canonical_products (
                org_id, name, normalized_name, base_unit, brand, presentation
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (str(org_id), name, normalized_name, base_unit, brand, presentation),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def resolve_product_alias(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    supplier_id: UUID | str | None,
    sku: str | None,
    alias_name: str,
    normalized_alias: str,
    base_unit: str | None = None,
    confidence: float = 1.0,
    confirmed: bool = True,
) -> tuple[UUID, float, bool]:
    normalized_alias = (normalized_alias or alias_name or "").strip().lower()
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT pa.canonical_product_id, pa.confidence, pa.confirmed
            FROM product_aliases pa
            WHERE pa.org_id = %s
              AND pa.normalized_alias = %s
              AND COALESCE(pa.supplier_id::text, '') = COALESCE(%s, '')
              AND COALESCE(pa.sku, '') = COALESCE(%s, '')
            ORDER BY pa.confirmed DESC, pa.confidence DESC
            LIMIT 1
            """,
            (str(org_id), normalized_alias, str(supplier_id) if supplier_id else None, sku),
        )
        row = await cur.fetchone()
        if row is not None:
            return row["canonical_product_id"], float(row["confidence"] or 0), bool(row["confirmed"])

        canonical = await get_or_create_canonical_product(
            conn,
            org_id=org_id,
            name=alias_name,
            normalized_name=normalized_alias,
            base_unit=base_unit,
        )
        await cur.execute(
            """
            INSERT INTO product_aliases (
                org_id, canonical_product_id, supplier_id, sku, alias_name,
                normalized_alias, confidence, confirmed
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(org_id),
                str(canonical["id"]),
                str(supplier_id) if supplier_id else None,
                sku,
                alias_name,
                normalized_alias,
                max(0.0, min(float(confidence), 1.0)),
                bool(confirmed),
            ),
        )
        return canonical["id"], float(confidence), bool(confirmed)


async def canonical_product_name(conn: AsyncConnection, canonical_product_id: UUID | str | None) -> str | None:
    if not canonical_product_id:
        return None
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT name FROM canonical_products WHERE id = %s",
            (str(canonical_product_id),),
        )
        row = await cur.fetchone()
    return row["name"] if row else None
