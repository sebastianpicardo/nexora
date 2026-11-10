from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg import AsyncConnection

from src.api.deps import require_roles
from src.db import repositories
from src.db.pool import get_pool
from src.core.config import settings
from src.core.logging import get_logger
from src.services import notification_service

logger = get_logger(__name__)

ALERT_TYPES = [
    "price_spike",
    "exception_pending",
    "approval_pending",
    "document_pending",
    "quota_warning",
    "quota_exceeded",
]


async def check_price_spike_alerts(
    conn: AsyncConnection,
    org_id: str,
    config: dict,
) -> list[dict]:
    """Verifica si hay alzas de precio que superan el umbral configurado."""
    threshold = config.get("threshold_pct")
    if threshold is None or threshold <= 0:
        return []

    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                i.supplier_id,
                s.name AS supplier_name,
                i.item_id,
                i.original_description,
                i.normalized_unit_price,
                i.quantity,
                i.currency,
                e.evidence->>'historical_median' AS historical_median,
                e.evidence->>'historical_median' AS raw_median
            FROM exceptions_log e
            JOIN items_history i ON i.id = e.item_id
            LEFT JOIN suppliers s ON s.id = i.supplier_id
            WHERE e.org_id = %s
              AND e.type = 'price_spike'
              AND e.status = 'pending'
              AND e.created_at >= now() - interval '24 hours'
            """,
            (str(org_id),),
        )
        rows = await cur.fetchall()

    triggered = []
    for row in rows or []:
        current_price = float(row["normalized_unit_price"] or 0)
        median = float(row["historical_median"] or 0)
        if median <= 0:
            continue
        spike_pct = ((current_price - median) / median) * 100
        if spike_pct >= threshold:
            triggered.append({
                "type": "price_spike",
                "supplier": row["supplier_name"] or "Desconocido",
                "item": row["original_description"] or "Ítem sin nombre",
                "current_price": current_price,
                "historical_median": median,
                "spike_pct": round(spike_pct, 2),
                "currency": i_currency if (i_currency := row.get("currency")) else "CLP",
                "severity": "high" if spike_pct >= threshold * 2 else "medium",
            })
    return triggered


async def check_exception_pending_alerts(
    conn: AsyncConnection,
    org_id: str,
    config: dict,
) -> list[dict]:
    threshold = config.get("threshold_pct")
    if threshold is None:
        threshold = 1

    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT count(*) AS cnt
            FROM exceptions_log
            WHERE org_id = %s AND status = 'pending'
            """,
            (str(org_id),),
        )
        row = await cur.fetchone()
    count = int(row["cnt"] or 0) if row else 0
    if count >= threshold:
        return [{
            "type": "exception_pending",
            "supplier": "Varios",
            "item": f"{count} excepción(es) pendiente(s)",
            "current_price": 0,
            "historical_median": 0,
            "spike_pct": 0,
            "currency": "CLP",
            "severity": "high" if count >= 10 else "medium",
        }]
    return []


async def check_approval_pending_alerts(
    conn: AsyncConnection,
    org_id: str,
    config: dict,
) -> list[dict]:
    threshold = config.get("threshold_pct")
    if threshold is None:
        threshold = 1

    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT count(*) AS cnt
            FROM purchase_approvals
            WHERE org_id = %s AND status = 'pending'
            """,
            (str(org_id),),
        )
        row = await cur.fetchone()
    count = int(row["cnt"] or 0) if row else 0
    if count >= threshold:
        return [{
            "type": "approval_pending",
            "supplier": "Varios",
            "item": f"{count} compra(s) pendiente(s) de aprobación",
            "current_price": 0,
            "historical_median": 0,
            "spike_pct": 0,
            "currency": "CLP",
            "severity": "high" if count >= 5 else "medium",
        }]
    return []


async def check_document_pending_alerts(
    conn: AsyncConnection,
    org_id: str,
    config: dict,
) -> list[dict]:
    threshold = config.get("threshold_pct")
    if threshold is None:
        threshold = 1

    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT count(*) AS cnt
            FROM documents_log
            WHERE org_id = %s AND status IN ('queued', 'processing')
            """,
            (str(org_id),),
        )
        row = await cur.fetchone()
    count = int(row["cnt"] or 0) if row else 0
    if count >= threshold:
        return [{
            "type": "document_pending",
            "supplier": "Varios",
            "item": f"{count} documento(s) en proceso de extracción",
            "current_price": 0,
            "historical_median": 0,
            "spike_pct": 0,
            "currency": "CLP",
            "severity": "medium",
        }]
    return []


async def check_quota_alerts(
    conn: AsyncConnection,
    org_id: str,
    config: dict,
) -> list[dict]:
    from src.db import repositories as repos
    billing = await repos.get_billing(conn, org_id)
    if not billing:
        return []
    usage = billing.get("usage", {})
    percentage = float(usage.get("percentage", 0) or 0)
    exceeded = bool(usage.get("exceeded"))

    results = []
    threshold = config.get("threshold_pct", 80)
    alert_type = config.get("alert_type", "quota_warning")

    if exceeded and alert_type == "quota_exceeded":
        results.append({
            "type": "quota_exceeded",
            "supplier": "Sistema",
            "item": "Límite de documentos alcanzado",
            "current_price": percentage,
            "historical_median": 100,
            "spike_pct": percentage,
            "currency": "CLP",
            "severity": "danger",
        })
    elif percentage >= threshold and alert_type == "quota_warning":
        results.append({
            "type": "quota_warning",
            "supplier": "Sistema",
            "item": f"Uso de cuota al {percentage:.0f}%",
            "current_price": percentage,
            "historical_median": 100,
            "spike_pct": percentage,
            "currency": "CLP",
            "severity": "warning",
        })
    return results


ALERT_CHECKERS = {
    "price_spike": check_price_spike_alerts,
    "exception_pending": check_exception_pending_alerts,
    "approval_pending": check_approval_pending_alerts,
    "document_pending": check_document_pending_alerts,
    "quota_warning": check_quota_alerts,
    "quota_exceeded": check_quota_alerts,
}


async def evaluate_alerts_for_org(
    conn: AsyncConnection,
    org_id: str,
) -> list[dict]:
    """Evalúa todas las alertas configuradas para una organización y retorna las activadas."""
    configs = await repositories.get_org_alert_configs(conn, org_id)
    if not configs:
        return []

    triggered_all = []
    for config in configs:
        if not config.get("enabled"):
            continue
        alert_type = config.get("alert_type")
        checker = ALERT_CHECKERS.get(alert_type)
        if not checker:
            continue
        try:
            triggered = await checker(conn, org_id, config)
            for t in triggered:
                t["alert_config_id"] = config.get("id")
                t["org_id"] = org_id
                triggered_all.append(t)
        except Exception as exc:
            logger.warning("Error evaluando alerta %s para org %s: %s", alert_type, org_id, exc)

    return triggered_all


async def send_alert_notifications(
    conn: AsyncConnection,
    org_id: str,
    alerts: list[dict],
) -> int:
    """Envía notificaciones para las alertas activadas según configuración."""
    if not alerts:
        return 0

    configs = await repositories.get_org_alert_configs(conn, org_id)
    config_map = {c["alert_type"]: c for c in configs}

    sent = 0
    for alert in alerts:
        alert_type = alert.get("alert_type", "price_spike")
        config = config_map.get(alert_type, {})
        channels = config.get("channels") or []

        # Notificar por cada canal habilitado
        for channel in channels:
            try:
                if channel == "email":
                    recipients = config.get("email_recipients") or []
                    for recipient in recipients:
                        await notification_service.send_email_notification(
                            org_id=org_id,
                            recipient=recipient,
                            alert=alert,
                        )
                        sent += 1
                elif channel == "slack":
                    channels_slack = config.get("slack_channels") or []
                    for slack_channel in channels_slack:
                        await notification_service.send_slack_notification(
                            org_id=org_id,
                            channel=slack_channel,
                            alert=alert,
                        )
                        sent += 1
                elif channel == "webhook":
                    await notification_service.send_webhook_notification(
                        org_id=org_id,
                        alert=alert,
                    )
                    sent += 1
            except Exception as exc:
                logger.warning("Error enviando notificación %s para org %s: %s", channel, org_id, exc)

    # Marcar como activado
    for config in configs:
        await repositories.update_alert_triggered_at(conn, config.get("id"))

    return sent


async def evaluate_all_orgs() -> dict:
    """Evalúa alertas para todas las organizaciones. Llamado por worker periódico."""
    from src.db.pool import get_pool
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT DISTINCT org_id FROM organizations")
            orgs = await cur.fetchall()

    total_sent = 0
    org_results = []
    for row in orgs:
        org_id = row["org_id"]
        async with get_pool().connection() as conn:
            alerts = await evaluate_alerts_for_org(conn, org_id)
            sent = await send_alert_notifications(conn, org_id, alerts)
            total_sent += sent
            org_results.append({
                "org_id": org_id,
                "alerts_triggered": len(alerts),
                "notifications_sent": sent,
            })

    return {
        "total_orgs": len(org_results),
        "total_alerts": sum(r["alerts_triggered"] for r in org_results),
        "total_sent": total_sent,
        "orgs": org_results,
    }
