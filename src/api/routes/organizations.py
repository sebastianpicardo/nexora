from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import CurrentUser, require_roles
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.auth import OrganizationOut, OrganizationUpdate

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


def _org_out(org: dict) -> OrganizationOut:
    return OrganizationOut(
        id=org["id"],
        name=org["name"],
        slug=org["slug"],
        price_spike_threshold_pct=float(org["price_spike_threshold_pct"]),
        min_confidence=float(org["min_confidence"]),
        default_currency=org["default_currency"],
    )


@router.get("/current", response_model=OrganizationOut)
async def current_organization(user: CurrentUser) -> OrganizationOut:
    async with get_pool().connection() as conn:
        org = await repositories.get_organization(conn, user["org_id"])
    if org is None:
        raise HTTPException(status_code=404, detail="Organización no encontrada")
    return _org_out(org)


@router.patch("/current", response_model=OrganizationOut)
async def update_current_organization(
    payload: OrganizationUpdate,
    user: dict = Depends(require_roles("owner", "admin")),
) -> OrganizationOut:
    async with get_pool().connection() as conn:
        org = await repositories.update_organization(
            conn,
            user["org_id"],
            payload.model_dump(exclude_unset=True),
        )
    if org is None:
        raise HTTPException(status_code=404, detail="Organización no encontrada")
    return _org_out(org)


@router.get("/current/audit")
async def list_audit_events(
    user: CurrentUser,
    action: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    async with get_pool().connection() as conn:
        result = await repositories.list_audit_events(
            conn,
            user["org_id"],
            action=action,
            page=page,
            page_size=page_size,
        )
    return result


@router.get("/current/export")
async def export_organization_data(user: CurrentUser):
    async with get_pool().connection() as conn:
        org = await repositories.get_organization(conn, user["org_id"])
        if org is None:
            raise HTTPException(status_code=404, detail="Organización no encontrada")
        users = await repositories.list_users(conn, user["org_id"])
        suppliers = await repositories.list_suppliers(conn, user["org_id"])
        documents = await repositories.list_documents(
            conn, user["org_id"], page=1, page_size=5000
        )
        items = await repositories.list_items(conn, user["org_id"], page=1, page_size=5000)
        exceptions = await repositories.list_exceptions(
            conn, user["org_id"], page=1, page_size=5000
        )
        audit = await repositories.list_audit_events(
            conn, user["org_id"], page=1, page_size=5000
        )
    return {
        "organization": org,
        "users": users,
        "suppliers": suppliers,
        "documents": documents["items"],
        "items": items["items"],
        "exceptions": exceptions["items"],
        "audit": audit["items"],
    }


@router.delete("/current", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_organization(
    user: dict = Depends(require_roles("owner")),
    confirm: str = Query(..., min_length=1, max_length=100),
):
    async with get_pool().connection() as conn:
        org = await repositories.get_organization(conn, user["org_id"])
        if org is None:
            raise HTTPException(status_code=404, detail="Organización no encontrada")
        if confirm != org["slug"]:
            raise HTTPException(
                status_code=400,
                detail="El parámetro 'confirm' debe coincidir con el slug de la organización",
            )
        await repositories.delete_organization(conn, user["org_id"])
    return None
