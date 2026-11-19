from __future__ import annotations

import csv
import io
import re
from datetime import date
from typing import Any

from src.db import repositories
from src.db.pool import get_pool


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _serialize(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "opportunity_key": row["opportunity_key"],
        "status": row["status"],
        "title": row.get("title"),
        "sku": row.get("sku"),
        "product": row.get("product"),
        "supplier_before": row.get("supplier_before"),
        "supplier_after": row.get("supplier_after"),
        "document_before_id": str(row["document_before_id"]) if row.get("document_before_id") else None,
        "document_after_id": str(row["document_after_id"]) if row.get("document_after_id") else None,
        "unit_price_before": float(row["unit_price_before"]) if row.get("unit_price_before") is not None else None,
        "unit_price_after": float(row["unit_price_after"]) if row.get("unit_price_after") is not None else None,
        "quantity": float(row["quantity"]) if row.get("quantity") is not None else None,
        "realized_amount": float(row["realized_amount"] or 0),
        "currency": row["currency"],
        "notes": row.get("notes"),
        "evidence": row.get("evidence") or {},
        "realized_at": _iso(row.get("realized_at") or row.get("updated_at")),
    }


async def build_verified_report(user: dict, month: str | None = None) -> dict[str, Any]:
    selected = month or date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", selected):
        raise ValueError("El período debe tener formato YYYY-MM.")
    async with get_pool().connection() as conn:
        rows = await repositories.list_verified_savings(conn, user["org_id"], month=selected)
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT DISTINCT to_char(coalesce(realized_at, updated_at), 'YYYY-MM') AS month
                FROM savings_tracking
                WHERE org_id = %s AND status = 'realized'
                ORDER BY month DESC
                """,
                (user["org_id"],),
            )
            available = [row["month"] for row in await cur.fetchall()]

    items = [_serialize(row) for row in rows]
    total = sum(item["realized_amount"] for item in items)
    currency = items[0]["currency"] if items else (user.get("default_currency") or "CLP")
    return {
        "month": selected,
        "available_months": available,
        "currency": currency,
        "count": len(items),
        "total_amount": round(total, 2),
        "items": items,
        "note": (
            "Cada registro incluye evidencia del documento anterior y alternativo, diferencia "
            "unitaria, cantidad y ahorro total."
        ),
    }


def report_to_csv(report: dict) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(
        [
            "Fecha",
            "Producto",
            "SKU",
            "Proveedor anterior",
            "Proveedor nuevo",
            "Documento anterior",
            "Documento nuevo",
            "Precio unitario anterior",
            "Precio unitario nuevo",
            "Diferencia unitaria",
            "Cantidad",
            "Ahorro total",
            "Moneda",
            "Notas",
        ]
    )
    for item in report["items"]:
        before = item.get("unit_price_before")
        after = item.get("unit_price_after")
        difference = round(before - after, 4) if before is not None and after is not None else None
        writer.writerow(
            [
                item.get("realized_at") or "",
                item.get("product") or item.get("title") or "",
                item.get("sku") or "",
                item.get("supplier_before") or "",
                item.get("supplier_after") or "",
                item.get("document_before_id") or "",
                item.get("document_after_id") or "",
                before if before is not None else "",
                after if after is not None else "",
                difference if difference is not None else "",
                item.get("quantity") if item.get("quantity") is not None else "",
                item["realized_amount"],
                item["currency"],
                item.get("notes") or "",
            ]
        )
    writer.writerow([])
    writer.writerow(["Total ahorro verificado", report["total_amount"], report["currency"]])
    return buffer.getvalue().encode("utf-8-sig")


def report_to_pdf(report: dict, org_name: str = "") -> bytes:
    from src.services.export_service import build_pdf

    headers = ["Fecha", "Producto", "Proveedor", "Dif. unitaria", "Cantidad", "Ahorro"]
    rows = []
    for item in report["items"]:
        before = item.get("unit_price_before")
        after = item.get("unit_price_after")
        difference = round(before - after, 2) if before is not None and after is not None else "—"
        supplier = item.get("supplier_before") or "—"
        if item.get("supplier_after"):
            supplier = f"{supplier} → {item['supplier_after']}"
        rows.append(
            [
                item.get("realized_at") or "—",
                item.get("product") or item.get("title") or "—",
                supplier,
                difference,
                item.get("quantity") if item.get("quantity") is not None else "—",
                item["realized_amount"],
            ]
        )
    subtitle = (
        f"{org_name + ' · ' if org_name else ''}Período {report['month']} · "
        f"{report['count']} ahorros verificados · Total {report['total_amount']:,.0f} "
        f"{report['currency']}"
    )
    return build_pdf("Registro de Ahorro Verificado", subtitle, headers, rows)
