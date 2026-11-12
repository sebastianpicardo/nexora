from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from src.parsers.extractors.base import ExtractedContent
from src.parsers.llm.prompts import build_user_text
from src.parsers.schemas import ExtractedDocument

logger = logging.getLogger(__name__)

_RETRYABLE_MARKERS = (
    "503",
    "429",
    "500",
    "502",
    "504",
    "unavailable",
    "resource_exhausted",
    "overloaded",
    "high demand",
    "rate limit",
    "too many requests",
    "timeout",
    "timed out",
    "connection reset",
    "temporarily",
)


def is_transient_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _RETRYABLE_MARKERS)


async def with_retries[T](
    call: Callable[[], Awaitable[T]],
    *,
    label: str,
    attempts: int = 3,
    base_delay: float = 1.5,
) -> T:
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except Exception as exc:
            last_exc = exc
            if not is_transient_error(exc) or attempt >= attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "%s falló de forma transitoria (intento %s/%s): %s. Reintentando en %.1fs",
                label,
                attempt,
                attempts,
                str(exc)[:200],
                delay,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


class LLMProvider(ABC):
    name: str
    model: str
    last_usage: dict[str, int] | None = None

    def __init__(self) -> None:
        self.last_usage = None

    @abstractmethod
    async def extract_document(
        self,
        content: ExtractedContent,
        *,
        filename: str,
        doc_type_hint: str | None = None,
    ) -> ExtractedDocument:
        raise NotImplementedError

    def user_text(self, content: ExtractedContent, filename: str, doc_type_hint: str | None) -> str:
        return build_user_text(content, filename=filename, doc_type_hint=doc_type_hint)
