from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.config import Settings


def test_default_currency_is_normalized_and_validated():
    assert Settings(_env_file=None, default_currency="usd").default_currency == "USD"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, default_currency="ABC")


def test_production_requires_secure_cookie_and_long_secrets():
    with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
        Settings(
            _env_file=None, database_url="postgresql://db", app_env="production", cookie_secure=False
        ).validate_startup()

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings(
            _env_file=None,
            database_url="postgresql://db",
            app_env="production",
            cookie_secure=True,
            jwt_secret="short",
        ).validate_startup()


def test_supabase_storage_requires_credentials():
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        Settings(
            _env_file=None,
            database_url="postgresql://db",
            storage_backend="supabase",
        ).validate_startup()
