from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import require_roles
from src.services import native_integrations_service as ni

router = APIRouter(prefix="/api/integrations/native", tags=["native-integrations"])


@router.get("/status")
async def native_integrations_status(
    user: dict = Depends(require_roles("owner", "admin", "analyst", "user")),
) -> dict[str, Any]:
    return await ni.list_native_integrations(user)


@router.post("/{provider}/{action}")
async def native_integration_action(
    provider: str,
    action: str,
    payload: dict[str, Any] | None = None,
    user: dict = Depends(require_roles("owner", "admin", "analyst", "user")),
) -> dict[str, Any]:
    if payload is None:
        payload = {}
    if provider not in ni.PROVIDERS:
        raise HTTPException(status_code=404, detail="Proveedor no soportado.")
    handlers = ni.ACTION_HANDLERS.get(provider, {})
    handler = handlers.get(action)
    if handler is None:
        raise HTTPException(status_code=404, detail="Acci��n no soportada para este proveedor.")
    provider_status = await ni.list_native_integrations(user)
    current = next((item for item in provider_status["providers"] if item["provider"] == provider), None)
    action_status = next((item for item in (current or {}).get("actions", []) if item["id"] == action), None)
    if not current or not current.get("available") or not action_status or not action_status.get("enabled", True):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta integración o acción todavía no está disponible.",
        )
    try:
        return await handler(user, payload)
    except HTTPException:
        raise
    except Exception:  # pragma: no cover - degrade seguro
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al comunicarse con el proveedor.",
        ) from None
