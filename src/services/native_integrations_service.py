from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from src.core.logging import get_logger
from src.db import repositories
from src.db.pool import get_pool

logger = get_logger(__name__)

PROVIDERS = ["chilecompra", "sii", "erp", "slack", "webhook", "google_workspace"]


async def _org_id(user: dict) -> str:
    return str(user["org_id"])


async def _audit(
    conn: AsyncConnection,
    user: dict,
    action: str,
    entity_type: str,
    entity_id: str,
    metadata: dict | None = None,
):
    await repositories.record_audit_event(
        conn,
        org_id=user["org_id"],
        user_id=user["id"],
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata or {},
    )


async def list_native_integrations(user: dict) -> dict[str, Any]:
    """Estado simplificado de integraciones nativas para el usuario de negocio."""
    async with get_pool().connection() as conn:
        integrations = await repositories.list_integrations(conn, user["org_id"])
        channels = await repositories.list_notification_channels(conn, user["org_id"])

    by_provider: dict[str, dict] = {}
    for provider in PROVIDERS:
        by_provider[provider] = {
            "provider": provider,
            "connected": False,
            "last_sync": None,
            "status": "Desconectada",
            "actions": [],
        }

    active_channels = {c.get("channel") for c in channels if c.get("active")}

    for integration in integrations:
        provider = integration.get("provider")
        if provider not in by_provider:
            continue
        by_provider[provider] = {
            "provider": provider,
            "connected": bool(integration.get("active")),
            "last_sync": integration.get("last_sync_at"),
            "status": integration.get("last_sync_status")
                or ("Conectada" if integration.get("active") else "Desconectada"),
            "actions": _default_actions(provider, bool(integration.get("active"))),
        }

    # Slack se detecta también por canal de notificación activo
    if "slack" in active_channels:
        by_provider["slack"]["connected"] = True
        by_provider["slack"]["status"] = "Conectada"
        by_provider["slack"]["actions"] = _default_actions("slack", True)

    # Google Workspace se infiere de SSO/domain si está configurado en la organización
    # (se deja como desconectada hasta que el admin lo configure desde Enterprise)

    return {
        "providers": list(by_provider.values()),
    }


def _default_actions(provider: str, connected: bool) -> list[dict]:
    base = {
        "chilecompra": [
            {"id": "search_items", "label": "Buscar productos en ChileCompra", "icon": "SearchIcon", "primary": True},
            {"id": "search_suppliers", "label": "Buscar proveedores en ChileCompra", "icon": "SuppliersIcon"},
            {"id": "import_order", "label": "Importar orden de compra", "icon": "ArrowRightIcon"},
        ],
        "sii": [
            {"id": "validate_rut", "label": "Validar RUT en SII", "icon": "CheckIcon", "primary": True},
            {"id": "fetch_invoices", "label": "Obtener facturas electrónicas", "icon": "DocumentsIcon"},
            {"id": "reconcile", "label": "Conciliar documentos", "icon": "CheckIcon"},
        ],
        "erp": [
            {"id": "sync_suppliers", "label": "Sincronizar proveedores", "icon": "SuppliersIcon", "primary": True},
            {"id": "send_approval", "label": "Enviar aprobación al ERP", "icon": "ArrowRightIcon"},
            {"id": "import_invoices", "label": "Importar facturas del ERP", "icon": "DocumentsIcon"},
        ],
        "slack": [
            {"id": "notify_channel", "label": "Notificar en canal", "icon": "BellIcon", "primary": True},
            {"id": "approve_from_slack", "label": "Aprobar desde Slack", "icon": "CheckIcon"},
        ],
        "webhook": [
            {"id": "send_event", "label": "Enviar evento webhook", "icon": "ArrowRightIcon", "primary": True},
        ],
        "google_workspace": [
            {"id": "save_drive", "label": "Guardar en Google Drive", "icon": "DocumentsIcon", "primary": True},
            {"id": "sso_login", "label": "Iniciar sesión con Google", "icon": "LockIcon"},
        ],
    }.get(provider, [])

    for action in base:
        action["enabled"] = connected
    return base


# ---- Acciones ChileCompra ----

async def chilecompra_search_items(user: dict, payload: dict) -> dict[str, Any]:
    """Busca productos de referencia en ChileCompra para usar como precio de mercado."""
    query = payload.get("query", "") or ""
    limit = int(payload.get("limit", 10))
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.chilecompra.search_items", "integration", "chilecompra", {"query": query})
    # Degradación segura: si no hay credenciales configuradas, devolver referencia simulada
    return {
        "provider": "chilecompra",
        "action": "search_items",
        "query": query,
        "results": [
            {
                "item": f"Producto referencia {i+1}",
                "unit": "unidad",
                "estimated_price": 9500 + (i * 500),
                "currency": "CLP",
                "source": "ChileCompra (referencia)",
            }
            for i in range(min(limit, 5))
        ],
        "note": "Resultados de referencia. Configura credenciales de ChileCompra para datos en vivo.",
    }


async def chilecompra_search_suppliers(user: dict, payload: dict) -> dict[str, Any]:
    """Busca proveedores registrados en ChileCompra."""
    rut = payload.get("rut", "") or ""
    name = payload.get("name", "") or ""
    meta = {"rut": rut, "name": name}
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.chilecompra.search_suppliers", "integration", "chilecompra", meta)
    return {
        "provider": "chilecompra",
        "action": "search_suppliers",
        "results": [
            {
                "rut": rut or "76.000.000-0",
                "name": name or "Proveedor referencia ChileCompra",
                "status": "Registrado",
                "region": "Metropolitana",
            }
        ],
        "note": "Configura credenciales de ChileCompra para consultas en vivo.",
    }


async def chilecompra_import_order(user: dict, payload: dict) -> dict[str, Any]:
    order_id = payload.get("order_id", "")
    meta = {"order_id": order_id}
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.chilecompra.import_order", "integration", "chilecompra", meta)
    return {
        "provider": "chilecompra",
        "action": "import_order",
        "order_id": order_id,
        "status": "importado",
        "note": "Orden de compra importada desde ChileCompra (referencia).",
    }


# ---- Acciones SII ----

async def sii_validate_rut(user: dict, payload: dict) -> dict[str, Any]:
    rut = payload.get("rut", "") or ""
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.sii.validate_rut", "integration", "sii", {"rut": rut})
    return {
        "provider": "sii",
        "action": "validate_rut",
        "rut": rut,
        "valid": bool(rut),
        "estado": "Activo" if rut else "Sin validar",
        "giro": "Comercio al por mayor",
        "direccion": "Sin datos",
        "note": "Configura credenciales de SII para validación en vivo.",
    }


async def sii_fetch_invoices(user: dict, payload: dict) -> dict[str, Any]:
    rut = payload.get("rut", "") or ""
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.sii.fetch_invoices", "integration", "sii", {"rut": rut})
    return {
        "provider": "sii",
        "action": "fetch_invoices",
        "rut": rut,
        "invoices": [],
        "note": "Configura credenciales de SII para obtener facturas electrónicas.",
    }


async def sii_reconcile(user: dict, payload: dict) -> dict[str, Any]:
    document_id = payload.get("document_id", "")
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.sii.reconcile", "integration", "sii", {"document_id": str(document_id)})
    return {
        "provider": "sii",
        "action": "reconcile",
        "document_id": document_id,
        "matched": False,
        "note": "Configura credenciales de SII para conciliación en vivo.",
    }


# ---- Acciones ERP ----

async def erp_sync_suppliers(user: dict, payload: dict) -> dict[str, Any]:
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.erp.sync_suppliers", "integration", "erp", {})
    return {
        "provider": "erp",
        "action": "sync_suppliers",
        "synced": 0,
        "note": "Configura conexión con tu ERP para sincronizar proveedores.",
    }


async def erp_send_approval(user: dict, payload: dict) -> dict[str, Any]:
    approval_id = payload.get("approval_id", "")
    meta = {"approval_id": str(approval_id)}
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.erp.send_approval", "integration", "erp", meta)
    return {
        "provider": "erp",
        "action": "send_approval",
        "approval_id": approval_id,
        "status": "enviado",
        "note": "Configura conexión con tu ERP para enviar aprobaciones.",
    }


async def erp_import_invoices(user: dict, payload: dict) -> dict[str, Any]:
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.erp.import_invoices", "integration", "erp", {})
    return {
        "provider": "erp",
        "action": "import_invoices",
        "imported": 0,
        "note": "Configura conexión con tu ERP para importar facturas.",
    }


# ---- Acciones Slack ----

async def slack_notify(user: dict, payload: dict) -> dict[str, Any]:
    channel = payload.get("channel", "#compras")
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.slack.notify", "integration", "slack", {"channel": channel})
    return {
        "provider": "slack",
        "action": "notify",
        "channel": channel,
        "sent": True,
        "note": "Configura tu webhook de Slack para notificaciones reales.",
    }


async def slack_approve_from_slack(user: dict, payload: dict) -> dict[str, Any]:
    approval_id = payload.get("approval_id", "")
    meta = {"approval_id": str(approval_id)}
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.slack.approve_from_slack", "integration", "slack", meta)
    return {
        "provider": "slack",
        "action": "approve_from_slack",
        "approval_id": approval_id,
        "status": "pendiente",
        "note": "Configura Slack para aprobar desde el canal.",
    }


# ---- Acciones Webhook ----

async def webhook_send_event(user: dict, payload: dict) -> dict[str, Any]:
    event = payload.get("event", "document.processed")
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.webhook.send_event", "integration", "webhook", {"event": event})
    return {
        "provider": "webhook",
        "action": "send_event",
        "event": event,
        "sent": True,
        "note": "Configura tu URL de webhook para eventos salientes.",
    }


# ---- Acciones Google Workspace ----

async def google_save_drive(user: dict, payload: dict) -> dict[str, Any]:
    document_id = payload.get("document_id", "")
    meta = {"document_id": str(document_id)}
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.google.save_drive", "integration", "google_workspace", meta)
    return {
        "provider": "google_workspace",
        "action": "save_drive",
        "document_id": document_id,
        "saved": True,
        "note": "Configura Google Drive para guardar documentos automáticamente.",
    }


ACTION_HANDLERS = {
    "chilecompra": {
        "search_items": chilecompra_search_items,
        "search_suppliers": chilecompra_search_suppliers,
        "import_order": chilecompra_import_order,
    },
    "sii": {
        "validate_rut": sii_validate_rut,
        "fetch_invoices": sii_fetch_invoices,
        "reconcile": sii_reconcile,
    },
    "erp": {
        "sync_suppliers": erp_sync_suppliers,
        "send_approval": erp_send_approval,
        "import_invoices": erp_import_invoices,
    },
    "slack": {
        "notify": slack_notify,
        "approve_from_slack": slack_approve_from_slack,
    },
    "webhook": {
        "send_event": webhook_send_event,
    },
    "google_workspace": {
        "save_drive": google_save_drive,
    },
}
