from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfileOut(BaseModel):
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
    last_login_at: datetime | None = None
    created_at: datetime


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    job_title: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    timezone: str | None = Field(default=None, max_length=80)
    notify_quota: bool | None = None
    notify_weekly: bool | None = None
