from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import require_super_admin
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.admin import AdminOrganizationOut, AdminOverview, AdminStats

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverview)
async def overview(user: dict = Depends(require_super_admin)):
    async with get_pool().connection() as conn:
        stats = await repositories.get_platform_stats(conn)
        organizations = await repositories.list_organization_overviews(conn)

    return AdminOverview(
        stats=AdminStats(
            organizations_total=int(stats.get("organizations_total", 0)),
            users_total=int(stats.get("users_total", 0)),
            documents_month=int(stats.get("documents_month", 0)),
            documents_total=int(stats.get("documents_total", 0)),
            exceptions_pending=int(stats.get("exceptions_pending", 0)),
            mrr=float(stats.get("mrr", 0)),
        ),
        organizations=[
            AdminOrganizationOut(
                id=row["id"],
                name=row["name"],
                slug=row["slug"],
                plan_id=row["plan_id"],
                plan_name=row["plan_name"],
                subscription_status=row["subscription_status"],
                users_total=int(row["users_total"]),
                documents_total=int(row["documents_total"]),
                documents_month=int(row["documents_month"]),
                exceptions_pending=int(row["exceptions_pending"]),
                created_at=row["created_at"],
            )
            for row in organizations
        ],
    )
