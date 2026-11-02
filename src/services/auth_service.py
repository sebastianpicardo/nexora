from __future__ import annotations

from psycopg.errors import UniqueViolation

from src.core.config import settings
from src.core.errors import ConflictError, PermissionDeniedError
from src.core.security import hash_password, verify_password
from src.db import repositories
from src.db.pool import get_pool


async def _ensure_super_admin(conn, user: dict) -> dict:
    if user["email"].lower() not in settings.super_admin_emails_set:
        return user
    if user["role"] == "super_admin":
        return user
    await repositories.set_user_role(conn, user["id"], "super_admin")
    refreshed = await repositories.get_user_with_org(conn, user["id"])
    return refreshed or user


def _profile_values(profile: dict) -> tuple[str, str, str, str]:
    email = str(profile.get("email") or "").strip().lower()
    google_id = str(profile.get("sub") or "").strip()
    name = str(profile.get("name") or email.split("@")[0]).strip()
    avatar_url = str(profile.get("picture") or "").strip()

    if not email or "@" not in email:
        raise PermissionDeniedError("Google no entregó un email válido.")
    if not google_id:
        raise PermissionDeniedError("Google no entregó un identificador de usuario.")
    if profile.get("email_verified") is False:
        raise PermissionDeniedError("El email de Google no está verificado.")
    return email, google_id, name, avatar_url


async def register_with_password(
    *, email: str, password: str, name: str, organization_name: str | None = None
) -> dict:
    password_hash = hash_password(password)
    async with get_pool().connection() as conn:
        existing = await repositories.get_user_by_email(conn, email)
        if existing is not None:
            raise ConflictError("Ya existe una cuenta con este email. Inicia sesión.")
        try:
            created = await repositories.create_user_with_org(
                conn,
                email=email,
                google_id=None,
                password_hash=password_hash,
                name=name,
                avatar_url="",
                organization_name=organization_name,
                price_spike_threshold_pct=settings.default_price_spike_threshold_pct,
                min_confidence=settings.min_extraction_confidence,
                default_currency=settings.default_currency.strip().upper(),
            )
        except UniqueViolation as exc:
            await conn.rollback()
            raise ConflictError("Ya existe una cuenta con este email. Inicia sesión.") from exc
        return await _ensure_super_admin(conn, created)


async def authenticate_with_password(*, email: str, password: str) -> dict:
    async with get_pool().connection() as conn:
        row = await repositories.get_user_auth_by_email(conn, email)
        if row is None or not verify_password(password, row.get("password_hash")):
            raise PermissionDeniedError("Email o contraseña incorrectos.")
        if not row["active"]:
            raise PermissionDeniedError("La cuenta está desactivada. Contacta al administrador.")

        await repositories.touch_last_login(conn, row["id"])
        user = await repositories.get_user_with_org(conn, row["id"])
        if user is None:
            raise PermissionDeniedError("No se pudo recuperar la cuenta.")
        return await _ensure_super_admin(conn, user)


async def upsert_google_user(profile: dict) -> dict:
    email, google_id, name, avatar_url = _profile_values(profile)

    async with get_pool().connection() as conn:
        user = await repositories.get_user_by_google_id(conn, google_id)
        if user:
            if not user["active"]:
                raise PermissionDeniedError("La cuenta está desactivada.")
            await repositories.update_google_profile(
                conn,
                user_id=user["id"],
                google_id=google_id,
                name=name,
                avatar_url=avatar_url,
            )
            refreshed = await repositories.get_user_with_org(conn, user["id"])
            if refreshed is None:
                raise RuntimeError("No se pudo refrescar el usuario.")
            return await _ensure_super_admin(conn, refreshed)

        user = await repositories.get_user_by_email(conn, email)
        if user:
            if not user["active"]:
                raise PermissionDeniedError("La cuenta está desactivada.")
            await repositories.update_google_profile(
                conn,
                user_id=user["id"],
                google_id=google_id,
                name=name,
                avatar_url=avatar_url,
            )
            refreshed = await repositories.get_user_with_org(conn, user["id"])
            if refreshed is None:
                raise RuntimeError("No se pudo refrescar el usuario.")
            return await _ensure_super_admin(conn, refreshed)

        try:
            created = await repositories.create_user_with_org(
                conn,
                email=email,
                google_id=google_id,
                name=name,
                avatar_url=avatar_url,
                price_spike_threshold_pct=settings.default_price_spike_threshold_pct,
                min_confidence=settings.min_extraction_confidence,
                default_currency=settings.default_currency.strip().upper(),
            )
            return await _ensure_super_admin(conn, created)
        except UniqueViolation:
            await conn.rollback()

    # Condición de carrera: otro request creó el usuario mientras tanto.
    async with get_pool().connection() as conn:
        user = await repositories.get_user_by_email(conn, email)
        if user is None:
            raise RuntimeError("No se pudo crear ni recuperar el usuario de Google.")
        if not user["active"]:
            raise PermissionDeniedError("La cuenta está desactivada.")
        await repositories.touch_last_login(conn, user["id"])
        return await _ensure_super_admin(conn, user)
