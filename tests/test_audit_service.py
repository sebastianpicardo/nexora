from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from src.parsers.schemas import NormalizedItem
from src.services import audit_service


async def test_price_history_is_scoped_by_currency_and_unit(monkeypatch):
    captured: dict = {}

    async def fake_get_price_history(conn, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(audit_service.items_repo, "get_price_history", fake_get_price_history)

    item = NormalizedItem(
        sku="TOR-1",
        original_description="Tornillo",
        normalized_description="tornillo acero",
        original_unit="kg",
        base_unit="kg",
        unit_factor=Decimal(1),
        quantity=Decimal(2),
        package_size=None,
        original_unit_price=Decimal(10),
        normalized_unit_price=Decimal(10),
        currency="USD",
        price_date=date(2026, 1, 1),
        confidence=0.95,
        source_page=1,
        source_text=None,
        flags=[],
    )

    flags = await audit_service.audit_item(
        object(),
        org_id=uuid4(),
        document_id=uuid4(),
        supplier_id=uuid4(),
        item=item,
        price_spike_threshold_pct=10,
        lookback_days=365,
        min_history_samples=2,
    )

    assert flags == []
    assert captured["currency"] == "USD"
    assert captured["base_unit"] == "kg"
