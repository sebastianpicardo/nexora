from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from src.api.deps import CurrentUser, require_roles
from src.api.routes.documents import ALLOWED_DOC_TYPES, ALLOWED_EXTENSIONS
from src.core.config import settings
from src.db import repositories
from src.db.pool import get_pool
from src.services import automation_service

router = APIRouter(prefix="/api/automation", tags=["automation"])

OPERATOR_ROLES = ("owner", "admin", "analyst", "user")


class AutomationRunIn(BaseModel):
    document_id: UUID


@router.post("/run/upload", status_code=status.HTTP_202_ACCEPTED)
async def run_automation_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: str = Form(default="quote"),
    document_date: str | None = Form(default=None, max_length=40),
    user: dict = Depends(require_roles(*OPERATOR_ROLES)),
) -> dict[str, Any]:
    if doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="doc_type debe ser quote, invoice o price_list",
        )
    filename = file.filename or "documento"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Formato no permitido: {suffix or 'sin extensión'}",
        )
    content = await file.read(settings.max_upload_bytes + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo supera el límite de {settings.max_upload_mb} MB",
        )

    run = await automation_service.prepare_run(
        user,
        trigger_source="upload",
        filename=filename,
    )
    background_tasks.add_task(
        automation_service.execute_run,
        user,
        run["id"],
        content=content,
        filename=filename,
        mime_type=file.content_type,
        doc_type=doc_type,
        document_date=document_date,
    )
    return {"success": True, "run": run}


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_automation_existing(
    payload: AutomationRunIn,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_roles(*OPERATOR_ROLES)),
) -> dict[str, Any]:
    async with get_pool().connection() as conn:
        document = await repositories.get_document(conn, user["org_id"], payload.document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")

    run = await automation_service.prepare_run(
        user,
        document_id=payload.document_id,
        trigger_source="existing",
        filename=document.get("original_filename"),
    )
    background_tasks.add_task(
        automation_service.execute_run,
        user,
        run["id"],
        document_id=payload.document_id,
    )
    return {"success": True, "run": run}


@router.get("/runs")
async def list_automation_runs(
    user: CurrentUser,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    runs = await automation_service.list_runs(user, limit=limit)
    return {"items": runs, "total": len(runs)}


@router.get("/runs/latest")
async def latest_automation_run(user: CurrentUser) -> dict[str, Any]:
    runs = await automation_service.list_runs(user, limit=1)
    return {"run": runs[0] if runs else None}


@router.get("/runs/{run_id}")
async def get_automation_run(run_id: UUID, user: CurrentUser) -> dict[str, Any]:
    run = await automation_service.get_run(user, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ejecución no encontrada")
    return {"run": run}
