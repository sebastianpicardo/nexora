from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from src.core.config import settings
from src.core.logging import get_logger
from src.db import repositories
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
