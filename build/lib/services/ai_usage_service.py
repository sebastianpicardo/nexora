from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection

from src.core.config import settings
from src.db import repositories


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    input_cost = max(int(input_tokens or 0), 0) / 1_000_000 * settings.ai_input_cost_per_million_usd
    output_cost = max(int(output_tokens or 0), 0) / 1_000_000 * settings.ai_output_cost_per_million_usd
    return round(input_cost + output_cost, 6)


def _limit_for(kind: str) -> int:
    if kind == "assistant":
        return settings.ai_assistant_monthly_limit
    return settings.ai_document_monthly_limit


async def quota_exceeded(conn: AsyncConnection, org_id: UUID | str, *, kind: str) -> bool:
    if not settings.ai_usage_tracking_enabled:
        return False
    limit = _limit_for(kind)
    if limit <= 0:
        return False
    used = await repositories.count_ai_usage_this_month(conn, org_id, kind=kind)
    return used >= limit


async def record_usage(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    kind: str,
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    document_id: UUID | str | None = None,
    user_id: UUID | str | None = None,
    status: str = "success",
    metadata: dict | None = None,
) -> dict | None:
    if not settings.ai_usage_tracking_enabled:
        return None
    return await repositories.record_ai_usage(
        conn,
        org_id=org_id,
        kind=kind,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimate_cost_usd(input_tokens, output_tokens),
        document_id=document_id,
        user_id=user_id,
        status=status,
        metadata=metadata,
    )
