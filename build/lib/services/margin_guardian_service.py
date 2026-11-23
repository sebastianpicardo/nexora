from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date
from typing import Any

from src.db.pool import get_pool

COST_INCREASE_ALERT_PCT = 3.0


def _f(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


async def _price_history(user: dict, currency: str) -> dict[str, list[dict]]:
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT sku, normalized_unit_price, price_date
                FROM items_history
                WHERE org_id = %s
                  AND sku IS NOT NULL AND sku <> ''
                  AND normalized_unit_price > 0
                  AND upper(currency) = %s
                  AND review_status <> 'rejected'
                ORDER BY sku, price_date DESC, created_at DESC
                """,
                (user["org_id"], currency),
            )
            rows = await cur.fetchall()

    history: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = str(row["sku"]).strip().lower()
        prices = history[key]
        if len(prices) >= 2:
            continue
        price = _f(row["normalized_unit_price"])
        if prices and abs(prices[-1]["price"] - price) < 0.0001:
            continue
        prices.append({"price": price, "date": row["price_date"]})
    return history


def _margin(sale: float, cost: float) -> float:
    if sale <= 0:
        return 0.0
    return (sale - cost) / sale * 100


def _suggested_sale(cost: float, target_margin: float) -> float:
    if cost <= 0 or target_margin >= 100:
        return round(cost, 2)
    return round(cost / (1 - target_margin / 100), 2)


async def build_margin_guardian(
    user: dict,
    *,
    target_margin: float = 15.0,
    min_margin: float = 8.0,
) -> dict[str, Any]:
    currency = (user.get("default_currency") or "CLP").strip().upper()
    target_margin = max(0.0, min(float(target_margin), 90.0))
    min_margin = max(0.0, min(float(min_margin), target_margin))

    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, sku, name, unit, cost_price, sale_price, margin_pct,
                       supplier_name, category
                FROM price_catalog
                WHERE org_id = %s AND active
                ORDER BY name
                """,
                (user["org_id"],),
            )
            catalog = await cur.fetchall()

    history = await _price_history(user, currency)
    items: list[dict] = []
    for row in catalog:
        sku_key = str(row["sku"]).strip().lower()
        prices = history.get(sku_key, [])
        catalog_cost = _f(row["cost_price"])
        sale = _f(row["sale_price"])
        previous_cost = prices[1]["price"] if len(prices) > 1 else catalog_cost
        current_cost = prices[0]["price"] if prices else catalog_cost
        cost_change_pct = (
            (current_cost - previous_cost) / previous_cost * 100 if previous_cost > 0 else 0.0
        )
        current_margin = _margin(sale, current_cost)
        previous_margin = _margin(sale, previous_cost)
        suggested = _suggested_sale(current_cost, target_margin)
        cost_increase = max(current_cost - previous_cost, 0.0)

        if sale <= 0:
            status = "sin_precio"
            severity = "high"
            label = "Sin precio de venta"
        elif sale < current_cost:
            status = "bajo_costo"
            severity = "critical"
            label = "Vende bajo el costo"
        elif current_margin < min_margin:
            status = "bajo_umbral"
            severity = "high"
            label = "Margen bajo el mínimo"
        elif cost_change_pct >= COST_INCREASE_ALERT_PCT:
            status = "alza_costo"
            severity = "medium"
            label = "Alza de costo detectada"
        else:
            status = "ok"
            severity = "low"
            label = "Margen saludable"

        recovery = max(suggested - sale, 0.0) if sale > 0 else 0.0
        items.append(
            {
                "id": row["id"],
                "sku": row["sku"],
                "name": row["name"],
                "unit": row["unit"],
                "category": row["category"],
                "supplier": row["supplier_name"],
                "cost_previous": round(previous_cost, 2),
                "cost_current": round(current_cost, 2),
                "cost_change_pct": round(cost_change_pct, 1),
                "sale_price": round(sale, 2),
                "margin_pct": round(current_margin, 1),
                "margin_previous_pct": round(previous_margin, 1),
                "margin_delta_pct": round(current_margin - previous_margin, 1),
                "status": status,
                "severity": severity,
                "status_label": label,
                "target_margin": target_margin,
                "suggested_sale": suggested,
                "recovery_per_unit": round(recovery, 2),
                "pass_through": {
                    "p50": round(sale + cost_increase * 0.5, 2),
                    "p75": round(sale + cost_increase * 0.75, 2),
                    "p100": round(sale + cost_increase, 2),
                },
            }
        )

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items.sort(key=lambda item: (severity_rank[item["severity"]], -item["recovery_per_unit"]))
    summary = {
        "items_total": len(items),
        "at_risk": sum(1 for item in items if item["status"] != "ok"),
        "below_cost": sum(1 for item in items if item["status"] == "bajo_costo"),
        "below_threshold": sum(1 for item in items if item["status"] == "bajo_umbral"),
        "cost_increases": sum(1 for item in items if item["status"] == "alza_costo"),
        "recovery_per_unit": round(sum(item["recovery_per_unit"] for item in items), 2),
        "currency": currency,
        "target_margin": target_margin,
        "min_margin": min_margin,
    }
    return {
        "generated_at": date.today().isoformat(),
        "summary": summary,
        "items": items,
        "note": (
            "El costo actual usa el último precio de compra registrado en NEXORA. "
            "Si no hay compras, se usa el costo del catálogo."
        ),
    }


def build_pos_csv(user: dict, items: list[dict]) -> tuple[str, bytes, int]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(
        [
            "SKU",
            "Nombre",
            "Unidad",
            "Precio costo",
            "Precio venta",
            "Precio venta sugerido",
            "Margen %",
            "Proveedor",
            "Categoria",
            "Actualizado",
        ]
    )
    updated = date.today().isoformat()
    for item in items:
        writer.writerow(
            [
                item["sku"],
                item["name"],
                item["unit"],
                item["cost_current"],
                item["sale_price"],
                item["suggested_sale"],
                item["margin_pct"],
                item.get("supplier") or "",
                item.get("category") or "",
                updated,
            ]
        )
    filename = f"precios_nexora_{updated}.csv"
    return filename, buffer.getvalue().encode("utf-8-sig"), len(items)


async def pos_export(user: dict, *, only_changes: bool = False) -> tuple[str, bytes, int]:
    guardian = await build_margin_guardian(user)
    items = guardian["items"]
    if only_changes:
        items = [item for item in items if item["status"] != "ok"]
    return build_pos_csv(user, items)
