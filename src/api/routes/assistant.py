from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.deps import CurrentUser, rate_limit
from src.db.pool import get_pool
from src.services import ai_usage_service, assistant_service

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


@router.post("/chat")
async def assistant_chat(
    payload: ChatRequest,
    user: CurrentUser,
    _: None = Depends(rate_limit("assistant", "assistant_rate_limit_per_minute")),
):
    async with get_pool().connection() as conn:
        if await ai_usage_service.quota_exceeded(conn, user["org_id"], kind="assistant"):
            raise HTTPException(
                status_code=403,
                detail="Alcanzaste el lÃ­mite mensual de uso de IA del asistente. Actualiza tu plan.",
            )
    answer, provider = await assistant_service.answer_question(
        payload.message.strip(),
        history=[turn.model_dump() for turn in payload.history],
        org_id=user["org_id"],
        user_id=user["id"],
    )
    if not answer:
        return {
            "ai_available": False,
            "source": "knowledge_base",
            "answer": "",
        }
    return {
        "ai_available": True,
        "source": provider,
        "answer": answer,
    }
