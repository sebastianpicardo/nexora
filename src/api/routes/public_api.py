from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from src.db import repositories
from src.db.pool import get_pool

router = APIRouter(prefix="/api/public/v1", tags=["public-api"])


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    required_scopes: list[str] | None = None,
) -> dict:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Falta el header X-API-Key")
    async with get_pool().connection() as conn:
        key = await repositories.get_api_key_by_hash(conn, _hash(x_api_key.strip()))
        if key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key inválida o revocada")
        org = await repositories.get_organization(conn, key["org_id"])
    if org is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Organización no disponible")

    # Validar scopes si se especifican
    if required_scopes:
        key_scopes = set(key.get("scopes") or [])
        missing = set(required_scopes) - key_scopes
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"La API key no tiene los alcances requeridos: {', '.join(sorted(missing))}",
            )

    return {**key, "default_currency": org["default_currency"], "org_name": org["name"]}


async def require_api_key_read(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    return await require_api_key(x_api_key, required_scopes=["read"])


ApiKeyRead = Annotated[dict, Depends(require_api_key_read)]


@router.get("/summary")
async def public_summary(
    key: ApiKeyRead,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
):
    active_currency = (currency or key["default_currency"] or "CLP").strip().upper()
    async with get_pool().connection() as conn:
        items = await repositories.summarize_items(conn, key["org_id"], currency=active_currency)
        exceptions = await repositories.summarize_exceptions(
            conn, key["org_id"], currency=active_currency
        )
        approvals = await repositories.list_approvals(conn, key["org_id"], status="pending", page=1, page_size=5)
        scorecards = await repositories.list_supplier_scorecards(
            conn, key["org_id"], currency=active_currency, limit=5
        )
    return {
        "organization": key["org_name"],
        "currency": active_currency,
        "items": items,
        "exceptions": exceptions,
        "pending_approvals": approvals["total"],
        "top_suppliers": scorecards,
    }


@router.get("/items")
async def public_items(
    key: ApiKeyRead,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    async with get_pool().connection() as conn:
        result = await repositories.list_items(conn, key["org_id"], page=page, page_size=page_size)
    return {
        "items": result["items"],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    }


@router.get("/suppliers")
async def public_suppliers(
    key: ApiKeyRead,
    search: str | None = Query(default=None, max_length=100),
):
    async with get_pool().connection() as conn:
        rows = await repositories.list_suppliers(conn, key["org_id"], search)
    return {"items": rows}


@router.get("/approvals")
async def public_approvals(
    key: ApiKeyRead,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    async with get_pool().connection() as conn:
        return await repositories.list_approvals(
            conn,
            key["org_id"],
            status=status_filter,
            page=page,
            page_size=page_size,
        )
