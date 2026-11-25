from __future__ import annotations

import asyncio
import time

import pytest

from src.db import pool


def test_get_pool_raises_typed_error_with_cause(monkeypatch):
    monkeypatch.setattr(pool, "_pool", None)
    cause = RuntimeError("no route to host")
    monkeypatch.setattr(pool, "_pool_error", cause)

    with pytest.raises(pool.PoolNotInitializedError) as excinfo:
        pool.get_pool()

    assert excinfo.value.cause is cause
    assert "no route to host" in str(excinfo.value)
    assert "RuntimeError" in str(excinfo.value)


def test_get_pool_without_previous_error(monkeypatch):
    monkeypatch.setattr(pool, "_pool", None)
    monkeypatch.setattr(pool, "_pool_error", None)

    with pytest.raises(pool.PoolNotInitializedError) as excinfo:
        pool.get_pool()

    assert excinfo.value.cause is None
    assert "no está inicializado" in str(excinfo.value)


def test_ensure_pool_respects_cooldown(monkeypatch):
    monkeypatch.setattr(pool, "_pool", None)
    cause = RuntimeError("boom")
    monkeypatch.setattr(pool, "_pool_error", cause)
    monkeypatch.setattr(pool, "_last_attempt_at", time.monotonic())

    async def _should_not_run():
        raise AssertionError("open_pool no debería llamarse durante el cooldown")

    monkeypatch.setattr(pool, "open_pool", _should_not_run)

    with pytest.raises(pool.PoolNotInitializedError) as excinfo:
        asyncio.run(pool.ensure_pool())

    assert excinfo.value.cause is cause
