from __future__ import annotations

import pytest

from src.core.config import settings
from src.services import recaptcha_service
from src.services.recaptcha_service import RecaptchaError, verify_recaptcha


class _DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _DummyClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self) -> _DummyClient:
        return self

    async def __aexit__(self, *_args) -> bool:
        return False

    async def post(self, url: str, data: dict) -> _DummyResponse:
        self.calls.append((url, data))
        return _DummyResponse(self.payload)


@pytest.fixture(autouse=True)
def _configure(monkeypatch):
    monkeypatch.setattr(settings, "recaptcha_secret_key", "test-secret")
    monkeypatch.setattr(settings, "recaptcha_min_score", 0.5)


def _patch_client(monkeypatch, payload: dict) -> _DummyClient:
    client = _DummyClient(payload)
    monkeypatch.setattr(recaptcha_service.httpx, "AsyncClient", lambda **_kwargs: client)
    return client


async def test_verify_recaptcha_skips_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "recaptcha_secret_key", "")

    result = await verify_recaptcha(None)

    assert result == {"skipped": True, "score": None, "action": None}


async def test_verify_recaptcha_requires_token():
    with pytest.raises(RecaptchaError):
        await verify_recaptcha(None)


async def test_verify_recaptcha_returns_score(monkeypatch):
    client = _patch_client(
        monkeypatch,
        {"success": True, "score": 0.9, "action": "login"},
    )

    result = await verify_recaptcha("token-123", remote_ip="1.2.3.4", expected_action="login")

    assert result == {"skipped": False, "score": 0.9, "action": "login"}
    assert client.calls[0][1]["response"] == "token-123"
    assert client.calls[0][1]["remoteip"] == "1.2.3.4"


async def test_verify_recaptcha_rejects_low_score(monkeypatch):
    _patch_client(monkeypatch, {"success": True, "score": 0.2, "action": "register"})

    with pytest.raises(RecaptchaError):
        await verify_recaptcha("token-123", expected_action="register")


async def test_verify_recaptcha_rejects_failed_verification(monkeypatch):
    _patch_client(monkeypatch, {"success": False, "error-codes": ["invalid-input-response"]})

    with pytest.raises(RecaptchaError):
        await verify_recaptcha("token-123")


async def test_verify_recaptcha_rejects_action_mismatch(monkeypatch):
    _patch_client(monkeypatch, {"success": True, "score": 0.9, "action": "login"})

    with pytest.raises(RecaptchaError):
        await verify_recaptcha("token-123", expected_action="register")
