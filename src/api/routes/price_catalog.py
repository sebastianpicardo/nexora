from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel

from src.api.deps import CurrentUser, require_roles
from src.db import repositories
from src.db.pool import get_pool

router = APIRouter(prefix="/api/price-catalog", tags=["price-catalog"])


class PriceCatalogItemIn(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    unit: str = "unidad"
    cost_price: float = 0
    sale_price: float = 0
    category: Optional[str] = None
    supplier_name: Optional[str] = None


class PriceCatalogItemOut(BaseModel):
    id: str
    sku: str
    name: str
    description: Optional[str] = None
    unit: str
    cost_price: float
    sale_price: float
    margin_pct: float
    category: Optional[str] = None
    supplier_name: Optional[str] = None
    active: bool
    created_at: str
    updated_at: str


@router.get("", response_model=list[PriceCatalogItemOut])
async def list_price_catalog(
    user: CurrentUser,
    active_only: bool = Query(default=True),
    search: Optional[str] = Query(default=None),
) -> list[Any]:
    try:
try:
        async with get_pool().connection() as conn:
            rows = await repositories.list_price_catalog(
                conn, user["org_id"], active_only=active_only, search=search
            )
        return [
            PriceCatalogItemOut(
                id=str(row["id"]),
                sku=row["sku"],
                name=row["name"],
                description=row.get("description"),
                unit=row["unit"],
                cost_price=float(row["cost_price"] or 0),
                sale_price=float(row["sale_price"] or 0),
                margin_pct=float(row["margin_pct"] or 0),
                category=row.get("category"),
                supplier_name=row.get("supplier_name"),
                active=bool(row["active"]),
                created_at=row["created_at"].isoformat() if row.get("created_at") else "",
                updated_at=row["updated_at"].isoformat() if row.get("updated_at") else "",
            )
            for row in rows
        ]
    except Exception:
        # Si la tabla no existe (migración 007 no aplicada), devolver lista vacía
        return []
    except Exception:
        # Si la tabla no existe (migración 007 no aplicada), devolver lista vacía
        return []


@router.post("", response_model=PriceCatalogItemOut, status_code=status.HTTP_201_CREATED)
async def create_price_catalog_item(
    payload: PriceCatalogItemIn,
    user: dict = Depends(require_roles("owner", "admin")),
) -> Any:
    async with get_pool().connection() as conn:
        row = await repositories.create_price_catalog_item(
            conn,
            org_id=user["org_id"],
            sku=payload.sku,
            name=payload.name,
            description=payload.description,
            unit=payload.unit,
            cost_price=payload.cost_price,
            sale_price=payload.sale_price,
            category=payload.category,
            supplier_name=payload.supplier_name,
        )
    return PriceCatalogItemOut(
        id=str(row["id"]),
        sku=row["sku"],
        name=row["name"],
        description=row.get("description"),
        unit=row["unit"],
        cost_price=float(row["cost_price"] or 0),
        sale_price=float(row["sale_price"] or 0),
        margin_pct=float(row["margin_pct"] or 0),
        category=row.get("category"),
        supplier_name=row.get("supplier_name"),
        active=bool(row["active"]),
        created_at=row["created_at"].isoformat() if row.get("created_at") else "",
        updated_at=row["updated_at"].isoformat() if row.get("updated_at") else "",
    )


@router.patch("/{item_id}", response_model=PriceCatalogItemOut)
async def update_price_catalog_item(
    item_id: str = Path(...),
    payload: PriceCatalogItemIn = None,
    user: dict = Depends(require_roles("owner", "admin")),
) -> Any:
    if payload is None:
        payload = PriceCatalogItemIn(sku="", name="")
    async with get_pool().connection() as conn:
        row = await repositories.update_price_catalog_item(
            conn,
            org_id=user["org_id"],
            item_id=item_id,
            fields=payload.model_dump(exclude_unset=True),
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")
    return PriceCatalogItemOut(
        id=str(row["id"]),
        sku=row["sku"],
        name=row["name"],
        description=row.get("description"),
        unit=row["unit"],
        cost_price=float(row["cost_price"] or 0),
        sale_price=float(row["sale_price"] or 0),
        margin_pct=float(row["margin_pct"] or 0),
        category=row.get("category"),
        supplier_name=row.get("supplier_name"),
        active=bool(row["active"]),
        created_at=row["created_at"].isoformat() if row.get("created_at") else "",
        updated_at=row["updated_at"].isoformat() if row.get("updated_at") else "",
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_price_catalog_item(
    item_id: str = Path(...),
    user: dict = Depends(require_roles("owner", "admin")),
) -> None:
    async with get_pool().connection() as conn:
        deleted = await repositories.delete_price_catalog_item(
            conn, user["org_id"], item_id
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")
