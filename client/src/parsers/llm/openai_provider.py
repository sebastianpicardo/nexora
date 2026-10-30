from __future__ import annotations

import base64
import logging

from openai import AsyncOpenAI

from src.core.config import settings
from src.core.errors import LLMError
from src.parsers.extractors.base import ExtractedContent
from src.parsers.llm.base import LLMProvider
from src.parsers.llm.prompts import SYSTEM_PROMPT
from src.parsers.schemas import ExtractedDocument

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        self.model = settings.llm_model
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )

    async def extract_document(
        self,
        content: ExtractedContent,
        *,
        filename: str,
        doc_type_hint: str | None = None,
    ) -> ExtractedDocument:
        user_content: list[dict] = [{"type": "text", "text": self.user_text(content, filename, doc_type_hint)}]
        for image in content.images[: settings.llm_max_pages]:
            encoded = base64.b64encode(image).decode("ascii")
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encoded}", "detail": "high"},
                }
            )

        try:
            completion = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_format=ExtractedDocument,
                temperature=0,
                max_completion_tokens=8192,
            )
        except Exception as exc:
            logger.exception("OpenAI extraction failed")
            raise LLMError(f"Error llamando a OpenAI: {exc}") from exc

        message = completion.choices[0].message
        if getattr(message, "refusal", None):
            raise LLMError(f"OpenAI rechazó la extracción: {message.refusal}")
        if message.parsed is None:
            raise LLMError("OpenAI no devolvió una extracción estructurada válida.")

        if completion.usage:
            logger.info(
                "OpenAI tokens input=%s output=%s",
                completion.usage.prompt_tokens,
                completion.usage.completion_tokens,
            )
        return message.parsed
