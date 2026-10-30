from __future__ import annotations

import base64
import json
import logging
import re

from anthropic import AsyncAnthropic

from src.core.config import settings
from src.core.errors import LLMError
from src.parsers.extractors.base import ExtractedContent
from src.parsers.llm.base import LLMProvider
from src.parsers.llm.prompts import SYSTEM_PROMPT
from src.parsers.llm.schema_utils import clean_schema
from src.parsers.schemas import ExtractedDocument

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        self.model = settings.anthropic_model
        self.client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
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
        blocks: list[dict] = []
        for image in content.images[: settings.llm_max_pages]:
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.b64encode(image).decode("ascii"),
                    },
                }
            )
        blocks.append({"type": "text", "text": self.user_text(content, filename, doc_type_hint)})

        tool = {
            "name": "extract_document",
            "description": "Registra la extracción estructurada del documento de compra.",
            "input_schema": clean_schema(ExtractedDocument.model_json_schema()),
        }

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": blocks}],
                tools=[tool],
                tool_choice={"type": "tool", "name": "extract_document"},
                temperature=0,
            )
        except Exception as exc:
            logger.exception("Anthropic extraction failed")
            raise LLMError(f"Error llamando a Anthropic: {exc}") from exc

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "extract_document":
                return ExtractedDocument.model_validate(block.input)

        text = "\n".join(
            getattr(block, "text", "") for block in response.content if getattr(block, "type", None) == "text"
        )
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return ExtractedDocument.model_validate(json.loads(match.group(0)))
            except (json.JSONDecodeError, ValueError) as exc:
                raise LLMError(f"Anthropic devolvió JSON inválido: {exc}") from exc

        raise LLMError("Anthropic no devolvió una extracción estructurada válida.")
