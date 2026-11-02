from __future__ import annotations

import pytest

from src.core.config import settings
from src.core.errors import ValidationError
from src.services.payment_service import _with_query, create_checkout_session

PRO_PLAN = {
    "id": "pro",
    "name": "Pro",
    "description": "Plan Pro",
    "price_monthly": 49,
    "currency": "USD",
}


def test_with_query_respects_existing_query_string():
    assert _with_query("http://localhost:5173/", {"a": "1"}) == "http://localhost:5173/?a=1"
    assert (
        _with_query("http://localhost:5173/?checkout=success", {"plan_id": "pro"})
        == "http://localhost:5173/?checkout=success&plan_id=pro"
    )


async def test_mock_checkout_returns_session(monkeypatch):
    monkeypatch.setattr(settings, "payment_provider", "mock")

    session = await create_checkout_session(PRO_PLAN, org_id="org-1", email="ana@empresa.com")

    assert session["provider"] == "mock"
    assert session["plan_id"] == "pro"
    assert session["amount"] == 49
    assert session["session_id"]
    assert "plan_id=pro" in session["checkout_url"]


async def test_unsupported_provider_raises(monkeypatch):
    monkeypatch.setattr(settings, "payment_provider", "paypal")

    with pytest.raises(ValidationError):
        await create_checkout_session(PRO_PLAN, org_id="org-1")


async def test_stripe_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "payment_provider", "stripe")
    monkeypatch.setattr(settings, "stripe_secret_key", "")

    with pytest.raises(ValidationError):
        await create_checkout_session(PRO_PLAN, org_id="org-1")
