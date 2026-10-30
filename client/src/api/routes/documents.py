from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import filetype
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from psycopg.errors import UniqueViolation

from src.api.deps import CurrentUser, require_roles
from src.core.config import settings
from src.core.logging import get_logger
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.documents import (
    DocumentIngestResponse,
    DocumentListResponse,
    DocumentOut,
    ReprocessResponse,
)
from src.services import document_service, storage_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".xlsx",
    ".xls",
    ".csv",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".tif",
    ".tiff",
}
ALLOWED_DOC_TYPES = {"quote", "invoice", "price_list"}


def _document_out(row: dict) -> DocumentOut:
    return DocumentOut.model_validate(row)


@router.post("/ingest", response_model=DocumentIngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    supplier_id: UUID | None = Form(default=None),
    supplier_name: str | None = Form(default=None, max_length=200),
    doc_type: str = Form(default="quote"),
    document_date: str | None = Form(default=None, max_length=40),
    user: dict = Depends(require_roles("owner", "admin", "analyst", "user")),
):
    if doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=422, detail="doc_type debe ser quote, invoice o price_list")

    filename = file.filename or "documento"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Formato no permitido: {suffix or 'sin extensión'}",
        )

    content = await file.read(settings.max_upload_bytes + 1)
    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo supera el límite de {settings.max_upload_mb} MB",
        )

    kind = filetype.guess(content)
    mime_type = kind.mime if kind else (file.content_type or "application/octet-stream")
    file_hash = hashlib.sha256(content).hexdigest()

    async with get_pool().connection() as conn:
        duplicate = await repositories.get_document_by_hash(conn, user["org_id"], file_hash)
        if duplicate:
            return DocumentIngestResponse(
                success=True,
                document=_document_out(duplicate),
                duplicate=True,
            )

        resolved_supplier_id = None
        if supplier_id:
            supplier = await repositories.get_supplier(conn, user["org_id"], supplier_id)
            if supplier is None:
                raise HTTPException(status_code=404, detail="Proveedor no encontrado")
            resolved_supplier_id = supplier["id"]
        elif supplier_name and supplier_name.strip():
            supplier = await repositories.get_or_create_supplier(
                conn,
                org_id=user["org_id"],
                name=supplier_name,
            )
            resolved_supplier_id = supplier["id"]

    async with get_pool().connection() as conn:
        billing = await repositories.get_billing(conn, user["org_id"])
    if billing["usage"]["exceeded"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alcanzaste el límite de documentos de tu plan. Actualiza tu suscripción para continuar.",
        )

    document_id = uuid4()
    storage_path = await storage_service.save_document(
        org_id=user["org_id"],
        document_id=document_id,
        filename=filename,
        content=content,
        mime_type=mime_type,
    )

    metadata = {}
    if document_date:
        try:
            metadata["requested_document_date"] = date.fromisoformat(document_date).isoformat()
        except ValueError:
            metadata["requested_document_date"] = document_date

    try:
        async with get_pool().connection() as conn:
            await repositories.create_document(
                conn,
                document_id=document_id,
                org_id=user["org_id"],
                supplier_id=resolved_supplier_id,
                uploaded_by=user["id"],
                original_filename=filename,
                storage_path=storage_path,
                file_hash=file_hash,
                mime_type=mime_type,
                file_size_bytes=len(content),
                doc_type=doc_type,
                metadata=metadata,
            )
            row = await repositories.get_document(conn, user["org_id"], document_id)
    except UniqueViolation:
        async with get_pool().connection() as conn:
            row = await repositories.get_document_by_hash(conn, user["org_id"], file_hash)
        if row is None:
            raise
        return DocumentIngestResponse(success=True, document=_document_out(row), duplicate=True)

    if row is None:
        raise HTTPException(status_code=500, detail="No se pudo registrar el documento")

    if settings.process_in_background:
        background_tasks.add_task(document_service.process_document, document_id)

    return DocumentIngestResponse(success=True, document=_document_out(row), duplicate=False)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    user: CurrentUser,
    status_filter: str | None = Query(default=None, alias="status"),
    supplier_id: UUID | None = Query(default=None),
    doc_type: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    async with get_pool().connection() as conn:
        result = await repositories.list_documents(
            conn,
            user["org_id"],
            status=status_filter,
            supplier_id=supplier_id,
            doc_type=doc_type,
            search=search,
            page=page,
            page_size=page_size,
        )
    return DocumentListResponse(
        items=[_document_out(row) for row in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: UUID, user: CurrentUser):
    async with get_pool().connection() as conn:
        row = await repositories.get_document(conn, user["org_id"], document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return _document_out(row)


@router.post("/{document_id}/reprocess", response_model=ReprocessResponse)
async def reprocess_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_roles("owner", "admin", "analyst", "user")),
):
    async with get_pool().connection() as conn:
        existing = await repositories.get_document(conn, user["org_id"], document_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        if existing["status"] == "processing":
            raise HTTPException(status_code=409, detail="El documento ya se está procesando")
        row = await repositories.reset_document_for_reprocess(
            conn,
            org_id=user["org_id"],
            document_id=document_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    if settings.process_in_background:
        background_tasks.add_task(document_service.process_document, document_id)

    refreshed = await _get_document_any(org_id=user["org_id"], document_id=document_id)
    return ReprocessResponse(success=True, document=_document_out(refreshed or row))


async def _get_document_any(*, org_id: UUID, document_id: UUID) -> dict | None:
    async with get_pool().connection() as conn:
        return await repositories.get_document(conn, org_id, document_id)
