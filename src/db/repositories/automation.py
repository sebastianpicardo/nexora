from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

RUN_SELECT = """
    SELECT id, org_id, document_id, status, trigger_source, filename, requested_by,
           stages, summary, results, ai_used, error_message, created_at, updated_at,
           completed_at
    FROM automation_runs
"""


async def create_automation_run(
    conn: AsyncConnection,
    *,
    run_id: UUID | str,
    org_id: UUID | str,
    document_id: UUID | str | None,
    status: str,
    trigger_source: str,
    filename: str | None,
    requested_by: UUID | str | None,
    stages: list[dict] | None = None,
    summary: dict | None = None,
    results: dict | None = None,
    ai_used: bool = False,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO automation_runs (
                id, org_id, document_id, status, trigger_source, filename, requested_by,
                stages, summary, results, ai_used
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, org_id, document_id, status, trigger_source, filename,
                      requested_by, stages, summary, results, ai_used, error_message,
                      created_at, updated_at, completed_at
            """,
            (
                str(run_id),
                str(org_id),
                str(document_id) if document_id else None,
                status,
                trigger_source,
                filename,
                str(requested_by) if requested_by else None,
                Jsonb(stages or []),
                Jsonb(summary or {}),
                Jsonb(results or {}),
                ai_used,
            ),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def update_automation_run(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    run_id: UUID | str,
    status: str | None = None,
    document_id: UUID | str | None = None,
    filename: str | None = None,
    stages: list[dict] | None = None,
    summary: dict | None = None,
    results: dict | None = None,
    ai_used: bool | None = None,
    error_message: str | None = None,
    clear_error: bool = False,
) -> dict | None:
    assignments = ["updated_at = now()"]
    values: list[Any] = []

    def add(column: str, value: Any) -> None:
        assignments.append(f"{column} = %s")
        values.append(value)

    if status is not None:
        add("status", status)
        if status in {"completed", "failed"}:
            assignments.append("completed_at = COALESCE(completed_at, now())")
    if document_id is not None:
        add("document_id", str(document_id) if document_id else None)
    if filename is not None:
        add("filename", filename)
    if stages is not None:
        add("stages", Jsonb(stages))
    if summary is not None:
        add("summary", Jsonb(summary))
    if results is not None:
        add("results", Jsonb(results))
    if ai_used is not None:
        add("ai_used", ai_used)
    if clear_error:
        assignments.append("error_message = NULL")
    elif error_message is not None:
        add("error_message", error_message[:2000])

    values.extend([str(org_id), str(run_id)])

    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            UPDATE automation_runs
            SET {", ".join(assignments)}
            WHERE org_id = %s AND id = %s
            RETURNING id, org_id, document_id, status, trigger_source, filename,
                      requested_by, stages, summary, results, ai_used, error_message,
                      created_at, updated_at, completed_at
            """,
            values,
        )
        return await cur.fetchone()


async def get_automation_run(
    conn: AsyncConnection,
    org_id: UUID | str,
    run_id: UUID | str,
) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            f"{RUN_SELECT} WHERE org_id = %s AND id = %s",
            (str(org_id), str(run_id)),
        )
        return await cur.fetchone()


async def list_automation_runs(
    conn: AsyncConnection,
    org_id: UUID | str,
    limit: int = 10,
) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            f"{RUN_SELECT} WHERE org_id = %s ORDER BY created_at DESC LIMIT %s",
            (str(org_id), max(1, min(limit, 50))),
        )
        return await cur.fetchall()
