from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SupplierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=200)
    tax_id: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)


class SupplierOut(BaseModel):
    id: UUID
    name: str
    normalized_name: str
    tax_id: str | None = None
    email: str | None = None
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierOut]
