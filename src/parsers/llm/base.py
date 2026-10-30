from __future__ import annotations

from abc import ABC, abstractmethod

from src.parsers.extractors.base import ExtractedContent
from src.parsers.llm.prompts import build_user_text
from src.parsers.schemas import ExtractedDocument


class LLMProvider(ABC):
    name: str
    model: str

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
