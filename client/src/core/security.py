from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from src.core.config import settings


def create_access_token(
    *,
    user_id: UUID | str,
    email: str,
    org_id: UUID | str,
    role: str,
    name: str,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "org_id": str(org_id),
        "role": role,
        "name": name,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expires_minutes),
        "iss": settings.app_name,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.app_name,
        )
    except InvalidTokenError as exc:
        raise ValueError("Token inválido o expirado") from exc

    if not payload.get("sub"):
        raise ValueError("Token sin identificador de usuario")
    return payload


def cookie_max_age() -> int:
    return settings.jwt_expires_minutes * 60
