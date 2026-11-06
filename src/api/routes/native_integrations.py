from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import CurrentUser, require_roles
from src.services import native_integrations_service as ni

router = APIRouter(prefix="/api/integrations/native", tags=["native-integrations"])


@router.get("/status")
async def native_integrations_status(user: CurrentUser) -> dict[str, Any]:
    return await ni.list_native_integrations(user)


@router.post("/{provider}/{action}")
async def native_integration_action(
    provider: str,
    action: str,
    payload: dict[str, Any] = {},
    user: dict = Depends(require_roles("owner", "admin", "analyst", "user")),
) -> dict[str, Any]:
    if provider not in ni.PROVIDERS:
        raise HTTPException(status_code=404, detail="Proveedor no soportado.")
    handlers = ni.ACTION_HANDLERS.get(provider, {})
    handler = handlers.get(action)
    if handler is None:
        raise HTTPException(status_code=404, detail="Acción no soportada para este proveedor.")
    try:
        return await handler(user, payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - degrade seguro
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
