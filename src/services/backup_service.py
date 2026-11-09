from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

BACKUP_DIR = Path("./backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def is_backup_available() -> bool:
    """Indica si pg_dump está instalado en el servidor."""
    try:
        subprocess.run(
            ["pg_dump", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def _database_name(database_url: str) -> str:
    """Extrae el nombre de la base de datos de la URL."""
    # postgres://user:pass@host:port/dbname
    parts = database_url.rstrip("/").split("/")
    return parts[-1] if parts else "nexora"


def list_backups() -> list[dict[str, Any]]:
    """Lista los backups disponibles en disco."""
    backups: list[dict[str, Any]] = []
    if not BACKUP_DIR.exists():
        return backups
    for path in sorted(BACKUP_DIR.glob("*.sql"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = path.stat()
        backups.append(
            {
                "filename": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "download_url": f"/api/backups/download/{path.name}",
            }
        )
    return backups


def create_backup() -> dict[str, Any]:
    """Crea un backup de la base de datos usando pg_dump."""
    database_url = settings.database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL no está configurada.")

    db_name = _database_name(database_url)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"nexora_backup_{db_name}_{timestamp}.sql"
    filepath = BACKUP_DIR / filename

    env = os.environ.copy()
    # Extraer credenciales de la URL para pg_dump
    # postgres://user:pass@host:port/dbname
    try:
        from urllib.parse import urlparse

        parsed = urlparse(database_url)
        if parsed.password:
            env["PGPASSWORD"] = parsed.password
        if parsed.username:
            env["PGUSER"] = parsed.username
        if parsed.hostname:
            env["PGHOST"] = parsed.hostname
        if parsed.port:
            env["PGPORT"] = str(parsed.port)
        env["PGDATABASE"] = db_name
    except Exception as exc:  # pragma: no cover - fallback
        logger.warning("No se pudieron extraer credenciales de DATABASE_URL: %s", exc)

    cmd = [
        "pg_dump",
        "--no-password",
        "--verbose",
        "--file",
        str(filepath),
        db_name,
    ]

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            logger.error("pg_dump falló: %s", result.stderr)
            raise RuntimeError(f"pg_dump falló: {result.stderr[:500]}")

        stat = filepath.stat()
        return {
            "success": True,
            "filename": filename,
            "path": str(filepath),
            "size_bytes": stat.st_size,
            "created_at": datetime.utcnow().isoformat(),
            "download_url": f"/api/backups/download/{filename}",
            "message": "Backup creado correctamente.",
        }
    except subprocess.TimeoutExpired:
        raise RuntimeError("El backup tardó demasiado y se canceló.")
    except FileNotFoundError:
        raise RuntimeError("pg_dump no está instalado en el servidor.")


def restore_backup(filename: str) -> dict[str, Any]:
    """Restaura un backup usando psql."""
    filepath = BACKUP_DIR / filename
    if not filepath.exists():
        raise RuntimeError(f"El backup {filename} no existe.")

    database_url = settings.database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL no está configurada.")

    db_name = _database_name(database_url)
    env = os.environ.copy()
    try:
        from urllib.parse import urlparse

        parsed = urlparse(database_url)
        if parsed.password:
            env["PGPASSWORD"] = parsed.password
        if parsed.username:
            env["PGUSER"] = parsed.username
        if parsed.hostname:
            env["PGHOST"] = parsed.hostname
        if parsed.port:
            env["PGPORT"] = str(parsed.port)
        env["PGDATABASE"] = db_name
    except Exception as exc:  # pragma: no cover
        logger.warning("No se pudieron extraer credenciales de DATABASE_URL: %s", exc)

    cmd = [
        "psql",
        "--no-password",
        "--verbose",
        "--file",
        str(filepath),
        db_name,
    ]

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            logger.error("psql restore falló: %s", result.stderr)
            raise RuntimeError(f"Restauración falló: {result.stderr[:500]}")
        return {
            "success": True,
            "filename": filename,
            "message": "Backup restaurado correctamente.",
        }
    except subprocess.TimeoutExpired:
        raise RuntimeError("La restauración tardó demasiado y se canceló.")
    except FileNotFoundError:
        raise RuntimeError("psql no está instalado en el servidor.")
