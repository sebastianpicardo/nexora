from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.api.deps import CurrentUser, require_roles
from src.core.config import settings
from src.db import repositories
from src.db.pool import get_pool
from src.services import savings_report_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/insights", tags=["insights"])


def _empty_analytics(currency: str, months: int) -> dict:
    return {
        "currency": currency,
        "months": months,
        "summary": {
            "products": 0,
            "suppliers": 0,
            "items": 0,
            "avg_confidence": 0.0,
            "price_index": 100.0,
            "price_index_products": 0,
            "price_index_basis": "sin datos suficientes",
            "price_change_pct": 0.0,
        },
        "monthly": [],
        "top_increases": [],
    }


def _empty_opportunities(currency: str) -> dict:
    return {
        "currency": currency,
        "days": 90,
        "min_overprice_pct": 10.0,
        "min_samples": settings.min_history_samples,
        "summary": {
            "opportunities": 0,
            "total_items": 0,
            "data_available": False,
            "total_potential_savings": 0.0,
            "total_conservative_savings": 0.0,
            "total_excess_cost": 0.0,
            "suppliers_affected": 0,
        },
        "top_suppliers": [],
        "items": [],
    }


def _empty_forecast(currency: str) -> dict:
    return {
        "currency": currency,
        "history_months": 6,
        "horizon": 1,
        "summary": {
            "products": 0,
            "projected_spend": 0.0,
            "products_rising": 0,
            "products_falling": 0,
            "skipped_low_history": 0,
        },
        "items": [],
    }


def _empty_approvals(currency: str) -> dict:
    return {
        "currency": currency,
        "threshold": 0.9,
        "days": 120,
        "max_amount": settings.auto_approve_max_amount,
        "summary": {
            "pending": 0,
            "auto_eligible": 0,
            "needs_review": 0,
            "auto_amount": 0.0,
            "review_amount": 0.0,
        },
        "items": [],
    }


def _warning_for(section: str, exc: Exception) -> str:
    message = str(exc).lower()
    if "undefinedtable" in message or "does not exist" in message or "undefinedcolumn" in message:
        return (
            f"No pudimos calcular {section} porque falta una tabla o columna en la base de datos. "
            "Aplica las migraciones pendientes de Supabase y vuelve a intentar."
        )
    return f"No pudimos calcular {section}. El resto del panel sigue disponible."


async def _safe_section(conn, label: str, awaitable, fallback, warnings: list[str]):
    try:
        async with conn.transaction():
            return await awaitable
    except Exception as exc:  # noqa: BLE001 - la sección se degrada sin tumbar el panel
        logger.exception("Error calculando sección de insights: %s", label)
        warnings.append(_warning_for(label, exc))
        return fallback


async def _verified_report(user: dict, month: str | None) -> dict:
    try:
        return await savings_report_service.build_verified_report(user, month=month)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error cargando ahorro verificado")
        selected = month or date.today().strftime("%Y-%m")
        return {
            "month": selected,
            "available_months": [],
            "currency": user.get("default_currency") or "CLP",
            "count": 0,
            "total_amount": 0.0,
            "items": [],
            "warnings": [_warning_for("el ahorro verificado", exc)],
            "note": "No se pudo leer la evidencia histórica en este momento.",
        }


class SavingsTrackingRequest(BaseModel):
    opportunity_key: str = Field(min_length=1, max_length=240)
    status: str = Field(default="identified")
    realized_amount: float = Field(default=0.0, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=1000)
    title: str | None = Field(default=None, max_length=240)
    sku: str | None = Field(default=None, max_length=120)
    product: str | None = Field(default=None, max_length=300)
    supplier_before: str | None = Field(default=None, max_length=200)
    supplier_after: str | None = Field(default=None, max_length=200)
    document_before_id: str | None = None
    document_after_id: str | None = None
    unit_price_before: float | None = Field(default=None, ge=0)
    unit_price_after: float | None = Field(default=None, ge=0)
    quantity: float | None = Field(default=None, ge=0)
    evidence: dict | None = None


class AutoApproveRequest(BaseModel):
    threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    max_amount: float | None = Field(default=None, ge=0.0)
    item_ids: list[str] | None = None


def _currency(user: dict, override: str | None) -> str:
    return (override or user["default_currency"] or "CLP").strip().upper()


@router.get("/overview")
async def insights_overview(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    months: int = Query(default=6, ge=1, le=24),
):
    active_currency = _currency(user, currency)
    warnings: list[str] = []
    async with get_pool().connection() as conn:
        analytics = await _safe_section(
            conn,
            "la analítica de gasto",
            repositories.analytics_overview(
                conn, user["org_id"], currency=active_currency, months=months
            ),
            _empty_analytics(active_currency, months),
            warnings,
        )
        opportunities = await _safe_section(
            conn,
            "las oportunidades de ahorro",
            repositories.price_opportunities(
                conn,
                user["org_id"],
                currency=active_currency,
                days=90,
                min_overprice_pct=10.0,
                min_samples=settings.min_history_samples,
                limit=5,
            ),
            _empty_opportunities(active_currency),
            warnings,
        )
        forecast = await _safe_section(
            conn,
            "el pronóstico de compras",
            repositories.consumption_forecast(
                conn,
                user["org_id"],
                currency=active_currency,
                history_months=6,
                horizon=1,
                limit=5,
            ),
            _empty_forecast(active_currency),
            warnings,
        )
        queue = await _safe_section(
            conn,
            "la cola de aprobaciones",
            repositories.approval_queue(
                conn,
                user["org_id"],
                currency=active_currency,
                threshold=0.9,
                days=120,
                max_amount=settings.auto_approve_max_amount,
            ),
            _empty_approvals(active_currency),
            warnings,
        )
    return {
        "currency": active_currency,
        "months": months,
        "partial": bool(warnings),
        "warnings": warnings,
        "analytics": analytics,
        "opportunities": {
            "summary": opportunities["summary"],
            "top_suppliers": opportunities["top_suppliers"],
            "items": opportunities["items"],
        },
        "forecast": {
            "summary": forecast["summary"],
            "items": forecast["items"],
        },
        "approvals": {
            "summary": queue["summary"],
            "items": [item for item in queue["items"] if item.get("auto_eligible")][:5],
        },
    }


@router.get("/opportunities")
async def price_opportunities(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    days: int = Query(default=90, ge=1, le=730),
    min_overprice_pct: float = Query(default=10.0, ge=0, le=1000),
    limit: int = Query(default=100, ge=1, le=500),
):
    active_currency = _currency(user, currency)
    warnings: list[str] = []
    async with get_pool().connection() as conn:
        data = await _safe_section(
            conn,
            "las oportunidades de ahorro",
            repositories.price_opportunities(
                conn,
                user["org_id"],
                currency=active_currency,
                days=days,
                min_overprice_pct=min_overprice_pct,
                min_samples=settings.min_history_samples,
                limit=limit,
            ),
            _empty_opportunities(active_currency),
            warnings,
        )
    data["partial"] = bool(warnings)
    data["warnings"] = warnings
    return data


@router.get("/forecast")
async def consumption_forecast(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    history_months: int = Query(default=6, ge=2, le=24),
    horizon: int = Query(default=1, ge=1, le=6),
    limit: int = Query(default=100, ge=1, le=500),
):
    active_currency = _currency(user, currency)
    warnings: list[str] = []
    async with get_pool().connection() as conn:
        data = await _safe_section(
            conn,
            "el pronóstico de compras",
            repositories.consumption_forecast(
                conn,
                user["org_id"],
                currency=active_currency,
                history_months=history_months,
                horizon=horizon,
                limit=limit,
            ),
            _empty_forecast(active_currency),
            warnings,
        )
    data["partial"] = bool(warnings)
    data["warnings"] = warnings
    return data


@router.get("/analytics")
async def analytics(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    months: int = Query(default=6, ge=1, le=24),
):
    active_currency = _currency(user, currency)
    warnings: list[str] = []
    async with get_pool().connection() as conn:
        data = await _safe_section(
            conn,
            "la analítica de gasto",
            repositories.analytics_overview(
                conn, user["org_id"], currency=active_currency, months=months
            ),
            _empty_analytics(active_currency, months),
            warnings,
        )
    data["partial"] = bool(warnings)
    data["warnings"] = warnings
    return data


@router.get("/approvals")
async def approval_queue(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    threshold: float = Query(default=0.9, ge=0, le=1),
    days: int = Query(default=120, ge=1, le=730),
):
    active_currency = _currency(user, currency)
    warnings: list[str] = []
    async with get_pool().connection() as conn:
        data = await _safe_section(
            conn,
            "la cola de aprobaciones",
            repositories.approval_queue(
                conn,
                user["org_id"],
                currency=active_currency,
                threshold=threshold,
                days=days,
                max_amount=settings.auto_approve_max_amount,
            ),
            _empty_approvals(active_currency),
            warnings,
        )
    data["partial"] = bool(warnings)
    data["warnings"] = warnings
    return data


@router.post("/savings/track")
async def track_savings(
    payload: SavingsTrackingRequest,
    user: dict = Depends(require_roles("owner", "admin", "analyst")),
):
    active_currency = (payload.currency or user["default_currency"] or "CLP").strip().upper()
    realized = payload.realized_amount
    if (
        payload.status == "realized"
        and realized <= 0
        and payload.unit_price_before is not None
        and payload.unit_price_after is not None
        and payload.quantity
    ):
        realized = round(abs(payload.unit_price_before - payload.unit_price_after) * payload.quantity, 2)
    evidence = {
        **(payload.evidence or {}),
        "source": (payload.evidence or {}).get("source", "manual"),
        "verified": payload.status == "realized",
    }
    async with get_pool().connection() as conn:
        row = await repositories.record_savings_tracking(
            conn,
            org_id=user["org_id"],
            opportunity_key=payload.opportunity_key,
            status=payload.status,
            realized_amount=realized,
            currency=active_currency,
            notes=payload.notes,
            title=payload.title,
            sku=payload.sku,
            product=payload.product,
            supplier_before=payload.supplier_before,
            supplier_after=payload.supplier_after,
            document_before_id=payload.document_before_id,
            document_after_id=payload.document_after_id,
            unit_price_before=payload.unit_price_before,
            unit_price_after=payload.unit_price_after,
            quantity=payload.quantity,
            evidence=evidence,
        )
    return {"success": True, "tracking": row}


@router.get("/savings")
async def list_savings(user: CurrentUser, status_filter: str | None = Query(default=None, alias="status")):
    async with get_pool().connection() as conn:
        items = await repositories.list_savings_tracking(conn, user["org_id"], status=status_filter)
        summary = await repositories.summarize_savings_tracking(conn, user["org_id"])
    return {"items": items, "summary": summary}


@router.get("/savings/verified")
async def verified_savings(
    user: CurrentUser,
    month: str | None = Query(default=None, max_length=7),
):
    try:
        return await _verified_report(user, month)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/savings/verified.csv")
async def verified_savings_csv(
    user: CurrentUser,
    month: str | None = Query(default=None, max_length=7),
):
    try:
        report = await _verified_report(user, month)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    content = savings_report_service.report_to_csv(report)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="ahorro_verificado_{report["month"]}.csv"'
        },
    )


@router.get("/savings/verified.pdf")
async def verified_savings_pdf(
    user: CurrentUser,
    month: str | None = Query(default=None, max_length=7),
):
    try:
        report = await _verified_report(user, month)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    content = savings_report_service.report_to_pdf(report, org_name=str(user.get("org_name") or ""))
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ahorro_verificado_{report["month"]}.pdf"'
        },
    )


@router.post("/auto-approve")
async def auto_approve(
    payload: AutoApproveRequest,
    user: dict = Depends(require_roles("owner", "admin", "analyst")),
):
    max_amount = settings.auto_approve_max_amount
    if payload.max_amount is not None:
        max_amount = min(max_amount, payload.max_amount)
    async with get_pool().connection() as conn:
        approved = await repositories.auto_approve_items(
            conn,
            user["org_id"],
            threshold=payload.threshold,
            max_amount=max_amount,
            item_ids=payload.item_ids,
        )
        if approved:
            await repositories.record_audit_event(
                conn,
                org_id=user["org_id"],
                user_id=user["id"],
                action="insights.auto_approve",
                entity_type="items_history",
                entity_id=str(user["org_id"]),
                metadata={
                    "approved": len(approved),
                    "threshold": payload.threshold,
                    "max_amount": max_amount,
                },
            )
    return {"approved": len(approved), "item_ids": approved}
