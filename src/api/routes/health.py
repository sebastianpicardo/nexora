from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.db.init_db import diagnose_schema
from src.db.pool import check_db

router = APIRouter(tags=["health"])

READINESS_TIMEOUT_SECONDS = 5


def _base_payload() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


async def _readiness_payload() -> tuple[dict, int]:
    try:
        await asyncio.wait_for(check_db(), timeout=READINESS_TIMEOUT_SECONDS)
        return (
            {
                **_base_payload(),
                "status": "ok",
                "database": "connected",
                "checks": {"database": "ok"},
            },
            200,
        )
    except Exception as exc:
        error = "Base de datos no disponible." if settings.is_production else str(exc)
        return (
            {
                **_base_payload(),
                "status": "error",
                "database": "disconnected",
                "checks": {"database": "error"},
                "error": error,
            },
            503,
        )


@router.get("/health")
async def health():
    return JSONResponse(
        content={
            **_base_payload(),
            "status": "ok",
            "database": "not_checked",
            "checks": {"api": "ok"},
        },
        status_code=200,
    )


@router.get("/api/health")
async def api_health():
    return await health()


@router.get("/health/ready")
async def health_ready():
    payload, status_code = await _readiness_payload()
    return JSONResponse(content=payload, status_code=status_code)


@router.get("/api/health/ready")
async def api_health_ready():
    payload, status_code = await _readiness_payload()
    return JSONResponse(content=payload, status_code=status_code)


@router.get("/health/schema")
async def health_schema():
    """Diagnóstico en vivo: conectividad y tablas/columnas faltantes.

    Útil para depurar ``internal_error`` en producción sin acceso a logs.
    """
    missing: dict | None = None
    connected = True
    error = None
    try:
        missing = await asyncio.to_thread(diagnose_schema)
    except Exception as exc:  # noqa: BLE001 - se reporta como diagnóstico
        connected = False
        error = type(exc).__name__
    schema_ok = connected and not missing
    payload = {
        **_base_payload(),
        "database": "connected" if connected else "disconnected",
        "schema_ok": schema_ok,
        "missing": missing,
    }
    if error:
        payload["error"] = error
    return JSONResponse(content=payload, status_code=200 if schema_ok else 503)


@router.get("/api/health/schema")
async def api_health_schema():
    return await health_schema()
