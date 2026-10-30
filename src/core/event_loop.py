from __future__ import annotations

import asyncio
import sys


def selector_loop_factory(use_subprocess: bool = False) -> asyncio.AbstractEventLoop:
    """Devuelve un loop compatible con psycopg async en Windows."""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


def configure_event_loop() -> None:
    """Configura el loop por defecto para scripts que usan asyncio.run."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
