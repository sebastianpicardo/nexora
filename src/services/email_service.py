from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from src.core.config import settings

logger = logging.getLogger(__name__)


def _build_message(*, to: str, subject: str, text: str, html: str | None = None) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from))
    message["To"] = to
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    return message


def _send_sync(message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if settings.smtp_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=20) as server:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.ehlo()
        if settings.smtp_tls:
            server.starttls(context=context)
            server.ehlo()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


async def send_email(*, to: str, subject: str, text: str, html: str | None = None) -> bool:
    """Envía un correo. Si SMTP no está configurado, registra el contenido y devuelve False."""
    if not to or "@" not in to:
        return False
    if not settings.email_enabled:
        logger.info("SMTP no configurado; correo omitido para %s: %s", to, subject)
        return False

    message = _build_message(to=to, subject=subject, text=text, html=html)
    try:
        await asyncio.to_thread(_send_sync, message)
        return True
    except Exception:
        logger.exception("No se pudo enviar el correo a %s", to)
        return False


def _layout(title: str, body: str, cta_label: str | None = None, cta_url: str | None = None) -> str:
    button = ""
    if cta_label and cta_url:
        button = (
            f'<p style="margin:24px 0"><a href="{cta_url}" '
            'style="background:#0f766e;color:#ffffff;padding:12px 20px;border-radius:8px;'
            f'text-decoration:none;font-weight:600">{cta_label}</a></p>'
            f'<p style="color:#64748b;font-size:12px">Si el botón no funciona, copia este enlace: {cta_url}</p>'
        )
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#1e293b">'
        f'<h2 style="color:#0b3b36">{title}</h2>'
        f'<div style="font-size:15px;line-height:1.6">{body}</div>'
        f"{button}"
        '<hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">'
        '<p style="color:#94a3b8;font-size:12px">NEXORA · Auditoría de compras y precios B2B</p>'
        "</div>"
    )


async def send_invitation_email(*, to: str, organization: str, invite_url: str, role: str) -> bool:
    subject = f"Invitación a {organization} en NEXORA"
    text = (
        f"Fuiste invitado/a a {organization} en NEXORA con el rol {role}.\n\n"
        f"Acepta la invitación aquí: {invite_url}\n\n"
        "La invitación expira en 14 días."
    )
    html = _layout(
        f"Invitación a {organization}",
        f"Fuiste invitado/a a <strong>{organization}</strong> con el rol <strong>{role}</strong>. "
        "La invitación expira en 14 días.",
        "Aceptar invitación",
        invite_url,
    )
    return await send_email(to=to, subject=subject, text=text, html=html)


async def send_password_reset_email(*, to: str, reset_url: str) -> bool:
    subject = "Restablece tu contraseña de NEXORA"
    text = (
        "Recibimos una solicitud para restablecer tu contraseña.\n\n"
        f"Abre este enlace para crear una nueva: {reset_url}\n\n"
        "El enlace expira en 30 minutos. Si no solicitaste el cambio, ignora este correo."
    )
    html = _layout(
        "Restablece tu contraseña",
        "Recibimos una solicitud para restablecer tu contraseña. El enlace expira en 30 minutos. "
        "Si no solicitaste el cambio, ignora este correo.",
        "Crear nueva contraseña",
        reset_url,
    )
    return await send_email(to=to, subject=subject, text=text, html=html)


async def send_verification_email(*, to: str, verification_url: str) -> bool:
    subject = "Verifica tu email en NEXORA"
    text = (
        "Confirma tu email para completar la configuración de tu cuenta.\n\n"
        f"Verifica aquí: {verification_url}\n\n"
        "El enlace expira en 24 horas."
    )
    html = _layout(
        "Verifica tu email",
        "Confirma tu email para completar la configuración de tu cuenta. El enlace expira en 24 horas.",
        "Verificar email",
        verification_url,
    )
    return await send_email(to=to, subject=subject, text=text, html=html)


async def send_quota_alert_email(*, to: str, organization: str, used: int, limit: int | None, plan: str) -> bool:
    limit_text = "ilimitado" if limit is None else str(limit)
    subject = f"Alerta de consumo de documentos en {organization}"
    text = (
        f"Tu organización {organization} ha usado {used} de {limit_text} documentos del plan {plan}.\n\n"
        "Revisa tu plan en NEXORA para evitar interrupciones."
    )
    html = _layout(
        "Alerta de consumo",
        f"Tu organización <strong>{organization}</strong> ha usado <strong>{used}</strong> de "
        f"<strong>{limit_text}</strong> documentos del plan <strong>{plan}</strong>.",
        "Revisar plan",
        f"{settings.public_app_url}/?checkout=usage",
    )
    return await send_email(to=to, subject=subject, text=text, html=html)


async def send_weekly_summary_email(
    *,
    to: str,
    organization: str,
    documents: int,
    exceptions: int,
    price_alerts: int,
) -> bool:
    subject = f"Resumen semanal de compras · {organization}"
    text = (
        f"Resumen de {organization}:\n\n"
        f"- Documentos procesados: {documents}\n"
        f"- Excepciones pendientes: {exceptions}\n"
        f"- Alertas de alza: {price_alerts}\n\n"
        "Ingresa a NEXORA para revisar el detalle."
    )
    html = _layout(
        "Resumen semanal de compras",
        f"Resumen de <strong>{organization}</strong>:<br><br>"
        f"• Documentos procesados: <strong>{documents}</strong><br>"
        f"• Excepciones pendientes: <strong>{exceptions}</strong><br>"
        f"• Alertas de alza: <strong>{price_alerts}</strong>",
        "Abrir dashboard",
        settings.public_app_url,
    )
    return await send_email(to=to, subject=subject, text=text, html=html)
