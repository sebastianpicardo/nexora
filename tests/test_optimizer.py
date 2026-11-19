from __future__ import annotations

import asyncio
from datetime import date

from src.services import purchase_optimizer_service as optimizer

ROWS = [
    {
        "product_key": "SKU-1",
        "sku": "SKU-1",
        "description": "Tornillo",
        "base_unit": "unidad",
        "currency": "CLP",
        "supplier_id": "a",
        "supplier_name": "Proveedor A",
        "price": 100,
        "quantity": 1,
        "price_date": date.today(),
    },
    {
        "product_key": "SKU-1",
        "sku": "SKU-1",
        "description": "Tornillo",
        "base_unit": "unidad",
        "currency": "CLP",
        "supplier_id": "b",
        "supplier_name": "Proveedor B",
        "price": 120,
        "quantity": 1,
        "price_date": date.today(),
    },
    {
        "product_key": "SKU-2",
        "sku": "SKU-2",
        "description": "Plancha",
        "base_unit": "unidad",
        "currency": "CLP",
        "supplier_id": "a",
        "supplier_name": "Proveedor A",
        "price": 50,
        "quantity": 1,
        "price_date": date.today(),
    },
    {
        "product_key": "SKU-2",
        "sku": "SKU-2",
        "description": "Plancha",
        "base_unit": "unidad",
        "currency": "CLP",
        "supplier_id": "b",
        "supplier_name": "Proveedor B",
        "price": 40,
        "quantity": 1,
        "price_date": date.today(),
    },
]

CART = {
    "items": [
        {"sku": "SKU-1", "quantity": 1},
        {"sku": "SKU-2", "quantity": 1},
    ]
}


def _run(monkeypatch, payload):
    async def fake_fetch(*args, **kwargs):
        return ROWS

    monkeypatch.setattr(optimizer, "_fetch_latest", fake_fetch)
    return asyncio.run(optimizer.optimize_purchase({"org_id": "org", "default_currency": "CLP"}, payload))


def test_optimal_purchase_splits_between_suppliers(monkeypatch):
    result = _run(monkeypatch, CART)

    assert result["total_purchase"] == 140
    suppliers = {line["supplier"] for line in result["lines"]}
    assert suppliers == {"Proveedor A", "Proveedor B"}
    assert result["savings_vs_single_supplier"] == 10


def test_optimal_purchase_considers_freight(monkeypatch):
    payload = {**CART, "freight_by_supplier": {"Proveedor B": 30}}
    result = _run(monkeypatch, payload)

    assert result["total_purchase"] == 150
    assert {line["supplier"] for line in result["lines"]} == {"Proveedor A"}
    assert result["total_freight"] == 0


def test_optimal_purchase_respects_minimum_order(monkeypatch):
    payload = {**CART, "min_order_by_supplier": {"Proveedor A": 200}}
    result = _run(monkeypatch, payload)

    assert result["total_purchase"] == 160
    assert {line["supplier"] for line in result["lines"]} == {"Proveedor B"}


def test_optimal_purchase_relaxes_minimum_when_no_feasible_option(monkeypatch):
    payload = {
        **CART,
        "min_order_by_supplier": {"Proveedor A": 500, "Proveedor B": 500},
    }
    result = _run(monkeypatch, payload)

    assert result["warnings"]
    assert result["total_purchase"] > 0
