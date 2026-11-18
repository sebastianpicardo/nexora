from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.api.deps import AuthAttemptLimiter, OriginGuardMiddleware, _client_ip_from_scope, require_roles
from src.api.routes.enterprise import _decrypt_config, _encrypt_config, _redact_config, _redact_target
from src.core.config import settings
from src.core.security import cookie_max_age, create_access_token, decode_access_token
from src.core.url_safety import ensure_safe_outbound_url, validate_outbound_url
from src.services.storage_service import resolve_upload_mime


def test_create_and_decode_access_token():
    user_id = uuid4()
    org_id = uuid4()

    token = create_access_token(
        user_id=user_id,
        email="owner@example.com",
        org_id=org_id,
        role="owner",
        name="Owner",
    )
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["org_id"] == str(org_id)
    assert payload["email"] == "owner@example.com"
    assert payload["role"] == "owner"
    assert payload["iss"] == settings.app_name


def test_invalid_token_raises_value_error():
    with pytest.raises(ValueError):
        decode_access_token("not-a-real-token")


def test_expired_token_raises_value_error(monkeypatch):
    monkeypatch.setattr(settings, "jwt_expires_minutes", -1)
    token = create_access_token(
        user_id=uuid4(),
        email="expired@example.com",
        org_id=uuid4(),
        role="viewer",
        name="Expired",
    )

    with pytest.raises(ValueError):
        decode_access_token(token)


def test_cookie_max_age_matches_settings():
    assert cookie_max_age() == settings.jwt_expires_minutes * 60
    assert cookie_max_age() > 0


def test_access_token_can_carry_session_id():
    session_id = uuid4()
    token = create_access_token(
        user_id=uuid4(),
        email="session@example.com",
        org_id=uuid4(),
        role="owner",
        name="Session",
        session_id=session_id,
    )

    assert decode_access_token(token)["sid"] == str(session_id)


async def test_admin_cannot_satisfy_owner_role():
    dependency = require_roles("owner")

    with pytest.raises(HTTPException) as exc_info:
        await dependency({"role": "admin"})

    assert exc_info.value.status_code == 403


async def test_owner_and_super_admin_satisfy_owner_role():
    dependency = require_roles("owner")

    assert (await dependency({"role": "owner"}))["role"] == "owner"
    assert (await dependency({"role": "super_admin"}))["role"] == "super_admin"


def test_client_ip_uses_last_forwarded_for_hop():
    scope = {
        "headers": [(b"x-forwarded-for", b"1.1.1.1, 203.0.113.9")],
        "client": ("10.0.0.1", 1234),
    }

    assert _client_ip_from_scope(scope) == "203.0.113.9"


def test_client_ip_falls_back_to_socket_client():
    assert _client_ip_from_scope({"headers": [], "client": ("198.51.100.7", 1234)}) == "198.51.100.7"


async def _ok_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b""})


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


async def _run_origin_guard(headers):
    messages = []

    async def send(message):
        messages.append(message)

    middleware = OriginGuardMiddleware(_ok_app)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/documents",
        "headers": headers,
        "client": ("198.51.100.7", 1234),
    }
    await middleware(scope, _receive, send)
    return messages


async def test_origin_guard_blocks_cross_site_session_requests():
    messages = await _run_origin_guard(
        [
            (b"cookie", f"{settings.cookie_name}=valid".encode("latin-1")),
            (b"origin", b"https://evil.example"),
        ]
    )

    assert messages[0]["status"] == 403


async def test_origin_guard_allows_configured_origin():
    origin = settings.cors_origins_list[0].encode("latin-1")
    messages = await _run_origin_guard(
        [
            (b"cookie", f"{settings.cookie_name}=valid".encode("latin-1")),
            (b"origin", origin),
        ]
    )

    assert messages[0]["status"] == 200


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "http://localhost/health",
        "http://127.0.0.1/health",
        "http://[::1]/health",
        "http://169.254.169.254/latest/meta-data",
        "https://user:pass@example.com/health",
    ],
)
def test_outbound_url_rejects_unsafe_destinations(url):
    with pytest.raises(ValueError):
        validate_outbound_url(url)


def test_outbound_url_accepts_public_http_urls():
    assert validate_outbound_url("https://example.com/health?check=1") == "https://example.com/health?check=1"


async def test_ensure_safe_outbound_url_rejects_private_literal():
    with pytest.raises(ValueError):
        await ensure_safe_outbound_url("http://10.0.0.5/internal")


async def test_ensure_safe_outbound_url_accepts_global_literal():
    assert await ensure_safe_outbound_url("https://8.8.8.8/health") == "https://8.8.8.8/health"


def test_resolve_upload_mime_accepts_declared_text_for_text_suffix():
    assert resolve_upload_mime("compras.csv", None, "text/csv") == "text/csv"
    assert resolve_upload_mime("nota.txt", None, "text/plain") == "text/plain"


def test_resolve_upload_mime_accepts_detected_pdf():
    assert resolve_upload_mime("factura.pdf", "application/pdf", None) == "application/pdf"


def test_resolve_upload_mime_rejects_mime_extension_mismatch():
    with pytest.raises(ValueError):
        resolve_upload_mime("documento.pdf", "text/html", None)
    with pytest.raises(ValueError):
        resolve_upload_mime("documento.xlsx", "application/pdf", None)
    with pytest.raises(ValueError):
        resolve_upload_mime("documento.png", None, "application/pdf")


def test_resolve_upload_mime_accepts_office_zip_wrapper():
    assert resolve_upload_mime("libro.xlsx", "application/zip", None) == "application/zip"
    assert resolve_upload_mime("libro.xls", None, "application/vnd.ms-excel") == "application/vnd.ms-excel"


async def test_auth_attempt_limiter_blocks_repeated_attempts(monkeypatch):
    monkeypatch.setattr(settings, "auth_attempt_rate_limit_per_minute", 2)
    limiter = AuthAttemptLimiter()

    class FakeRequest:
        scope = {"headers": [], "client": ("198.51.100.7", 1234)}

    request = FakeRequest()
    await limiter(request, "usuario@example.com")
    await limiter(request, "usuario@example.com")

    with pytest.raises(HTTPException) as exc_info:
        await limiter(request, "usuario@example.com")

    assert exc_info.value.status_code == 429


async def test_auth_attempt_limiter_is_scoped_by_email_and_ip(monkeypatch):
    monkeypatch.setattr(settings, "auth_attempt_rate_limit_per_minute", 2)
    limiter = AuthAttemptLimiter()

    class FakeRequest:
        scope = {"headers": [], "client": ("198.51.100.7", 1234)}

    request = FakeRequest()
    await limiter(request, "uno@example.com")
    await limiter(request, "dos@example.com")


def test_integration_config_encrypts_sensitive_values():
    config = {"token": "super-secret", "endpoint": "https://api.example.com/v1"}

    encrypted = _encrypt_config(config)

    assert encrypted["token"] != "super-secret"
    assert encrypted["endpoint"] == "https://api.example.com/v1"
    assert _decrypt_config(encrypted)["token"] == "super-secret"
    redacted = _redact_config(encrypted)
    assert redacted["endpoint"] == "https://api.example.com/v1"
    assert "super-secret" not in str(redacted)


def test_redact_target_hides_webhook_path_and_token():
    channel = {"channel": "webhook", "target": "https://hooks.example.com/services/T000/B000/XXXX"}

    redacted = _redact_target(channel)

    assert "hooks.example.com" in redacted["target"]
    assert "XXXX" not in redacted["target"]
    assert _redact_target({"channel": "email", "target": "compras@nexora.test"})["target"] == "compras@nexora.test"
