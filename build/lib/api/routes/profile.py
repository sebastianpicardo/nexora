from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.deps import CurrentUser
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.profile import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _profile_out(row: dict) -> ProfileOut:
    return ProfileOut(
        id=row["id"],
        org_id=row["org_id"],
        email=row["email"],
        name=row["name"],
        avatar_url=row["avatar_url"],
        role=row["role"],
        job_title=row.get("job_title", ""),
        phone=row.get("phone", ""),
        timezone=row.get("timezone", "America/Santiago"),
        notify_quota=row.get("notify_quota", True),
        notify_weekly=row.get("notify_weekly", True),
        last_login_at=row.get("last_login_at"),
        created_at=row["created_at"],
    )


@router.get("", response_model=ProfileOut)
async def get_profile(user: CurrentUser):
    return _profile_out(user)


@router.patch("", response_model=ProfileOut)
async def update_profile(payload: ProfileUpdate, user: CurrentUser):
    async with get_pool().connection() as conn:
        row = await repositories.update_profile(
            conn,
            user["id"],
            payload.model_dump(exclude_unset=True),
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return _profile_out(row)
