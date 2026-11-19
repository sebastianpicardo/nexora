from __future__ import annotations

import asyncio
import hashlib
import re
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from src.db import repositories
from src.db.pool import get_pool
from src.parsers.extractors.tabular import extract_tabular_document

MIN_SPREAD_PCT = 3.0
MIN_MARGIN_PCT = 8.0
TARGET_MARGIN_PCT = 15.0
MAX_FINDINGS = 60

LATEST_PRICES_SQL = """
SELECT DISTINCT ON (
    coalesce(nullif(i.sku, ''), i.normalized_description),
    i.base_unit,
    upper(i.currency),
    i.supplier_id
)
    coalesce(nullif(i.sku, ''), i.normalized_description) AS product_key,
    i.sku,
    i.normalized_description AS description,
    i.base_unit,
    upper(i.currency) AS currency,
    i.supplier_id,
    coalesce(s.name, 'Proveedor sin nombre') AS supplier_name,
    i.normalized_unit_price AS price,
    i.quantity,
    i.price_date
FROM items_history i
LEFT JOIN suppliers s ON s.id = i.supplier_id
WHERE i.org_id = %s
  AND i.price_date >= current_date - make_interval(days => %s)
  AND i.normalized_unit_price > 0
  AND upper(i.currency) = %s
  AND i.review_status <> 'rejected'
ORDER BY
    coalesce(nullif(i.sku, ''), i.normalized_description),
    i.base_unit,
    upper(i.currency),
    i.supplier_id,
    i.price_date DESC,
    i.created_at DESC
"""


def _f(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _round(value: float, places: int = 0) -> float:
    return round(float(value), places)


def _severity_by_gap(gap_pct: float) -> str:
    if gap_pct >= 15:
        return "critical"
    if gap_pct >= 8:
        return "high"
    return "medium"


async def _fetch_latest(user: dict, days: int, currency: str, search: str | None = None) -> list[dict]:
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(LATEST_PRICES_SQL, (user["org_id"], days, currency))
            rows = await cur.fetchall()
    if not search:
        return rows
    needle = search.strip().lower()
    return [
        row
        for row in rows
        if needle in str(row.get("description") or "").lower()
        or needle in str(row.get("product_key") or "").lower()
        or needle in str(row.get("supplier_name") or "").lower()
    ]


def _group_latest(rows: list[dict]) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (row["product_key"], row["base_unit"], row["currency"])
        groups[key].append(row)
    return groups


def _overpay_findings(rows: list[dict]) -> list[dict]:
    findings: list[dict] = []
    for (product_key, base_unit, currency), group in _group_latest(rows).items():
        if len(group) < 2:
            continue
        cheapest = min(group, key=lambda row: _f(row["price"]))
        priciest = max(group, key=lambda row: _f(row["price"]))
        min_price = _f(cheapest["price"])
        max_price = _f(priciest["price"])
        if min_price <= 0 or max_price <= min_price:
            continue
        gap_pct = (max_price - min_price) / min_price * 100
        if gap_pct < MIN_SPREAD_PCT:
            continue
        quantity = _f(priciest.get("quantity")) or 1.0
        savings = (max_price - min_price) * quantity
        findings.append(
            {
                "category": "price_overpay",
                "category_label": "Sobrecosto en precio",
                "severity": _severity_by_gap(gap_pct),
                "title": f"{priciest['description']}: pagas {gap_pct:.0f}% más que {cheapest['supplier_name']}",
                "detail": (
                    f"Último precio con {priciest['supplier_name']}: {max_price:,.0f} {currency} por "
                    f"{base_unit}; con {cheapest['supplier_name']}: {min_price:,.0f} {currency}. "
                    f"Diferencia estimada sobre la última compra registrada."
                ),
                "supplier": priciest["supplier_name"],
                "reference_supplier": cheapest["supplier_name"],
                "sku": priciest.get("sku") or None,
                "product": priciest["description"],
                "unit": base_unit,
                "currency": currency,
                "current_price": _round(max_price, 2),
                "reference_price": _round(min_price, 2),
                "gap_pct": _round(gap_pct, 1),
                "quantity": _round(quantity, 2),
                "savings": _round(savings),
                "action": (
                    f"Solicita cotización a {cheapest['supplier_name']} y renegocia con "
                    f"{priciest['supplier_name']} usando la diferencia como referencia."
                ),
                "evidence": {
                    "product_key": product_key,
                    "suppliers_compared": len(group),
                    "price_date": _iso(priciest.get("price_date")),
                },
            }
        )
    findings.sort(key=lambda item: item["savings"], reverse=True)
    return findings[:MAX_FINDINGS]


def _margin_findings(catalog: list[dict], currency: str) -> list[dict]:
    findings: list[dict] = []
    for row in catalog:
        cost = _f(row["cost_price"])
        sale = _f(row["sale_price"])
        margin = _f(row["margin_pct"])
        savings = 0.0
        severity = "medium"
        if sale <= 0:
            title = f"{row['name']}: producto activo sin precio de venta"
            detail = f"Costo actual {cost:,.0f} {currency}; no hay precio de venta definido."
            action = "Define precio de venta o desactiva el producto del catálogo."
            severity = "high"
        elif cost > sale:
            loss = cost - sale
            savings = loss
            title = f"{row['name']}: vendes bajo el costo ({margin:.1f}% de margen)"
            detail = (
                f"Costo {cost:,.0f} {currency} vs venta {sale:,.0f} {currency}. "
                f"Pérdida directa de {loss:,.0f} {currency} por unidad."
            )
            action = "Corrige el precio de venta o renegocia el costo con el proveedor."
            severity = "critical"
        elif margin < MIN_MARGIN_PCT:
            target_sale = cost / (1 - TARGET_MARGIN_PCT / 100) if cost > 0 else sale
            gap = max(target_sale - sale, 0.0)
            savings = gap
            title = f"{row['name']}: margen bajo ({margin:.1f}%)"
            detail = (
                f"Para llegar a {TARGET_MARGIN_PCT:.0f}% de margen necesitas vender a "
                f"{target_sale:,.0f} {currency} en lugar de {sale:,.0f} {currency}."
            )
            action = "Ajusta la lista de precios o negocia una rebaja de costo."
            severity = "high" if margin < 4 else "medium"
        else:
            continue
        findings.append(
            {
                "category": "margin_bleed",
                "category_label": "Margen bajo o negativo",
                "severity": severity,
                "title": title,
                "detail": detail,
                "supplier": row.get("supplier_name") or None,
                "reference_supplier": None,
                "sku": row.get("sku"),
                "product": row.get("name"),
                "unit": row.get("unit"),
                "currency": currency,
                "current_price": _round(sale, 2),
                "reference_price": _round(cost, 2),
                "gap_pct": _round(margin, 1),
                "quantity": 1,
                "savings": _round(savings),
                "action": action,
                "evidence": {
                    "category": row.get("category"),
                    "cost_price": _round(cost, 2),
                    "sale_price": _round(sale, 2),
                    "margin_pct": _round(margin, 2),
                    "savings_basis": "por unidad",
                },
            }
        )
    findings.sort(key=lambda item: item["savings"], reverse=True)
    return findings[:MAX_FINDINGS]


def _review_findings(pending_total: int, stale_pending: int, currency: str) -> list[dict]:
    findings: list[dict] = []
    if stale_pending > 0:
        findings.append(
            {
                "category": "review_backlog",
                "category_label": "Revisión pendiente",
                "severity": "high" if stale_pending >= 10 else "medium",
                "title": f"{stale_pending} ítems llevan más de 7 días sin revisión",
                "detail": (
                    "Los precios sin revisar no se usan para comparar y pueden esconder "
                    "sobrecostos o errores de unidad."
                ),
                "supplier": None,
                "reference_supplier": None,
                "sku": None,
                "product": "Bandeja de revisión",
                "unit": None,
                "currency": currency,
                "current_price": None,
                "reference_price": None,
                "gap_pct": None,
                "quantity": stale_pending,
                "savings": 0,
                "action": "Abre la bandeja de revisión y resuelve primero los ítems más antiguos.",
                "evidence": {"pending_total": pending_total, "stale_pending": stale_pending},
            }
        )
    return findings


async def build_audit(user: dict, days: int = 90, currency: str | None = None) -> dict:
    org_id = user["org_id"]
    window_currency = (currency or user.get("default_currency") or "CLP").strip().upper()
    days = max(7, min(int(days), 365))

    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    count(DISTINCT i.document_id) AS documents,
                    count(*) AS items,
                    count(DISTINCT i.supplier_id) AS suppliers,
                    coalesce(sum(i.normalized_unit_price * i.quantity), 0) AS spend,
                    min(i.price_date) AS first_date,
                    max(i.price_date) AS last_date
                FROM items_history i
                WHERE i.org_id = %s
                  AND i.price_date >= current_date - make_interval(days => %s)
                  AND upper(i.currency) = %s
                  AND i.review_status <> 'rejected'
                """,
                (org_id, days, window_currency),
            )
            coverage = await cur.fetchone() or {}

            await cur.execute(
                "SELECT count(*) AS total FROM price_catalog WHERE org_id = %s AND active",
                (org_id,),
            )
            catalog_count = int((await cur.fetchone() or {}).get("total") or 0)

            await cur.execute(
                """
                SELECT
                    count(*) FILTER (WHERE i.review_status = 'pending') AS pending_total,
                    count(*) FILTER (
                        WHERE i.review_status = 'pending' AND i.created_at < now() - interval '7 days'
                    ) AS stale_pending
                FROM items_history i
                WHERE i.org_id = %s
                """,
                (org_id,),
            )
            review_row = await cur.fetchone() or {}

            await cur.execute(
                """
                SELECT e.type, count(*) AS total
                FROM exceptions_log e
                WHERE e.org_id = %s
                  AND e.status = 'pending'
                  AND e.created_at >= now() - make_interval(days => %s)
                  AND e.type IN (
                      'price_mismatch', 'unit_mismatch', 'missing_price',
                      'partial_import', 'extraction_failed', 'invoice_discrepancy'
                  )
                GROUP BY e.type
                """,
                (org_id, days),
            )
            exception_rows = await cur.fetchall()

            await cur.execute(
                """
                SELECT coalesce(sum(
                    greatest(coalesce(i.normalized_unit_price, 0) - coalesce(
                        CASE WHEN jsonb_typeof(e.evidence->'historical_median') = 'number'
                             THEN (e.evidence->>'historical_median')::numeric ELSE 0 END, 0), 0)
                    * greatest(coalesce(i.quantity, 0), 0)
                ), 0) AS realized
                FROM exceptions_log e
                LEFT JOIN items_history i ON i.id = e.item_id
                WHERE e.org_id = %s
                  AND e.type = 'price_spike'
                  AND e.status IN ('approved', 'resolved')
                  AND (i.currency = %s OR i.currency IS NULL)
                """,
                (org_id, window_currency),
            )
            realized_row = await cur.fetchone() or {}

            await cur.execute(
                "SELECT coalesce(sum(realized_amount), 0) AS tracked FROM savings_tracking WHERE org_id = %s",
                (org_id,),
            )
            tracked_row = await cur.fetchone() or {}

            await cur.execute(
                "SELECT count(*) AS pending FROM purchase_approvals WHERE org_id = %s AND status = 'pending'",
                (org_id,),
            )
            approvals_row = await cur.fetchone() or {}

        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT sku, name, unit, cost_price, sale_price, margin_pct, supplier_name, category
                FROM price_catalog
                WHERE org_id = %s AND active
                """,
                (org_id,),
            )
            catalog = await cur.fetchall()

    latest = await _fetch_latest(user, days, window_currency)
    findings: list[dict] = []
    findings.extend(_overpay_findings(latest))
    findings.extend(_margin_findings(catalog, window_currency))
    for row in exception_rows:
        count = int(row.get("total") or 0)
        if count <= 0:
            continue
        exception_type = row["type"]
        labels = {
            "price_mismatch": "Precio de factura no coincide con la referencia",
            "unit_mismatch": "Unidad de medida inconsistente",
            "missing_price": "Línea sin precio",
            "partial_import": "Importación parcial de archivo",
            "extraction_failed": "Documento sin líneas extraídas",
            "invoice_discrepancy": "Discrepancia de factura",
        }
        severity = "medium" if exception_type in {"partial_import", "missing_price"} else "high"
        findings.append(
            {
                "category": "invoice_discrepancy",
                "category_label": "Diferencias de factura",
                "severity": severity,
                "title": f"{count} {labels.get(exception_type, exception_type)} sin conciliar",
                "detail": "Estas diferencias deben revisarse antes de pagar o cargar la factura al ERP.",
                "supplier": None,
                "reference_supplier": None,
                "sku": None,
                "product": labels.get(exception_type, exception_type),
                "unit": None,
                "currency": window_currency,
                "current_price": None,
                "reference_price": None,
                "gap_pct": None,
                "quantity": count,
                "savings": 0,
                "action": "Abre la bandeja de excepciones, valida contra la orden de compra y resuelve.",
                "evidence": {"type": exception_type, "count": count},
            }
        )
    findings.extend(
        _review_findings(
            int(review_row.get("pending_total") or 0),
            int(review_row.get("stale_pending") or 0),
            window_currency,
        )
    )

    for index, finding in enumerate(findings, start=1):
        finding["id"] = f"{finding['category']}-{index}"

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda item: (severity_rank.get(item["severity"], 9), -item["savings"]))
    findings = findings[:MAX_FINDINGS]

    by_category: dict[str, float] = defaultdict(float)
    for finding in findings:
        by_category[finding["category"]] += _f(finding["savings"])
    potential = sum(by_category.values())
    spend = _f(coverage.get("spend"))
    realized = _f(realized_row.get("realized")) + _f(tracked_row.get("tracked"))

    action_plan = _action_plan(by_category, findings)
    counts = {key: 0 for key in ("critical", "high", "medium", "low")}
    for finding in findings:
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "window_days": days,
        "currency": window_currency,
        "coverage": {
            "documents": int(coverage.get("documents") or 0),
            "items": int(coverage.get("items") or 0),
            "suppliers": int(coverage.get("suppliers") or 0),
            "catalog_items": catalog_count,
            "pending_review": int(review_row.get("pending_total") or 0),
            "first_date": _iso(coverage.get("first_date")),
            "last_date": _iso(coverage.get("last_date")),
        },
        "summary": {
            "potential_savings": _round(potential),
            "realized_savings": _round(realized),
            "spend_total": _round(spend),
            "leakage_pct": _round(potential / spend * 100, 1) if spend > 0 else 0.0,
            "findings_total": len(findings),
            "critical": counts.get("critical", 0),
            "high": counts.get("high", 0),
            "medium": counts.get("medium", 0),
            "low": counts.get("low", 0),
            "price_overpay": _round(by_category.get("price_overpay", 0)),
            "margin_bleed": _round(by_category.get("margin_bleed", 0)),
            "invoice_discrepancy": _round(by_category.get("invoice_discrepancy", 0)),
            "pending_approvals": int(approvals_row.get("pending") or 0),
        },
        "findings": findings,
        "action_plan": action_plan,
        "assumptions": [
            "Los ahorros de precio usan el volumen de la última compra registrada.",
            "El margen bajo se estima por unidad de catálogo, no por ventas históricas.",
            f"Solo se consideran movimientos de los últimos {days} días en {window_currency}.",
            "Los datos de demostración están marcados y no representan compras reales.",
        ],
    }


def _action_plan(by_category: dict[str, float], findings: list[dict]) -> list[dict]:
    plan: list[dict] = []
    if by_category.get("price_overpay", 0) > 0:
        plan.append(
            {
                "priority": "alta",
                "title": "Negociar los productos con mayor sobrecosto",
                "detail": (
                    "Toma los 5 hallazgos de precio con mayor ahorro, pide cotización a los "
                    "proveedores más baratos y renegocia con los actuales."
                ),
                "owner_role": "Compras",
                "expected_saving": _round(by_category["price_overpay"]),
            }
        )
    if by_category.get("margin_bleed", 0) > 0:
        plan.append(
            {
                "priority": "alta",
                "title": "Corregir márgenes bajo el objetivo",
                "detail": (
                    "Ajusta la lista de precios de los productos con margen bajo o negativo y "
                    "renegocia el costo de los que no resisten un alza."
                ),
                "owner_role": "Gerencia comercial",
                "expected_saving": _round(by_category["margin_bleed"]),
            }
        )
    invoice_findings = [item for item in findings if item["category"] == "invoice_discrepancy"]
    if invoice_findings:
        plan.append(
            {
                "priority": "media",
                "title": "Conciliar facturas antes de pagar",
                "detail": (
                    "Revisa las diferencias de precio y unidad pendientes. Cada factura no "
                    "conciliada puede transformarse en un sobrepago permanente."
                ),
                "owner_role": "Administración",
                "expected_saving": 0,
            }
        )
    review_findings = [item for item in findings if item["category"] == "review_backlog"]
    if review_findings:
        plan.append(
            {
                "priority": "media",
                "title": "Limpiar la bandeja de revisión",
                "detail": (
                    "Resuelve los ítems con más de 7 días pendientes para que la comparación "
                    "de precios tenga cobertura completa."
                ),
                "owner_role": "Analista de compras",
                "expected_saving": 0,
            }
        )
    if not plan:
        plan.append(
            {
                "priority": "baja",
                "title": "Mantener la disciplina de carga",
                "detail": (
                    "No se detectaron fugas con los datos actuales. Carga facturas y listas de "
                    "precios cada semana para sostener la comparación."
                ),
                "owner_role": "Compras",
                "expected_saving": 0,
            }
        )
    return plan


async def build_comparator(user: dict, search: str | None = None, limit: int = 40) -> dict:
    currency = (user.get("default_currency") or "CLP").strip().upper()
    latest = await _fetch_latest(user, 90, currency, search)
    groups = _group_latest(latest)

    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT sku, name, unit, cost_price, sale_price, margin_pct, supplier_name, category
                FROM price_catalog
                WHERE org_id = %s AND active
                """,
                (user["org_id"],),
            )
            catalog = await cur.fetchall()

    by_sku = {str(row["sku"]).lower(): row for row in catalog}
    by_name = {str(row["name"]).strip().lower(): row for row in catalog}

    comparisons: list[dict] = []
    for (product_key, base_unit, _currency), group in groups.items():
        suppliers = sorted(group, key=lambda row: _f(row["price"]))
        best = suppliers[0]
        worst = suppliers[-1]
        best_price = _f(best["price"])
        worst_price = _f(worst["price"])
        spread = (worst_price - best_price) / best_price * 100 if best_price > 0 else 0.0
        catalog_row = by_sku.get(str(product_key).lower()) or by_name.get(
            str(best["description"]).strip().lower()
        )
        comparisons.append(
            {
                "product": best["description"],
                "sku": best.get("sku") or (catalog_row or {}).get("sku"),
                "unit": base_unit,
                "category": (catalog_row or {}).get("category"),
                "suppliers": [
                    {
                        "name": row["supplier_name"],
                        "price": _round(_f(row["price"]), 2),
                        "date": _iso(row.get("price_date")),
                    }
                    for row in suppliers
                ],
                "best_supplier": best["supplier_name"],
                "best_price": _round(best_price, 2),
                "worst_supplier": worst["supplier_name"],
                "worst_price": _round(worst_price, 2),
                "spread_pct": _round(spread, 1),
                "catalog": (
                    {
                        "sku": catalog_row.get("sku"),
                        "cost_price": _round(_f(catalog_row.get("cost_price")), 2),
                        "sale_price": _round(_f(catalog_row.get("sale_price")), 2),
                        "margin_pct": _round(_f(catalog_row.get("margin_pct")), 2),
                    }
                    if catalog_row
                    else None
                ),
            }
        )

    comparisons.sort(key=lambda item: item["spread_pct"], reverse=True)
    return {
        "currency": currency,
        "window_days": 90,
        "total": len(comparisons),
        "items": comparisons[: max(1, min(limit, 100))],
    }


async def build_negotiation(user: dict, limit: int = 25) -> dict:
    currency = (user.get("default_currency") or "CLP").strip().upper()
    latest = await _fetch_latest(user, 90, currency)
    groups = _group_latest(latest)

    suppliers: dict[str, dict] = {}
    for (_product_key, base_unit, _currency), group in groups.items():
        if len(group) < 2:
            continue
        cheapest = min(group, key=lambda row: _f(row["price"]))
        min_price = _f(cheapest["price"])
        if min_price <= 0:
            continue
        target_price = min_price * 1.02
        for row in group:
            current = _f(row["price"])
            if current <= min_price * 1.03:
                continue
            quantity = _f(row.get("quantity")) or 1.0
            gap_pct = (current - target_price) / target_price * 100
            saving = max((current - target_price) * quantity, 0.0)
            supplier_name = row["supplier_name"]
            bucket = suppliers.setdefault(
                supplier_name,
                {
                    "supplier": supplier_name,
                    "items": [],
                    "current_total": 0.0,
                    "target_total": 0.0,
                    "estimated_savings": 0.0,
                },
            )
            bucket["items"].append(
                {
                    "product": row["description"],
                    "sku": row.get("sku"),
                    "unit": base_unit,
                    "current_price": _round(current, 2),
                    "target_price": _round(target_price, 2),
                    "best_supplier": cheapest["supplier_name"],
                    "gap_pct": _round(gap_pct, 1),
                    "quantity": _round(quantity, 2),
                    "estimated_savings": _round(saving),
                }
            )
            bucket["current_total"] += current * quantity
            bucket["target_total"] += target_price * quantity
            bucket["estimated_savings"] += saving

    ordered = sorted(suppliers.values(), key=lambda item: item["estimated_savings"], reverse=True)
    total = sum(item["estimated_savings"] for item in ordered)
    for item in ordered:
        item["items"].sort(key=lambda line: line["estimated_savings"], reverse=True)
        item["items"] = item["items"][:limit]
        item["current_total"] = _round(item["current_total"])
        item["target_total"] = _round(item["target_total"])
        item["estimated_savings"] = _round(item["estimated_savings"])

    return {
        "currency": currency,
        "window_days": 90,
        "generated_at": datetime.now(UTC).isoformat(),
        "total_estimated_savings": _round(total),
        "suppliers": ordered[:limit],
        "note": (
            "Precio objetivo = mejor precio vigente + 2%. Los montos usan el volumen de la "
            "última compra registrada de cada producto."
        ),
    }


async def build_weekly_report(user: dict) -> dict:
    currency = (user.get("default_currency") or "CLP").strip().upper()
    audit = await build_audit(user, days=7, currency=currency)

    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    count(*) FILTER (WHERE status = 'processed') AS processed,
                    count(*) FILTER (WHERE status = 'failed') AS failed
                FROM documents_log
                WHERE org_id = %s AND created_at >= now() - interval '7 days'
                """,
                (user["org_id"],),
            )
            docs = await cur.fetchone() or {}
            await cur.execute(
                """
                SELECT count(*) AS resolved
                FROM exceptions_log
                WHERE org_id = %s AND status IN ('resolved', 'approved')
                  AND resolved_at >= now() - interval '7 days'
                """,
                (user["org_id"],),
            )
            resolved = await cur.fetchone() or {}
            await cur.execute(
                """
                SELECT count(*) AS pending
                FROM purchase_approvals
                WHERE org_id = %s AND status = 'pending'
                """,
                (user["org_id"],),
            )
            approvals = await cur.fetchone() or {}

    top = audit["findings"][:3]
    highlights = [f"{item['title']} (ahorro estimado {item['savings']:,.0f} {currency})" for item in top]
    if not highlights:
        highlights = ["Sin fugas nuevas detectadas esta semana."]
    highlights.append(f"{int(docs.get('processed') or 0)} documentos procesados en los últimos 7 días.")
    if int(resolved.get("resolved") or 0) > 0:
        highlights.append(f"{int(resolved.get('resolved') or 0)} excepciones resueltas esta semana.")

    return {
        "period_days": 7,
        "generated_at": datetime.now(UTC).isoformat(),
        "currency": currency,
        "summary": {
            **audit["summary"],
            "documents_processed": int(docs.get("processed") or 0),
            "documents_failed": int(docs.get("failed") or 0),
            "exceptions_resolved": int(resolved.get("resolved") or 0),
            "approvals_pending": int(approvals.get("pending") or 0),
        },
        "highlights": highlights,
        "top_findings": top,
        "coverage": audit["coverage"],
    }


def _slug_sku(description: str) -> str:
    digest = hashlib.sha1(description.strip().lower().encode("utf-8")).hexdigest()[:10].upper()
    base = re.sub(r"[^A-Z0-9]+", "-", description.upper())[:18].strip("-")
    return f"RCV-{base}-{digest}" if base else f"RCV-{digest}"


async def rcv_import(
    user: dict,
    content: bytes,
    filename: str,
    *,
    apply: bool = False,
) -> dict:
    parsed = await asyncio.to_thread(extract_tabular_document, content, filename)
    if parsed is None:
        raise ValueError(
            "No se reconoció una tabla de RCV. El archivo debe tener columnas de producto y precio."
        )
    document, metadata = parsed
    currency = (document.currency or user.get("default_currency") or "CLP").strip().upper()
    org_id = user["org_id"]

    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, sku, name, cost_price, sale_price
                FROM price_catalog
                WHERE org_id = %s
                """,
                (org_id,),
            )
            catalog = await cur.fetchall()
        by_sku = {str(row["sku"]).strip().lower(): row for row in catalog}
        by_name = {str(row["name"]).strip().lower(): row for row in catalog}

        rows: list[dict] = []
        counts = {"nuevos": 0, "actualizados": 0, "sin_cambio": 0, "discrepancias": 0, "sin_precio": 0}

        async with conn.transaction():
            for index, item in enumerate(document.items[:5000], start=1):
                price = float(item.unit_price) if item.unit_price is not None else None
                description = item.description
                if price is None:
                    counts["sin_precio"] += 1
                    rows.append(
                        {
                            "line": index,
                            "sku": item.sku,
                            "product": description,
                            "unit": item.unit,
                            "rcv_price": None,
                            "catalog_cost": None,
                            "difference_pct": None,
                            "status": "sin_precio",
                        }
                    )
                    continue

                sku = str(item.sku or "").strip()
                match = by_sku.get(sku.lower()) if sku else None
                if match is None:
                    match = by_name.get(description.strip().lower())

                if match is None:
                    status = "nuevo"
                    counts["nuevos"] += 1
                    if apply:
                        new_sku = sku or _slug_sku(description)
                        cost = Decimal(str(round(price, 4)))
                        sale = (cost * Decimal("1.25")).quantize(Decimal("0.01"))
                        await cur.execute(
                            """
                            INSERT INTO price_catalog (
                                org_id, sku, name, unit, cost_price, sale_price, supplier_name
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (org_id, sku) DO UPDATE SET
                                name = EXCLUDED.name,
                                cost_price = EXCLUDED.cost_price,
                                supplier_name = coalesce(EXCLUDED.supplier_name, price_catalog.supplier_name),
                                updated_at = now()
                            """,
                            (
                                org_id,
                                new_sku,
                                description,
                                item.unit or "unidad",
                                cost,
                                sale,
                                document.supplier_name,
                            ),
                        )
                        by_sku[new_sku.lower()] = {
                            "sku": new_sku,
                            "name": description,
                            "cost_price": cost,
                            "sale_price": sale,
                        }
                    rows.append(
                        {
                            "line": index,
                            "sku": sku or None,
                            "product": description,
                            "unit": item.unit,
                            "rcv_price": _round(price, 2),
                            "catalog_cost": None,
                            "difference_pct": None,
                            "status": status,
                        }
                    )
                    continue

                catalog_cost = _f(match["cost_price"])
                difference = (
                    (price - catalog_cost) / catalog_cost * 100 if catalog_cost > 0 else None
                )
                if difference is None:
                    status = "nuevo"
                elif abs(difference) <= 1.0:
                    status = "sin_cambio"
                else:
                    status = "discrepancia"
                    counts["discrepancias"] += 1
                if status == "sin_cambio":
                    counts["sin_cambio"] += 1

                if apply and difference is not None and abs(difference) > 1.0:
                    await cur.execute(
                        """
                        UPDATE price_catalog
                        SET cost_price = %s,
                            supplier_name = coalesce(%s, supplier_name),
                            updated_at = now()
                        WHERE id = %s AND org_id = %s
                        """,
                        (Decimal(str(round(price, 4))), document.supplier_name, match["id"], org_id),
                    )
                    status = "actualizado"
                    counts["actualizados"] += 1
                elif apply and difference is None:
                    await cur.execute(
                        """
                        UPDATE price_catalog
                        SET cost_price = %s, updated_at = now()
                        WHERE id = %s AND org_id = %s
                        """,
                        (Decimal(str(round(price, 4))), match["id"], org_id),
                    )
                    status = "actualizado"
                    counts["actualizados"] += 1

                rows.append(
                    {
                        "line": index,
                        "sku": match["sku"],
                        "product": description,
                        "unit": item.unit,
                        "rcv_price": _round(price, 2),
                        "catalog_cost": _round(catalog_cost, 2),
                        "difference_pct": _round(difference, 1) if difference is not None else None,
                        "status": status,
                    }
                )

            if apply:
                await repositories.record_audit_event(
                    conn,
                    org_id=org_id,
                    user_id=user["id"],
                    action="leaks.rcv.import",
                    entity_type="price_catalog",
                    entity_id=document.supplier_name or filename,
                    metadata={"rows": len(rows), "counts": counts, "filename": filename},
                )

    return {
        "filename": filename,
        "supplier": document.supplier_name,
        "currency": currency,
        "applied": apply,
        "total_rows": len(rows),
        "counts": counts,
        "truncated": bool(metadata.get("truncated")),
        "warnings": metadata.get("warnings") or [],
        "rows": rows[:500],
    }


def audit_to_pdf(audit: dict, org_name: str = "") -> bytes:
    from src.services.export_service import build_pdf

    headers = [
        "Severidad",
        "Categoría",
        "Hallazgo",
        "Proveedor",
        "Actual",
        "Referencia",
        "Ahorro estimado",
    ]
    rows = []
    for finding in audit["findings"]:
        rows.append(
            [
                finding["severity"],
                finding["category_label"],
                finding["title"],
                finding.get("supplier") or "—",
                finding.get("current_price") if finding.get("current_price") is not None else "—",
                finding.get("reference_price") if finding.get("reference_price") is not None else "—",
                finding["savings"],
            ]
        )
    summary = audit["summary"]
    subtitle = (
        f"{org_name + ' · ' if org_name else ''}Ventana {audit['window_days']} días · "
        f"Moneda {audit['currency']} · Ahorro potencial {summary['potential_savings']:,.0f} "
        f"· {summary['findings_total']} hallazgos"
    )
    return build_pdf("Auditoría Express de Fugas y Sobrecostos", subtitle, headers, rows)
