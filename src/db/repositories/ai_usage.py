from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb


def _float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


async def record_ai_usage(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    kind: str,
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
    document_id: UUID | str | None = None,
    user_id: UUID | str | None = None,
    status: str = "success",
    metadata: dict | None = None,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO ai_usage (
                org_id, user_id, document_id, kind, provider, model,
                input_tokens, output_tokens, estimated_cost_usd, status, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                str(org_id),
                str(user_id) if user_id else None,
                str(document_id) if document_id else None,
                kind,
                provider,
                model,
                max(int(input_tokens or 0), 0),
                max(int(output_tokens or 0), 0),
                max(float(estimated_cost_usd or 0.0), 0.0),
                status,
                Jsonb(metadata or {}),
            ),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def count_ai_usage_this_month(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    kind: str,
) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM ai_usage
            WHERE org_id = %s
              AND kind = %s
              AND created_at >= date_trunc('month', now())
            """,
            (str(org_id), kind),
        )
        row = await cur.fetchone() or {}
    return int(row.get("total") or 0)


async def summarize_ai_usage(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    days: int = 30,
) -> dict:
    days = max(1, min(int(days), 365))
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                kind,
                COUNT(*) AS requests,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd
            FROM ai_usage
            WHERE org_id = %s
              AND created_at >= (now() - (%s * interval '1 day'))
            GROUP BY kind
            ORDER BY kind
            """,
            (str(org_id), days),
        )
        rows = list(await cur.fetchall())

        await cur.execute(
            """
            SELECT
                COUNT(*) AS requests,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd
            FROM ai_usage
            WHERE org_id = %s
              AND created_at >= date_trunc('month', now())
            """,
            (str(org_id),),
        )
        current = await cur.fetchone() or {}

    by_kind = {
        row["kind"]: {
            "requests": int(row.get("requests") or 0),
            "input_tokens": int(row.get("input_tokens") or 0),
            "output_tokens": int(row.get("output_tokens") or 0),
            "estimated_cost_usd": round(_float(row.get("estimated_cost_usd")), 6),
        }
        for row in rows
    }
    return {
        "days": days,
        "by_kind": by_kind,
        "current_month": {
            "requests": int(current.get("requests") or 0),
            "input_tokens": int(current.get("input_tokens") or 0),
            "output_tokens": int(current.get("output_tokens") or 0),
            "estimated_cost_usd": round(_float(current.get("estimated_cost_usd")), 6),
        },
    }
