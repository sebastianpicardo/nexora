from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from src.api.deps import require_roles
from src.services import backup_service

router = APIRouter(prefix="/api/backups", tags=["backups"])

BACKUP_DIR = Path("./backups").resolve()


def _safe_backup_path(filename: str) -> Path:
    """Valida que el nombre de archivo no escape del directorio de backups."""
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido.")
    if not filename.endswith(".sql"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos .sql.")
    resolved = (BACKUP_DIR / filename).resolve()
    if not str(resolved).startswith(str(BACKUP_DIR)):
        raise HTTPException(status_code=400, detail="Ruta de archivo no válida.")
    return resolved


@router.get("")
async def list_backups(user: dict = Depends(require_roles("owner", "admin"))) -> dict[str, Any]:
    return {"backups": backup_service.list_backups()}


@router.post("")
async def create_backup(user: dict = Depends(require_roles("owner", "admin"))) -> dict[str, Any]:
    try:
        return backup_service.create_backup()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/download/{filename}")
async def download_backup(
    filename: str,
    user: dict = Depends(require_roles("owner", "admin")),
):
    filepath = _safe_backup_path(filename)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Backup no encontrado.")
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/sql",
    )


@router.post("/restore/{filename}")
async def restore_backup(
    filename: str,
    user: dict = Depends(require_roles("owner", "admin")),
) -> dict[str, Any]:
    filepath = _safe_backup_path(filename)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Backup no encontrado.")
    try:
        return backup_service.restore_backup(filename)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
