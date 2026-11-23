from __future__ import annotations

import logging

import httpx

from src.core.config import settings
from src.core.errors import NexoraError

logger = logging.getLogger(__name__)


class RecaptchaError(NexoraError):
    status_code = 400
    code = "recaptcha_failed"


async def verify_recaptcha(
    token: str | None,
    *,
    remote_ip: str | None = None,
    expected_action: str | None = None,
    min_score: float | None = None,
) -> dict:
    """Verifica un token de reCAPTCHA v3 contra la API de Google.

    Si no hay `RECAPTCHA_SECRET_KEY` configurada, la verificación se omite para
    no bloquear entornos locales. En producción se recomienda configurarla.
    """
    if not settings.recaptcha_enabled:
        logger.warning("reCAPTCHA no configurado: se omite la verificación del token.")
        return {"skipped": True, "score": None, "action": None}

    if not token:
        raise RecaptchaError("Falta el token de reCAPTCHA. Recarga la página e intenta de nuevo.")

    payload = {"secret": settings.recaptcha_secret_key, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(settings.recaptcha_verify_url, data=payload)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.exception("No se pudo verificar reCAPTCHA: %s", exc)
        raise RecaptchaError("No pudimos verificar el reCAPTCHA. Intenta nuevamente.") from exc

    if not data.get("success"):
        codes = data.get("error-codes") or []
        logger.warning("reCAPTCHA rechazado: %s", codes)
        raise RecaptchaError("La verificación de seguridad falló.", details={"codes": codes})

    score = data.get("score")
    threshold = settings.recaptcha_min_score if min_score is None else min_score
    if score is not None and float(score) < float(threshold):
        raise RecaptchaError(
            "Detectamos actividad sospechosa. Intenta nuevamente.",
            details={"score": score, "threshold": threshold},
        )

    action = data.get("action")
    if expected_action and action and action != expected_action:
        raise RecaptchaError("La acción del reCAPTCHA no coincide con la operación.")

    return {"skipped": False, "score": float(score) if score is not None else None, "action": action}
