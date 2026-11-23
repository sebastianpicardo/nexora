from __future__ import annotations

import asyncio
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
            # Necesario con el pooler de Supabase (PgBouncer en modo transaction).
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
