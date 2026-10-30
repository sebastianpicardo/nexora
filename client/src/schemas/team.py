from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INVITABLE_ROLES = {"admin", "analyst", "user", "auditor", "viewer"}


class TeamMemberOut(BaseModel):
    id: UUID
    email: str
    name: str
    avatar_url: str
    role: str
    job_title: str = ""
    active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class InvitationOut(BaseModel):
    id: UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    invite_url: str | None = None


class TeamResponse(BaseModel):
    members: list[TeamMemberOut]
    invitations: list[InvitationOut]
    permissions: dict = {}


class InviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=5, max_length=254)
    role: Literal["admin", "analyst", "user", "auditor", "viewer"] = "user"

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_RE.match(normalized):
            raise ValueError("Ingresa un email válido.")
        return normalized


class MemberUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["admin", "analyst", "user", "auditor", "viewer"] | None = None
    active: bool | None = None


class AcceptInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=200)
