from __future__ import annotations

import json
import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from src.api.deps import CurrentUser, require_roles
from src.core.config import settings
from src.core.security import verify_signature, verify_stripe_signature
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.billing import (
    BillingSummary,
    ChangePlanRequest,
    CheckoutOut,
    CheckoutRequest,
    InvoiceListResponse,
    InvoiceOut,
    PlanOut,
    SubscriptionOut,
    UsageOut,
    WebhookAck,
)
from src.services.export_service import build_pdf
from src.services.payment_service import create_checkout_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])


def _invoice_out(row: dict) -> InvoiceOut:
    return InvoiceOut(
        id=row["id"],
        provider=row["provider"],
        provider_invoice_id=row.get("provider_invoice_id"),
        amount=float(row["amount"]),
        currency=row["currency"],
        status=row["status"],
        period_start=row.get("period_start"),
        period_end=row.get("period_end"),
        paid_at=row.get("paid_at"),
        created_at=row["created_at"],
    )


def _stripe_event(payload: dict) -> dict | None:
    """Normaliza un evento nativo de Stripe al formato interno."""
    obj = (payload.get("data") or {}).get("object") or {}
    metadata = obj.get("metadata") or {}
    org_id = str(obj.get("client_reference_id") or metadata.get("org_id") or "").strip()
    plan_id = str(metadata.get("plan_id") or "").strip()
    if not org_id or not plan_id:
        return None
    period_end = obj.get("current_period_end")
    if isinstance(period_end, (int, float)):
        period_end = date.fromtimestamp(period_end).isoformat()
    return {
        "event_id": str(payload.get("id") or ""),
        "type": str(payload.get("type") or "subscription.updated"),
        "org_id": org_id,
        "plan_id": plan_id,
        "status": str(obj.get("status") or "active"),
        "customer_id": obj.get("customer"),
        "subscription_id": obj.get("subscription") or obj.get("id"),
        "current_period_end": period_end,
        "amount": (obj.get("amount_total") or obj.get("amount_paid") or 0) / 100,
        "currency": str(obj.get("currency") or "usd").upper(),
        "invoice_id": obj.get("invoice") or obj.get("id"),
    }


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
    async with get_pool().connection() as conn:
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="billing.checkout",
            entity_type="plan",
            entity_id=session["plan_id"],
            metadata={"provider": session["provider"], "session_id": session["session_id"]},
        )
    return CheckoutOut(**session)


@router.post("/webhook/{provider}", response_model=WebhookAck)
async def payment_webhook(provider: str, request: Request):
    provider = provider.strip().lower()
    raw_body = await request.body()

    if provider == "stripe":
        if not verify_stripe_signature(
            settings.stripe_webhook_secret,
            raw_body,
            request.headers.get("stripe-signature"),
        ):
            raise HTTPException(status_code=401, detail="Firma de Stripe inválida")
        try:
            stripe_payload = json.loads(raw_body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Payload de webhook inválido") from exc
        event = _stripe_event(stripe_payload)
        if event is None:
            raise HTTPException(status_code=422, detail="Evento de Stripe sin org_id o plan_id")
    else:
        if settings.payment_webhook_secret.strip():
            signature = request.headers.get("x-nexora-signature") or request.headers.get("x-signature")
            if not verify_signature(settings.payment_webhook_secret, raw_body, signature):
                raise HTTPException(status_code=401, detail="Firma de webhook inválida")
        elif settings.is_production:
            raise HTTPException(status_code=503, detail="PAYMENT_WEBHOOK_SECRET no está configurado")

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Payload de webhook inválido") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="El webhook debe ser un objeto JSON")

        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        event = {
            "event_id": str(payload.get("event_id") or payload.get("id") or "").strip(),
            "type": str(payload.get("type") or "subscription.updated"),
            "org_id": str(payload.get("org_id") or data.get("org_id") or "").strip(),
            "plan_id": str(payload.get("plan_id") or data.get("plan_id") or "").strip(),
            "status": str(payload.get("status") or data.get("status") or "active"),
            "customer_id": payload.get("customer_id") or data.get("customer_id"),
            "subscription_id": payload.get("subscription_id") or data.get("subscription_id"),
            "current_period_end": payload.get("current_period_end") or data.get("current_period_end"),
            "amount": float(payload.get("amount") or data.get("amount") or 0),
            "currency": str(payload.get("currency") or data.get("currency") or "USD").upper(),
            "invoice_id": payload.get("invoice_id") or data.get("invoice_id"),
        }
        if not event["event_id"] or not event["org_id"] or not event["plan_id"]:
            raise HTTPException(status_code=422, detail="El webhook requiere event_id, org_id y plan_id")

    period_end = event.get("current_period_end")
    try:
        parsed_period_end = date.fromisoformat(str(period_end)) if period_end else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="current_period_end debe ser una fecha ISO") from exc

    async with get_pool().connection() as conn:
        organization = await repositories.get_organization(conn, event["org_id"])
        if organization is None:
            raise HTTPException(status_code=404, detail="Organización no encontrada")

        is_new = await repositories.record_payment_event(
            conn,
            provider=provider,
            event_id=event["event_id"],
            event_type=event["type"],
            payload=event,
        )
        if not is_new:
            return WebhookAck(success=True, received=True, duplicate=True)

        updated = await repositories.apply_subscription_payment(
            conn,
            org_id=event["org_id"],
            plan_id=event["plan_id"],
            status=event["status"],
            provider=provider,
            customer_id=event.get("customer_id"),
            external_subscription_id=event.get("subscription_id"),
            period_end=parsed_period_end,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

        plan = await repositories.get_plan(conn, event["plan_id"])
        await repositories.create_invoice(
            conn,
            org_id=event["org_id"],
            provider=provider,
            provider_invoice_id=str(event.get("invoice_id") or event["event_id"]),
            amount=float(event.get("amount") or (plan["price_monthly"] if plan else 0)),
            currency=str(event.get("currency") or (plan["currency"] if plan else "USD")),
            status="paid" if event["status"] in {"active", "trialing"} else event["status"],
            period_start=None,
            period_end=parsed_period_end,
            metadata={"event_id": event["event_id"], "event_type": event["type"]},
        )

    logger.info("Webhook %s aplicado para org %s (evento %s)", provider, event["org_id"], event["event_id"])
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

        is_paid = float(target["price_monthly"]) > 0
        if is_paid and settings.payment_provider != "mock":
            raise HTTPException(
                status_code=409,
                detail="Los planes pagados se activan con el checkout y el pago confirmado.",
            )

        updated = await repositories.change_plan(conn, user["org_id"], payload.plan_id)
        if updated is None:
            raise HTTPException(status_code=404, detail="Suscripción no encontrada")

        if is_paid:
            await repositories.create_invoice(
                conn,
                org_id=user["org_id"],
                provider="mock",
                provider_invoice_id=None,
                amount=float(target["price_monthly"]),
                currency=target["currency"],
                status="paid",
                metadata={"reason": "change_plan", "plan_id": payload.plan_id},
            )

        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="billing.change_plan",
            entity_type="plan",
            entity_id=payload.plan_id,
            metadata={"paid": is_paid},
        )
        plans = await repositories.list_plans(conn)
        return _summary(updated, plans)


@router.post("/subscription/cancel", response_model=BillingSummary)
async def cancel_subscription(
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        canceled = await repositories.cancel_subscription(conn, user["org_id"])
        if canceled is None:
            raise HTTPException(status_code=404, detail="Suscripción no encontrada")
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="billing.cancel",
            entity_type="subscription",
            entity_id=str(user["org_id"]),
        )
        plans = await repositories.list_plans(conn)
        return _summary(canceled, plans)


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(user: dict = Depends(CurrentUser)):
    async with get_pool().connection() as conn:
        rows = await repositories.list_invoices(conn, user["org_id"])
    return InvoiceListResponse(items=[_invoice_out(row) for row in rows])


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(invoice_id: UUID, user: dict = Depends(CurrentUser)):
    async with get_pool().connection() as conn:
        row = await repositories.get_invoice(conn, user["org_id"], invoice_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return _invoice_out(row)


@router.get("/invoices/{invoice_id}/pdf")
async def get_invoice_pdf(invoice_id: UUID, user: dict = Depends(CurrentUser)):
    async with get_pool().connection() as conn:
        row = await repositories.get_invoice(conn, user["org_id"], invoice_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    invoice = _invoice_out(row)
    pdf = build_pdf(
        "Factura NEXORA",
        f"Factura {invoice.id} · {invoice.status} · {invoice.created_at:%Y-%m-%d}",
        ["Concepto", "Detalle"],
        [
            ["Proveedor", invoice.provider],
            ["Monto", f"{invoice.amount:.2f} {invoice.currency}"],
            ["Estado", invoice.status],
            ["Periodo", f"{invoice.period_start or '-'} a {invoice.period_end or '-'}"],
        ],
        column_widths=[120, 500],
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="factura-{invoice.id}.pdf"'},
    )
