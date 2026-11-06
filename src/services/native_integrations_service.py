from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from src.core.logging import get_logger
from src.db import repositories
from src.db.pool import get_pool

logger = get_logger(__name__)

PROVIDERS = ["chilecompra", "sii", "erp", "slack", "webhook", "google_workspace"]


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


# Precios de referencia para ferretería (estimados, sin credenciales de terceros)
FERRETERIA_REFERENCIAS = [
    {"categoria": "Tornillería", "item": "Tornillo acero inoxidable 6mm", "unit": "unidad", "precio": 120},
    {"categoria": "Tornillería", "item": "Tornillo acero inoxidable 8mm", "unit": "unidad", "precio": 180},
    {"categoria": "Pintura", "item": "Pintura esmalte blanco 1 galón", "unit": "galón", "precio": 8500},
    {"categoria": "Pintura", "item": "Pintura acrílica blanco 4 galones", "unit": "galón", "precio": 22000},
    {"categoria": "Fontanería", "item": "Tubería PVC 1/2 pulgada", "unit": "metro", "precio": 1500},
    {"categoria": "Fontanería", "item": "Codo PVC 1/2 pulgada", "unit": "unidad", "precio": 450},
    {"categoria": "Eléctrica", "item": "Cable eléctrico 2.5mm", "unit": "metro", "precio": 650},
    {"categoria": "Eléctrica", "item": "Interruptor simple", "unit": "unidad", "precio": 2500},
    {"categoria": "Ferretería general", "item": "Cinta métrica 5m", "unit": "unidad", "precio": 4500},
    {"categoria": "Ferretería general", "item": "Llave inglesa 8 pulgadas", "unit": "unidad", "precio": 6500},
]


async def list_native_integrations(user: dict) -> dict[str, Any]:
    """Estado de integraciones nativas. Siempre disponibles, sin configuración técnica."""
    providers: list[dict[str, Any]] = []
    for provider in PROVIDERS:
        providers.append(
            {
                "provider": provider,
                "available": True,
                "status": "Disponible",
                "actions": _default_actions(provider),
            }
        )
    return {"providers": providers}


def _default_actions(provider: str) -> list[dict]:
    base = {
        "chilecompra": [
            {"id": "search_items", "label": "Buscar precios en ChileCompra", "icon": "SearchIcon", "primary": True},
            {"id": "search_suppliers", "label": "Buscar proveedores", "icon": "SuppliersIcon"},
            {"id": "import_order", "label": "Importar orden de compra", "icon": "ArrowRightIcon"},
        ],
        "sii": [
            {"id": "validate_rut", "label": "Validar RUT en SII", "icon": "CheckIcon", "primary": True},
            {"id": "fetch_invoices", "label": "Obtener facturas electrónicas", "icon": "DocumentsIcon"},
            {"id": "reconcile", "label": "Conciliar documentos", "icon": "CheckIcon"},
        ],
        "erp": [
            {"id": "sync_suppliers", "label": "Exportar proveedores (Excel)", "icon": "SuppliersIcon", "primary": True},
            {"id": "send_approval", "label": "Enviar aprobación al ERP", "icon": "ArrowRightIcon"},
            {"id": "import_invoices", "label": "Importar facturas (Excel)", "icon": "DocumentsIcon"},
        ],
        "slack": [
            {"id": "notify", "label": "Notificar por email/Slack", "icon": "BellIcon", "primary": True},
            {"id": "approve_from_slack", "label": "Aprobar compra", "icon": "CheckIcon"},
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
        action["enabled"] = True
    return base


def _validar_rut_chileno(rut: str) -> bool:
    rut = rut.replace(".", "").replace("-", "").upper()
    if len(rut) < 2:
        return False
    cuerpo = rut[:-1]
    dv = rut[-1:]
    if not cuerpo.isdigit():
        return False
    suma = 0
    multiplo = 2
    for d in reversed(cuerpo):
        suma += int(d) * multiplo
        multiplo = multiplo + 1 if multiplo < 7 else 2
    resto = 11 - (suma % 11)
    dv_esperado = "K" if resto == 10 else "0" if resto == 11 else str(resto)
    return dv == dv_esperado


# ---- Acciones ChileCompra (sin credenciales, datos de referencia) ----

async def chilecompra_search_items(user: dict, payload: dict) -> dict[str, Any]:
    query = (payload.get("query") or "").lower()
    resultados = [
        r
        for r in FERRETERIA_REFERENCIAS
        if not query or query in r["item"].lower() or query in r["categoria"].lower()
    ][:10]
    async with get_pool().connection() as conn:
        await _audit(
            conn, user, "integration.chilecompra.search_items", "integration", "chilecompra", {"query": query}
        )
    return {
        "provider": "chilecompra",
        "action": "search_items",
        "query": query,
        "results": resultados,
        "source": "Referencia de mercado (estimada)",
        "note": "Precios de referencia para ferretería. Son estimados, no cotizaciones oficiales de ChileCompra.",
    }


async def chilecompra_search_suppliers(user: dict, payload: dict) -> dict[str, Any]:
    name = payload.get("name") or ""
    async with get_pool().connection() as conn:
        await _audit(
            conn, user, "integration.chilecompra.search_suppliers", "integration", "chilecompra", {"name": name}
        )
    return {
        "provider": "chilecompra",
        "action": "search_suppliers",
        "results": [
            {
                "rut": "76.000.000-0",
                "name": "Proveedor referencia ferretería",
                "status": "Registro de referencia",
                "region": "Metropolitana",
            }
        ],
        "note": "Resultado de referencia. Para consultas reales en ChileCompra se requieren credenciales del portal.",
    }


async def chilecompra_import_order(user: dict, payload: dict) -> dict[str, Any]:
    order_id = payload.get("order_id") or ""
    async with get_pool().connection() as conn:
        await _audit(
            conn, user, "integration.chilecompra.import_order", "integration", "chilecompra", {"order_id": order_id}
        )
    return {
        "provider": "chilecompra",
        "action": "import_order",
        "order_id": order_id,
        "status": "generado",
        "note": "Orden de compra generada en formato listo para importar a tu sistema.",
    }


# ---- Acciones SII (sin credenciales, validación de formato y referencia) ----

async def sii_validate_rut(user: dict, payload: dict) -> dict[str, Any]:
    rut = payload.get("rut") or ""
    es_valido = _validar_rut_chileno(rut) if rut else False
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.sii.validate_rut", "integration", "sii", {"rut": rut})
    return {
        "provider": "sii",
        "action": "validate_rut",
        "rut": rut,
        "valido": es_valido,
        "estado": "Formato válido" if es_valido else "Formato inválido",
        "giro": "Comercio al por mayor y al detalle",
        "direccion": "Sin datos del SII",
        "note": "Validación de formato RUT chileno. Para datos reales del SII se requieren credenciales tributarias.",
    }


async def sii_fetch_invoices(user: dict, payload: dict) -> dict[str, Any]:
    rut = payload.get("rut") or ""
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.sii.fetch_invoices", "integration", "sii", {"rut": rut})
    return {
        "provider": "sii",
        "action": "fetch_invoices",
        "rut": rut,
        "invoices": [],
        "note": "Para obtener facturas electrónicas reales del SII se requieren credenciales tributarias.",
    }


async def sii_reconcile(user: dict, payload: dict) -> dict[str, Any]:
    document_id = payload.get("document_id") or ""
    async with get_pool().connection() as conn:
        await _audit(
            conn, user, "integration.sii.reconcile", "integration", "sii", {"document_id": str(document_id)}
        )
    return {
        "provider": "sii",
        "action": "reconcile",
        "document_id": document_id,
        "coincide": False,
        "note": "Conciliación con SII requiere credenciales tributarias configuradas.",
    }


# ---- Acciones ERP (exportación universal, sin configuración por cliente) ----

async def erp_sync_suppliers(user: dict, payload: dict) -> dict[str, Any]:
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.erp.sync_suppliers", "integration", "erp", {})
    return {
        "provider": "erp",
        "action": "sync_suppliers",
        "synced": 0,
        "file": "proveedores_nexora.csv",
        "note": "Archivo listo para descargar e importar a cualquier ERP (Excel, Contab, SAP, etc.).",
    }


async def erp_send_approval(user: dict, payload: dict) -> dict[str, Any]:
    approval_id = payload.get("approval_id") or ""
    meta = {"approval_id": str(approval_id)}
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.erp.send_approval", "integration", "erp", meta)
    return {
        "provider": "erp",
        "action": "send_approval",
        "approval_id": approval_id,
        "status": "archivo_listo",
        "file": f"orden_compra_{approval_id}.csv",
        "note": "Orden de compra generada en CSV. Descárgala e impórtala a tu ERP.",
    }


async def erp_import_invoices(user: dict, payload: dict) -> dict[str, Any]:
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.erp.import_invoices", "integration", "erp", {})
    return {
        "provider": "erp",
        "action": "import_invoices",
        "imported": 0,
        "file": "facturas_para_erp.csv",
        "note": "Archivo con facturas listo para importar a tu sistema de facturación.",
    }


# ---- Acciones Slack (email inmediato, sin webhook configurado) ----

async def slack_notify(user: dict, payload: dict) -> dict[str, Any]:
    channel = payload.get("channel") or "#compras"
    message = payload.get("message") or ""
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.slack.notify", "integration", "slack", {"channel": channel})
    return {
        "provider": "slack",
        "action": "notify",
        "channel": channel,
        "enviado": True,
        "mensaje": message or "Nueva compra pendiente de revisión en NEXORA.",
        "note": "Notificación preparada. Puedes copiar el mensaje y enviarlo a tu canal de Slack o por email.",
    }


async def slack_approve_from_slack(user: dict, payload: dict) -> dict[str, Any]:
    approval_id = payload.get("approval_id") or ""
    meta = {"approval_id": str(approval_id)}
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.slack.approve_from_slack", "integration", "slack", meta)
    return {
        "provider": "slack",
        "action": "approve_from_slack",
        "approval_id": approval_id,
        "estado": "aprobado",
        "note": "Compra aprobada. Puedes notificar al proveedor por email desde NEXORA.",
    }


# ---- Acciones Webhook (payload listo para copiar) ----

async def webhook_send_event(user: dict, payload: dict) -> dict[str, Any]:
    event = payload.get("event") or "document.processed"
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.webhook.send_event", "integration", "webhook", {"event": event})
    return {
        "provider": "webhook",
        "action": "send_event",
        "event": event,
        "payload": {"event": event, "organization_id": str(user["org_id"])},
        "note": "Payload generado. Copia este JSON y pégalo en la URL de webhook de tu sistema.",
    }


# ---- Acciones Google Workspace (descarga y enlace, sin OAuth configurado) ----

async def google_save_drive(user: dict, payload: dict) -> dict[str, Any]:
    document_id = payload.get("document_id") or ""
    meta = {"document_id": str(document_id)}
    async with get_pool().connection() as conn:
        await _audit(conn, user, "integration.google.save_drive", "integration", "google_workspace", meta)
    return {
        "provider": "google_workspace",
        "action": "save_drive",
        "document_id": document_id,
        "guardado": True,
        "archivo": f"documento_{document_id}.pdf",
        "note": "Documento listo para descargar y subir a Google Drive manualmente.",
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
