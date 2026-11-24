from __future__ import annotations

import sys

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_pool: AsyncConnectionPool | None = None


async def open_pool() -> AsyncConnectionPool:
    """Abre el pool async. Es idempotente y se llama en el lifespan."""
    global _pool
    if _pool is not None:
        return _pool

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL no configurada.")

    if settings.APP_ENV == "test" and settings.database_url.startswith("sqlite://"):
        # Modo prueba con SQLite: crear un pool ligero que usa sqlite3 por hilo.
        import sqlite3  # stdlib, ya disponible

        class _SqliteConnection:
            def __init__(self, db_path: str):
                self._conn = sqlite3.connect(db_path)
                self._conn.row_factory = sqlite3.Row

            async def fetchone(self, query: str, *args):
                loop = asyncio.get_running_loop()  # noqa
                return await loop.run_in_executor(None, self._conn.execute, query, *args).fetchone()

            async def execute(self, query: str, *args):
                loop = asyncio.get_running_loop()  # noqa
                return await loop.run_in_executor(None, self._conn.execute, query, *args)

            async def fetchall(self, query: str, *args):
                loop = asyncio.get_running_loop()  # noqa
                return await loop.run_in_executor(None, self._conn.execute, query, *args).fetchall()

            async def close(self):
                self._conn.close()

        class _SqlitePool:
            def __init__(self, url: str):
                self._url = url
                # extraer ruta del archivo
                self._db_path = url.replace("sqlite:///", "").replace("//", "") or ":memory:"
                self._conn = _SqliteConnection(self._db_path)

            async def connection(self):
                # devuelve un context manager async que yields the connection object
                return self._conn

            async def close(self):
                await self._conn.close()

        _pool = _SqlitePool(settings.database_url)
        logger.info("Pool SQLite inicializado en modo test")
        return _pool

    if sys.platform == "win32" and isinstance(asyncio.get_running_loop(), asyncio.ProactorEventLoop):  # noqa
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

    _pool = pool
    logger.info("Pool Postgres inicializado con conexión diferida")
    return _pool


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("El pool de base de datos no está inicializado.")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Pool Postgres cerrado")


async def check_db() -> None:
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            await cur.fetchone()
