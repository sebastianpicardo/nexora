from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api.deps import CurrentUser
from src.services import assistant_service

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


@router.post("/chat")
async def assistant_chat(payload: ChatRequest, user: CurrentUser):
    answer, provider = await assistant_service.answer_question(
        payload.message.strip(),
        history=[turn.model_dump() for turn in payload.history],
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
