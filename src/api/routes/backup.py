from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from src.api.deps import require_roles
from src.services import backup_service

router = APIRouter(prefix="/api/backups", tags=["backups"])


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
    from pathlib import Path

    filepath = Path("./backups") / filename
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
    try:
        return backup_service.restore_backup(filename)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
