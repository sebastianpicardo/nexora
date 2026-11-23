from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

BACKUP_DIR = Path("./backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
REMOTE_PREFIX = "backups/"


def _remote_bucket() -> str:
    return (os.getenv("BACKUP_STORAGE_BUCKET") or settings.supabase_storage_bucket or "").strip()


def _remote_enabled() -> bool:
    return bool(
        settings.storage_backend == "supabase"
        and settings.supabase_url
        and settings.supabase_service_role_key
        and _remote_bucket()
    )


def _supabase_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }


def _remote_object_url(filename: str) -> str:
    return (
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/"
        f"{_remote_bucket()}/{REMOTE_PREFIX}{filename}"
    )


def _upload_remote(filename: str, content: bytes) -> str:
    url = _remote_object_url(filename)
    headers = {**_supabase_headers(), "Content-Type": "application/sql", "x-upsert": "true"}
    with httpx.Client(timeout=120) as client:
        response = client.put(url, headers=headers, content=content)
    if response.status_code not in {200, 201}:
        logger.error("No se pudo subir el backup a Supabase Storage (%s)", response.status_code)
        raise RuntimeError("No se pudo persistir el backup en almacenamiento externo.")
    return f"{REMOTE_PREFIX}{filename}"


def _download_remote(filename: str) -> bytes | None:
    url = _remote_object_url(filename)
    with httpx.Client(timeout=120) as client:
        response = client.get(url, headers=_supabase_headers())
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise RuntimeError("No se pudo descargar el backup desde almacenamiento externo.")
    return response.content


def _list_remote() -> list[dict[str, Any]]:
    if not _remote_enabled():
        return []
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/list/{_remote_bucket()}"
    payload = {"prefix": REMOTE_PREFIX, "limit": 100, "offset": 0, "sortBy": {"column": "name", "order": "desc"}}
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                url,
                headers={**_supabase_headers(), "Content-Type": "application/json"},
                json=payload,
            )
        if response.status_code >= 400:
            logger.warning("No se pudo listar backups remotos (%s)", response.status_code)
            return []
    except httpx.HTTPError:
        logger.warning("No se pudo conectar con el almacenamiento de backups")
        return []

    items: list[dict[str, Any]] = []
    for entry in response.json() or []:
        name = str(entry.get("name") or "")
        if not name.endswith(".sql"):
            continue
        metadata = entry.get("metadata") or {}
        items.append(
            {
                "filename": name,
                "path": f"{REMOTE_PREFIX}{name}",
                "size_bytes": int(metadata.get("size") or 0),
                "created_at": metadata.get("lastModified") or entry.get("updated_at"),
                "download_url": f"/api/backups/download/{name}",
                "storage": "supabase",
                "durable": True,
            }
        )
    return items



def _tool_available(name: str) -> bool:
    try:
        subprocess.run(
            [name, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def is_backup_available() -> bool:
    """Indica si pg_dump está instalado en el servidor."""
    return _tool_available("pg_dump")


def is_restore_available() -> bool:
    """Indica si psql está instalado para restaurar backups."""
    return _tool_available("psql")


def _database_name(database_url: str) -> str:
    """Extrae el nombre de la base de datos de la URL."""
    # postgres://user:pass@host:port/dbname
    parts = database_url.rstrip("/").split("/")
    return parts[-1] if parts else "nexora"


def list_backups() -> list[dict[str, Any]]:
    """Lista los backups locales y los persistidos en almacenamiento externo."""
    backups: list[dict[str, Any]] = []
    seen: set[str] = set()
    if BACKUP_DIR.exists():
        for path in sorted(BACKUP_DIR.glob("*.sql"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = path.stat()
            seen.add(path.name)
            backups.append(
                {
                    "filename": path.name,
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "download_url": f"/api/backups/download/{path.name}",
                    "storage": "local",
                    "durable": False,
                }
            )
    for remote in _list_remote():
        if remote["filename"] not in seen:
            backups.append(remote)
    backups.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return backups


def read_backup_bytes(filename: str) -> bytes | None:
    """Devuelve el contenido de un backup local o remoto."""
    local = BACKUP_DIR / filename
    if local.exists():
        return local.read_bytes()
    if _remote_enabled():
        return _download_remote(filename)
    return None


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
        storage = "local"
        durable = False
        if _remote_enabled():
            content = filepath.read_bytes()
            _upload_remote(filename, content)
            storage = "supabase"
            durable = True
            try:
                filepath.unlink(missing_ok=True)
            except OSError:
                logger.warning("No se pudo eliminar el backup local temporal %s", filename)
        return {
            "success": True,
            "filename": filename,
            "path": f"{REMOTE_PREFIX}{filename}" if durable else str(filepath),
            "size_bytes": stat.st_size,
            "created_at": datetime.utcnow().isoformat(),
            "download_url": f"/api/backups/download/{filename}",
            "storage": storage,
            "durable": durable,
            "message": (
                "Backup creado y persistido en almacenamiento externo."
                if durable
                else "Backup creado en disco local (configura Supabase Storage para persistencia)."
            ),
        }
    except subprocess.TimeoutExpired:
        raise RuntimeError("El backup tardó demasiado y se canceló.") from None
    except FileNotFoundError:
        raise RuntimeError("pg_dump no está instalado en el servidor.") from None


def restore_backup(filename: str) -> dict[str, Any]:
    """Restaura un backup local o remoto usando psql."""
    content = read_backup_bytes(filename)
    if content is None:
        raise RuntimeError(f"El backup {filename} no existe.")

    database_url = settings.database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL no está configurada.")

    local_path = BACKUP_DIR / filename
    temporary = not local_path.exists()
    if temporary:
        fd, temp_name = tempfile.mkstemp(prefix="nexora_restore_", suffix=".sql", dir=BACKUP_DIR)
        os.close(fd)
        local_path = Path(temp_name)
        local_path.write_bytes(content)

    db_name = _database_name(database_url)
    env = os.environ.copy()
    try:
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
        str(local_path),
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
        raise RuntimeError("La restauración tardó demasiado y se canceló.") from None
    except FileNotFoundError:
        raise RuntimeError("psql no está instalado en el servidor.") from None
    finally:
        if temporary:
            try:
                local_path.unlink(missing_ok=True)
            except OSError:
                pass
