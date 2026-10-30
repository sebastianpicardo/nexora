from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection

from src.db.repositories import items as items_repo
from src.parsers.normalization.pricing import detect_price_spike
from src.parsers.schemas import AuditFlag, NormalizedItem

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _merge_flags(flags: list[AuditFlag]) -> list[AuditFlag]:
    merged: dict[str, AuditFlag] = {}
    for flag in flags:
        current = merged.get(flag.type)
        if current is None or SEVERITY_RANK.get(flag.severity, 0) > SEVERITY_RANK.get(current.severity, 0):
            merged[flag.type] = flag
    return list(merged.values())


async def audit_item(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    document_id: UUID | str,
    supplier_id: UUID | str | None,
    item: NormalizedItem,
    price_spike_threshold_pct: float,
    lookback_days: int,
    min_history_samples: int,
) -> list[AuditFlag]:
    flags = list(item.flags)

    history = await items_repo.get_price_history(
        conn,
        org_id=org_id,
        supplier_id=supplier_id,
        sku=item.sku,
        normalized_description=item.normalized_description,
        base_unit=item.base_unit,
        currency=item.currency,
        before_date=item.price_date,
        lookback_days=lookback_days,
        exclude_document_id=document_id,
    )

    price_audit = detect_price_spike(
        item.normalized_unit_price,
        history,
        threshold_pct=price_spike_threshold_pct,
        min_samples=min_history_samples,
    )
    if price_audit.flagged:
        flags.append(
            AuditFlag(
                type="price_spike",
                severity=price_audit.severity or "medium",
                reason=price_audit.reason or "Se detectó un alza de precio anómala.",
                evidence=price_audit.evidence,
            )
        )

    return _merge_flags(flags)
