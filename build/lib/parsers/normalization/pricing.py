from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from statistics import median


@dataclass(frozen=True)
class PriceAudit:
    flagged: bool
    severity: str | None
    median: Decimal | None
    sample_size: int
    pct_change: float | None
    reason: str | None
    evidence: dict = field(default_factory=dict)


def _severity(pct_change: float) -> str:
    if pct_change >= 50:
        return "critical"
    if pct_change >= 25:
        return "high"
    return "medium"


def detect_price_spike(
    current_price: Decimal | None,
    history: list[dict],
    *,
    threshold_pct: float,
    min_samples: int,
) -> PriceAudit:
    valid = [
        row
        for row in history
        if row.get("normalized_unit_price") is not None and Decimal(row["normalized_unit_price"]) > 0
    ]
    history_evidence = [
        {
            "document_id": str(row.get("document_id")) if row.get("document_id") else None,
            "price_date": row["price_date"].isoformat() if row.get("price_date") else None,
            "normalized_unit_price": str(row["normalized_unit_price"]),
            "currency": row.get("currency"),
        }
        for row in valid
    ]

    if current_price is None or current_price <= 0 or len(valid) < min_samples:
        return PriceAudit(
            flagged=False,
            severity=None,
            median=None,
            sample_size=len(valid),
            pct_change=None,
            reason=None,
            evidence={
                "sample_size": len(valid),
                "min_samples": min_samples,
                "previous_prices": history_evidence,
            },
        )

    baseline = median([Decimal(row["normalized_unit_price"]) for row in valid])
    pct_change = float((current_price - baseline) / baseline * 100)
    evidence = {
        "current_price": str(current_price),
        "historical_median": str(baseline),
        "pct_change": round(pct_change, 2),
        "threshold_pct": threshold_pct,
        "sample_size": len(valid),
        "previous_prices": history_evidence,
    }

    if pct_change < threshold_pct:
        return PriceAudit(
            flagged=False,
            severity=None,
            median=baseline,
            sample_size=len(valid),
            pct_change=round(pct_change, 2),
            reason=None,
            evidence=evidence,
        )

    severity = _severity(pct_change)
    return PriceAudit(
        flagged=True,
        severity=severity,
        median=baseline,
        sample_size=len(valid),
        pct_change=round(pct_change, 2),
        reason=(
            f"El precio unitario normalizado aumentó {pct_change:.1f}% "
            f"respecto de la mediana histórica ({baseline:.4f})."
        ),
        evidence=evidence,
    )


def validate_line_total(
    unit_price: Decimal | None,
    quantity: Decimal | None,
    line_total: Decimal | None,
    *,
    tolerance: float = 0.02,
) -> tuple[bool, float | None]:
    if unit_price is None or quantity is None or line_total is None or line_total == 0:
        return True, None
    expected = unit_price * quantity
    difference = abs(line_total - expected)
    delta = float(difference / max(abs(line_total), Decimal(1)) * 100)
    return delta <= tolerance * 100, round(delta, 2)
