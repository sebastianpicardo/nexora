from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class ItemOut(BaseModel):
    id: UUID
    org_id: UUID
    document_id: UUID
    supplier_id: UUID | None = None
    supplier_name: str | None = None
    document_filename: str | None = None
    sku: str | None = None
    original_description: str
    normalized_description: str
    original_unit: str | None = None
    base_unit: str | None = None
    unit_factor: float
    quantity: float | None = None
    package_size: float | None = None
    original_unit_price: float | None = None
    normalized_unit_price: float | None = None
    currency: str
    price_date: date
    confidence: float
    review_status: str
    source_page: int | None = None
    source_text: str | None = None
    metadata: dict = {}
    created_at: datetime


class ItemListResponse(BaseModel):
    items: list[ItemOut]
    total: int
    page: int
    page_size: int
