from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import CurrentUser, require_roles
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.exceptions import (
    ExceptionListResponse,
    ExceptionOut,
    ExceptionResolveRequest,
)
from src.services.exception_service import resolve_exception

router = APIRouter(prefix="/api/exceptions", tags=["exceptions"])


@router.get("", response_model=ExceptionListResponse)
async def list_exceptions(
    user: CurrentUser,
    status_filter: str | None = Query(default=None, alias="status"),
    type_filter: str | None = Query(default=None, alias="type"),
    severity: str | None = Query(default=None),
    document_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    async with get_pool().connection() as conn:
        result = await repositories.list_exceptions(
            conn,
            user["org_id"],
            status=status_filter,
            type=type_filter,
            severity=severity,
            document_id=document_id,
            page=page,
            page_size=page_size,
        )
    return ExceptionListResponse(
        items=[ExceptionOut.model_validate(row) for row in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/{exception_id}", response_model=ExceptionOut)
async def get_exception(exception_id: UUID, user: CurrentUser):
    async with get_pool().connection() as conn:
        row = await repositories.get_exception(conn, user["org_id"], exception_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Excepción no encontrada")
    return ExceptionOut.model_validate(row)


@router.post("/{exception_id}/resolve", response_model=ExceptionOut)
async def resolve(
    exception_id: UUID,
    payload: ExceptionResolveRequest,
    user: dict = Depends(require_roles("owner", "admin", "analyst", "user")),
):
    async with get_pool().connection() as conn:
        row = await resolve_exception(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            exception_id=exception_id,
            payload=payload,
            default_currency=user["default_currency"],
        )
    return ExceptionOut.model_validate(row)
