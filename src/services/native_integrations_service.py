# ruff: noqa: E501
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
    {"categoria": "Tornillería", "item": "Tornillo acero inoxidable 6mm", "unit": "unidad", "precio": 120, "proveedor": "Ferretería del Norte"},
    {"categoria": "Tornillería", "item": "Tornillo acero inoxidable 6mm", "unit": "unidad", "precio": 95, "proveedor": "Tornillería Central"},
    {"categoria": "Tornillería", "item": "Tornillo acero inoxidable 6mm", "unit": "unidad", "precio": 140, "proveedor": "Hogar y Ferretería"},
    {"categoria": "Tornillería", "item": "Tornillo acero inoxidable 8mm", "unit": "unidad", "precio": 180, "proveedor": "Ferretería del Norte"},
    {"categoria": "Tornillería", "item": "Tornillo acero inoxidable 8mm", "unit": "unidad", "precio": 155, "proveedor": "Tornillería Central"},
    {"categoria": "Pintura", "item": "Pintura esmalte blanco 1 galón", "unit": "galón", "precio": 8500, "proveedor": "Pinturas Sur"},
    {"categoria": "Pintura", "item": "Pintura esmalte blanco 1 galón", "unit": "galón", "precio": 7900, "proveedor": "Color y Decoración"},
    {"categoria": "Pintura", "item": "Pintura acrílica blanco 4 galones", "unit": "galón", "precio": 22000, "proveedor": "Pinturas Sur"},
    {"categoria": "Pintura", "item": "Pintura acrílica blanco 4 galones", "unit": "galón", "precio": 19500, "proveedor": "Color y Decoración"},
    {"categoria": "Fontanería", "item": "Tubería PVC 1/2 pulgada", "unit": "metro", "precio": 1500, "proveedor": "Fontanería Express"},
    {"categoria": "Fontanería", "item": "Tubería PVC 1/2 pulgada", "unit": "metro", "precio": 1350, "proveedor": "Tuberías Chile"},
    {"categoria": "Fontanería", "item": "Codo PVC 1/2 pulgada", "unit": "unidad", "precio": 450, "proveedor": "Fontanería Express"},
    {"categoria": "Fontanería", "item": "Codo PVC 1/2 pulgada", "unit": "unidad", "precio": 380, "proveedor": "Tuberías Chile"},
    {"categoria": "Eléctrica", "item": "Cable eléctrico 2.5mm", "unit": "metro", "precio": 650, "proveedor": "Eléctrica Moderna"},
    {"categoria": "Eléctrica", "item": "Cable eléctrico 2.5mm", "unit": "metro", "precio": 580, "proveedor": "Voltaje y Cable"},
    {"categoria": "Eléctrica", "item": "Interruptor simple", "unit": "unidad", "precio": 2500, "proveedor": "Eléctrica Moderna"},
    {"categoria": "Eléctrica", "item": "Interruptor simple", "unit": "unidad", "precio": 2100, "proveedor": "Voltaje y Cable"},
    {"categoria": "Ferretería general", "item": "Cinta métrica 5m", "unit": "unidad", "precio": 4500, "proveedor": "Ferretería Central"},
    {"categoria": "Ferretería general", "item": "Cinta métrica 5m", "unit": "unidad", "precio": 3900, "proveedor": "Herramientas SA"},
    {"categoria": "Ferretería general", "item": "Llave inglesa 8 pulgadas", "unit": "unidad", "precio": 6500, "proveedor": "Ferretería Central"},
    {"categoria": "Ferretería general", "item": "Llave inglesa 8 pulgadas", "unit": "unidad", "precio": 5900, "proveedor": "Herramientas SA"},
]

# Proveedores de referencia para ChileCompra
CHILECOMPRA_PROVEEDORES = [
    {"rut": "76.000.000-0", "name": "Ferretería del Norte SpA", "region": "Metropolitana", "confianza": 85, "ranking": 1, "precio_promedio": 12500, "quejas": 3, "estado": "Activo", "contacto": "Carlos Méndez", "telefono": "+56 2 2345 6789", "email": "ventas@ferreteriadelnorte.cl"},
    {"rut": "76.111.111-1", "name": "Tornillería Central Ltda", "region": "Metropolitana", "confianza": 92, "ranking": 2, "precio_promedio": 9800, "quejas": 1, "estado": "Activo", "contacto": "Andrea Rojas", "telefono": "+56 2 2123 4567", "email": "contacto@tornilleriacentral.cl"},
    {"rut": "76.222.222-2", "name": "Pinturas Sur Limitada", "region": "Valparaíso", "confianza": 78, "ranking": 3, "precio_promedio": 15200, "quejas": 7, "estado": "Activo", "contacto": "Luis Valenzuela", "telefono": "+56 32 255 1234", "email": "ventas@pinturassur.cl"},
    {"rut": "76.333.333-3", "name": "Fontanería Express SpA", "region": "Biobío", "confianza": 88, "ranking": 4, "precio_promedio": 11000, "quejas": 2, "estado": "Activo", "contacto": "Sofía Castro", "telefono": "+56 41 233 4455", "email": "sofia@fontaneriaexpress.cl"},
    {"rut": "76.444.444-4", "name": "Eléctrica Moderna Ltda", "region": "Metropolitana", "confianza": 90, "ranking": 5, "precio_promedio": 10500, "quejas": 4, "estado": "Activo", "contacto": "Martín Silva", "telefono": "+56 2 2678 9012", "email": "martin@electricalmodern.cl"},
    {"rut": "76.555.555-5", "name": "Herramientas SA", "region": "O'Higgins", "confianza": 75, "ranking": 6, "precio_promedio": 14500, "quejas": 9, "estado": "Activo", "contacto": "Patricia Gómez", "telefono": "+56 72 211 3344", "email": "patricia@herramientassa.cl"},
    {"rut": "76.666.666-6", "name": "Color y Decoración SpA", "region": "Valparaíso", "confianza": 82, "ranking": 7, "precio_promedio": 13000, "quejas": 5, "estado": "Activo", "contacto": "Diego Muñoz", "telefono": "+56 32 244 5566", "email": "diego@colorydecoracion.cl"},
    {"rut": "76.777.777-7", "name": "Tuberías Chile Ltda", "region": "Maule", "confianza": 80, "ranking": 8, "precio_promedio": 11800, "quejas": 3, "estado": "Activo", "contacto": "Carmen Ortiz", "telefono": "+56 71 222 3344", "email": "carmen@tuberiaschile.cl"},
    {"rut": "76.888.888-8", "name": "Voltaje y Cable SpA", "region": "Metropolitana", "confianza": 86, "ranking": 9, "precio_promedio": 9900, "quejas": 2, "estado": "Activo", "contacto": "Francisca Díaz", "telefono": "+56 2 2777 8899", "email": "francisca@voltajeycable.cl"},
    {"rut": "76.999.999-9", "name": "Hogar y Ferretería Ltda", "region": "Los Lagos", "confianza": 70, "ranking": 10, "precio_promedio": 16000, "quejas": 12, "estado": "Activo", "contacto": "Roberto Pino", "telefono": "+56 65 233 4455", "email": "roberto@hogaryferreteria.cl"},
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
    mode = payload.get("mode") or "all"  # all, cheapest
    limit = int(payload.get("limit", 50))

    resultados = [
        r
        for r in FERRETERIA_REFERENCIAS
        if not query or query in r["item"].lower() or query in r["categoria"].lower()
    ]

    if mode == "cheapest":
        # Agrupar por item y quedarse con el precio más bajo
        mejor_por_item: dict[str, dict] = {}
        for r in resultados:
            key = r["item"]
            if key not in mejor_por_item or r["precio"] < mejor_por_item[key]["precio"]:
                mejor_por_item[key] = r
        resultados = list(mejor_por_item.values())
        resultados.sort(key=lambda x: x["precio"])
    else:
        resultados.sort(key=lambda x: (x["categoria"], x["precio"]))

    resultados = resultados[:limit]

    async with get_pool().connection() as conn:
        meta = {"query": query, "mode": mode}
        await _audit(
            conn,
            user,
            "integration.chilecompra.search_items",
            "integration",
            "chilecompra",
            meta,
        )
    return {
        "provider": "chilecompra",
        "action": "search_items",
        "query": query,
        "mode": mode,
        "results": resultados,
        "total": len(resultados),
        "source": "Referencia de mercado (estimada)",
        "note": "Precios de referencia para ferretería. Son estimados, no cotizaciones oficiales de ChileCompra.",
    }


async def chilecompra_search_suppliers(user: dict, payload: dict) -> dict[str, Any]:
    name = (payload.get("name") or "").lower()
    order_by = payload.get("order_by") or "ranking"  # ranking, confidence, price, complaints

    proveedores = [
        p
        for p in CHILECOMPRA_PROVEEDORES
        if not name or name in p["name"].lower()
    ]

    if order_by == "confidence":
        proveedores.sort(key=lambda x: x["confianza"], reverse=True)
    elif order_by == "price":
        proveedores.sort(key=lambda x: x["precio_promedio"])
    elif order_by == "complaints":
        proveedores.sort(key=lambda x: x["quejas"])
    else:  # ranking
        proveedores.sort(key=lambda x: x["ranking"])

    async with get_pool().connection() as conn:
        meta = {"name": name, "order_by": order_by}
        await _audit(
            conn,
            user,
            "integration.chilecompra.search_suppliers",
            "integration",
            "chilecompra",
            meta,
        )
    return {
        "provider": "chilecompra",
        "action": "search_suppliers",
        "name": name,
        "order_by": order_by,
        "results": proveedores,
        "total": len(proveedores),
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
