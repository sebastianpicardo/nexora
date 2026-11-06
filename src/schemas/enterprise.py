from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.parsers.normalization.currency import normalize_currency

APPROVAL_STATUSES = {"pending", "approved", "rejected", "cancelled"}
APPROVAL_PRIORITIES = {"low", "normal", "high", "urgent"}
CHANNEL_TYPES = {"email", "slack", "whatsapp", "webhook"}
INTEGRATION_PROVIDERS = {"erp", "sii", "chilecompra", "slack", "webhook", "google_workspace"}


def _clean_currency(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_currency(value, default="")
    if not normalized:
        raise ValueError("Moneda no soportada.")
    return normalized


class ApprovalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=2, max_length=200)
    amount: float = Field(ge=0)
    currency: str = Field(default="CLP", min_length=3, max_length=3)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    document_id: UUID | None = None
    supplier_id: UUID | None = None
    notes: str = Field(default="", max_length=2000)
    metadata: dict = {}

    @field_validator("currency")
    @classmethod
    def _currency(cls, value: str) -> str:
        return _clean_currency(value) or "CLP"


class ApprovalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=2, max_length=200)
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    notes: str | None = Field(default=None, max_length=2000)
    metadata: dict | None = None

    @field_validator("currency")
    @classmethod
    def _currency(cls, value: str | None) -> str | None:
        return _clean_currency(value)


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "rejected", "cancelled"]
    notes: str | None = Field(default=None, max_length=2000)


class NotificationChannelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    channel: Literal["email", "slack", "whatsapp", "webhook"]
    target: str = Field(min_length=1, max_length=500)
    events: list[str] = ["alerts"]


class NotificationChannelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    channel: Literal["email", "slack", "whatsapp", "webhook"] | None = None
    target: str | None = Field(default=None, min_length=1, max_length=500)
    events: list[str] | None = None
    active: bool | None = None


class IntegrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["erp", "sii", "chilecompra", "slack", "webhook", "google_workspace"]
    name: str = Field(min_length=2, max_length=120)
    config: dict = {}
    active: bool = True


class IntegrationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    config: dict | None = None
    active: bool | None = None


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    scopes: list[str] = ["read"]


class WebhookCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=8, max_length=500)
    events: list[str] = ["document.processed"]
    secret: str | None = Field(default=None, max_length=200)


class InboundTokenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(default="", max_length=120)


class OnboardingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: dict[str, bool] | None = None
    dismissed: bool | None = None
    completed: bool | None = None


class BrandingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand_name: str | None = Field(default=None, max_length=120)
    brand_primary_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    brand_accent_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    logo_url: str | None = Field(default=None, max_length=500)
    support_email: str | None = Field(default=None, max_length=255)
    custom_domain: str | None = Field(default=None, max_length=255)
    hide_powered_by: bool | None = None


class SecurityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sso_enabled: bool | None = None
    sso_domain: str | None = Field(default=None, max_length=255)
    sso_required: bool | None = None
    audit_retention_days: int | None = Field(default=None, ge=30, le=3650)


class PushSubscriptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(min_length=10, max_length=2000)
    p256dh: str = Field(min_length=10, max_length=500)
    auth: str = Field(min_length=5, max_length=500)


class PushUnsubscribeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(min_length=10, max_length=2000)


class ApiKeyOut(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    scopes: list[str] = []
    active: bool
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    token: str | None = None
