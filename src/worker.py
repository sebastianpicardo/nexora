from __future__ import annotations

import argparse
import asyncio
import logging

from src.core.config import settings
from src.core.event_loop import configure_event_loop
from src.db.pool import close_pool, open_pool
from src.services.document_service import process_pending_once

logger = logging.getLogger(__name__)


async def run_once() -> bool:
    settings.validate_startup()
    await open_pool()
    try:
        return await process_pending_once()
    finally:
        await close_pool()


async def run_forever() -> None:
    settings.validate_startup()
    await open_pool()
    logger.info("Worker NEXORA iniciado (poll=%ss)", settings.worker_poll_seconds)
    try:
        while True:
            try:
                processed = await process_pending_once()
            except Exception:
                logger.exception("Error en el ciclo del worker; se reintentará")
                processed = False
            if not processed:
                await asyncio.sleep(settings.worker_poll_seconds)
    finally:
        await close_pool()


def main() -> None:
    configure_event_loop()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    parser = argparse.ArgumentParser(description="Worker de procesamiento NEXORA")
    parser.add_argument("--once", action="store_true", help="Procesa como máximo un documento y termina")
    args = parser.parse_args()

    try:
        if args.once:
            asyncio.run(run_once())
        else:
            asyncio.run(run_forever())
    except KeyboardInterrupt:
        logger.info("Worker detenido por el usuario")


if __name__ == "__main__":
    main()
