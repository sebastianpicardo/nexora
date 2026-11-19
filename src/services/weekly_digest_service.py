from __future__ import annotations

import html
from typing import Any

from src.core.config import settings
from src.db import repositories
from src.db.pool import get_pool
from src.services import notification_service
from src.services.email_service import send_email
from src.services.leak_audit_service import build_weekly_report


def _money(value: Any, currency: str) -> str:
    try:
        return f"${float(value or 0):,.0f} {currency}"
    except (TypeError, ValueError):
        return f"$0 {currency}"


def _compose(report: dict, org_name: str) -> tuple[str, str, str]:
    summary = report["summary"]
    currency = report["currency"]
    subject = f"Resumen semanal NEXORA · {org_name}"
    lines = [
        f"Resumen semanal de {org_name}",
        "",
        f"Documentos procesados: {summary.get('documents_processed', 0)}",
        f"Excepciones resueltas: {summary.get('exceptions_resolved', 0)}",
        f"Ahorro potencial detectado: {_money(summary.get('potential_savings'), currency)}",
        f"Ahorro verificado: {_money(summary.get('realized_savings'), currency)}",
        f"Aprobaciones pendientes: {summary.get('approvals_pending', 0)}",
        "",
        "Lo importante de la semana:",
    ]
    for highlight in report.get("highlights") or []:
        lines.append(f"- {highlight}")
    lines.extend(["", f"Revisa el detalle en {settings.public_app_url}"])
    text = "\n".join(lines)

    highlights_html = "".join(f"<li>{html.escape(item)}</li>" for item in report.get("highlights") or [])
    html_body = (
        f"<h2>Resumen semanal de {html.escape(org_name)}</h2>"
        f"<p><strong>Ahorro potencial:</strong> {_money(summary.get('potential_savings'), currency)}<br>"
        f"<strong>Ahorro verificado:</strong> {_money(summary.get('realized_savings'), currency)}<br>"
        f"<strong>Documentos procesados:</strong> {summary.get('documents_processed', 0)}<br>"
        f"<strong>Aprobaciones pendientes:</strong> {summary.get('approvals_pending', 0)}</p>"
        f"<ul>{highlights_html}</ul>"
        f'<p><a href="{html.escape(settings.public_app_url)}">Abrir NEXORA</a></p>'
    )
    return subject, text, html_body


async def send_weekly_digest(
    user: dict,
    *,
    email: str | None = None,
    channel_id: str | None = None,
) -> dict[str, Any]:
    report = await build_weekly_report(user)
    org_name = str(user.get("org_name") or "tu organización")
    subject, text, html_body = _compose(report, org_name)
    recipient = (email or user.get("email") or "").strip()
    deliveries: list[dict] = []

    if recipient:
        sent = await send_email(to=recipient, subject=subject, text=text, html=html_body)
        if not settings.email_enabled:
            status = "skipped"
            error = "SMTP no configurado"
        else:
            status = "sent" if sent else "failed"
            error = None if sent else "No se pudo enviar el correo"
        deliveries.append(
            {"channel": "email", "recipient": recipient, "status": status, "error": error}
        )
        async with get_pool().connection() as conn:
            await repositories.record_notification_delivery(
                conn,
                org_id=user["org_id"],
                channel_id=None,
                event_type="weekly_digest",
                status=status,
                recipient=recipient,
                payload={"subject": subject, "summary": report["summary"]},
                error=error,
            )

    async with get_pool().connection() as conn:
        channels = await repositories.list_notification_channels(conn, user["org_id"])
        for channel in channels:
            if channel_id and str(channel["id"]) != str(channel_id):
                continue
            if not channel.get("active"):
                continue
            if channel.get("channel") not in {"whatsapp", "email", "slack", "webhook"}:
                continue
            target = str(channel.get("target") or "").strip()
            if not target:
                continue
            if channel.get("channel") == "email" and target.lower() == recipient.lower():
                continue
            status, error = await notification_service.deliver_message(
                channel=channel,
                subject=subject,
                text=text,
                payload={"event": "weekly_digest", "summary": report["summary"]},
            )
            deliveries.append(
                {
                    "channel": channel.get("channel"),
                    "recipient": target,
                    "status": status,
                    "error": error,
                }
            )
            await repositories.record_notification_delivery(
                conn,
                org_id=user["org_id"],
                channel_id=channel["id"],
                event_type="weekly_digest",
                status=status,
                recipient=target,
                payload={"subject": subject, "summary": report["summary"]},
                error=error,
            )

    return {
        "subject": subject,
        "text": text,
        "deliveries": deliveries,
        "summary": report["summary"],
        "note": (
            "Envío listo para cron: llama este endpoint cada lunes o programa un job que use "
            "send_weekly_digest."
        ),
    }
