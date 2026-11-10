from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import CurrentUser, require_roles
from src.db import repositories
from src.db.pool import get_pool
from src.services import alert_service

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
async def list_alert_configs(
    user: dict = Depends(require_roles("owner", "admin", "analyst", "user")),
) -> dict[str, Any]:
    async with get_pool().connection() as conn:
        rows = await repositories.list_alert_config(conn, user["org_id"])
    return {
        "configs": [
            {
                "id": str(row["id"]),
                "alert_type": row["alert_type"],
                "threshold_pct": float(row["threshold_pct"] or 0),
                "enabled": bool(row["enabled"]),
                "channels": row.get("channels") or [],
                "email_recipients": row.get("email_recipients") or [],
                "slack_channels": row.get("slack_channels") or [],
                "last_triggered_at": row["last_triggered_at"].isoformat() if row.get("last_triggered_at") else None,
                "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
            }
            for row in rows
        ]
    }


@router.post("")
async def create_or_update_alert_config(
    payload: dict,
    user: dict = Depends(require_roles("owner", "admin")),
) -> dict[str, Any]:
    alert_type = payload.get("alert_type")
    if not alert_type:
        raise HTTPException(status_code=400, detail="alert_type es obligatorio")

    allowed_types = {"price_spike", "exception_pending", "approval_pending", "document_pending", "quota_warning", "quota_exceeded"}
    if alert_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Tipo de alerta no válido. Opciones: {', '.join(sorted(allowed_types))}")

    threshold_pct = payload.get("threshold_pct")
    if threshold_pct is not None:
        try:
            threshold_pct = float(threshold_pct)
            if threshold_pct < 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="threshold_pct debe ser un número mayor o igual a 0")

    async with get_pool().connection() as conn:
        row = await repositories.create_or_update_alert_config(
            conn,
            org_id=user["org_id"],
            alert_type=alert_type,
            threshold_pct=threshold_pct,
            enabled=payload.get("enabled"),
            channels=payload.get("channels"),
            email_recipients=payload.get("email_recipients"),
            slack_channels=payload.get("slack_channels"),
        )
    return {
        "id": str(row["id"]),
        "alert_type": row["alert_type"],
        "threshold_pct": float(row["threshold_pct"] or 0),
        "enabled": bool(row["enabled"]),
        "channels": row.get("channels") or [],
        "email_recipients": row.get("email_recipients") or [],
        "slack_channels": row.get("slack_channels") or [],
        "message": "Configuración de alerta guardada correctamente",
    }


@router.delete("/{alert_type}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_config(
    alert_type: str,
    user: dict = Depends(require_roles("owner", "admin")),
) -> None:
    async with get_pool().connection() as conn:
        deleted = await repositories.delete_alert_config(conn, user["org_id"], alert_type)
    if not deleted:
        raise HTTPException(status_code=404, detail="Configuración de alerta no encontrada")


@router.post("/evaluate", status_code=status.HTTP_200_OK)
async def evaluate_alerts(
    user: dict = Depends(require_roles("owner", "admin")),
) -> dict[str, Any]:
    """Evalúa las alertas de la organización actual y envía notificaciones."""
    async with get_pool().connection() as conn:
        alerts = await alert_service.evaluate_alerts_for_org(conn, user["org_id"])
        sent = await alert_service.send_alert_notifications(conn, user["org_id"], alerts)
    return {
        "alerts_triggered": len(alerts),
        "notifications_sent": sent,
        "alerts": alerts,
    }


@router.post("/evaluate-all", status_code=status.HTTP_200_OK)
async def evaluate_all_orgs(
    user: dict = Depends(require_roles("owner", "admin")),
) -> dict[str, Any]:
    """Evalúa alertas para todas las organizaciones (solo super admin)."""
    from src.api.deps import is_super_admin
    if not is_super_admin(user):
        raise HTTPException(status_code=403, detail="Solo super administrador puede ejecutar evaluación global")
    result = await alert_service.evaluate_all_orgs()
    return result
