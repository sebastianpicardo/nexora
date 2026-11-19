from __future__ import annotations

from itertools import combinations
from typing import Any

from src.services.leak_audit_service import _fetch_latest, _group_latest

MAX_OPTIMIZER_SUPPLIERS = 14


def _f(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _match_group(
    index: dict[str, tuple],
    groups: dict[tuple, list[dict]],
    sku: str | None,
    product: str | None,
) -> tuple | None:
    if sku:
        key = sku.strip().lower()
        if key in index:
            return index[key]
    if product:
        needle = product.strip().lower()
        if needle in index:
            return index[needle]
        for key, group in groups.items():
            description = str(group[0].get("description") or "").lower()
            if needle and (needle in description or description in needle):
                return key
    return None


async def optimize_purchase(user: dict, payload: dict) -> dict[str, Any]:
    requested = payload.get("items") or []
    if not requested:
        raise ValueError("Agrega al menos un producto para calcular la compra óptima.")
    currency = (payload.get("currency") or user.get("default_currency") or "CLP").strip().upper()
    freight_map = {
        str(key).strip().lower(): _f(value)
        for key, value in (payload.get("freight_by_supplier") or {}).items()
    }
    minimum_map = {
        str(key).strip().lower(): _f(value)
        for key, value in (payload.get("min_order_by_supplier") or {}).items()
    }

    latest = await _fetch_latest(user, 90, currency)
    groups = _group_latest(latest)
    index: dict[str, tuple] = {}
    for key, group in groups.items():
        index[str(key[0]).strip().lower()] = key
        for row in group:
            if row.get("sku"):
                index[str(row["sku"]).strip().lower()] = key

    lines: list[dict] = []
    missing: list[dict] = []
    for raw in requested:
        sku = str(raw.get("sku") or "").strip() or None
        product = str(raw.get("product") or "").strip() or None
        quantity = _f(raw.get("quantity"))
        if quantity <= 0:
            quantity = 1.0
        group_key = _match_group(index, groups, sku, product)
        if group_key is None:
            missing.append({"sku": sku, "product": product, "quantity": quantity})
            continue
        options = sorted(
            (
                {
                    "supplier": row["supplier_name"],
                    "price": _f(row["price"]),
                    "unit": row["base_unit"],
                }
                for row in groups[group_key]
            ),
            key=lambda option: option["price"],
        )
        lines.append(
            {
                "sku": sku or groups[group_key][0].get("sku"),
                "product": product or groups[group_key][0]["description"],
                "quantity": quantity,
                "unit": groups[group_key][0]["base_unit"],
                "options": options,
            }
        )

    if not lines:
        raise ValueError(
            "Ninguno de los productos tiene precios registrados. Carga listas o facturas primero."
        )

    suppliers = sorted({option["supplier"] for line in lines for option in line["options"]})
    if len(suppliers) > MAX_OPTIMIZER_SUPPLIERS:
        keep: set[str] = set()
        for line in lines:
            for option in line["options"][:3]:
                keep.add(option["supplier"])
        suppliers = sorted(keep)[:MAX_OPTIMIZER_SUPPLIERS]

    def evaluate(selected: set[str], enforce_minimum: bool) -> dict | None:
        chosen: list[dict] = []
        supplier_subtotals: dict[str, float] = {name: 0.0 for name in selected}
        for line in lines:
            options = [option for option in line["options"] if option["supplier"] in selected]
            if not options:
                return None
            best = min(options, key=lambda option: option["price"])
            subtotal = best["price"] * line["quantity"]
            supplier_subtotals[best["supplier"]] += subtotal
            chosen.append(
                {
                    "sku": line["sku"],
                    "product": line["product"],
                    "quantity": line["quantity"],
                    "unit": line["unit"],
                    "supplier": best["supplier"],
                    "unit_price": round(best["price"], 2),
                    "subtotal": round(subtotal, 2),
                }
            )
        total_freight = 0.0
        supplier_rows = []
        for name in sorted(selected):
            subtotal = supplier_subtotals.get(name, 0.0)
            if subtotal <= 0:
                continue
            minimum = minimum_map.get(name.lower(), 0.0)
            if enforce_minimum and minimum > 0 and subtotal < minimum:
                return None
            freight = freight_map.get(name.lower(), 0.0)
            total_freight += freight
            supplier_rows.append(
                {
                    "supplier": name,
                    "subtotal": round(subtotal, 2),
                    "freight": round(freight, 2),
                    "minimum_order": round(minimum, 2),
                    "meets_minimum": minimum <= 0 or subtotal >= minimum,
                }
            )
        total = sum(row["subtotal"] for row in supplier_rows) + total_freight
        return {
            "suppliers": supplier_rows,
            "lines": chosen,
            "total": round(total, 2),
            "total_freight": round(total_freight, 2),
        }

    best: dict | None = None
    relaxed = False
    for size in range(1, len(suppliers) + 1):
        for combination in combinations(suppliers, size):
            result = evaluate(set(combination), enforce_minimum=True)
            if result is not None and (best is None or result["total"] < best["total"]):
                best = result

    if best is None:
        relaxed = True
        result = evaluate(set(suppliers), enforce_minimum=False)
        best = result

    if best is None:
        raise ValueError("No se pudo construir una compra óptima con los precios disponibles.")

    single_totals = []
    for supplier in suppliers:
        result = evaluate({supplier}, enforce_minimum=False)
        if result is not None:
            single_totals.append(result["total"])
    cheapest_single = min(single_totals) if single_totals else best["total"]
    warnings: list[str] = []
    if relaxed:
        warnings.append(
            "No se cumplieron todos los montos mínimos de pedido. Revisa si conviene agregar "
            "productos o negociar el mínimo con el proveedor."
        )
    if missing:
        warnings.append(
            f"{len(missing)} producto(s) no tienen precios registrados y quedaron fuera del cálculo."
        )

    return {
        "currency": currency,
        "requested_lines": len(lines) + len(missing),
        "optimized_lines": len(best["lines"]),
        "missing": missing,
        "suppliers": best["suppliers"],
        "lines": best["lines"],
        "total_purchase": best["total"],
        "total_freight": best["total_freight"],
        "cheapest_single_supplier_total": round(cheapest_single, 2),
        "savings_vs_single_supplier": round(cheapest_single - best["total"], 2),
        "warnings": warnings,
        "note": (
            "La compra óptima elige el proveedor más barato por producto y luego valida "
            "monto mínimo y flete por proveedor."
        ),
    }
