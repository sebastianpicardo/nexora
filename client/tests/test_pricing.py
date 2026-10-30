from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.parsers.normalization.pricing import detect_price_spike, validate_line_total


def _history(*prices: str) -> list[dict]:
    return [
        {
            "document_id": f"00000000-0000-0000-0000-00000000000{index}",
            "price_date": date(2026, 1, index + 1),
            "normalized_unit_price": Decimal(price),
            "currency": "CLP",
        }
        for index, price in enumerate(prices)
    ]


def test_price_spike_is_flagged_against_median():
    result = detect_price_spike(
        Decimal("150"),
        _history("100", "110"),
        threshold_pct=10,
        min_samples=2,
    )

    assert result.flagged is True
    assert result.severity == "high"
    assert result.sample_size == 2
    assert result.median == Decimal("105")
    assert result.pct_change == pytest.approx(42.86, abs=0.01)
    assert result.evidence["historical_median"] == "105"


def test_price_below_threshold_is_not_flagged():
    result = detect_price_spike(
        Decimal("110"),
        _history("100", "110"),
        threshold_pct=10,
        min_samples=2,
    )

    assert result.flagged is False
    assert result.severity is None
    assert result.pct_change == pytest.approx(4.76, abs=0.01)


def test_price_spike_requires_minimum_samples():
    result = detect_price_spike(
        Decimal("500"),
        _history("100"),
        threshold_pct=10,
        min_samples=2,
    )

    assert result.flagged is False
    assert result.sample_size == 1
    assert result.median is None


def test_large_price_spike_is_critical():
    result = detect_price_spike(
        Decimal("250"),
        _history("100", "100"),
        threshold_pct=10,
        min_samples=2,
    )

    assert result.flagged is True
    assert result.severity == "critical"
    assert result.pct_change == 150.0


def test_missing_current_price_is_not_flagged():
    result = detect_price_spike(
        None,
        _history("100", "110"),
        threshold_pct=10,
        min_samples=2,
    )

    assert result.flagged is False
    assert result.evidence["sample_size"] == 2


def test_line_total_valid():
    valid, delta = validate_line_total(
        unit_price=Decimal("10"),
        quantity=Decimal("3"),
        line_total=Decimal("30"),
    )

    assert valid is True
    assert delta == 0.0


def test_line_total_invalid():
    valid, delta = validate_line_total(
        unit_price=Decimal("10"),
        quantity=Decimal("3"),
        line_total=Decimal("31"),
        tolerance=0.02,
    )

    assert valid is False
    assert delta == pytest.approx(3.23, abs=0.01)


def test_line_total_with_missing_data_is_valid():
    valid, delta = validate_line_total(None, Decimal("3"), Decimal("30"))

    assert valid is True
    assert delta is None
