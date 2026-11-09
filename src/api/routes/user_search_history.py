from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from src.api.deps import CurrentUser
from src.db import repositories
from src.db.pool import get_pool

router = APIRouter(prefix="/api/user/search-history", tags=["user-search-history"])


@router.get("")
async def list_search_history(
    user: CurrentUser,
    provider: str | None = None,
    action: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    async with get_pool().connection() as conn:
        rows = await repositories.list_user_search_history(
            conn, user["id"], provider=provider, action=action, limit=limit
        )
    return {"items": rows}


@router.post("")
async def save_search_history(
    payload: dict,
    user: CurrentUser,
) -> dict[str, Any]:
    provider = payload.get("provider")
    action = payload.get("action")
    query = payload.get("query", "")
    result_summary = payload.get("result_summary", "")
    result_data = payload.get("result_data", {})

    if not provider or not action:
        raise HTTPException(status_code=400, detail="provider y action son obligatorios")

    async with get_pool().connection() as conn:
        row = await repositories.save_user_search_history(
            conn,
            user_id=user["id"],
            provider=provider,
            action=action,
            query=query,
            result_summary=result_summary,
            result_data=result_data,
        )
    return row
