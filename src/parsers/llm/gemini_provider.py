from __future__ import annotations

import logging

from google import genai
from google.genai import types

from src.core.config import settings
from src.core.errors import LLMError
from src.parsers.extractors.base import ExtractedContent
from src.parsers.llm.base import LLMProvider, with_retries
from src.parsers.llm.prompts import SYSTEM_PROMPT
from src.parsers.schemas import ExtractedDocument

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self) -> None:
        super().__init__()
        self.model = settings.gemini_model
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def extract_document(
        self,
        content: ExtractedContent,
        *,
        filename: str,
        doc_type_hint: str | None = None,
    ) -> ExtractedDocument:
        parts: list[types.Part] = [types.Part.from_text(text=self.user_text(content, filename, doc_type_hint))]
        for image in content.images[: settings.llm_max_pages]:
            parts.append(types.Part.from_bytes(data=image, mime_type="image/png"))

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0,
            response_mime_type="application/json",
            response_schema=ExtractedDocument,
            max_output_tokens=8192,
        )

        try:
            response = await with_retries(
                lambda: self.client.aio.models.generate_content(
                    model=self.model,
                    contents=parts,
                    config=config,
                ),
                label="Gemini",
            )
        except Exception as exc:
            logger.exception("Gemini extraction failed")
            if "503" in str(exc) or "UNAVAILABLE" in str(exc):
                raise LLMError(
                    "Gemini está temporalmente saturado (503). Reintenta en unos minutos "
                    "o configura otro proveedor en LLM_PROVIDER_ORDER."
                ) from exc
            raise LLMError(f"Error llamando a Gemini: {exc}") from exc

        if getattr(response, "usage_metadata", None):
            self.last_usage = {
                "input_tokens": int(getattr(response.usage_metadata, "prompt_token_count", 0) or 0),
                "output_tokens": int(getattr(response.usage_metadata, "candidates_token_count", 0) or 0),
            }

        if not response.text:
            raise LLMError("Gemini no devolvió contenido.")
        try:
            return ExtractedDocument.model_validate_json(response.text)
        except ValueError as exc:
            raise LLMError(f"Gemini devolvió JSON inválido: {exc}") from exc
