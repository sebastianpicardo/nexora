from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import CurrentUser, require_roles
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.suppliers import SupplierCreate, SupplierListResponse, SupplierOut, SupplierUpdate

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


@router.patch("/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: UUID,
    payload: SupplierUpdate,
    user: dict = Depends(require_roles("owner", "admin", "analyst")),
):
    async with get_pool().connection() as conn:
        row = await repositories.update_supplier(
            conn,
            org_id=user["org_id"],
            supplier_id=supplier_id,
            name=payload.name,
            tax_id=payload.tax_id,
            email=payload.email,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="supplier.update",
            entity_type="supplier",
            entity_id=str(supplier_id),
        )
    return SupplierOut.model_validate(row)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: UUID,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        deleted = await repositories.delete_supplier(conn, user["org_id"], supplier_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="supplier.delete",
            entity_type="supplier",
            entity_id=str(supplier_id),
        )
    return None
