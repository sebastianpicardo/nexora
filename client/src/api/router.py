from __future__ import annotations

from fastapi import APIRouter

from src.api.routes import (
    admin,
    auth,
    billing,
    dashboard,
    documents,
    exceptions,
    exports,
    items,
    organizations,
    profile,
    suppliers,
    team,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(organizations.router)
api_router.include_router(team.router)
api_router.include_router(billing.router)
api_router.include_router(admin.router)
api_router.include_router(suppliers.router)
api_router.include_router(documents.router)
api_router.include_router(items.router)
api_router.include_router(exceptions.router)
api_router.include_router(exports.router)
api_router.include_router(dashboard.router)
