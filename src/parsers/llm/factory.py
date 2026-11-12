from __future__ import annotations

from typing import Any

from src.core.config import settings
from src.core.errors import LLMError, LLMNotConfiguredError
from src.parsers.llm.anthropic_provider import AnthropicProvider
from src.parsers.llm.base import LLMProvider
from src.parsers.llm.gemini_provider import GeminiProvider
from src.parsers.llm.openai_provider import OpenAIProvider

_PROVIDER_CLASSES = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def get_llm_provider() -> LLMProvider:
    """Obtiene el proveedor primario configurado (compatibilidad hacia atrás)."""
    providers = get_llm_providers()
    if not providers:
        raise LLMNotConfiguredError("No hay proveedores LLM configurados.")
    return providers[0]


def get_llm_providers() -> list[LLMProvider]:
    """Devuelve todos los proveedores LLM configurados en orden de prioridad."""
    default_order = "openai,anthropic,gemini"
    order = [p.strip().lower() for p in (settings.llm_provider_order or default_order).split(",") if p.strip()]
    providers: list[LLMProvider] = []
    errors: list[str] = []

    for name in order:
        provider_cls = _PROVIDER_CLASSES.get(name)
        if provider_cls is None:
            errors.append(f"Proveedor LLM no soportado: {name}")
            continue
        try:
            provider = provider_cls()
            providers.append(provider)
        except LLMNotConfiguredError as exc:
            errors.append(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"{name}: error al inicializar ({exc})")

    if not providers:
        detail = "; ".join(errors) if errors else "No hay proveedores LLM configurados."
        raise LLMNotConfiguredError(detail)

    return providers


async def extract_with_fallback(
    content: Any,
    *,
    filename: str,
    doc_type_hint: str | None = None,
) -> tuple[Any, str, dict[str, int] | None]:
    """Intenta extraer con el primer proveedor disponible y hace fallback si falla.

    Retorna (resultado, nombre_proveedor_usado, uso_de_tokens).
    """
    providers = get_llm_providers()
    last_error: str | None = None

    for provider in providers:
        try:
            result = await provider.extract_document(
                content,
                filename=filename,
                doc_type_hint=doc_type_hint,
            )
            return result, provider.name, getattr(provider, "last_usage", None)
        except LLMError as exc:
            last_error = str(exc)
            continue
        except Exception as exc:  # pragma: no cover - defensive
            last_error = str(exc)
            continue

    raise LLMError(f"Todos los proveedores LLM fallaron. Último error: {last_error}")
