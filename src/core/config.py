from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.parsers.normalization.currency import normalize_currency

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_PUBLIC_URL = "https://nexora-web-g9td.onrender.com"


def _normalize_origin(value: str) -> str:
    candidate = value.strip().rstrip("/")
    if not candidate:
        return ""
    parts = urlsplit(candidate)
    if not parts.scheme or not parts.netloc:
        return candidate
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), "", "", ""))


def _is_placeholder_url(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ("localhost", "127.0.0.1", "tu-url", "tu_dominio", "example.com"))


class Settings(BaseSettings):
    """Configuración centralizada leída desde variables de entorno o .env."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "NEXORA"
    app_env: str = "development"
    app_version: str = "0.1.0"
    port: int = 8000
    log_level: str = "INFO"

    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"

    database_url: str = ""

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "nexora-documents"
    storage_backend: str = "local"
    local_upload_dir: str = "./uploads"

    jwt_secret: str = "change-me-in-production"
    jwt_expires_minutes: int = 10080
    session_secret: str = "change-me-in-production"
    cookie_name: str = "nexora_token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    super_admin_emails: str = ""

    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    llm_max_pages: int = Field(default=8, ge=1, le=30)
    llm_max_input_chars: int = Field(default=60000, ge=1000)
    llm_timeout_seconds: int = Field(default=120, ge=10)

    default_price_spike_threshold_pct: float = Field(default=10.0, ge=0)
    min_extraction_confidence: float = Field(default=0.75, ge=0, le=1)
    default_currency: str = Field(default="CLP", min_length=3, max_length=3)
    price_lookback_days: int = Field(default=365, ge=1)
    min_history_samples: int = Field(default=2, ge=1)
    max_upload_mb: int = Field(default=25, ge=1)

    process_in_background: bool = True
    worker_poll_seconds: int = Field(default=10, ge=1)

    @field_validator("default_currency", mode="after")
    @classmethod
    def _validate_default_currency(cls, value: str) -> str:
        normalized = normalize_currency(value, default="")
        if not normalized:
            raise ValueError("DEFAULT_CURRENCY no es una moneda soportada.")
        return normalized

    @field_validator("frontend_url", mode="after")
    @classmethod
    def _normalize_frontend_url(cls, value: str) -> str:
        return _normalize_origin(value)

    @field_validator("google_redirect_uri", mode="after")
    @classmethod
    def _normalize_google_redirect_uri(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def frontend_origin(self) -> str:
        origin = _normalize_origin(self.frontend_url)
        if not self.is_production:
            return origin or "http://localhost:5173"

        render_origin = _normalize_origin(os.getenv("RENDER_EXTERNAL_URL", ""))
        if not origin or _is_placeholder_url(origin) or origin.endswith(".onrender.com"):
            return render_origin or PRODUCTION_PUBLIC_URL
        return origin

    @property
    def cors_origins_list(self) -> list[str]:
        candidates = [*self.cors_origins.split(","), self.frontend_origin]
        if self.is_production:
            candidates.append(PRODUCTION_PUBLIC_URL)

        origins: list[str] = []
        for candidate in candidates:
            origin = _normalize_origin(candidate)
            if not origin or origin == "*" or origin in origins:
                continue
            if self.is_production and _is_placeholder_url(origin):
                continue
            if self.is_production and origin.endswith(".onrender.com") and origin != self.frontend_origin:
                continue
            origins.append(origin)
        return origins

    @property
    def google_redirect_url(self) -> str:
        configured = self.google_redirect_uri.strip().rstrip("/")
        if self.is_production:
            configured_origin = _normalize_origin(configured)
            if configured_origin.endswith(".onrender.com") and configured_origin != self.frontend_origin:
                configured = ""
        if not configured or (self.is_production and _is_placeholder_url(configured)):
            return f"{self.frontend_origin}/api/auth/google/callback"
        return configured

    @property
    def super_admin_emails_set(self) -> set[str]:
        return {email.strip().lower() for email in self.super_admin_emails.split(",") if email.strip()}

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def validate_startup(self) -> None:
        """Falla rápido si falta lo imprescindible para arrancar."""
        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL no está configurada. Copia .env.example a .env y completa la conexión de Supabase."
            )
        if self.is_production and not self.cookie_secure:
            raise RuntimeError("COOKIE_SECURE debe ser true en producción.")
        if self.is_production and len(self.jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres en producción.")
        if self.is_production and len(self.session_secret) < 32:
            raise RuntimeError("SESSION_SECRET debe tener al menos 32 caracteres en producción.")
        if self.storage_backend not in {"local", "supabase"}:
            raise RuntimeError("STORAGE_BACKEND debe ser 'local' o 'supabase'.")
        if self.storage_backend == "supabase" and not (self.supabase_url and self.supabase_service_role_key):
            raise RuntimeError(
                "SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son obligatorias cuando STORAGE_BACKEND=supabase."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
