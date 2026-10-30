from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

import httpx

from src.core.config import PROJECT_ROOT, settings
from src.core.errors import StorageError
from src.core.logging import get_logger

logger = get_logger(__name__)
_bucket_checked = False


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:180] or "documento"


def _supabase_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }


def _supabase_url(path: str) -> str:
    return f"{settings.supabase_url.rstrip('/')}{path}"


def _local_root() -> Path:
    root = Path(settings.local_upload_dir)
    return root if root.is_absolute() else PROJECT_ROOT / root


async def _ensure_bucket() -> None:
    global _bucket_checked
    if _bucket_checked:
        return
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise StorageError("SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son obligatorias para Storage.")

    bucket = settings.supabase_storage_bucket
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(_supabase_url(f"/storage/v1/bucket/{bucket}"), headers=_supabase_headers())
        if response.status_code == 404:
            created = await client.post(
                _supabase_url("/storage/v1/bucket"),
                headers=_supabase_headers(),
                json={"id": bucket, "name": bucket, "public": False},
            )
            if created.status_code not in {200, 201}:
                raise StorageError(f"No se pudo crear el bucket '{bucket}': {created.text}")
        elif response.status_code >= 400:
            raise StorageError(f"No se pudo verificar el bucket '{bucket}': {response.text}")
    _bucket_checked = True


async def save_document(
    *,
    org_id: UUID | str,
    document_id: UUID | str,
    filename: str,
    content: bytes,
    mime_type: str,
) -> str:
    safe_name = _safe_filename(filename)
    storage_path = f"{org_id}/{document_id}/{safe_name}"

    if settings.storage_backend == "local":
        target = _local_root() / str(org_id) / str(document_id) / safe_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return storage_path

    if settings.storage_backend != "supabase":
        raise StorageError(f"STORAGE_BACKEND no soportado: {settings.storage_backend}")

    await _ensure_bucket()
    url = _supabase_url(f"/storage/v1/object/{settings.supabase_storage_bucket}/{storage_path}")
    headers = {**_supabase_headers(), "Content-Type": mime_type, "x-upsert": "true"}
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.put(url, headers=headers, content=content)
    if response.status_code not in {200, 201}:
        logger.error("Supabase Storage upload failed: %s %s", response.status_code, response.text)
        raise StorageError(f"No se pudo subir el documento a Supabase Storage: {response.text}")
    return storage_path


async def read_document(storage_path: str) -> bytes:
    if settings.storage_backend == "local":
        target = _local_root() / storage_path
        if not target.exists():
            raise StorageError(f"No se encontró el archivo local: {storage_path}")
        return target.read_bytes()

    url = _supabase_url(f"/storage/v1/object/{settings.supabase_storage_bucket}/{storage_path}")
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.get(url, headers=_supabase_headers())
    if response.status_code >= 400:
        raise StorageError(f"No se pudo descargar el documento desde Supabase: {response.text}")
    return response.content


async def create_signed_url(storage_path: str, expires_in: int = 3600) -> str | None:
    if settings.storage_backend == "local":
        return None
    url = _supabase_url(f"/storage/v1/object/sign/{settings.supabase_storage_bucket}/{storage_path}")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            url,
            headers=_supabase_headers(),
            json={"expiresIn": expires_in},
        )
    if response.status_code >= 400:
        logger.warning("No se pudo firmar URL: %s", response.text)
        return None
    signed_path = response.json().get("signedURL", "")
    if not signed_path:
        return None
    if signed_path.startswith("http"):
        return signed_path
    base = f"{settings.supabase_url.rstrip('/')}/storage/v1"
    return f"{base}{signed_path if signed_path.startswith('/') else '/' + signed_path}"
