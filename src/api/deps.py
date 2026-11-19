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

# Matriz explícita de privilegios: cada rol puede satisfacer únicamente los
# roles listados. No se usan equivalencias implícitas (p. ej. `user` no puede
# actuar como `analyst` ni `viewer` como `auditor`).
ROLE_GRANTS: dict[str, set[str]] = {
    "owner": {"owner", "admin", "analyst", "user", "auditor", "viewer"},
    "admin": {"admin", "analyst", "user", "auditor", "viewer"},
    "analyst": {"analyst", "user", "viewer"},
    "user": {"user", "viewer"},
    "auditor": {"auditor", "viewer"},
    "viewer": {"viewer"},
}


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")

    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
        raw_session_id = payload.get("sid")
        session_id = UUID(raw_session_id) if raw_session_id else None
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida") from exc

    if session_id is None and settings.is_production:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida")

    async with get_pool().connection() as conn:
        user = await repositories.get_user_with_org(conn, user_id, session_id=session_id)

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
        if ROLE_GRANTS.get(role, set()) & set(roles):
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
        "ai_data_consent": bool(user.get("ai_data_consent", True)),
        "ai_images_enabled": bool(user.get("ai_images_enabled", True)),
        "ai_text_max_chars": int(user.get("ai_text_max_chars") or 200_000),
    }


def _client_ip_from_scope(scope: Scope) -> str:
    """Obtiene la IP del cliente usando el ultimo salto de X-Forwarded-For.

    El proxy de despliegue agrega la IP real al final de la cadena; usar el
    primer valor permitia a un atacante falsificar su IP y evadir el limite.
    """

    headers = dict(scope.get("headers") or [])
    forwarded = headers.get(b"x-forwarded-for", b"").decode("latin-1")
    if forwarded:
        for candidate in reversed(forwarded.split(",")):
            candidate = candidate.strip()
            if candidate:
                return candidate[:64]
    client = scope.get("client")
    return (client[0] if client else "unknown")[:64]


def client_ip_from_request(request: Request) -> str:
    return _client_ip_from_scope(request.scope)


class RateLimitMiddleware:
    """Rate limiting en memoria por IP para las rutas /api.

    Adecuado para una instancia unica (Render starter). Los webhooks de pago
    quedan exentos para no perder notificaciones del proveedor.
    """

    EXEMPT_PREFIXES = ("/api/billing/webhook/",)
    MAX_BUCKETS = 20_000

    def __init__(self, app: ASGIApp, limit: int | None = None, window_seconds: int = 60):
        self.app = app
        self.limit = max(int(limit or settings.rate_limit_per_minute), 1)
        self.window_seconds = max(int(window_seconds), 1)
        self._hits: dict[str, deque[float]] = {}

    def _is_limited(self, path: str) -> bool:
        if not path.startswith("/api"):
            return False
        return not any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES)

    def _prune(self, cutoff: float) -> None:
        if len(self._hits) < self.MAX_BUCKETS:
            return
        for key, values in list(self._hits.items()):
            if not values or values[-1] <= cutoff:
                self._hits.pop(key, None)
        while len(self._hits) >= self.MAX_BUCKETS:
            self._hits.pop(next(iter(self._hits)))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._is_limited(str(scope.get("path", ""))):
            await self.app(scope, receive, send)
            return

        ip = _client_ip_from_scope(scope)

        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._prune(cutoff)
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


class SpecificRateLimiter:
    """Rate limiting en memoria por usuario/organizacion para rutas costosas."""

    def __init__(self, scope: str, setting_name: str, window_seconds: int = 60):
        self.scope = scope
        self.setting_name = setting_name
        self.window_seconds = max(int(window_seconds), 1)
        self._hits: dict[str, deque[float]] = {}

    async def __call__(self, request: Request, user: CurrentUser) -> None:
        limit = max(int(getattr(settings, self.setting_name, 1) or 1), 1)
        now = time.monotonic()
        cutoff = now - self.window_seconds
        key = f"{self.scope}:{user.get('org_id')}:{user.get('id')}"
        bucket = self._hits.setdefault(key, deque())
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(int(self.window_seconds - (now - bucket[0])) if bucket else self.window_seconds, 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes. Intenta nuevamente en unos segundos.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def rate_limit(scope: str, setting_name: str, window_seconds: int = 60) -> SpecificRateLimiter:
    return SpecificRateLimiter(scope, setting_name, window_seconds)


class AuthAttemptLimiter:
    """Rate limiting por IP+email para endpoints de autenticación sin sesión."""

    def __init__(self, setting_name: str = "auth_attempt_rate_limit_per_minute", window_seconds: int = 60):
        self.setting_name = setting_name
        self.window_seconds = max(int(window_seconds), 1)
        self._hits: dict[str, deque[float]] = {}

    async def __call__(self, request: Request, email: str) -> None:
        limit = max(int(getattr(settings, self.setting_name, 10) or 10), 1)
        key = f"auth:{client_ip_from_request(request)}:{str(email or '').strip().lower()}"
        bucket = self._hits.setdefault(key, deque())
        now = time.monotonic()
        cutoff = now - self.window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(int(self.window_seconds - (now - bucket[0])) if bucket else self.window_seconds, 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos. Intenta nuevamente en unos segundos.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


auth_attempt_limiter = AuthAttemptLimiter()


class OriginGuardMiddleware:
    """Bloquea peticiones mutables con cookie de sesion desde origenes ajenos.

    SameSite=Lax mitiga la mayoria de CSRF, pero esta comprobacion de Origin
    y Sec-Fetch-Site agrega defensa en profundidad para navegadores antiguos.
    Las peticiones sin cookie (API keys, webhooks externos) no se ven afectadas.
    """

    UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, app: ASGIApp):
        self.app = app
        self.allowed_origins = {
            origin.strip().rstrip("/").lower()
            for origin in settings.cors_origins_list
            if origin.strip()
        }

    @staticmethod
    def _has_session_cookie(header_value: bytes) -> bool:
        cookie_name = f"{settings.cookie_name}=".encode("latin-1")
        return cookie_name in header_value

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", "")).upper()
        path = str(scope.get("path", ""))
        if method not in self.UNSAFE_METHODS or not path.startswith("/api"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        if not self._has_session_cookie(headers.get(b"cookie", b"")):
            await self.app(scope, receive, send)
            return

        origin = headers.get(b"origin", b"").decode("latin-1").strip().rstrip("/").lower()
        fetch_site = headers.get(b"sec-fetch-site", b"").decode("latin-1").strip().lower()
        cross_site = fetch_site == "cross-site"
        invalid_origin = bool(origin) and origin not in self.allowed_origins
        if cross_site or invalid_origin:
            response = JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"success": False, "error": "Origen no permitido para esta accion."},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """Añade encabezados de seguridad a todas las respuestas HTTP."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                # Prevenir clickjacking
                headers["X-Frame-Options"] = "DENY"
                # Prevenir MIME sniffing
                headers["X-Content-Type-Options"] = "nosniff"
                # Política de remitente
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                # HSTS solo en producción (HTTPS)
                if settings.is_production:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                # Content Security Policy con soporte para Google reCAPTCHA v3.
                headers["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
                    "https://www.google.com https://www.gstatic.com; "
                    "script-src-elem 'self' 'unsafe-inline' "
                    "https://www.google.com https://www.gstatic.com; "
                    "style-src 'self' 'unsafe-inline' https://www.gstatic.com; "
                    "img-src 'self' data: https:; "
                    "connect-src 'self' https: https://www.google.com https://www.gstatic.com; "
                    "frame-src 'self' https://www.google.com https://www.gstatic.com; "
                    "font-src 'self' https://www.gstatic.com; "
                    "object-src 'none'; "
                    "base-uri 'self'; "
                    "frame-ancestors 'none'; "
                    "form-action 'self';"
                )
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
