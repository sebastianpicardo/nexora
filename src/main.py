from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
import psycopg_pool
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from psycopg.errors import InsufficientPrivilege, UndefinedColumn, UndefinedTable
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from src.api.deps import OriginGuardMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from src.api.router import api_router
from src.api.routes import health
from src.core.config import PROJECT_ROOT, settings
from src.core.errors import NexoraError
from src.core.logging import get_logger, setup_logging
from src.db import repositories
from src.db.init_db import apply_migrations, diagnose_schema
from src.db.pool import PoolNotInitializedError, close_pool, ensure_pool, open_pool

try:  # Sentry es opcional en desarrollo/test.
    import sentry_sdk
except ImportError:  # pragma: no cover - solo ocurre si falta la dependencia
    sentry_sdk = None

logger = get_logger(__name__)


def _init_sentry() -> None:
    dsn = settings.sentry_dsn.strip()
    if not dsn or sentry_sdk is None:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=settings.app_env,
        release=f"nexora@{settings.app_version}",
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
    logger.info("Sentry inicializado para %s", settings.app_env)


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            if not self._can_fallback(path, scope):
                return PlainTextResponse("Not found", status_code=404)
            response = await super().get_response("index.html", scope)
            self._apply_cache_headers(response, "index.html")
            return response

        if response.status_code == 404:
            if not self._can_fallback(path, scope):
                return PlainTextResponse("Not found", status_code=404)
            response = await super().get_response("index.html", scope)
            self._apply_cache_headers(response, "index.html")
            return response

        self._apply_cache_headers(response, path)
        return response

    @staticmethod
    def _apply_cache_headers(response, path: str) -> None:
        normalized = (path or "").lstrip("/")
        name = normalized.rsplit("/", 1)[-1].lower()
        if normalized in {"", "."} or name in {"index.html", "sw.js", "manifest.webmanifest"}:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif normalized.startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

    @staticmethod
    def _can_fallback(path: str, scope: dict) -> bool:
        request_path = str(scope.get("path", ""))
        relative_path = path.lstrip("/")
        if request_path.startswith("/api") or relative_path.startswith("api"):
            return False
        if request_path.startswith("/assets/") or relative_path.startswith("assets/"):
            return False
        return "." not in Path(request_path).name and "." not in Path(relative_path).name


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    if settings.app_env.lower() != "test":
        settings.validate_startup()
        try:
            pool = await open_pool()
        except Exception as exc:  # noqa: BLE001 - no bloqueamos el arranque
            logger.exception(
                "No se pudo inicializar el pool de Postgres al arrancar (%s: %s). "
                "Se reintentará de forma perezosa en la primera petición que use la base.",
                type(exc).__name__,
                exc,
            )
        else:
            try:
                async with pool.connection() as conn:
                    await repositories.ensure_default_plans(conn)
                    purged = await repositories.purge_expired_ai_usage(conn)
                    if purged:
                        logger.info("Retención IA aplicada: %s registros depurados", purged)
            except Exception:  # noqa: BLE001 - datos iniciales no bloquean el arranque
                logger.exception(
                    "El pool existe pero no se pudieron preparar los datos iniciales (planes/limpieza)."
                )
        logger.info(
            "%s %s iniciado en %s (storage=%s, llm=%s)",
            settings.app_name,
            settings.app_version,
            settings.app_env,
            settings.storage_backend,
            settings.llm_provider,
        )
        if settings.is_production:
            try:
                from src.services import backup_service

                if not backup_service.is_backup_available():
                    logger.warning(
                        "pg_dump no está disponible: los backups de base de datos están deshabilitados."
                    )
            except Exception:
                logger.exception("No se pudo verificar la disponibilidad de pg_dump.")
        
        # Aplicar migraciones pendientes
        apply_migrations()

        # Diagnóstico de esquema: loguea exactamente qué tablas/columnas faltan.
        try:
            missing = diagnose_schema()
            if missing:
                logger.error("Esquema incompleto. Faltan: %s", missing)
            else:
                logger.info("Diagnóstico de esquema: tablas y columnas requeridas presentes.")
        except Exception as exc:  # noqa: BLE001 - nunca bloquear el arranque
            logger.error(
                "No se pudo ejecutar el diagnóstico de esquema (%s): %s",
                type(exc).__name__,
                exc,
            )
    else:
        logger.info("Modo test: pool de base de datos no inicializado")
    try:
        yield
    finally:
        if settings.app_env.lower() != "test":
            await close_pool()


def create_app() -> FastAPI:
    _init_sentry()
    app = FastAPI(
        title=f"{settings.app_name} API",
        description="Analizador y auditor automatizado de compras y precios B2B.",
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site=settings.cookie_samesite,
        https_only=settings.cookie_secure,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
        expose_headers=["Content-Disposition"],
        max_age=600,
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(OriginGuardMiddleware)

    @app.middleware("http")
    async def ensure_database_pool(request: Request, call_next):
        """Inicialización perezosa del pool.

        Si el ``lifespan`` no se ejecutó (o falló), la primera petición que usa
        la base crea el pool con un lock. Nunca lanza: si falla, el handler de
        ``PoolNotInitializedError`` responde 503 con el diagnóstico real.
        """
        path = request.url.path
        if settings.app_env.lower() != "test" and (
            path.startswith("/api") or path.startswith("/health/ready")
        ):
            try:
                await ensure_pool()
            except Exception:  # noqa: BLE001 - se maneja en el handler de rutas
                pass
        return await call_next(request)

    @app.exception_handler(NexoraError)
    async def nexora_error_handler(_request: Request, exc: NexoraError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.message,
                "code": exc.code,
                "details": exc.details,
            },
        )

    @app.exception_handler(InsufficientPrivilege)
    async def insufficient_privilege_handler(request: Request, exc: InsufficientPrivilege):
        logger.error("Permisos insuficientes en %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": (
                    "La base de datos rechazó la operación por políticas de seguridad (RLS). "
                    "Un administrador debe ejecutar database/migrations/020_rls_app_policies.sql "
                    "como dueño de la base."
                ),
                "code": "database_rls_misconfigured",
            },
        )

    @app.exception_handler(UndefinedTable)
    async def undefined_table_handler(request: Request, exc: UndefinedTable):
        logger.error("Tabla faltante en %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": (
                    "La base de datos no tiene el esquema más reciente. "
                    "Un administrador debe aplicar las migraciones pendientes "
                    "(database/migrations, incluida 021_automation_runs.sql)."
                ),
                "code": "database_schema_outdated",
            },
        )

    @app.exception_handler(UndefinedColumn)
    async def undefined_column_handler(request: Request, exc: UndefinedColumn):
        logger.error("Columna faltante en %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": (
                    "La base de datos no tiene el esquema más reciente (falta una columna). "
                    "Un administrador debe aplicar las migraciones pendientes en "
                    "database/migrations (o database/schema.sql)."
                ),
                "code": "database_schema_outdated",
                "detail": str(exc)[:300],
            },
        )

    @app.exception_handler(psycopg_pool.PoolTimeout)
    async def pool_timeout_handler(request: Request, exc: psycopg_pool.PoolTimeout):
        logger.error(
            "Timeout de conexión a PostgreSQL en %s %s: %s",
            request.method,
            request.url.path,
            exc,
        )
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": (
                    "No se pudo conectar a la base de datos (tiempo de espera agotado). "
                    "Revisa DATABASE_URL/MIGRATION_DATABASE_URL y que el servidor acepte conexiones."
                ),
                "code": "database_unavailable",
            },
        )

    @app.exception_handler(psycopg.errors.DatabaseError)
    async def database_error_handler(request: Request, exc: psycopg.errors.DatabaseError):
        # Fallback para cualquier error de PostgreSQL no cubierto arriba
        # (operacional, de programación, integridad, etc.). Nunca un 500 mudo.
        logger.error(
            "Error de base de datos en %s %s [sqlstate=%s]: %s",
            request.method,
            request.url.path,
            getattr(exc, "sqlstate", None),
            exc,
        )
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": (
                    "La base de datos rechazó la operación. Revisa los logs del servidor y "
                    "aplica las migraciones pendientes si el esquema está desactualizado."
                ),
                "code": "database_error",
                "sqlstate": getattr(exc, "sqlstate", None),
                "detail": str(exc)[:300],
            },
        )

    @app.exception_handler(sqlite3.Error)
    async def sqlite_error_handler(request: Request, exc: sqlite3.Error):
        logger.error(
            "Error de SQLite en %s %s: %s", request.method, request.url.path, exc
        )
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": (
                    "Error en la base de datos SQLite. Verifica el esquema local y los logs."
                ),
                "code": "database_error",
                "detail": str(exc)[:300],
            },
        )

    @app.exception_handler(PoolNotInitializedError)
    async def pool_not_initialized_handler(request: Request, exc: PoolNotInitializedError):
        cause = exc.cause
        logger.error(
            "Pool de base de datos no inicializado en %s %s (%s): %s",
            request.method,
            request.url.path,
            type(cause).__name__ if cause else "sin causa registrada",
            cause or exc,
        )
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": (
                    "La base de datos no está disponible en este momento. "
                    "Revisa DATABASE_URL y los logs del servidor."
                ),
                "code": "database_unavailable",
                "exception": type(cause).__name__ if cause else "PoolNotInitializedError",
                "detail": (str(cause) if cause else str(exc))[:300],
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Loguea traza completa y devuelve un detalle corto y diagnóstico
        # (nunca un "internal_error" mudo sin información para depurar).
        logger.exception(
            "Error no controlado en %s %s (%s)",
            request.method,
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Error interno del servidor",
                "code": "internal_error",
                "exception": type(exc).__name__,
                "detail": str(exc)[:300],
            },
        )

    app.include_router(health.router)
    app.include_router(api_router)

    @app.get("/version", include_in_schema=False)
    async def app_version():
        commit = (
            os.getenv("RENDER_GIT_COMMIT")
            or os.getenv("GIT_COMMIT")
            or os.getenv("COMMIT_SHA")
            or "dev"
        )
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "commit": commit[:12],
            "environment": settings.app_env,
        }

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        include_in_schema=False,
    )
    async def api_not_found(path: str):
        raise HTTPException(status_code=404, detail="Ruta API no encontrada")

    client_dist = PROJECT_ROOT / "client" / "dist"
    if client_dist.exists():
        app.mount("/", SPAStaticFiles(directory=client_dist, html=True), name="client")
    else:

        @app.get("/", include_in_schema=False)
        async def api_root():
            return {
                "service": settings.app_name,
                "version": settings.app_version,
                "docs": "/docs",
                "health": "/health",
            }

    return app


app = create_app()
