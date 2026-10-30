from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import Response

from src.api.deps import CurrentUser
from src.db import repositories
from src.db.pool import get_pool
from src.services.export_service import build_excel, build_pdf

router = APIRouter(prefix="/api/exports", tags=["exports"])

EXCEPTION_LABELS = {
    "low_confidence": "Baja confianza",
    "price_spike": "Alza de precio",
    "unit_mismatch": "Unidad inconsistente",
    "price_mismatch": "Total inconsistente",
    "missing_price": "Precio faltante",
    "extraction_failed": "Extracción fallida",
    "pending": "Pendiente",
    "approved": "Aprobado",
    "rejected": "Rechazado",
    "resolved": "Resuelto",
    "low": "Baja",
    "medium": "Media",
    "high": "Alta",
    "critical": "Crítica",
}

ITEM_LABELS = {
    "auto_approved": "Auto-aprobado",
    "pending": "Pendiente",
    "approved": "Aprobado",
    "rejected": "Rechazado",
}


def _date_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _money(value, currency: str | None) -> str:
    if value is None:
        return ""
    return f"{currency or ''} {float(value):,.2f}".strip()


def _file_response(content: bytes, fmt: str, name: str) -> Response:
    if fmt == "pdf":
        media_type = "application/pdf"
        extension = "pdf"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        extension = "xlsx"
    filename = f"nexora-{name}-{date.today().isoformat()}.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/exceptions")
async def export_exceptions(
    user: CurrentUser,
    fmt: Literal["pdf", "xlsx"] = Query(default="xlsx", alias="format"),
    status_filter: str | None = Query(default=None, alias="status"),
    type_filter: str | None = Query(default=None, alias="type"),
    severity: str | None = Query(default=None),
):
    async with get_pool().connection() as conn:
        result = await repositories.list_exceptions(
            conn,
            user["org_id"],
            status=status_filter,
            type=type_filter,
            severity=severity,
            page=1,
            page_size=2000,
        )

    headers = ["Severidad", "Tipo", "Proveedor", "Documento", "Ítem", "SKU", "Motivo", "Estado", "Fecha"]
    rows = [
        [
            EXCEPTION_LABELS.get(row["severity"], row["severity"]),
            EXCEPTION_LABELS.get(row["type"], row["type"]),
            row.get("supplier_name") or "Sin proveedor",
            row.get("document_filename") or "",
            row.get("item_description") or "Documento completo",
            row.get("item_sku") or "",
            row.get("reason") or "",
            EXCEPTION_LABELS.get(row["status"], row["status"]),
            _date_value(row.get("created_at")),
        ]
        for row in result["items"]
    ]

    if fmt == "pdf":
        content = build_pdf(
            "Excepciones de auditoría",
            f"NEXORA · {len(rows)} registros · Generado el {date.today().isoformat()}",
            headers,
            rows,
            column_widths=[20 * 2.5, 32 * 2.5, 34 * 2.5, 38 * 2.5, 48 * 2.5, 18 * 2.5, 70 * 2.5, 22 * 2.5, 22 * 2.5],
        )
    else:
        content = build_excel("Excepciones", headers, rows)
    return _file_response(content, fmt, "excepciones")


@router.get("/items")
async def export_items(
    user: CurrentUser,
    fmt: Literal["pdf", "xlsx"] = Query(default="xlsx", alias="format"),
    supplier_id: UUID | None = Query(default=None),
    review_status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
):
    async with get_pool().connection() as conn:
        result = await repositories.list_items(
            conn,
            user["org_id"],
            supplier_id=supplier_id,
            review_status=review_status,
            date_from=date_from,
            date_to=date_to,
            search=search,
            page=1,
            page_size=5000,
        )

    headers = [
        "Fecha",
        "Proveedor",
        "SKU",
        "Descripción",
        "Unidad original",
        "Cantidad",
        "Precio original",
        "Precio normalizado",
        "Unidad base",
        "Confianza",
        "Estado",
    ]
    rows = [
        [
            _date_value(row.get("price_date")),
            row.get("supplier_name") or "Sin proveedor",
            row.get("sku") or "",
            row.get("original_description") or "",
            row.get("original_unit") or "",
            row.get("quantity") or "",
            _money(row.get("original_unit_price"), row.get("currency")),
            _money(row.get("normalized_unit_price"), row.get("currency")),
            row.get("base_unit") or "",
            f"{round(float(row.get('confidence') or 0) * 100)}%",
            ITEM_LABELS.get(row["review_status"], row["review_status"]),
        ]
        for row in result["items"]
    ]

    if fmt == "pdf":
        content = build_pdf(
            "Precios auditados",
            f"NEXORA · {len(rows)} registros · Generado el {date.today().isoformat()}",
            headers,
            rows,
            column_widths=[
                20 * 2.5,
                34 * 2.5,
                18 * 2.5,
                60 * 2.5,
                28 * 2.5,
                18 * 2.5,
                26 * 2.5,
                30 * 2.5,
                22 * 2.5,
                18 * 2.5,
                24 * 2.5,
            ],
        )
    else:
        content = build_excel("Precios", headers, rows)
    return _file_response(content, fmt, "precios")
