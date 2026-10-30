from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from src.api.deps import CurrentUser, require_roles
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.suppliers import SupplierCreate, SupplierListResponse, SupplierOut

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("", response_model=SupplierListResponse)
async def list_suppliers(user: CurrentUser, search: str | None = Query(default=None, max_length=100)):
    async with get_pool().connection() as conn:
        rows = await repositories.list_suppliers(conn, user["org_id"], search)
    return SupplierListResponse(items=[SupplierOut.model_validate(row) for row in rows])


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    payload: SupplierCreate,
    user: dict = Depends(require_roles("owner", "admin", "analyst", "user")),
):
    async with get_pool().connection() as conn:
        row = await repositories.get_or_create_supplier(
            conn,
            org_id=user["org_id"],
            name=payload.name,
            tax_id=payload.tax_id,
            email=payload.email,
        )
    return SupplierOut.model_validate(row)
