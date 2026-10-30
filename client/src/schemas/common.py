from __future__ import annotations

from pydantic import BaseModel


class MessageResponse(BaseModel):
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    code: str = "error"
    details: dict = {}
