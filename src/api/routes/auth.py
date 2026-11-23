from __future__ import annotations

import logging

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from src.api.deps import CurrentUser, auth_attempt_limiter, client_ip_from_request
from src.core.config import settings
from src.core.security import cookie_max_age, create_access_token, decode_access_token
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    OrganizationOut,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    UserOut,
    VerifyEmailRequest,
)
from src.services.auth_service import (
    authenticate_with_password,
    register_with_password,
    request_password_reset,
    resend_verification,
    reset_password_with_token,
    upsert_google_user,
    verify_email_with_token,
)
from src.services.recaptcha_service import verify_recaptcha

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def _user_out(user: dict) -> UserOut:
    return UserOut(
        id=user["id"],
        org_id=user["org_id"],
        email=user["email"],
        name=user["name"],
        avatar_url=user["avatar_url"],
        role=user["role"],
        job_title=user.get("job_title", ""),
        phone=user.get("phone", ""),
        timezone=user.get("timezone", "America/Santiago"),
        notify_quota=user.get("notify_quota", True),
        notify_weekly=user.get("notify_weekly", True),
        email_verified=user.get("email_verified", True),
        active=user["active"],
        last_login_at=user["last_login_at"],
        created_at=user["created_at"],
    )


def _org_out(user: dict) -> OrganizationOut:
    return OrganizationOut(
        id=user["org_id"],
        name=user["org_name"],
        slug=user["org_slug"],
        price_spike_threshold_pct=float(user["price_spike_threshold_pct"]),
        min_confidence=float(user["min_confidence"]),
        default_currency=user["default_currency"],
    )


def _set_session_cookie(response: Response, user: dict, session_id: str) -> None:
    token = create_access_token(
        user_id=user["id"],
        email=user["email"],
        org_id=user["org_id"],
        role=user["role"],
        name=user["name"],
        session_id=session_id,
    )
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=cookie_max_age(),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def _client_ip(request: Request) -> str | None:
    value = client_ip_from_request(request)
    return value if value and value != "unknown" else None


async def _record_session(user: dict, request: Request) -> str:
    try:
        async with get_pool().connection() as conn:
            max_sessions = settings.max_concurrent_sessions
            sessions = await repositories.list_user_sessions_for_user(
                conn,
                org_id=user["org_id"],
                user_id=user["id"],
                limit=max_sessions,
            )
            if len(sessions) >= max_sessions:
                await repositories.delete_user_session(conn, sessions[-1]["id"])
            return await repositories.record_user_session(
                conn,
                org_id=user["org_id"],
                user_id=user["id"],
                ip_address=_client_ip(request),
                user_agent=request.headers.get("user-agent", ""),
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("No se pudo registrar la sesión del usuario %s", user.get("id"))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo iniciar la sesión. Intenta nuevamente.",
        ) from exc


def _sanitize_metadata(metadata: dict | None) -> dict | None:
    """Elimina campos sensibles de los metadatos de auditoría (M4)."""
    if not metadata:
        return metadata
    sensitive_keys = {
        "password", "password_hash", "token", "access_token", "refresh_token",
        "api_key", "secret", "private_key", "client_secret", "recaptcha_token",
        "email", "ip_address", "user_agent",
    }
    sanitized: dict = {}
    for key, value in metadata.items():
        if key.lower() in sensitive_keys:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_metadata(value)
        else:
            sanitized[key] = value
    return sanitized


async def _audit(user: dict, action: str, request: Request) -> None:
    try:
        async with get_pool().connection() as conn:
            await repositories.record_audit_event(
                conn,
                org_id=user.get("org_id"),
                user_id=user.get("id"),
                action=action,
                entity_type="auth",
                entity_id=str(user.get("id") or ""),
                ip_address=_client_ip(request),
                metadata=_sanitize_metadata({"action": action}),
            )
    except Exception:
        logger.exception("No se pudo registrar el evento de auditoría %s", action)


@router.get("/config")
async def auth_config() -> dict:
    """Configuración pública que el cliente necesita para autenticarse."""
    return {
        "google_enabled": bool(settings.google_client_id and settings.google_client_secret),
        "recaptcha_enabled": settings.recaptcha_enabled,
        "recaptcha_site_key": settings.recaptcha_site_key,
        "payment_provider": settings.payment_provider,
    }


@router.post("/register", response_model=MeResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
) -> MeResponse:
    await auth_attempt_limiter(request, payload.email)
# Verificar reCAPTCHA solo si está configurado y viene token; si no,
    # degradar gracefully para permitir login con email/password sin bloqueos.
    if settings.recaptcha_enabled and payload.recaptcha_token:
        await verify_recaptcha(
            payload.recaptcha_token,
            remote_ip=_client_ip(request),
            expected_action="login",
        )
    user = await register_with_password(
        email=payload.email,
        password=payload.password,
        name=payload.name,
        organization_name=payload.organization_name,
    )
    session_id = await _record_session(user, request)
    _set_session_cookie(response, user, session_id)
    await _audit(user, "auth.register", request)
    return MeResponse(success=True, user=_user_out(user), organization=_org_out(user))


@router.post("/login", response_model=MeResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
) -> MeResponse:
    await auth_attempt_limiter(request, payload.email)
    # Verificar reCAPTCA solo si está configurado; si no, degradar gracefully
    # para permitir login con email/password sin bloqueos de CSP o tokens.
    if settings.recaptcha_enabled:
        await verify_recaptcha(
            payload.recaptcha_token,
            remote_ip=_client_ip(request),
            expected_action="login",
        )
    user = await authenticate_with_password(email=payload.email, password=payload.password)
    session_id = await _record_session(user, request)
    _set_session_cookie(response, user, session_id)
    await _audit(user, "auth.login", request)
    return MeResponse(success=True, user=_user_out(user), organization=_org_out(user))


@router.get("/google")
async def google_login(request: Request):
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth no está configurado. Completa GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET.",
        )
    return await oauth.google.authorize_redirect(request, settings.google_redirect_url)


@router.get("/google/callback")
async def google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        userinfo = token.get("userinfo")
        if not userinfo:
            userinfo = await oauth.google.userinfo(token=token)
        user = await upsert_google_user(dict(userinfo))
    except Exception as exc:
        logger.exception("Google OAuth callback failed: %s", exc)
        return RedirectResponse(url=f"{settings.frontend_origin}/?auth=error", status_code=302)

    response = RedirectResponse(url=f"{settings.frontend_origin}/?auth=ok", status_code=302)
    session_id = await _record_session(user, request)
    _set_session_cookie(response, user, session_id)
    await _audit(user, "auth.google", request)
    return response


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser) -> MeResponse:
    return MeResponse(success=True, user=_user_out(user), organization=_org_out(user))


@router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(settings.cookie_name)
    if token:
        try:
            payload = decode_access_token(token)
            session_id = payload.get("sid")
            if session_id:
                async with get_pool().connection() as conn:
                    await repositories.delete_user_session(conn, session_id)
        except Exception:
            logger.debug("No se pudo revocar la sesión al cerrar sesión", exc_info=True)
    response = JSONResponse({"success": True})
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return response


@router.post("/forgot-password")
async def forgotten_password(payload: ForgotPasswordRequest, request: Request) -> dict:
    await auth_attempt_limiter(request, payload.email)
# Verificar reCAPTCHA solo si está configurado y viene token; si no,
    # degradar gracefully para permitir solicitud de recuperación sin bloqueos.
    if settings.recaptcha_enabled and payload.recaptcha_token:
        await verify_recaptcha(
            payload.recaptcha_token,
            remote_ip=_client_ip(request),
            expected_action="forgot_password",
        )
    await request_password_reset(email=payload.email)
    return {"success": True, "message": "Si el email existe, recibirás un enlace de recuperación."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest) -> dict:
    await reset_password_with_token(token=payload.token, password=payload.password)
    return {"success": True, "message": "Contraseña actualizada. Ya puedes iniciar sesión."}


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest) -> dict:
    await verify_email_with_token(token=payload.token)
    return {"success": True, "message": "Email verificado correctamente."}


@router.post("/resend-verification")
async def resend_verification_email(
    payload: ResendVerificationRequest,
    request: Request,
) -> dict:
    await auth_attempt_limiter(request, payload.email)
    await resend_verification(email=payload.email)
    return {"success": True, "message": "Si la cuenta existe y no está verificada, recibirás un correo."}
