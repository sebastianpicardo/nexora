from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from src.core.config import settings
from src.core.security import decode_access_token
from src.db import repositories
from src.db.pool import get_pool

ORG_ADMIN_ROLES = {"owner", "admin"}
AUDIT_ROLES = {"owner", "admin", "analyst", "user"}
READ_ROLES = {"owner", "admin", "analyst", "user", "auditor", "viewer"}


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")

    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida") from exc

    async with get_pool().connection() as conn:
        user = await repositories.get_user_with_org(conn, user_id)

    if user is None or not user["active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no disponible")
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]


def is_super_admin(user: dict) -> bool:
    return user.get("role") == "super_admin"


def is_org_admin(user: dict) -> bool:
    return user.get("role") in ORG_ADMIN_ROLES or is_super_admin(user)


def require_roles(*roles: str):
    async def dependency(user: CurrentUser) -> dict:
        role = user["role"]
        if role == "super_admin":
            return user
        if role in roles:
            return user
        if role == "owner" and "admin" in roles:
            return user
        if role == "admin" and "owner" in roles:
            return user
        if role == "analyst" and "user" in roles:
            return user
        if role == "viewer" and "auditor" in roles:
            return user
        if role == "user" and "analyst" in roles:
            return user
        if role == "auditor" and "viewer" in roles:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para esta acción",
        )

    return dependency


async def require_super_admin(user: CurrentUser) -> dict:
    if not is_super_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol super admin")
    return user


def org_settings(user: dict) -> dict:
    return {
        "price_spike_threshold_pct": float(user["price_spike_threshold_pct"]),
        "min_confidence": float(user["min_confidence"]),
        "default_currency": user["default_currency"],
    }
