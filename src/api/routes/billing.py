from __future__ import annotations

import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.deps import CurrentUser, require_roles
from src.core.config import settings
from src.core.security import verify_signature
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.billing import (
    BillingSummary,
    ChangePlanRequest,
    CheckoutOut,
    CheckoutRequest,
    PlanOut,
    SubscriptionOut,
    UsageOut,
    WebhookAck,
)
from src.services.payment_service import create_checkout_session

logger = logging.getLogger(__name__)
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


@router.get("/plans", response_model=list[PlanOut])
async def list_plans():
    """Catálogo público de planes para la tabla de precios."""
    async with get_pool().connection() as conn:
        rows = await repositories.list_plans(conn)
        return [_plan_out(row) for row in rows]


@router.get("/summary", response_model=BillingSummary)
async def billing_summary(user: CurrentUser):
    async with get_pool().connection() as conn:
        return await _load(conn, user["org_id"])


@router.post("/checkout", response_model=CheckoutOut)
async def checkout(
    payload: CheckoutRequest,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        plan = await repositories.get_plan(conn, payload.plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        if float(plan["price_monthly"]) <= 0:
            raise HTTPException(
                status_code=409,
                detail="El plan Free no requiere pago. Actívalo desde el panel de facturación.",
            )
    session = await create_checkout_session(
        plan,
        org_id=str(user["org_id"]),
        email=user.get("email"),
    )
    return CheckoutOut(**session)


@router.post("/webhook/{provider}", response_model=WebhookAck)
async def payment_webhook(provider: str, request: Request):
    raw_body = await request.body()
    if settings.payment_webhook_secret.strip():
        signature = request.headers.get("x-nexora-signature")
        if not verify_signature(settings.payment_webhook_secret, raw_body, signature):
            raise HTTPException(status_code=401, detail="Firma de webhook inválida")
    elif settings.is_production:
        raise HTTPException(status_code=503, detail="PAYMENT_WEBHOOK_SECRET no está configurado")

    try:
        event = json.loads(raw_body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Payload de webhook inválido") from exc
    if not isinstance(event, dict):
        raise HTTPException(status_code=422, detail="El webhook debe ser un objeto JSON")

    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    event_id = str(event.get("event_id") or event.get("id") or "").strip()
    org_id = str(event.get("org_id") or data.get("org_id") or "").strip()
    plan_id = str(event.get("plan_id") or data.get("plan_id") or "").strip()
    if not event_id or not org_id or not plan_id:
        raise HTTPException(status_code=422, detail="El webhook requiere event_id, org_id y plan_id")

    period_end = event.get("current_period_end") or data.get("current_period_end")
    try:
        parsed_period_end = date.fromisoformat(str(period_end)) if period_end else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="current_period_end debe ser una fecha ISO") from exc

    async with get_pool().connection() as conn:
        organization = await repositories.get_organization(conn, org_id)
        if organization is None:
            raise HTTPException(status_code=404, detail="Organización no encontrada")

        is_new = await repositories.record_payment_event(
            conn,
            provider=provider,
            event_id=event_id,
            event_type=str(event.get("type") or "subscription.updated"),
            payload=event,
        )
        if not is_new:
            return WebhookAck(success=True, received=True, duplicate=True)

        updated = await repositories.apply_subscription_payment(
            conn,
            org_id=org_id,
            plan_id=plan_id,
            status=str(event.get("status") or "active"),
            provider=provider,
            customer_id=event.get("customer_id"),
            external_subscription_id=event.get("subscription_id"),
            period_end=parsed_period_end,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

    logger.info("Webhook %s aplicado para org %s (evento %s)", provider, org_id, event_id)
    return WebhookAck(success=True, received=True, duplicate=False)


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
