from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.deps import CurrentUser, require_roles
from src.core.config import settings
from src.db import repositories
from src.db.pool import get_pool

router = APIRouter(prefix="/api/insights", tags=["insights"])


class SavingsTrackingRequest(BaseModel):
    opportunity_key: str = Field(min_length=1, max_length=240)
    status: str = Field(default="identified")
    realized_amount: float = Field(default=0.0, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=1000)


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
    async with get_pool().connection() as conn:
        analytics = await repositories.analytics_overview(
            conn, user["org_id"], currency=active_currency, months=months
        )
        opportunities = await repositories.price_opportunities(
            conn,
            user["org_id"],
            currency=active_currency,
            days=90,
            min_overprice_pct=10.0,
            min_samples=settings.min_history_samples,
            limit=5,
        )
        forecast = await repositories.consumption_forecast(
            conn,
            user["org_id"],
            currency=active_currency,
            history_months=6,
            horizon=1,
            limit=5,
        )
        queue = await repositories.approval_queue(
            conn,
            user["org_id"],
            currency=active_currency,
            threshold=0.9,
            days=120,
            max_amount=settings.auto_approve_max_amount,
        )
    return {
        "currency": active_currency,
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
            "items": [item for item in queue["items"] if item["auto_eligible"]][:5],
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
    async with get_pool().connection() as conn:
        return await repositories.price_opportunities(
            conn,
            user["org_id"],
            currency=active_currency,
            days=days,
            min_overprice_pct=min_overprice_pct,
            min_samples=settings.min_history_samples,
            limit=limit,
        )


@router.get("/forecast")
async def consumption_forecast(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    history_months: int = Query(default=6, ge=2, le=24),
    horizon: int = Query(default=1, ge=1, le=6),
    limit: int = Query(default=100, ge=1, le=500),
):
    active_currency = _currency(user, currency)
    async with get_pool().connection() as conn:
        return await repositories.consumption_forecast(
            conn,
            user["org_id"],
            currency=active_currency,
            history_months=history_months,
            horizon=horizon,
            limit=limit,
        )


@router.get("/analytics")
async def analytics(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    months: int = Query(default=6, ge=1, le=24),
):
    active_currency = _currency(user, currency)
    async with get_pool().connection() as conn:
        return await repositories.analytics_overview(
            conn, user["org_id"], currency=active_currency, months=months
        )


@router.get("/approvals")
async def approval_queue(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    threshold: float = Query(default=0.9, ge=0, le=1),
    days: int = Query(default=120, ge=1, le=730),
):
    active_currency = _currency(user, currency)
    async with get_pool().connection() as conn:
        return await repositories.approval_queue(
            conn,
            user["org_id"],
            currency=active_currency,
            threshold=threshold,
            days=days,
            max_amount=settings.auto_approve_max_amount,
        )


@router.post("/savings/track")
async def track_savings(
    payload: SavingsTrackingRequest,
    user: dict = Depends(require_roles("owner", "admin", "analyst")),
):
    active_currency = (payload.currency or user["default_currency"] or "CLP").strip().upper()
    async with get_pool().connection() as conn:
        row = await repositories.record_savings_tracking(
            conn,
            org_id=user["org_id"],
            opportunity_key=payload.opportunity_key,
            status=payload.status,
            realized_amount=payload.realized_amount,
            currency=active_currency,
            notes=payload.notes,
        )
    return {"success": True, "tracking": row}


@router.get("/savings")
async def list_savings(user: CurrentUser, status_filter: str | None = Query(default=None, alias="status")):
    async with get_pool().connection() as conn:
        items = await repositories.list_savings_tracking(conn, user["org_id"], status=status_filter)
        summary = await repositories.summarize_savings_tracking(conn, user["org_id"])
    return {"items": items, "summary": summary}


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
