from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

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
