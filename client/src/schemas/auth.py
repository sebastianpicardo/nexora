from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.parsers.normalization.currency import normalize_currency


class UserOut(BaseModel):
    id: UUID
    org_id: UUID
    email: str
    name: str
    avatar_url: str
    role: str
    job_title: str = ""
    phone: str = ""
    timezone: str = "America/Santiago"
    notify_quota: bool = True
    notify_weekly: bool = True
    active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    slug: str
    price_spike_threshold_pct: float
    min_confidence: float
    default_currency: str


class MeResponse(BaseModel):
    success: bool = True
    user: UserOut
    organization: OrganizationOut


class OrganizationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    price_spike_threshold_pct: float | None = Field(default=None, ge=0, le=500)
    min_confidence: float | None = Field(default=None, ge=0, le=1)
    default_currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("default_currency")
    @classmethod
    def _validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_currency(value, default="")
        if not normalized:
            raise ValueError("Moneda no soportada.")
        return normalized
