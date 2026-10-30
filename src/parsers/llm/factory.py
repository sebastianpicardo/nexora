from __future__ import annotations

from src.core.config import settings
from src.core.errors import LLMNotConfiguredError
from src.parsers.llm.anthropic_provider import AnthropicProvider
from src.parsers.llm.base import LLMProvider
from src.parsers.llm.gemini_provider import GeminiProvider
from src.parsers.llm.openai_provider import OpenAIProvider


def get_llm_provider() -> LLMProvider:
    provider = (settings.llm_provider or "openai").strip().lower()

    if provider == "openai":
        if not settings.openai_api_key:
            raise LLMNotConfiguredError("OPENAI_API_KEY no está configurada.")
        return OpenAIProvider()
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMNotConfiguredError("ANTHROPIC_API_KEY no está configurada.")
        return AnthropicProvider()
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise LLMNotConfiguredError("GEMINI_API_KEY no está configurada.")
        return GeminiProvider()

    raise LLMNotConfiguredError(f"Proveedor LLM no soportado: {provider}")
