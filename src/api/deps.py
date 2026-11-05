from __future__ import annotations

import time
from collections import deque
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send

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

class RateLimitMiddleware:
    """Rate limiting en memoria por IP para las rutas /api.

    Adecuado para una instancia unica (Render starter). Los webhooks de pago
    quedan exentos para no perder notificaciones del proveedor.
    """

    EXEMPT_PREFIXES = ("/api/billing/webhook/",)

    def __init__(self, app: ASGIApp, limit: int | None = None, window_seconds: int = 60):
        self.app = app
        self.limit = max(int(limit or settings.rate_limit_per_minute), 1)
        self.window_seconds = max(int(window_seconds), 1)
        self._hits: dict[str, deque[float]] = {}

    def _is_limited(self, path: str) -> bool:
        if not path.startswith("/api"):
            return False
        return not any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._is_limited(str(scope.get("path", ""))):
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        headers = dict(scope.get("headers") or [])
        forwarded = headers.get(b"x-forwarded-for", b"").decode("latin-1")
        ip = forwarded.split(",")[0].strip() if forwarded else (client[0] if client else "unknown")

        now = time.monotonic()
        cutoff = now - self.window_seconds
        bucket = self._hits.setdefault(ip, deque())
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.limit:
            retry_after = max(int(self.window_seconds - (now - bucket[0])) if bucket else self.window_seconds, 1)
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"success": False, "error": "Demasiadas solicitudes. Intenta nuevamente en unos segundos."},
                headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(self.limit)},
            )
            await response(scope, receive, send)
            return

        bucket.append(now)
        remaining = max(self.limit - len(bucket), 0)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers["X-RateLimit-Limit"] = str(self.limit)
                response_headers["X-RateLimit-Remaining"] = str(remaining)
            await send(message)

        await self.app(scope, receive, send_with_headers)
