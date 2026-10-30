from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: UUID
    org_id: UUID
    supplier_id: UUID | None = None
    supplier_name: str | None = None
    uploaded_by: UUID | None = None
    uploaded_by_name: str | None = None
    original_filename: str
    mime_type: str
    file_size_bytes: int
    doc_type: str
    status: str
    extraction_provider: str | None = None
    extraction_model: str | None = None
    error_message: str | None = None
    metadata: dict = {}
    created_at: datetime
    updated_at: datetime
    processing_started_at: datetime | None = None
    processed_at: datetime | None = None


class DocumentIngestResponse(BaseModel):
    success: bool = True
    document: DocumentOut
    duplicate: bool = False


class DocumentListResponse(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class ReprocessResponse(BaseModel):
    success: bool = True
    document: DocumentOut
