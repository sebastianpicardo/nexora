from __future__ import annotations

import hashlib
import hmac
import secrets
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from src.core.config import settings
from src.core.errors import ValidationError

STRIPE_CHECKOUT_URL = "https://api.stripe.com/v1/checkout/sessions"
MERCADOPAGO_PREFERENCES_URL = "https://api.mercadopago.com/checkout/preferences"
FLOW_PAYMENT_CREATE_URL = "https://www.flow.cl/api/payment/create"

SUPPORTED_PROVIDERS = {"mock", "stripe", "mercadopago", "flow"}


def _plan_amount(plan: dict) -> float:
    return float(plan["price_monthly"])


def _minor_units(amount: float) -> int:
    return max(int(round(amount * 100)), 0)


def _require(value: str, name: str) -> str:
    if not value.strip():
        raise ValidationError(f"El proveedor de pagos no está configurado: falta {name}.")
    return value.strip()


def _with_query(url: str, params: dict[str, str]) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.update(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _checkout_result(*, provider: str, session_id: str, checkout_url: str, plan: dict) -> dict:
    return {
        "provider": provider,
        "session_id": session_id,
        "checkout_url": checkout_url,
        "plan_id": plan["id"],
        "amount": _plan_amount(plan),
        "currency": plan["currency"],
    }


async def _create_stripe_checkout(plan: dict, *, org_id: str, email: str | None) -> dict:
    api_key = _require(settings.stripe_secret_key, "STRIPE_SECRET_KEY")
    success_url = _with_query(settings.payment_checkout_success_url, {"provider": "stripe"})
    cancel_url = _with_query(settings.payment_checkout_cancel_url, {"provider": "stripe"})
    data = {
        "mode": "subscription",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": org_id,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": plan["currency"].lower(),
        "line_items[0][price_data][unit_amount]": str(_minor_units(_plan_amount(plan))),
        "line_items[0][price_data][recurring][interval]": "month",
        "line_items[0][price_data][product_data][name]": f"NEXORA {plan['name']}",
        "metadata[org_id]": org_id,
        "metadata[plan_id]": plan["id"],
    }
    if email:
        data["customer_email"] = email

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            STRIPE_CHECKOUT_URL,
            data=data,
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if response.status_code >= 400:
        raise ValidationError("Stripe rechazó la creación del pago.", details={"status": response.status_code})
    payload = response.json()
    session_id = str(payload.get("id") or "")
    checkout_url = str(payload.get("url") or "")
    if not session_id or not checkout_url:
        raise ValidationError("Stripe no devolvió una sesión de pago válida.")
    return _checkout_result(provider="stripe", session_id=session_id, checkout_url=checkout_url, plan=plan)


async def _create_mercadopago_checkout(plan: dict, *, org_id: str, email: str | None) -> dict:
    access_token = _require(settings.mercadopago_access_token, "MERCADOPAGO_ACCESS_TOKEN")
    body = {
        "items": [
            {
                "id": plan["id"],
                "title": f"NEXORA {plan['name']}",
                "description": plan["description"],
                "quantity": 1,
                "currency_id": plan["currency"],
                "unit_price": _plan_amount(plan),
            }
        ],
        "external_reference": org_id,
        "metadata": {"org_id": org_id, "plan_id": plan["id"]},
        "back_urls": {
            "success": settings.payment_checkout_success_url,
            "failure": settings.payment_checkout_cancel_url,
            "pending": settings.payment_checkout_success_url,
        },
        "auto_return": "approved",
    }
    if email:
        body["payer"] = {"email": email}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            MERCADOPAGO_PREFERENCES_URL,
            json=body,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        raise ValidationError(
            "MercadoPago rechazó la creación del pago.", details={"status": response.status_code}
        )
    payload = response.json()
    session_id = str(payload.get("id") or "")
    checkout_url = str(payload.get("init_point") or payload.get("sandbox_init_point") or "")
    if not session_id or not checkout_url:
        raise ValidationError("MercadoPago no devolvió una preferencia de pago válida.")
    return _checkout_result(
        provider="mercadopago", session_id=session_id, checkout_url=checkout_url, plan=plan
    )


def _flow_signature(params: dict[str, str], secret: str) -> str:
    ordered = "".join(f"{key}{params[key]}" for key in sorted(params))
    return hmac.new(secret.encode("utf-8"), ordered.encode("utf-8"), hashlib.sha256).hexdigest()


async def _create_flow_checkout(plan: dict, *, org_id: str, email: str | None) -> dict:
    api_key = _require(settings.flow_api_key, "FLOW_API_KEY")
    secret_key = _require(settings.flow_secret_key, "FLOW_SECRET_KEY")
    commerce_order = f"{org_id}-{secrets.token_hex(4)}"
    params = {
        "apiKey": api_key,
        "commerceOrder": commerce_order,
        "subject": f"NEXORA {plan['name']}",
        "currency": plan["currency"],
        "amount": f"{_plan_amount(plan):.2f}",
        "email": email or "pagos@nexora.app",
        "urlConfirmation": f"{settings.frontend_origin}/api/billing/webhook/flow",
        "urlReturn": settings.payment_checkout_success_url,
    }
    params["s"] = _flow_signature(params, secret_key)

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(FLOW_PAYMENT_CREATE_URL, data=params)
    if response.status_code >= 400:
        raise ValidationError("Flow rechazó la creación del pago.", details={"status": response.status_code})
    payload = response.json()
    token = str(payload.get("token") or "")
    url = str(payload.get("url") or "")
    if not token or not url:
        raise ValidationError("Flow no devolvió una sesión de pago válida.")
    return _checkout_result(
        provider="flow",
        session_id=commerce_order,
        checkout_url=f"{url}?token={token}",
        plan=plan,
    )


async def create_checkout_session(plan: dict, *, org_id: str, email: str | None = None) -> dict:
    """Crea una sesión de pago con el proveedor configurado."""
    provider = settings.payment_provider.strip().lower() or "mock"
    if provider not in SUPPORTED_PROVIDERS:
        raise ValidationError(f"Proveedor de pagos no soportado: {provider}.")

    if provider == "mock":
        if settings.is_production:
            raise ValidationError(
                "El proveedor de pagos mock está deshabilitado en producción. "
                "Configura Stripe, MercadoPago o Flow."
            )
        session_id = secrets.token_urlsafe(18)
        checkout_url = _with_query(
            settings.payment_checkout_success_url,
            {"plan_id": plan["id"], "session": session_id, "provider": "mock"},
        )
        return _checkout_result(
            provider="mock",
            session_id=session_id,
            checkout_url=checkout_url,
            plan=plan,
        )
    if provider == "stripe":
        return await _create_stripe_checkout(plan, org_id=org_id, email=email)
    if provider == "mercadopago":
        return await _create_mercadopago_checkout(plan, org_id=org_id, email=email)
    return await _create_flow_checkout(plan, org_id=org_id, email=email)
