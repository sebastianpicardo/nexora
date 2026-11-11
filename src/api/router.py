from __future__ import annotations

from fastapi import APIRouter

from src.api.routes import (
    admin,
    alerts,
    auth,
    backup,
    billing,
    dashboard,
    documents,
    enterprise,
    exceptions,
    exports,
    insights,
    items,
    native_integrations,
    organizations,
    price_catalog,
    profile,
    public_api,
    suppliers,
    team,
    user_search_history,
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
api_router.include_router(enterprise.router)
api_router.include_router(enterprise.inbound_router)
api_router.include_router(native_integrations.router)
api_router.include_router(user_search_history.router)
api_router.include_router(price_catalog.router)
api_router.include_router(alerts.router)
api_router.include_router(insights.router)
api_router.include_router(backup.router)
api_router.include_router(public_api.router)
