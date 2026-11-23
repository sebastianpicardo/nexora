from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

from src.core.config import settings

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
}
MAX_URL_LENGTH = 2000


def _validate_host(host: str) -> None:
    normalized = host.strip().lower().rstrip(".")
    if not normalized:
        raise ValueError("La URL no incluye un host valido.")
    if normalized in BLOCKED_HOSTNAMES or normalized.endswith(".localhost"):
        raise ValueError("La URL apunta a un host local no permitido.")
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return
    if not address.is_global and not settings.outbound_allow_private:
        raise ValueError("La URL apunta a una direccion privada o reservada.")


def validate_outbound_url(url: str) -> str:
    """Valida esquema, credenciales y hosts literales de una URL saliente."""

    candidate = (url or "").strip()
    if not candidate or len(candidate) > MAX_URL_LENGTH:
        raise ValueError("La URL no es valida.")
    parts = urlsplit(candidate)
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("Solo se permiten URLs http o https.")
    if parts.username or parts.password:
        raise ValueError("La URL no puede incluir credenciales.")
    if not parts.hostname:
        raise ValueError("La URL no incluye un host valido.")
    _validate_host(parts.hostname)
    return candidate


async def ensure_safe_outbound_url(url: str) -> str:
    """Valida una URL y resuelve DNS para bloquear destinos internos (SSRF)."""

    candidate = validate_outbound_url(url)
    host = urlsplit(candidate).hostname or ""
    try:
        ipaddress.ip_address(host)
        return candidate
    except ValueError:
        pass

    port = 443 if urlsplit(candidate).scheme.lower() == "https" else 80
    loop = asyncio.get_running_loop()
    try:
        records = await loop.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except OSError as exc:
        raise ValueError("No se pudo resolver el host de destino.") from exc

    if not records:
        raise ValueError("No se pudo resolver el host de destino.")
    for record in records:
        address = ipaddress.ip_address(record[4][0])
        if not address.is_global and not settings.outbound_allow_private:
            raise ValueError("La URL resuelve a una direccion privada o reservada.")
    return candidate
