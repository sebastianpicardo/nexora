from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from src.api.deps import CurrentUser, require_roles
from src.services import compra_agil_service

router = APIRouter(prefix="/api/compra-agil", tags=["compra-agil"])

MAX_IMPORT_BYTES = 25 * 1024 * 1024
IMPORT_SUFFIXES = (".csv", ".xlsx", ".xls")


@router.get("/opportunities")
async def list_opportunities(
    user: CurrentUser,
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    return await compra_agil_service.list_opportunities(user, search=q, limit=limit)


@router.post("/import")
async def import_opportunities(
    file: UploadFile = File(...),
    user: dict = Depends(require_roles("owner", "admin", "analyst")),
) -> dict[str, Any]:
    filename = file.filename or "compra_agil.csv"
    if not filename.lower().endswith(IMPORT_SUFFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no soportado. Sube un CSV o Excel de oportunidades.",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío.")
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El archivo supera el límite de 25 MB. Divídelo en partes.",
        )
    try:
        return await compra_agil_service.import_opportunities(user, content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{external_id}/quote")
async def quote(
    external_id: str,
    user: CurrentUser,
    target_margin: float = Query(default=25, ge=0, le=90),
) -> dict[str, Any]:
    try:
        return await compra_agil_service.build_quote(user, external_id, target_margin=target_margin)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{external_id}/quote.csv")
async def quote_csv(
    external_id: str,
    user: CurrentUser,
    target_margin: float = Query(default=25, ge=0, le=90),
):
    try:
        quote_data = await compra_agil_service.build_quote(
            user,
            external_id,
            target_margin=target_margin,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    content = compra_agil_service.quote_to_csv(quote_data)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="cotizacion_compra_agil_{external_id}.csv"'
        },
    )
