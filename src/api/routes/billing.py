from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import CurrentUser, require_roles
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.billing import (
    BillingSummary,
    ChangePlanRequest,
    PlanOut,
    SubscriptionOut,
    UsageOut,
)

router = APIRouter(prefix="/api/billing", tags=["billing"])


def _plan_out(row: dict) -> PlanOut:
    return PlanOut(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        price_monthly=float(row["price_monthly"]),
        currency=row["currency"],
        document_limit=row["document_limit"],
        features=list(row["features"] or []),
        sort_order=row["sort_order"],
    )


def _summary(billing: dict, plans: list[dict]) -> BillingSummary:
    subscription = billing["subscription"]
    usage = billing["usage"]
    return BillingSummary(
        subscription=SubscriptionOut(
            id=subscription["id"],
            plan_id=subscription["plan_id"],
            plan_name=subscription["plan_name"],
            status=subscription["status"],
            current_period_start=subscription["current_period_start"],
            current_period_end=subscription["current_period_end"],
            trial_ends_at=subscription["trial_ends_at"],
        ),
        usage=UsageOut(**usage),
        plans=[_plan_out(row) for row in plans],
    )


async def _load(conn, org_id) -> BillingSummary:
    billing = await repositories.get_billing(conn, org_id)
    plans = await repositories.list_plans(conn)
    return _summary(billing, plans)


@router.get("/summary", response_model=BillingSummary)
async def billing_summary(user: CurrentUser):
    async with get_pool().connection() as conn:
        return await _load(conn, user["org_id"])


@router.post("/change-plan", response_model=BillingSummary)
async def change_plan(
    payload: ChangePlanRequest,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        target = await repositories.get_plan(conn, payload.plan_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

        current = await repositories.get_billing(conn, user["org_id"])
        limit = target["document_limit"]
        if limit is not None and current["usage"]["used"] > int(limit):
            raise HTTPException(
                status_code=409,
                detail=("Tu consumo actual supera el límite del plan seleccionado. Elige un plan con mayor capacidad."),
            )

        updated = await repositories.change_plan(conn, user["org_id"], payload.plan_id)
        if updated is None:
            raise HTTPException(status_code=404, detail="Suscripción no encontrada")
        plans = await repositories.list_plans(conn)
        return _summary(updated, plans)
