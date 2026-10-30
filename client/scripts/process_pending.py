from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.event_loop import configure_event_loop  # noqa: E402
from src.worker import run_once  # noqa: E402

if __name__ == "__main__":
    configure_event_loop()
    processed = asyncio.run(run_once())
    print("Documento procesado." if processed else "No hay documentos pendientes.")
