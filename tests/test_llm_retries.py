from __future__ import annotations

import pytest

from src.core.errors import AI_TEMPORARY_MESSAGE, LLMTemporaryError
from src.parsers.llm import base
from src.services import assistant_service


async def test_with_retries_recovers_from_transient_error(monkeypatch):
    calls: list[int] = []

    async def call():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("503 UNAVAILABLE: high demand")
        return "ok"

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(base.asyncio, "sleep", no_sleep)

    assert await base.with_retries(call, label="test") == "ok"
    assert len(calls) == 3


def test_llm_temporary_error_is_transient():
    assert base.is_transient_error(LLMTemporaryError())


async def test_with_retries_does_not_retry_permanent_error(monkeypatch):
    calls: list[int] = []

    async def call():
        calls.append(1)
        raise ValueError("payload inválido")

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(base.asyncio, "sleep", no_sleep)

    with pytest.raises(ValueError):
        await base.with_retries(call, label="test")
    assert len(calls) == 1


async def test_assistant_returns_no_provider_when_unconfigured(monkeypatch):
    for attribute in ("gemini_api_key", "openai_api_key", "anthropic_api_key"):
        monkeypatch.setattr(assistant_service.settings, attribute, "")
    monkeypatch.setattr(assistant_service.settings, "llm_provider_order", "gemini,openai,anthropic")

    answer, provider = await assistant_service.answer_question("¿Cómo subo un documento?")

    assert answer is None
    assert provider is None


async def test_assistant_raises_temporary_when_all_providers_are_saturated(monkeypatch):
    calls: list[int] = []

    async def saturated(_question, _history):
        calls.append(1)
        raise RuntimeError("503 UNAVAILABLE: high demand")

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(assistant_service, "_ask_gemini", saturated)
    monkeypatch.setattr(assistant_service.settings, "llm_provider_order", "gemini")
    monkeypatch.setattr(base.asyncio, "sleep", no_sleep)

    with pytest.raises(LLMTemporaryError) as exc_info:
        await assistant_service.answer_question("¿Cómo subo un documento?")

    assert str(exc_info.value) == AI_TEMPORARY_MESSAGE
    assert len(calls) == 3
