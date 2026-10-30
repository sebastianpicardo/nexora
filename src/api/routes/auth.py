from __future__ import annotations

import logging

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from src.api.deps import CurrentUser
from src.core.config import settings
from src.core.security import cookie_max_age, create_access_token
from src.schemas.auth import MeResponse, OrganizationOut, UserOut
from src.services.auth_service import upsert_google_user

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


def _set_session_cookie(response: Response, user: dict) -> None:
    token = create_access_token(
        user_id=user["id"],
        email=user["email"],
        org_id=user["org_id"],
        role=user["role"],
        name=user["name"],
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
    _set_session_cookie(response, user)
    return response


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser) -> MeResponse:
    return MeResponse(success=True, user=_user_out(user), organization=_org_out(user))


@router.post("/logout")
async def logout():
    response = JSONResponse({"success": True})
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return response
