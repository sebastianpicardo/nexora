from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

DOCUMENT_SELECT = """
    SELECT
        d.id,
        d.org_id,
        d.supplier_id,
        s.name AS supplier_name,
        d.uploaded_by,
        u.name AS uploaded_by_name,
        d.original_filename,
        d.storage_path,
        d.file_hash,
        d.mime_type,
        d.file_size_bytes,
        d.doc_type,
        d.status,
        d.extraction_provider,
        d.extraction_model,
        d.error_message,
        d.metadata,
        d.created_at,
        d.updated_at,
        d.processing_started_at,
        d.processed_at
    FROM documents_log d
    LEFT JOIN suppliers s ON s.id = d.supplier_id
    LEFT JOIN users u ON u.id = d.uploaded_by
"""


async def create_document(
    conn: AsyncConnection,
    *,
    document_id: UUID | str,
    org_id: UUID | str,
    supplier_id: UUID | str | None,
    uploaded_by: UUID | str,
    original_filename: str,
    storage_path: str,
    file_hash: str,
    mime_type: str,
    file_size_bytes: int,
    doc_type: str,
    metadata: dict | None = None,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO documents_log (
                id, org_id, supplier_id, uploaded_by, original_filename, storage_path,
                file_hash, mime_type, file_size_bytes, doc_type, status, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'queued', %s)
            RETURNING *
            """,
            (
                str(document_id),
                str(org_id),
                str(supplier_id) if supplier_id else None,
                str(uploaded_by),
                original_filename,
                storage_path,
                file_hash,
                mime_type,
                file_size_bytes,
                doc_type,
                Jsonb(metadata or {}),
            ),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def get_document(conn: AsyncConnection, org_id: UUID | str, document_id: UUID | str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            f"{DOCUMENT_SELECT} WHERE d.org_id = %s AND d.id = %s",
            (str(org_id), str(document_id)),
        )
        return await cur.fetchone()


async def get_document_by_hash(conn: AsyncConnection, org_id: UUID | str, file_hash: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            f"{DOCUMENT_SELECT} WHERE d.org_id = %s AND d.file_hash = %s",
            (str(org_id), file_hash),
        )
        return await cur.fetchone()


async def list_documents(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    status: str | None = None,
    supplier_id: UUID | str | None = None,
    doc_type: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    filters = ["d.org_id = %s"]
    values: list = [str(org_id)]

    if status:
        filters.append("d.status = %s")
        values.append(status)
    if supplier_id:
        filters.append("d.supplier_id = %s")
        values.append(str(supplier_id))
    if doc_type:
        filters.append("d.doc_type = %s")
        values.append(doc_type)
    if search:
        filters.append("(d.original_filename ILIKE %s OR s.name ILIKE %s)")
        like = f"%{search.strip()}%"
        values.extend([like, like])

    where_clause = " AND ".join(filters)
    offset = (page - 1) * page_size

    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT count(*) AS total
            FROM documents_log d
            LEFT JOIN suppliers s ON s.id = d.supplier_id
            WHERE {where_clause}
            """,
            values,
        )
        count_row = await cur.fetchone()
        total = int(count_row["total"]) if count_row else 0

        await cur.execute(
            f"""
            {DOCUMENT_SELECT}
            WHERE {where_clause}
            ORDER BY d.created_at DESC
            LIMIT %s OFFSET %s
            """,
            [*values, page_size, offset],
        )
        rows = list(await cur.fetchall())

    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def update_document_status(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    document_id: UUID | str,
    status: str,
    error_message: str | None = None,
) -> dict | None:
    processed_at = "now()" if status == "processed" else "NULL"
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            UPDATE documents_log
            SET status = %s,
                error_message = %s,
                processed_at = {processed_at}
            WHERE org_id = %s AND id = %s
            RETURNING *
            """,
            (status, error_message, str(org_id), str(document_id)),
        )
        return await cur.fetchone()


async def mark_processing(conn: AsyncConnection, *, org_id: UUID | str, document_id: UUID | str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE documents_log
            SET status = 'processing', processing_started_at = now(), error_message = NULL
            WHERE org_id = %s AND id = %s
            RETURNING *
            """,
            (str(org_id), str(document_id)),
        )
        return await cur.fetchone()


async def mark_processed(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    document_id: UUID | str,
    supplier_id: UUID | str | None,
    extraction_provider: str,
    extraction_model: str,
    raw_text: str | None,
    metadata: dict | None,
) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE documents_log
            SET status = 'processed',
                supplier_id = COALESCE(%s, supplier_id),
                extraction_provider = %s,
                extraction_model = %s,
                raw_text = %s,
                metadata = COALESCE(metadata, '{}'::jsonb) || %s,
                error_message = NULL,
                processed_at = now()
            WHERE org_id = %s AND id = %s
            RETURNING *
            """,
            (
                str(supplier_id) if supplier_id else None,
                extraction_provider,
                extraction_model,
                raw_text,
                Jsonb(metadata or {}),
                str(org_id),
                str(document_id),
            ),
        )
        return await cur.fetchone()


async def mark_failed(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    document_id: UUID | str,
    error_message: str,
) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE documents_log
            SET status = 'failed', error_message = %s
            WHERE org_id = %s AND id = %s
            RETURNING *
            """,
            (error_message[:2000], str(org_id), str(document_id)),
        )
        return await cur.fetchone()


async def claim_document_by_id(conn: AsyncConnection, document_id: UUID | str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE documents_log
            SET status = 'processing', processing_started_at = now(), error_message = NULL
            WHERE id = %s AND status = 'queued'
            RETURNING *
            """,
            (str(document_id),),
        )
        return await cur.fetchone()


async def claim_next_queued(conn: AsyncConnection) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            WITH next_doc AS (
                SELECT id
                FROM documents_log
                WHERE status = 'queued'
                   OR (status = 'processing'
                       AND processing_started_at < now() - interval '15 minutes')
                ORDER BY created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE documents_log d
            SET status = 'processing', processing_started_at = now(), error_message = NULL
            FROM next_doc
            WHERE d.id = next_doc.id
            RETURNING d.*
            """
        )
        return await cur.fetchone()


async def reset_document_children(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    document_id: UUID | str,
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM exceptions_log WHERE org_id = %s AND document_id = %s",
            (str(org_id), str(document_id)),
        )
        await cur.execute(
            "DELETE FROM items_history WHERE org_id = %s AND document_id = %s",
            (str(org_id), str(document_id)),
        )


async def reset_document_for_reprocess(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    document_id: UUID | str,
) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE documents_log
            SET status = 'queued',
                processing_started_at = NULL,
                processed_at = NULL,
                error_message = NULL
            WHERE org_id = %s AND id = %s
            RETURNING *
            """,
            (str(org_id), str(document_id)),
        )
        return await cur.fetchone()
