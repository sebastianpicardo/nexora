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

    jwt_secret: str = ""
    jwt_expires_minutes: int = 10080
    jwt_key_version: int = 1
    session_secret: str = ""
    cookie_name: str = "nexora_token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    super_admin_emails: str = ""

    recaptcha_site_key: str = ""
    recaptcha_secret_key: str = ""
    recaptcha_min_score: float = Field(default=0.5, ge=0, le=1)
    recaptcha_verify_url: str = "https://www.google.com/recaptcha/api/siteverify"

    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@nexora.app"
    smtp_from_name: str = "NEXORA"
    smtp_tls: bool = True
    smtp_ssl: bool = False

    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0, le=1)

    rate_limit_per_minute: int = Field(default=120, ge=1)

    inbound_email_domain: str = "inbox.nexora.app"
    whatsapp_api_url: str = "https://graph.facebook.com/v21.0"
    whatsapp_phone_id: str = ""
    whatsapp_token: str = ""
    integration_timeout_seconds: int = Field(default=10, ge=2, le=60)
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:no-reply@nexora.app"

    ai_usage_tracking_enabled: bool = True
    ai_document_monthly_limit: int = Field(default=1000, ge=0)
    ai_assistant_monthly_limit: int = Field(default=300, ge=0)
    ai_input_cost_per_million_usd: float = Field(default=0.5, ge=0)
    ai_output_cost_per_million_usd: float = Field(default=1.5, ge=0)
    assistant_rate_limit_per_minute: int = Field(default=20, ge=1)
    document_ingest_rate_limit_per_minute: int = Field(default=30, ge=1)
    document_reprocess_rate_limit_per_minute: int = Field(default=20, ge=1)
    export_rate_limit_per_minute: int = Field(default=30, ge=1)
    auto_approve_max_amount: float = Field(default=500000.0, ge=0)

    payment_provider: str = "mock"
    payment_webhook_secret: str = ""
    payment_success_url: str = ""
    payment_cancel_url: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    mercadopago_access_token: str = ""
    mercadopago_webhook_secret: str = ""
    flow_api_key: str = ""
    flow_secret_key: str = ""

    llm_provider: str = "openai"
    llm_provider_order: str = "openai,anthropic,gemini"
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
    max_concurrent_sessions: int = Field(default=5, ge=1, le=50)

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
            if not origin or origin in origins:
                continue
            # En producción nunca permitir comodín
            if self.is_production and origin == "*":
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
    def recaptcha_enabled(self) -> bool:
        return bool(self.recaptcha_secret_key.strip())

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_host.strip())

    @property
    def public_app_url(self) -> str:
        return self.frontend_origin.rstrip("/")

    @property
    def payment_checkout_success_url(self) -> str:
        return self.payment_success_url.strip() or f"{self.frontend_origin}/?checkout=success"

    @property
    def payment_checkout_cancel_url(self) -> str:
        return self.payment_cancel_url.strip() or f"{self.frontend_origin}/?checkout=cancel"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def validate_startup(self) -> None:
        """Falla rápido si falta lo imprescindible para arrancar."""
        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL no está configurada. Copia .env.example a .env y completa la conexión de Supabase."
            )
        if self.is_production:
            if not self.jwt_secret or self.jwt_secret == "change-me-in-production":
                raise RuntimeError("JWT_SECRET debe configurarse con un valor seguro en producción.")
            if len(self.jwt_secret) < 32:
                raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres en producción.")
            if not self.session_secret or self.session_secret == "change-me-in-production":
                raise RuntimeError("SESSION_SECRET debe configurarse con un valor seguro en producción.")
            if len(self.session_secret) < 32:
                raise RuntimeError("SESSION_SECRET debe tener al menos 32 caracteres en producción.")
            if not self.cookie_secure:
                raise RuntimeError("COOKIE_SECURE debe ser true en producción.")
            if self.payment_provider.strip().lower() == "mock":
                raise RuntimeError(
                    "PAYMENT_PROVIDER=mock está prohibido en producción. Configura Stripe, MercadoPago o Flow."
                )
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
