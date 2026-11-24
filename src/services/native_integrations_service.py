# ruff: noqa: E501
from __future__ import annotations

import csv
import io
import re
from typing import Any

from psycopg import AsyncConnection

from src.core.logging import get_logger
from src.db import repositories
from src.db.pool import get_pool
from src.services import compra_agil_service

logger = get_logger(__name__)

PROVIDERS = ["chilecompra", "compra_agil", "sii", "erp", "slack", "webhook", "google_workspace"]


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
    """Estado de integraciones nativas. Siempre disponibles, sin configuración técnica."""
    providers: list[dict[str, Any]] = []
    integration_status = {
        "chilecompra": (True, "Radar Compra Ágil (API o carga manual)"),
        "compra_agil": (True, "API configurable o carga CSV"),
        "sii": (True, "Validación local de RUT"),
        "erp": (True, "Exportación CSV real"),
        "slack": (False, "Próximamente"),
        "webhook": (False, "Próximamente"),
        "google_workspace": (False, "Próximamente"),
    }
    for provider in PROVIDERS:
        available, status = integration_status[provider]
        providers.append(
            {
                "provider": provider,
                "available": available,
                "status": status,
                "simulated": False,
                "actions": _default_actions(provider),
            }
        )
    return {"providers": providers}


def _default_actions(provider: str) -> list[dict]:
    base = {
        "chilecompra": [
            {"id": "search_items", "label": "Ver oportunidades Compra Ágil", "icon": "SearchIcon", "primary": True},
            {"id": "search_suppliers", "label": "Buscar proveedores", "icon": "SuppliersIcon"},
            {"id": "import_order", "label": "Importar orden de compra", "icon": "ArrowRightIcon"},
        ],
        "compra_agil": [
            {"id": "opportunities", "label": "Ver oportunidades", "icon": "SearchIcon", "primary": True},
        ],
        "sii": [
            {"id": "validate_rut", "label": "Validar formato de RUT", "icon": "CheckIcon", "primary": True},
        ],
        "erp": [
            {"id": "sync_suppliers", "label": "Exportar proveedores (CSV)", "icon": "SuppliersIcon", "primary": True},
            {"id": "send_approval", "label": "Exportar órdenes (CSV)", "icon": "ArrowRightIcon"},
            {"id": "import_invoices", "label": "Exportar facturas (CSV)", "icon": "DocumentsIcon"},
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
    disabled_actions = {
        "chilecompra": {"search_suppliers", "import_order"},
        "slack": {"notify", "approve_from_slack"},
        "webhook": {"send_event"},
        "google_workspace": {"save_drive", "sso_login"},
    }
    for action in base:
        action["enabled"] = action["id"] not in disabled_actions.get(provider, set())
    return base


def _rut_clean(rut: str) -> str:
    """Normaliza cualquier formato de RUT chileno a cuerpo+DV en mayúsculas, sin separadores."""
    return re.sub(r"[^0-9kK]", "", str(rut or "")).upper()


def _format_rut_chileno(rut: str) -> str:
    """Formatea un RUT en estilo chileno: 12.345.678-9."""
    clean = _rut_clean(rut)
    if len(clean) < 2:
        return str(rut or "").strip()
    cuerpo, dv = clean[:-1], clean[-1]
    cuerpo = cuerpo.lstrip("0") or "0"
    groups: list[str] = []
    while len(cuerpo) > 3:
        groups.insert(0, cuerpo[-3:])
        cuerpo = cuerpo[:-3]
    groups.insert(0, cuerpo)
    return f"{'.'.join(groups)}-{dv}"


def _validar_rut_chileno(rut: str) -> bool:
    """Valida un RUT chileno con su dígito verificador real (módulo 11)."""
    clean = _rut_clean(rut)
    if len(clean) < 2 or len(clean) > 9:
        return False
    cuerpo, dv = clean[:-1], clean[-1]
    if not cuerpo.isdigit() or len(cuerpo) > 8:
        return False
    suma = 0
    multiplo = 2
    for d in reversed(cuerpo):
        suma += int(d) * multiplo
        multiplo = multiplo + 1 if multiplo < 7 else 2
    resto = 11 - (suma % 11)
    dv_esperado = "K" if resto == 10 else "0" if resto == 11 else str(resto)
    return dv == dv_esperado


# ---- Compra Ágil / ChileCompra (datos reales de API o carga manual) ----

async def chilecompra_search_items(user: dict, payload: dict) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    limit = int(payload.get("limit", 50))
    result = await compra_agil_service.list_opportunities(user, search=query or None, limit=limit)
    async with get_pool().connection() as conn:
        await _audit(
            conn,
            user,
            "integration.chilecompra.search_items",
            "integration",
            "chilecompra",
            {"query": query, "mode": result.get("mode")},
        )
    return {
        "provider": "chilecompra",
        "action": "search_items",
        "query": query,
        "results": result["opportunities"],
        "total": len(result["opportunities"]),
        "configured": result["configured"],
        "source": "API Compra Ágil" if result["mode"] == "api" else "Carga manual",
        "note": result["message"],
    }


async def compra_agil_opportunities(user: dict, payload: dict) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    limit = int(payload.get("limit", 50))
    result = await compra_agil_service.list_opportunities(user, search=query or None, limit=limit)
    async with get_pool().connection() as conn:
        await _audit(
            conn,
            user,
            "integration.compra_agil.opportunities",
            "integration",
            "compra_agil",
            {"query": query, "mode": result.get("mode")},
        )
    return {"provider": "compra_agil", "action": "opportunities", **result}


async def chilecompra_search_suppliers(user: dict, payload: dict) -> dict[str, Any]:
    async with get_pool().connection() as conn:
        await _audit(
            conn,
            user,
            "integration.chilecompra.search_suppliers",
            "integration",
            "chilecompra",
            {},
        )
    return {
        "provider": "chilecompra",
        "action": "search_suppliers",
        "results": [],
        "total": 0,
        "note": "La búsqueda de proveedores requiere una fuente oficial configurada. No mostramos datos inventados.",
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
        "status": "no_disponible",
        "note": "La importación de órdenes reales requiere credenciales de ChileCompra. Sube el archivo manualmente.",
    }


# ---- Acciones SII (sin credenciales, validación de formato y referencia) ----

async def sii_validate_rut(user: dict, payload: dict) -> dict[str, Any]:
    rut = str(payload.get("rut") or "").strip()
    normalized = _rut_clean(rut)
    es_valido = _validar_rut_chileno(rut) if rut else False
    rut_formatted = _format_rut_chileno(rut) if normalized else ""
    if not rut:
        estado = "Sin RUT"
    elif es_valido:
        estado = "Formato válido"
    else:
        estado = "Formato inválido"

    supplier: dict[str, Any] | None = None
    stats: dict[str, Any] = {"documents": 0, "items": 0, "spend": 0.0, "last_purchase": None}
    recent_documents: list[dict[str, Any]] = []
    rcv_documents: list[dict[str, Any]] = []

    if normalized:
        async with get_pool().connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, name, email, tax_id, created_at
                    FROM suppliers
                    WHERE org_id = %s
                      AND regexp_replace(upper(coalesce(tax_id, '')), '[^0-9K]', '', 'g') = %s
                    LIMIT 1
                    """,
                    (user["org_id"], normalized),
                )
                supplier = await cur.fetchone()
                if supplier:
                    await cur.execute(
                        """
                        SELECT count(DISTINCT i.document_id) AS documents,
                               count(*) AS items,
                               coalesce(sum(
                                   coalesce(i.normalized_unit_price, 0) * coalesce(i.quantity, 0)
                               ), 0) AS spend,
                               max(i.price_date) AS last_purchase
                        FROM items_history i
                        WHERE i.org_id = %s AND i.supplier_id = %s
                          AND i.review_status <> 'rejected'
                        """,
                        (user["org_id"], supplier["id"]),
                    )
                    row = await cur.fetchone() or {}
                    stats = {
                        "documents": int(row.get("documents") or 0),
                        "items": int(row.get("items") or 0),
                        "spend": float(row.get("spend") or 0),
                        "last_purchase": (
                            str(row["last_purchase"]) if row.get("last_purchase") else None
                        ),
                    }
                    await cur.execute(
                        """
                        SELECT d.original_filename,
                               d.doc_type,
                               d.status,
                               coalesce(d.metadata->>'document_number', '') AS folio,
                               coalesce(
                                   d.metadata->>'document_date',
                                   to_char(d.created_at, 'YYYY-MM-DD')
                               ) AS document_date,
                               coalesce(d.metadata->>'total', '') AS total,
                               d.created_at
                        FROM documents_log d
                        WHERE d.org_id = %s AND d.supplier_id = %s
                        ORDER BY d.created_at DESC
                        LIMIT 5
                        """,
                        (user["org_id"], supplier["id"]),
                    )
                    recent_documents = [dict(r) for r in await cur.fetchall()]

                await cur.execute(
                    """
                    SELECT folio, tipo_doc, supplier_name, period,
                           total_amount, currency
                    FROM rcv_documents
                    WHERE org_id = %s
                      AND regexp_replace(upper(coalesce(rut_emisor, '')), '[^0-9K]', '', 'g') = %s
                    ORDER BY period DESC, folio DESC
                    LIMIT 5
                    """,
                    (user["org_id"], normalized),
                )
                rcv_documents = [
                    {
                        "folio": r["folio"],
                        "tipo_doc": r["tipo_doc"],
                        "supplier_name": r["supplier_name"],
                        "period": str(r["period"]) if r["period"] else None,
                        "total_amount": float(r["total_amount"]) if r["total_amount"] else 0.0,
                        "currency": r["currency"],
                    }
                    for r in await cur.fetchall()
                ]

            await _audit(conn, user, "integration.sii.validate_rut", "integration", "sii", {"rut": rut})

    return {
        "provider": "sii",
        "action": "validate_rut",
        "rut": rut,
        "rut_formatted": rut_formatted,
        "valido": es_valido,
        "estado": estado,
        "supplier": (
            {
                "name": supplier["name"],
                "email": supplier["email"],
                "tax_id": supplier["tax_id"],
                "created_at": str(supplier["created_at"]) if supplier.get("created_at") else None,
            }
            if supplier
            else None
        ),
        "stats": stats,
        "recent_documents": recent_documents,
        "rcv_documents": rcv_documents,
        "giro": None,
        "direccion": None,
        "simulated": False,
        "source": "Validación local del dígito verificador + historial de tu organización",
        "note": (
            "Validamos el dígito verificador y mostramos el historial real registrado en tu "
            "organización para ese RUT. No consultamos datos tributarios en línea del SII."
        ),
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


# ---- Acciones ERP (exportación CSV real, sin configuración por cliente) ----

ERP_EXPORTS = {
    "suppliers": (
        "proveedores_nexora.csv",
        ["Nombre", "RUT", "Email", "Creado"],
        "SELECT name, tax_id, email, created_at FROM suppliers WHERE org_id = %s ORDER BY name",
    ),
    "approvals": (
        "ordenes_compra_nexora.csv",
        ["Título", "Proveedor", "Monto", "Moneda", "Prioridad", "Estado", "Solicitado por", "Creado"],
        """
        SELECT a.title, coalesce(s.name, '') AS supplier_name, a.amount, a.currency,
               a.priority, a.status, coalesce(u.name, '') AS requested_by_name, a.created_at
        FROM purchase_approvals a
        LEFT JOIN suppliers s ON s.id = a.supplier_id
        LEFT JOIN users u ON u.id = a.requested_by
        WHERE a.org_id = %s
        ORDER BY a.created_at DESC
        """,
    ),
    "invoices": (
        "facturas_nexora.csv",
        ["Archivo", "Tipo", "Estado", "Proveedor", "Número", "Fecha", "Neto", "IVA", "Total", "Creado"],
        """
        SELECT d.original_filename, d.doc_type, d.status, coalesce(s.name, '') AS supplier_name,
               coalesce(d.metadata->>'document_number', '') AS document_number,
               coalesce(d.metadata->>'document_date', '') AS document_date,
               coalesce(d.metadata->>'subtotal', '') AS subtotal,
               coalesce(d.metadata->>'tax', '') AS tax,
               coalesce(d.metadata->>'total', '') AS total,
               d.created_at
        FROM documents_log d
        LEFT JOIN suppliers s ON s.id = d.supplier_id
        WHERE d.org_id = %s
        ORDER BY d.created_at DESC
        """,
    ),
}


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        text = f"'{text}"
    return text


async def erp_export_csv(kind: str, user: dict) -> tuple[str, bytes, int]:
    """Genera un CSV real (UTF-8 con BOM) para ERP o contabilidad."""
    export = ERP_EXPORTS.get(kind)
    if export is None:
        raise ValueError("Exportación ERP no soportada.")
    filename, headers, query = export
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (str(user["org_id"]),))
            rows = await cur.fetchall()
        await _audit(conn, user, f"integration.erp.export_{kind}", "integration", "erp", {"rows": len(rows)})

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        values = list(row.values())
        writer.writerow([_csv_value(value) for value in values])
    return filename, buffer.getvalue().encode("utf-8-sig"), len(rows)


async def erp_sync_suppliers(user: dict, payload: dict) -> dict[str, Any]:
    filename, _content, rows = await erp_export_csv("suppliers", user)
    return {
        "provider": "erp",
        "action": "sync_suppliers",
        "rows": rows,
        "filename": filename,
        "download_url": "/api/integrations/native/erp/export/suppliers.csv",
        "note": "CSV real generado con tus proveedores. Descárgalo e impórtalo a tu ERP.",
    }


async def erp_send_approval(user: dict, payload: dict) -> dict[str, Any]:
    filename, _content, rows = await erp_export_csv("approvals", user)
    return {
        "provider": "erp",
        "action": "send_approval",
        "rows": rows,
        "filename": filename,
        "download_url": "/api/integrations/native/erp/export/approvals.csv",
        "note": "CSV real generado con tus órdenes y aprobaciones.",
    }


async def erp_import_invoices(user: dict, payload: dict) -> dict[str, Any]:
    filename, _content, rows = await erp_export_csv("invoices", user)
    return {
        "provider": "erp",
        "action": "import_invoices",
        "rows": rows,
        "filename": filename,
        "download_url": "/api/integrations/native/erp/export/invoices.csv",
        "note": "CSV real generado con tus facturas y documentos.",
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
        "enviado": False,
        "mensaje": message or "Nueva compra pendiente de revisión en NEXORA.",
        "note": "Mensaje preparado localmente. La integración con Slack aún no está habilitada.",
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
        "estado": "no_disponible",
        "note": "La aprobación desde Slack no está habilitada. Usa la bandeja de aprobaciones de NEXORA.",
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
        "guardado": False,
        "archivo": f"documento_{document_id}.pdf",
        "note": "La integración con Google Drive no está habilitada. Descarga el documento y súbelo manualmente.",
    }


ACTION_HANDLERS = {
    "chilecompra": {
        "search_items": chilecompra_search_items,
        "search_suppliers": chilecompra_search_suppliers,
        "import_order": chilecompra_import_order,
    },
    "compra_agil": {
        "opportunities": compra_agil_opportunities,
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
