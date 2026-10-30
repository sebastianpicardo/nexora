from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExceptionOut(BaseModel):
    id: UUID
    org_id: UUID
    document_id: UUID
    item_id: UUID | None = None
    document_filename: str | None = None
    doc_type: str | None = None
    supplier_name: str | None = None
    item_description: str | None = None
    item_sku: str | None = None
    item_original_unit: str | None = None
    item_base_unit: str | None = None
    item_original_unit_price: float | None = None
    item_normalized_unit_price: float | None = None
    item_quantity: float | None = None
    item_currency: str | None = None
    type: str
    severity: str
    reason: str
    evidence: dict = {}
    status: str
    resolution: dict | None = None
    notes: str | None = None
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime


class ExceptionListResponse(BaseModel):
    items: list[ExceptionOut]
    total: int
    page: int
    page_size: int


class ExceptionCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str | None = None
    original_description: str | None = None
    normalized_description: str | None = None
    original_unit: str | None = None
    quantity: float | None = None
    package_size: float | None = Field(default=None, gt=0)
    original_unit_price: float | None = Field(default=None, ge=0)
    currency: str | None = None
    price_date: date | None = None


class ExceptionResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject", "correct"]
    corrections: ExceptionCorrection | None = None
    notes: str | None = Field(default=None, max_length=2000)
