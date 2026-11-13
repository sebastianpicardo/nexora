from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.api.deps import CurrentUser, rate_limit
from src.core.config import settings
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
    "extraction_failed": "ExtracciÃ³n fallida",
    "pending": "Pendiente",
    "approved": "Aprobado",
    "rejected": "Rechazado",
    "resolved": "Resuelto",
    "low": "Baja",
    "medium": "Media",
    "high": "Alta",
    "critical": "CrÃ­tica",
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
    _: None = Depends(rate_limit("export", "export_rate_limit_per_minute")),
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

    headers = ["Severidad", "Tipo", "Proveedor", "Documento", "Ãtem", "SKU", "Motivo", "Estado", "Fecha"]
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
            "Excepciones de auditorÃ­a",
            f"NEXORA Â· {len(rows)} registros Â· Generado el {date.today().isoformat()}",
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
    _: None = Depends(rate_limit("export", "export_rate_limit_per_minute")),
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
        "DescripciÃ³n",
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
            f"NEXORA Â· {len(rows)} registros Â· Generado el {date.today().isoformat()}",
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


@router.get("/opportunities")
async def export_opportunities(
    user: CurrentUser,
    fmt: Literal["pdf", "xlsx"] = Query(default="xlsx", alias="format"),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    days: int = Query(default=90, ge=1, le=730),
    min_overprice_pct: float = Query(default=10.0, ge=0, le=1000),
    limit: int = Query(default=100, ge=1, le=500),
    _: None = Depends(rate_limit("export", "export_rate_limit_per_minute")),
):
    active_currency = (currency or user["default_currency"] or "CLP").strip().upper()
    async with get_pool().connection() as conn:
        result = await repositories.price_opportunities(
            conn,
            user["org_id"],
            currency=active_currency,
            days=days,
            min_overprice_pct=min_overprice_pct,
            min_samples=settings.min_history_samples,
            limit=limit,
        )

    headers = [
        "Producto comparable",
        "Proveedor",
        "Precio actual",
        "Mediana",
        "Mejor precio",
        "Mejor proveedor",
        "Sobreprecio %",
        "Ahorro conservador",
        "Ahorro potencial",
        "Muestras",
        "Fecha",
    ]
    rows = [
        [
            row.get("comparable_product") or row.get("normalized_description") or row.get("sku") or "",
            row.get("supplier_name") or "Sin proveedor",
            _money(row.get("current_price"), active_currency),
            _money(row.get("median_price"), active_currency),
            _money(row.get("best_price"), active_currency),
            row.get("best_supplier_name") or "",
            f"{float(row.get('overprice_pct') or 0):.1f}%",
            _money(row.get("savings_min"), active_currency),
            _money(row.get("potential_savings"), active_currency),
            row.get("samples") or 0,
            _date_value(row.get("price_date")),
        ]
        for row in result.get("items", [])
    ]

    if fmt == "pdf":
        content = build_pdf(
            "Oportunidades de ahorro",
            f"NEXORA · {len(rows)} oportunidades · Generado el {date.today().isoformat()}",
            headers,
            rows,
            column_widths=[
                42 * 2.5,
                34 * 2.5,
                24 * 2.5,
                24 * 2.5,
                24 * 2.5,
                34 * 2.5,
                20 * 2.5,
                26 * 2.5,
                26 * 2.5,
                16 * 2.5,
                22 * 2.5,
            ],
        )
    else:
        content = build_excel("Oportunidades", headers, rows)
    return _file_response(content, fmt, "oportunidades")


@router.post("/opportunities/share")
async def share_opportunities(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    days: int = Query(default=90, ge=1, le=730),
    min_overprice_pct: float = Query(default=10.0, ge=0, le=1000),
    limit: int = Query(default=100, ge=1, le=500),
    expires_hours: int = Query(default=168, ge=1, le=720),
):
    serializer = URLSafeTimedSerializer(settings.session_secret or settings.jwt_secret)
    token = serializer.dumps(
        {
            "org_id": str(user["org_id"]),
            "currency": (currency or user["default_currency"] or "CLP").strip().upper(),
            "days": days,
            "min_overprice_pct": min_overprice_pct,
            "limit": limit,
        }
    )
    return {
        "share_url": f"/api/exports/opportunities/shared/{token}",
        "expires_in_hours": expires_hours,
    }


@router.get("/opportunities/shared/{token}")
async def shared_opportunities(
    token: str,
    fmt: Literal["pdf", "xlsx"] = Query(default="pdf", alias="format"),
):
    serializer = URLSafeTimedSerializer(settings.session_secret or settings.jwt_secret)
    try:
        data = serializer.loads(token, max_age=7 * 24 * 3600)
    except SignatureExpired:
        raise HTTPException(status_code=410, detail="El enlace compartido expiró.") from None
    except BadSignature:
        raise HTTPException(status_code=404, detail="Enlace compartido inválido.") from None

    async with get_pool().connection() as conn:
        result = await repositories.price_opportunities(
            conn,
            data["org_id"],
            currency=data["currency"],
            days=data["days"],
            min_overprice_pct=data["min_overprice_pct"],
            min_samples=settings.min_history_samples,
            limit=data["limit"],
        )

    headers = [
        "Producto comparable",
        "Proveedor",
        "Precio actual",
        "Mediana",
        "Mejor precio",
        "Mejor proveedor",
        "Sobreprecio %",
        "Ahorro conservador",
        "Ahorro potencial",
        "Muestras",
        "Fecha",
    ]
    rows = [
        [
            row.get("comparable_product") or row.get("normalized_description") or row.get("sku") or "",
            row.get("supplier_name") or "Sin proveedor",
            _money(row.get("current_price"), data["currency"]),
            _money(row.get("median_price"), data["currency"]),
            _money(row.get("best_price"), data["currency"]),
            row.get("best_supplier_name") or "",
            f"{float(row.get('overprice_pct') or 0):.1f}%",
            _money(row.get("savings_min"), data["currency"]),
            _money(row.get("potential_savings"), data["currency"]),
            row.get("samples") or 0,
            _date_value(row.get("price_date")),
        ]
        for row in result.get("items", [])
    ]

    if fmt == "pdf":
        content = build_pdf(
            "Oportunidades de ahorro",
            f"NEXORA · {len(rows)} oportunidades · Enlace compartido",
            headers,
            rows,
            column_widths=[
                42 * 2.5,
                34 * 2.5,
                24 * 2.5,
                24 * 2.5,
                24 * 2.5,
                34 * 2.5,
                20 * 2.5,
                26 * 2.5,
                26 * 2.5,
                16 * 2.5,
                22 * 2.5,
            ],
        )
    else:
        content = build_excel("Oportunidades", headers, rows)
    return _file_response(content, fmt, "oportunidades-compartidas")
