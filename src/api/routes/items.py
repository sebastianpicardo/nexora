from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from src.api.deps import CurrentUser
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.items import ItemListResponse, ItemOut

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("", response_model=ItemListResponse)
async def list_items(
    user: CurrentUser,
    supplier_id: UUID | None = Query(default=None),
    document_id: UUID | None = Query(default=None),
    sku: str | None = Query(default=None, max_length=100),
    review_status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    async with get_pool().connection() as conn:
        result = await repositories.list_items(
            conn,
            user["org_id"],
            supplier_id=supplier_id,
            document_id=document_id,
            sku=sku,
            review_status=review_status,
            date_from=date_from,
            date_to=date_to,
            search=search,
            page=page,
            page_size=page_size,
        )
    return ItemListResponse(
        items=[ItemOut.model_validate(row) for row in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(item_id: UUID, user: CurrentUser):
    async with get_pool().connection() as conn:
        row = await repositories.get_item(conn, user["org_id"], item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")
    return ItemOut.model_validate(row)
