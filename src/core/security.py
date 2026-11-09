from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from src.core.config import settings

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 390_000
PASSWORD_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Devuelve un hash PBKDF2-HMAC-SHA256 con sal aleatoria y formato autodescriptivo."""
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")
    salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "$".join(
        (
            PASSWORD_ALGORITHM,
            str(PASSWORD_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, stored_hash: str | None) -> bool:
    """Compara en tiempo constante una contraseña contra el hash almacenado."""
    if not password or not stored_hash:
        return False
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored_hash.split("$")
        if algorithm != PASSWORD_ALGORITHM:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sign_payload(secret: str, payload: bytes) -> str:
    """Firma HMAC-SHA256 de un payload crudo, usada para webhooks de pago."""
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_signature(secret: str, payload: bytes, signature: str | None) -> bool:
    if not secret or not signature:
        return False
    return hmac.compare_digest(sign_payload(secret, payload), signature.strip())


def verify_stripe_signature(secret: str, payload: bytes, header: str | None, tolerance_seconds: int = 300) -> bool:
    """Valida el header Stripe-Signature (t=timestamp,v1=firma)."""
    if not secret or not header:
        return False
    parts: dict[str, str] = {}
    for item in header.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
    timestamp = parts.get("t")
    provided = parts.get("v1")
    if not timestamp or not provided or not timestamp.isdigit():
        return False
    now = int(datetime.now(UTC).timestamp())
    if abs(now - int(timestamp)) > tolerance_seconds:
        return False
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


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
        "kid": settings.jwt_key_version,
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

    # Validar versión de clave (key rotation)
    kid = payload.get("kid")
    if kid is not None and int(kid) != settings.jwt_key_version:
        raise ValueError("Token con clave de firma obsoleta. Inicie sesión nuevamente.")

    return payload


def cookie_max_age() -> int:
    return settings.jwt_expires_minutes * 60
