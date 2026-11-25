from __future__ import annotations

import asyncio
import sys
import time

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_pool: AsyncConnectionPool | None = None
_pool_lock: asyncio.Lock | None = None
_pool_error: Exception | None = None
_last_attempt_at: float = 0.0

# Evita martillar la base de datos si el arranque falló y llegan muchas peticiones.
_RETRY_COOLDOWN_SECONDS = 5.0


class PoolNotInitializedError(RuntimeError):
    """El pool no está disponible porque no se pudo crear.

    Conserva la causa original para que los logs y los handlers HTTP muestren el
    error real en vez de un mensaje genérico.
    """

    def __init__(self, cause: Exception | None = None) -> None:
        self.cause = cause
        if cause is not None:
            message = (
                "El pool de base de datos no está inicializado. "
                f"Causa: {type(cause).__name__}: {cause}"
            )
        else:
            message = "El pool de base de datos no está inicializado."
        super().__init__(message)


def _get_lock() -> asyncio.Lock:
    global _pool_lock
    if _pool_lock is None:
        _pool_lock = asyncio.Lock()
    return _pool_lock


async def _create_pool() -> AsyncConnectionPool:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL no configurada.")

    if settings.app_env.lower() == "test" and settings.database_url.startswith("sqlite://"):
        # Modo prueba con SQLite: crear un pool ligero que usa sqlite3 por hilo.
        import sqlite3  # stdlib, ya disponible

        class _SqliteConnection:
            def __init__(self, db_path: str):
                self._conn = sqlite3.connect(db_path)
                self._conn.row_factory = sqlite3.Row

            async def fetchone(self, query: str, *args):
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, self._conn.execute, query, *args)

            async def execute(self, query: str, *args):
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, self._conn.execute, query, *args)

            async def fetchall(self, query: str, *args):
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, self._conn.execute, query, *args)

            async def close(self):
                self._conn.close()

        class _SqlitePool:
            def __init__(self, url: str):
                self._url = url
                self._db_path = url.replace("sqlite:///", "").replace("//", "") or ":memory:"
                self._conn = _SqliteConnection(self._db_path)

            async def connection(self):
                return self._conn

            async def close(self):
                await self._conn.close()

        logger.info("Pool SQLite inicializado en modo test")
        return _SqlitePool(settings.database_url)

    if sys.platform == "win32" and isinstance(asyncio.get_running_loop(), asyncio.ProactorEventLoop):
        raise RuntimeError(
            "psycopg async no soporta ProactorEventLoop en Windows. "
            "Usa 'python scripts/dev_server.py' para la API o 'python -m src.worker' para el worker."
        )

    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        open=False,
        min_size=1,
        max_size=10,
        timeout=15,
        kwargs={
            "row_factory": dict_row,
            "prepare_threshold": None,
            "application_name": "nexora-api",
        },
    )
    try:
        await pool.open(wait=False)
    except Exception:
        await pool.close()
        raise

    logger.info("Pool Postgres inicializado con conexión diferida")
    return pool


async def open_pool() -> AsyncConnectionPool:
    """Abre el pool async de forma idempotente y segura ante concurrencia.

    Si ya existe, lo devuelve. Si la creación falla, registra el error real y
    lo propaga (la causa queda guardada para ``get_pool``).
    """
    global _pool, _pool_error, _last_attempt_at
    if _pool is not None:
        return _pool

    async with _get_lock():
        if _pool is not None:
            return _pool
        _last_attempt_at = time.monotonic()
        try:
            _pool = await _create_pool()
            _pool_error = None
            return _pool
        except Exception as exc:  # noqa: BLE001 - se registra y se propaga
            _pool_error = exc
            logger.exception(
                "No se pudo inicializar el pool de base de datos (%s): %s",
                type(exc).__name__,
                exc,
            )
            raise


async def ensure_pool() -> AsyncConnectionPool:
    """Inicialización perezosa segura.

    Permite que una petición cree el pool aunque el ``lifespan`` no se haya
    ejecutado (o haya fallado). Aplica un pequeño cooldown para no reintentar
    en cada request cuando la causa es persistente.
    """
    if _pool is not None:
        return _pool
    if _pool_error is not None and (time.monotonic() - _last_attempt_at) < _RETRY_COOLDOWN_SECONDS:
        raise PoolNotInitializedError(_pool_error)
    return await open_pool()


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise PoolNotInitializedError(_pool_error)
    return _pool


def is_pool_initialized() -> bool:
    return _pool is not None


async def close_pool() -> None:
    global _pool, _pool_error, _last_attempt_at
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Pool Postgres cerrado")
    _pool_error = None
    _last_attempt_at = 0.0


async def check_db() -> None:
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            await cur.fetchone()
