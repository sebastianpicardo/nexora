from __future__ import annotations

from uuid import uuid4

import pytest

from src.core.config import settings
from src.core.security import cookie_max_age, create_access_token, decode_access_token


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
