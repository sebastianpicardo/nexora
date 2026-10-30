from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from src.api.router import api_router
from src.api.routes import health
from src.core.config import PROJECT_ROOT, settings
from src.core.errors import NexoraError
from src.core.logging import get_logger, setup_logging
from src.db import repositories
from src.db.pool import close_pool, open_pool

logger = get_logger(__name__)


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or not self._can_fallback(path, scope):
                raise
            return await super().get_response("index.html", scope)

        if response.status_code == 404 and self._can_fallback(path, scope):
            return await super().get_response("index.html", scope)
        return response

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
            async with pool.connection() as conn:
                await repositories.ensure_default_plans(conn)
        except Exception:
            logger.exception("No se pudo inicializar el pool de Postgres; el servicio seguirá disponible")
        logger.info(
            "%s %s iniciado en %s (storage=%s, llm=%s)",
            settings.app_name,
            settings.app_version,
            settings.app_env,
            settings.storage_backend,
            settings.llm_provider,
        )
    else:
        logger.info("Modo test: pool de base de datos no inicializado")
    try:
        yield
    finally:
        if settings.app_env.lower() != "test":
            await close_pool()


def create_app() -> FastAPI:
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

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Error no controlado en %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Error interno del servidor", "code": "internal_error"},
        )

    app.include_router(health.router)
    app.include_router(api_router)

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
