from __future__ import annotations

import pytest

from src.core.config import PRODUCTION_PUBLIC_URL, Settings


@pytest.fixture(autouse=True)
def _clear_render_external_url(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)


def _production_settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "app_env": "production",
        "frontend_url": "https://nexora-web-g9td.onrender.com/",
        "cors_origins": "https://nexora-web-g9td.onrender.com/, http://localhost:5173/",
        "google_redirect_uri": "",
    }
    values.update(overrides)
    return Settings(**values)


def test_cors_origins_normalize_trailing_slashes():
    settings = _production_settings()

    assert settings.frontend_origin == "https://nexora-web-g9td.onrender.com"
    assert settings.cors_origins_list == ["https://nexora-web-g9td.onrender.com"]


def test_cors_origins_include_configured_extra_origins():
    settings = _production_settings(
        cors_origins="https://nexora-web-g9td.onrender.com/, https://app.example.org/",
    )

    assert "https://app.example.org" in settings.cors_origins_list
    assert all(not origin.endswith("/") for origin in settings.cors_origins_list)


def test_old_onrender_url_is_replaced_by_current_public_url(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    settings = _production_settings(frontend_url="https://nexora-web.onrender.com/")

    assert settings.frontend_origin == PRODUCTION_PUBLIC_URL
    assert settings.cors_origins_list == [PRODUCTION_PUBLIC_URL]


def test_render_external_url_takes_precedence(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://nexora-preview.onrender.com/")
    settings = _production_settings(frontend_url="https://nexora-web.onrender.com/")

    assert settings.frontend_origin == "https://nexora-preview.onrender.com"
    assert settings.google_redirect_url == ("https://nexora-preview.onrender.com/api/auth/google/callback")


def test_google_redirect_derived_from_frontend_url():
    settings = _production_settings()

    assert settings.google_redirect_url == ("https://nexora-web-g9td.onrender.com/api/auth/google/callback")


def test_old_google_redirect_is_replaced(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    settings = _production_settings(
        google_redirect_uri="https://nexora-web.onrender.com/api/auth/google/callback/",
    )

    assert settings.google_redirect_url == (f"{PRODUCTION_PUBLIC_URL}/api/auth/google/callback")


def test_google_redirect_normalizes_configured_url():
    settings = _production_settings(
        google_redirect_uri="https://nexora-web-g9td.onrender.com/api/auth/google/callback/",
    )

    assert settings.google_redirect_url == ("https://nexora-web-g9td.onrender.com/api/auth/google/callback")


def test_production_placeholder_frontend_uses_public_url():
    settings = _production_settings(frontend_url="https://TU-URL.onrender.com/")

    assert settings.frontend_origin == PRODUCTION_PUBLIC_URL
    assert settings.google_redirect_url == (f"{PRODUCTION_PUBLIC_URL}/api/auth/google/callback")


@pytest.mark.parametrize("frontend_url", ["", "http://localhost:5173/"])
def test_missing_or_local_frontend_uses_public_url(frontend_url):
    settings = _production_settings(frontend_url=frontend_url)

    assert settings.frontend_origin == PRODUCTION_PUBLIC_URL
