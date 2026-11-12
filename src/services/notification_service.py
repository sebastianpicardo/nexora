from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from src.core.config import settings
from src.core.logging import get_logger
from src.db import repositories
from src.db.pool import get_pool
from src.services.email_service import send_email

logger = get_logger(__name__)


def _matches(events: Any, event_type: str) -> bool:
    if not events:
        return True
    if not isinstance(events, list):
        return True
    normalized = {str(value).lower() for value in events}
    return bool({"all", event_type.lower()} & normalized)


def _message(org_name: str, alerts: list[dict]) -> tuple[str, str]:
    subject = f"Alertas de compras · {org_name}"
    lines = [f"Resumen de alertas para {org_name}:", ""]
    for alert in alerts:
        lines.append(f"- {alert.get('title')}: {alert.get('body')}")
    lines.extend(["", "Ingresa a NEXORA para revisar el detalle."])
    return subject, "\n".join(lines)


async def _deliver(
    *,
    channel: dict,
    subject: str,
    text: str,
    payload: dict,
) -> tuple[str, str | None]:
    target = (channel.get("target") or "").strip()
    channel_type = channel.get("channel")

    if channel_type == "email":
        sent = await send_email(
            to=target,
            subject=subject,
            text=text,
            html=f"<p>{text.replace(chr(10), '<br>')}</p>",
        )
        if not settings.email_enabled:
            return "skipped", "SMTP no configurado"
        return ("sent", None) if sent else ("failed", "No se pudo enviar el correo")

    if channel_type in {"slack", "webhook"}:
        try:
            async with httpx.AsyncClient(timeout=settings.integration_timeout_seconds) as client:
                response = await client.post(target, json={"text": text, "alerts": payload})
                response.raise_for_status()
            return "sent", None
        except Exception as exc:
            logger.warning("No se pudo entregar alerta a %s: %s", target, exc)
            return "failed", str(exc)[:500]

    if channel_type == "whatsapp":
        if not (settings.whatsapp_phone_id and settings.whatsapp_token):
            return "skipped", "WhatsApp no configurado"
        url = f"{settings.whatsapp_api_url.rstrip('/')}/{settings.whatsapp_phone_id}/messages"
        body = {
            "messaging_product": "whatsapp",
            "to": target,
            "type": "text",
            "text": {"body": text[:4096]},
        }
        try:
            async with httpx.AsyncClient(timeout=settings.integration_timeout_seconds) as client:
                response = await client.post(
                    url,
                    json=body,
                    headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
                )
                response.raise_for_status()
            return "sent", None
        except Exception as exc:
            logger.warning("No se pudo entregar WhatsApp a %s: %s", target, exc)
            return "failed", str(exc)[:500]

    return "skipped", "Canal no soportado"


async def dispatch_alerts(
    conn,
    *,
    org_id: UUID | str,
    org_name: str,
    currency: str,
    event_type: str = "alerts",
    channel_id: UUID | str | None = None,
) -> dict:
    alerts = await repositories.list_alerts(conn, org_id, currency=currency)
    channels = await repositories.list_notification_channels(conn, org_id)
    subject, text = _message(org_name, alerts)

    deliveries = []
    for channel in channels:
        if channel_id and str(channel["id"]) != str(channel_id):
            continue
        if not channel.get("active"):
            continue
        if channel_id is None and not _matches(channel.get("events"), event_type):
            continue
        status, error = await _deliver(
            channel=channel,
            subject=subject,
            text=text,
            payload={"event": event_type, "alerts": alerts},
        )
        delivery = await repositories.record_notification_delivery(
            conn,
            org_id=org_id,
            channel_id=channel["id"],
            event_type=event_type,
            status=status,
            recipient=channel.get("target") or "",
            payload={"alerts": alerts},
            error=error,
        )
        deliveries.append(delivery)

    return {
        "alerts": alerts,
        "deliveries": deliveries,
        "channels": len(channels),
    }


async def send_email_notification(
    *,
    org_id: str,
    recipient: str,
    alert: dict,
) -> bool:
    """Envía una notificación de alerta por email a un destinatario específico."""
    org_name = "Tu organización"
    subject = f"Alerta de compra · {org_name}"
    lines = [f"Alerta detectada en {org_name}:", ""]
    lines.append(f"- Tipo: {alert.get('type')}")
    lines.append(f"- Descripción: {alert.get('item')}")
    if alert.get("spike_pct") is not None:
        lines.append(f"- Variación: {alert['spike_pct']:.1f}%")
    if alert.get("current_price") not in (None, 0):
        lines.append(f"- Precio actual: {alert['current_price']} {alert.get('currency', 'CLP')}")
    if alert.get("historical_median") not in (None, 0):
        lines.append(f"- Precio medio histórico: {alert['historical_median']} {alert.get('currency', 'CLP')}")
    lines.extend(["", "Ingresa a NEXORA para revisar el detalle."])
    text = "\n".join(lines)

    try:
        sent = await send_email(
            to=recipient,
            subject=subject,
            text=text,
            html=f"<p>{text.replace(chr(10), '<br>')}</p>",
        )
        if not settings.email_enabled:
            logger.warning("SMTP no configurado; email de alerta no se envía realmente a %s", recipient)
        return bool(sent)
    except Exception as exc:
        logger.warning("No se pudo enviar email de alerta a %s: %s", recipient, exc)
        return False


async def send_slack_notification(
    *,
    org_id: str,
    channel: str,
    alert: dict,
) -> bool:
    """Envía una notificación de alerta a un canal de Slack."""
    org_name = "Tu organización"
    text = (
        f"*Alerta de compra · {org_name}*\n"
        f"• Tipo: {alert.get('type')}\n"
        f"• Descripción: {alert.get('item')}\n"
    )
    if alert.get("spike_pct") is not None:
        text += f"• Variación: {alert['spike_pct']:.1f}%\n"
    if alert.get("current_price") not in (None, 0):
        text += f"• Precio actual: {alert['current_price']} {alert.get('currency', 'CLP')}\n"
    if alert.get("historical_median") not in (None, 0):
        text += f"• Precio medio histórico: {alert['historical_median']} {alert.get('currency', 'CLP')}\n"
    text += "\nIngresa a NEXORA para revisar el detalle."

    try:
        async with httpx.AsyncClient(timeout=settings.integration_timeout_seconds) as client:
            response = await client.post(channel, json={"text": text})
            response.raise_for_status()
            return True
    except Exception as exc:
        logger.warning("No se pudo enviar alerta a Slack %s: %s", channel, exc)
        return False


async def send_webhook_notification(
    *,
    org_id: str,
    alert: dict,
) -> bool:
    """Envía una notificación de alerta al webhook configurado de la organización."""
    async with get_pool().connection() as conn:
        rows = await repositories.list_integrations(conn, org_id)
    webhook_url = None
    for row in rows or []:
        config = row.get("config") or {}
        if row.get("active") and config.get("url"):
            webhook_url = config.get("url")
            break
    if not webhook_url:
        logger.warning("No hay webhook configurado para la organización %s", org_id)
        return False

    payload = {
        "event": "alert",
        "organization_id": org_id,
        "alert": alert,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.integration_timeout_seconds) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
            return True
    except Exception as exc:
        logger.warning("No se pudo enviar webhook de alerta a %s: %s", webhook_url, exc)
        return False
