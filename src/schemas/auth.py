from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.parsers.normalization.currency import normalize_currency

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise ValueError("Ingresa un email válido.")
    return email


def _validate_password_strength(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres.")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"La contraseña no puede superar {PASSWORD_MAX_LENGTH} caracteres.")
    if not re.search(r"[A-Z]", value):
        raise ValueError("La contraseña debe incluir al menos una mayúscula.")
    if not re.search(r"[a-z]", value):
        raise ValueError("La contraseña debe incluir al menos una minúscula.")
    if not re.search(r"\d", value):
        raise ValueError("La contraseña debe incluir al menos un número.")
    return value


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


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    organization_name: str | None = Field(default=None, max_length=120)
    recaptcha_token: str | None = Field(default=None, max_length=4096)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Ingresa tu nombre completo.")
        return cleaned

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return _validate_password_strength(value)

    @field_validator("organization_name")
    @classmethod
    def _clean_organization(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    recaptcha_token: str | None = Field(default=None, max_length=4096)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return _normalize_email(value)


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
