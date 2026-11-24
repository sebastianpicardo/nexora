"""Orquestador del pipeline automático de NEXORA.

Ejecuta, en una sola corrida y sin intervención del usuario, todas las
capacidades de análisis disponibles sobre un documento nuevo o ya cargado.

Principio deterministic-first: cada etapa intenta resolverse con código
interno (parsers tabulares/DTE/PDF, normalización, reglas de precio, catálogo
y RCV). La IA solo se invoca como fallback dentro de ``run_pipeline`` cuando el
documento no puede resolverse internamente y la organización autorizó su uso.
"""

from __future__ import annotations

import hashlib
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation

from src.core.logging import get_logger
from src.db import repositories
from src.db.pool import get_pool
from src.services import (
    compra_agil_service,
    document_service,
    leak_audit_service,
    margin_guardian_service,
    native_integrations_service,
    rcv_service,
    savings_report_service,
    storage_service,
)

logger = get_logger(__name__)

STATUS_PENDING = "pendiente"
STATUS_RUNNING = "en_proceso"
STATUS_COMPLETED = "completado"
STATUS_NO_DATA = "sin_datos"
STATUS_FALLBACK = "fallback_ia"
STATUS_SKIPPED = "omitido_con_motivo"

SOURCE_INTERNAL = "internal_process"
SOURCE_AI = "ai_fallback"

STAGE_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("extraction", "Extracción y normalización"),
    ("document_impact", "Impacto en este documento"),
    ("audit", "Fugas y sobrecostos"),
    ("margin", "Guardián de margen"),
    ("sii_rcv", "Validación SII / RCV"),
    ("negotiation", "Comparador, negociación y ahorro"),
    ("compra_agil", "Compra Ágil y oportunidades"),
)

STAGE_SCOPES: dict[str, str] = {
    "extraction": "Documento actual",
    "document_impact": "Documento actual",
    "audit": "Historial de compras · 90 días",
    "margin": "Catálogo de precios",
    "sii_rcv": "Documento + período SII / RCV",
    "negotiation": "Historial de compras · 90 días",
    "compra_agil": "Documento + catálogo",
}

ALLOWED_DOC_TYPES = {"quote", "invoice", "price_list"}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _initial_stages() -> list[dict]:
    return [
        {
            "id": stage_id,
            "label": label,
            "scope": STAGE_SCOPES.get(stage_id, ""),
            "status": STATUS_PENDING,
            "source": None,
            "detail": "",
            "metrics": {},
            "duration_ms": 0,
        }
        for stage_id, label in STAGE_DEFINITIONS
    ]


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _agile_stage_detail(
    opportunities: list[dict], catalog_matches: list[dict], mode: str | None
) -> str:
    """Redacta el resultado de Compra Ágil en español natural (singular/plural)."""
    opp = len(opportunities)
    matches = len(catalog_matches)
    if not opp and not matches:
        return "Sin oportunidades ni coincidencias para los ítems del documento."
    parts: list[str] = []
    if opp:
        parts.append(_plural(opp, "oportunidad", "oportunidades"))
    if matches:
        parts.append(_plural(matches, "coincidencia de catálogo", "coincidencias de catálogo"))
    body = " y ".join(parts)
    suffix = f" ({mode})" if mode else ""
    return f"{body}{suffix}."


def _set_stage(stages: list[dict], stage_id: str, **fields: Any) -> dict:
    for stage in stages:
        if stage.get("id") == stage_id:
            stage.update(fields)
            return stage
    return {}


async def _save_run(
    org_id: UUID | str,
    run_id: UUID | str,
    *,
    stages: list[dict] | None = None,
    summary: dict | None = None,
    results: dict | None = None,
    status: str | None = None,
    ai_used: bool | None = None,
    document_id: UUID | str | None = None,
    filename: str | None = None,
    error_message: str | None = None,
    clear_error: bool = False,
) -> dict | None:
    async with get_pool().connection() as conn:
        return await repositories.update_automation_run(
            conn,
            org_id=org_id,
            run_id=run_id,
            stages=_json_safe(stages) if stages is not None else None,
            summary=_json_safe(summary) if summary is not None else None,
            results=_json_safe(results) if results is not None else None,
            status=status,
            ai_used=ai_used,
            document_id=document_id,
            filename=filename,
            error_message=error_message,
            clear_error=clear_error,
        )


async def prepare_run(
    user: dict,
    *,
    document_id: UUID | str | None = None,
    trigger_source: str,
    filename: str | None = None,
) -> dict:
    run_id = uuid4()
    async with get_pool().connection() as conn:
        return await repositories.create_automation_run(
            conn,
            run_id=run_id,
            org_id=user["org_id"],
            document_id=document_id,
            status="running",
            trigger_source=trigger_source,
            filename=filename,
            requested_by=user.get("id"),
            stages=_initial_stages(),
            summary={},
            results={},
            ai_used=False,
        )


async def get_run(user: dict, run_id: UUID | str) -> dict | None:
    async with get_pool().connection() as conn:
        return await repositories.get_automation_run(conn, user["org_id"], run_id)


async def list_runs(user: dict, limit: int = 10) -> list[dict]:
    async with get_pool().connection() as conn:
        return await repositories.list_automation_runs(conn, user["org_id"], limit=limit)


async def _get_document(user: dict, document_id: UUID | str) -> dict | None:
    async with get_pool().connection() as conn:
        return await repositories.get_document(conn, user["org_id"], document_id)


async def _count_document_items(user: dict, document_id: UUID | str) -> list[dict]:
    async with get_pool().connection() as conn:
        result = await repositories.list_items(
            conn,
            user["org_id"],
            document_id=document_id,
            page=1,
            page_size=5000,
        )
    return result["items"]


async def _ensure_processed(
    user: dict,
    doc: dict,
    *,
    provider: object | None = None,
) -> None:
    status = doc.get("status")
    if status == "processed" or status == "processing":
        return
    if status in {"failed", "temporary_error"}:
        await document_service.reprocess_failed_document(doc["id"], provider=provider)
        return
    await document_service.process_document(doc["id"], provider=provider)


async def _create_or_reuse_document(
    user: dict,
    *,
    content: bytes,
    filename: str,
    mime_type: str | None,
    doc_type: str,
    document_date: str | None,
    provider: object | None,
) -> tuple[dict | None, bool]:
    """Registra el archivo o reutiliza el documento duplicado de la organización."""
    doc_type = doc_type if doc_type in ALLOWED_DOC_TYPES else "quote"
    file_hash = hashlib.sha256(content).hexdigest()

    async with get_pool().connection() as conn:
        duplicate = await repositories.get_document_by_hash(conn, user["org_id"], file_hash)
    if duplicate is not None:
        await _ensure_processed(user, duplicate, provider=provider)
        return await _get_document(user, duplicate["id"]), True

    async with get_pool().connection() as conn:
        billing = await repositories.get_billing(conn, user["org_id"])
    if billing["usage"]["exceeded"]:
        raise ValueError(
            "Alcanzaste el límite de documentos de tu plan. Actualiza tu suscripción para continuar."
        )

    resolved_mime = storage_service.resolve_upload_mime(filename, None, mime_type)
    document_id = uuid4()
    storage_path = await storage_service.save_document(
        org_id=user["org_id"],
        document_id=document_id,
        filename=filename,
        content=content,
        mime_type=resolved_mime,
    )

    metadata: dict[str, Any] = {}
    if document_date:
        try:
            metadata["requested_document_date"] = date.fromisoformat(document_date).isoformat()
        except ValueError:
            metadata["requested_document_date"] = document_date

    try:
        async with get_pool().connection() as conn:
            await repositories.create_document(
                conn,
                document_id=document_id,
                org_id=user["org_id"],
                supplier_id=None,
                uploaded_by=user.get("id"),
                original_filename=filename,
                storage_path=storage_path,
                file_hash=file_hash,
                mime_type=resolved_mime,
                file_size_bytes=len(content),
                doc_type=doc_type,
                metadata=metadata,
            )
    except UniqueViolation:
        async with get_pool().connection() as conn:
            duplicate = await repositories.get_document_by_hash(conn, user["org_id"], file_hash)
        if duplicate is None:
            raise
        await _ensure_processed(user, duplicate, provider=provider)
        return await _get_document(user, duplicate["id"]), True

    await document_service.process_document(document_id, provider=provider)
    return await _get_document(user, document_id), False


def _extraction_status(doc: dict | None, items: list[dict]) -> tuple[str, str, bool]:
    if doc is None:
        return STATUS_SKIPPED, "No se pudo registrar ni recuperar el documento.", False
    status = doc.get("status")
    metadata = doc.get("metadata") or {}
    ai_used = bool(metadata.get("ai_used"))
    fallback = metadata.get("fallback_reason")
    if status != "processed":
        reason = doc.get("error_message") or f"Documento en estado {status}."
        if fallback:
            reason = f"{reason} Motivo del fallback: {fallback}."
        return STATUS_SKIPPED, reason, ai_used
    if not items:
        detail = "El documento se procesó pero no generó ítems."
        if fallback:
            detail = f"{detail} Fallback: {fallback}."
        return STATUS_NO_DATA, detail, ai_used
    if ai_used:
        return STATUS_FALLBACK, f"Extracción resuelta con IA ({fallback or 'campos incompletos'}).", True
    return STATUS_COMPLETED, "Extracción determinista sin consumir tokens de IA.", False


def _compact_document(doc: dict | None) -> dict:
    if doc is None:
        return {}
    metadata = doc.get("metadata") or {}
    return {
        "id": str(doc["id"]),
        "filename": doc.get("original_filename"),
        "status": doc.get("status"),
        "doc_type": doc.get("doc_type"),
        "supplier_name": doc.get("supplier_name") or metadata.get("supplier_name"),
        "supplier_tax_id": metadata.get("supplier_tax_id"),
        "document_number": metadata.get("document_number"),
        "document_date": metadata.get("document_date"),
        "currency": metadata.get("currency"),
        "total": metadata.get("total"),
        "item_count": metadata.get("item_count"),
        "extraction_provider": doc.get("extraction_provider"),
        "extraction_model": doc.get("extraction_model"),
        "resolution_source": metadata.get("resolution_source")
        or metadata.get("extraction_source"),
        "ai_used": bool(metadata.get("ai_used")),
        "fallback_reason": metadata.get("fallback_reason"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
    }


async def _validate_supplier_rut(user: dict, doc: dict | None) -> dict:
    if doc is None:
        return {"rut": None, "valid": None, "source": "sin documento"}
    metadata = doc.get("metadata") or {}
    rut = metadata.get("supplier_tax_id")
    if not rut and doc.get("supplier_id"):
        async with get_pool().connection() as conn:
            supplier = await repositories.get_supplier(conn, user["org_id"], doc["supplier_id"])
        rut = (supplier or {}).get("tax_id")
    if not rut:
        return {"rut": None, "valid": None, "source": "sin RUT en el documento"}
    result = await native_integrations_service.sii_validate_rut(user, {"rut": rut})
    return {
        "rut": result.get("rut"),
        "valid": bool(result.get("valido")),
        "status": result.get("estado"),
        "source": result.get("source"),
    }


def _norm_key(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


async def _build_document_impact(
    user: dict,
    document: dict | None,
    items: list[dict],
) -> dict:
    """Impacto exclusivo del documento actual contra compras previas del mismo producto.

    Compara cada ítem del documento contra el mejor precio de los últimos 90 días
    (excluyendo este mismo documento) usando solo datos internos, sin IA.
    """
    metadata = (document or {}).get("metadata") or {}
    doc_currency = (
        metadata.get("currency")
        or (items[0].get("currency") if items else None)
        or user.get("default_currency")
        or "CLP"
    )
    doc_currency = str(doc_currency).strip().upper()

    if document is None or not items:
        return {
            "document_id": str(document["id"]) if document else None,
            "currency": doc_currency,
            "window_days": 90,
            "items": len(items),
            "items_with_history": 0,
            "items_without_history": len(items),
            "items_other_currency": 0,
            "spend": 0.0,
            "potential_savings": 0.0,
            "overcost": 0.0,
            "overcost_items": 0,
            "top_items": [],
            "note": "Sin ítems del documento para comparar.",
        }

    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT i.sku, i.normalized_description, i.base_unit,
                       upper(i.currency) AS currency,
                       i.normalized_unit_price AS price,
                       coalesce(s.name, 'Proveedor sin nombre') AS supplier_name
                FROM items_history i
                LEFT JOIN suppliers s ON s.id = i.supplier_id
                WHERE i.org_id = %s
                  AND i.document_id <> %s
                  AND i.price_date >= current_date - make_interval(days => 90)
                  AND i.normalized_unit_price > 0
                  AND i.review_status <> 'rejected'
                """,
                (str(user["org_id"]), str(document["id"])),
            )
            history = await cur.fetchall()

    best: dict[tuple[str, str, str], dict] = {}
    for row in history:
        row_currency = str(row["currency"] or "").upper()
        unit = _norm_key(row["base_unit"])
        for key_value in {_norm_key(row["sku"]), _norm_key(row["normalized_description"])}:
            if not key_value:
                continue
            key = (row_currency, key_value, unit)
            current = best.get(key)
            if current is None or float(row["price"]) < float(current["price"]):
                best[key] = row

    spend = 0.0
    potential = 0.0
    with_history = 0
    without_history = 0
    other_currency = 0
    comparisons: list[dict] = []

    for item in items:
        price = float(item.get("normalized_unit_price") or 0)
        quantity = float(item.get("quantity") or 0)
        item_currency = str(item.get("currency") or doc_currency).upper()
        if item_currency != doc_currency:
            other_currency += 1
            continue
        spend += price * quantity
        unit = _norm_key(item.get("base_unit"))
        reference = None
        sku_key = _norm_key(item.get("sku"))
        if sku_key:
            reference = best.get((item_currency, sku_key, unit))
        if reference is None:
            reference = best.get(
                (item_currency, _norm_key(item.get("normalized_description")), unit)
            )
        if reference is None:
            without_history += 1
            continue
        with_history += 1
        best_price = float(reference["price"])
        if best_price <= 0 or price <= best_price:
            continue
        gap_pct = (price - best_price) / best_price * 100
        if gap_pct < 2.0:
            continue
        savings = (price - best_price) * quantity
        potential += savings
        comparisons.append(
            {
                "sku": item.get("sku"),
                "product": item.get("original_description"),
                "unit": item.get("base_unit"),
                "supplier": item.get("supplier_name"),
                "current_price": round(price, 2),
                "best_price": round(best_price, 2),
                "best_supplier": reference["supplier_name"],
                "gap_pct": round(gap_pct, 1),
                "quantity": round(quantity, 2),
                "savings": round(savings, 2),
                "currency": item_currency,
            }
        )

    comparisons.sort(key=lambda row: row["savings"], reverse=True)
    return {
        "document_id": str(document["id"]),
        "currency": doc_currency,
        "window_days": 90,
        "items": len(items),
        "items_with_history": with_history,
        "items_without_history": without_history,
        "items_other_currency": other_currency,
        "spend": round(spend, 2),
        "potential_savings": round(potential, 2),
        "overcost": round(potential, 2),
        "overcost_items": len(comparisons),
        "top_items": comparisons[:6],
        "note": (
            "Comparación contra el mejor precio de los últimos 90 días, "
            "excluyendo este mismo documento."
        ),
    }


async def execute_run(
    user: dict,
    run_id: UUID | str,
    *,
    document_id: UUID | str | None = None,
    content: bytes | None = None,
    filename: str | None = None,
    mime_type: str | None = None,
    doc_type: str = "quote",
    document_date: str | None = None,
    provider: object | None = None,
) -> dict | None:
    """Ejecuta todas las etapas del pipeline y persiste el avance en cada una."""
    run = await get_run(user, run_id)
    if run is None:
        return None

    stages: list[dict] = run.get("stages") or _initial_stages()
    org_id = user["org_id"]
    ai_used = False
    document: dict | None = None
    items: list[dict] = []

    # ── Etapa 1: extracción y normalización ────────────────────────────────
    stage_started = time.perf_counter()
    _set_stage(stages, "extraction", status=STATUS_RUNNING, detail="Procesando documento…")
    await _save_run(org_id, run_id, stages=stages)
    reused = False
    try:
        if content is not None:
            document, reused = await _create_or_reuse_document(
                user,
                content=content,
                filename=filename or "documento",
                mime_type=mime_type,
                doc_type=doc_type,
                document_date=document_date,
                provider=provider,
            )
        elif document_id is not None:
            document = await _get_document(user, document_id)
            if document is None:
                raise LookupError("Documento no encontrado en tu organización.")
            reused = document.get("status") == "processed"
            await _ensure_processed(user, document, provider=provider)
            document = await _get_document(user, document_id)
        else:
            raise ValueError("Debes subir un archivo o seleccionar un documento existente.")

        if document is not None:
            await _save_run(
                org_id,
                run_id,
                document_id=document["id"],
                filename=document.get("original_filename") or filename,
            )
            items = await _count_document_items(user, document["id"])
            metadata = document.get("metadata") or {}
            ai_used = bool(metadata.get("ai_used"))
        status, detail, ai_used = _extraction_status(document, items)
        if reused and status == STATUS_COMPLETED:
            detail = f"{detail} Documento existente reutilizado sin reprocesar."
        _set_stage(
            stages,
            "extraction",
            status=status,
            source=SOURCE_AI if ai_used else SOURCE_INTERNAL,
            detail=detail,
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
            metrics={
                "items": len(items),
                "document_status": (document or {}).get("status"),
                "supplier": (document or {}).get("supplier_name")
                or ((document or {}).get("metadata") or {}).get("supplier_name"),
                "currency": ((document or {}).get("metadata") or {}).get("currency")
                or user.get("default_currency"),
                "total": ((document or {}).get("metadata") or {}).get("total"),
                "resolution_source": ((document or {}).get("metadata") or {}).get(
                    "resolution_source"
                )
                or ((document or {}).get("metadata") or {}).get("extraction_source"),
                "fallback_reason": ((document or {}).get("metadata") or {}).get("fallback_reason"),
                "reused": reused,
                "ai_used": ai_used,
            },
        )
    except Exception as exc:  # etapa resiliente: no aborta el resto
        logger.warning("Automatización: falló la extracción: %s", str(exc)[:300])
        _set_stage(
            stages,
            "extraction",
            status=STATUS_SKIPPED,
            source=SOURCE_INTERNAL,
            detail=f"No se pudo extraer el documento: {str(exc)[:280]}",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
            metrics={"items": 0},
        )
    await _save_run(org_id, run_id, stages=stages, ai_used=ai_used)

    currency = (user.get("default_currency") or "CLP").strip().upper()
    document_info = _compact_document(document)
    document_info["item_count"] = len(items)
    results: dict[str, Any] = {"document": document_info, "items_preview": []}
    summary: dict[str, Any] = {
        "currency": currency,
        "ai_used": ai_used,
        "document_items": len(items),
        "document_supplier": document_info.get("supplier_name"),
        "document_tax_id": document_info.get("supplier_tax_id"),
        "document_number": document_info.get("document_number"),
    }

    if items:
        results["items_preview"] = [
            {
                "sku": item.get("sku"),
                "description": item.get("original_description"),
                "unit": item.get("base_unit"),
                "quantity": float(item["quantity"]) if item.get("quantity") is not None else None,
                "normalized_unit_price": (
                    float(item["normalized_unit_price"])
                    if item.get("normalized_unit_price") is not None
                    else None
                ),
                "currency": item.get("currency"),
                "review_status": item.get("review_status"),
            }
            for item in items[:100]
        ]

    # ── Etapa 2: impacto exclusivo del documento actual ────────────────────
    stage_started = time.perf_counter()
    _set_stage(
        stages,
        "document_impact",
        status=STATUS_RUNNING,
        detail="Comparando este documento con tus compras anteriores…",
    )
    await _save_run(org_id, run_id, stages=stages)
    try:
        impact = await _build_document_impact(user, document, items)
        if impact["items"] == 0:
            impact_status = STATUS_NO_DATA
            impact_detail = "El documento no tiene ítems para comparar."
        elif impact["items_with_history"] == 0:
            impact_status = STATUS_NO_DATA
            impact_detail = (
                "No hay compras anteriores de estos productos para comparar. "
                "Sube otra cotización o factura del mismo proveedor/producto."
            )
        elif impact["overcost_items"] == 0:
            impact_status = STATUS_COMPLETED
            impact_detail = (
                f"Se compararon {impact['items_with_history']} productos y no hay sobrecostos "
                "frente al mejor precio de los últimos 90 días."
            )
        else:
            impact_status = STATUS_COMPLETED
            impact_detail = (
                f"{impact['overcost_items']} productos de este documento están sobre el mejor "
                f"precio de los últimos 90 días. Sobrecosto estimado: "
                f"${impact['potential_savings']:,.0f} {impact['currency']}."
            )
        _set_stage(
            stages,
            "document_impact",
            status=impact_status,
            source=SOURCE_INTERNAL,
            detail=impact_detail,
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
            metrics={
                "items": impact["items"],
                "items_with_history": impact["items_with_history"],
                "items_without_history": impact["items_without_history"],
                "spend": impact["spend"],
                "potential_savings": impact["potential_savings"],
                "overcost_items": impact["overcost_items"],
            },
        )
        results["document_impact"] = impact
        summary["document_spend"] = impact["spend"]
        summary["document_potential_savings"] = impact["potential_savings"]
        summary["document_overcost"] = impact["overcost"]
        summary["document_items_with_history"] = impact["items_with_history"]
        summary["document_items_without_history"] = impact["items_without_history"]
        summary["document_overcost_items"] = impact["overcost_items"]
    except Exception as exc:
        logger.warning("Automatización: falló el impacto del documento: %s", str(exc)[:300])
        _set_stage(
            stages,
            "document_impact",
            status=STATUS_SKIPPED,
            source=SOURCE_INTERNAL,
            detail=f"No se pudo comparar este documento: {str(exc)[:280]}",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
        )
    await _save_run(org_id, run_id, stages=stages)

    # ── Etapa 3: fugas y sobrecostos (historial) ───────────────────────────
    stage_started = time.perf_counter()
    _set_stage(stages, "audit", status=STATUS_RUNNING, detail="Cruzando precios y detectando fugas…")
    await _save_run(org_id, run_id, stages=stages)
    try:
        audit = await leak_audit_service.build_audit(user, days=90, currency=currency)
        audit_summary = audit.get("summary") or {}
        has_data = bool((audit.get("coverage") or {}).get("items"))
        _set_stage(
            stages,
            "audit",
            status=STATUS_COMPLETED if has_data else STATUS_NO_DATA,
            source=SOURCE_INTERNAL,
            detail=(
                f"{audit_summary.get('findings_total', 0)} hallazgos · "
                f"fuga estimada {audit_summary.get('leakage_pct', 0)}%."
                if has_data
                else "Sin compras auditables en los últimos 90 días."
            ),
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
            metrics={
                "potential_savings": audit_summary.get("potential_savings", 0),
                "overcost": audit_summary.get("price_overpay", 0),
                "margin_bleed": audit_summary.get("margin_bleed", 0),
                "findings": audit_summary.get("findings_total", 0),
            },
        )
        results["audit"] = audit
        summary["potential_savings"] = audit_summary.get("potential_savings", 0)
        summary["overcost"] = audit_summary.get("price_overpay", 0)
        summary["margin_bleed"] = audit_summary.get("margin_bleed", 0)
        summary["findings"] = audit_summary.get("findings_total", 0)
        summary["historical_documents"] = (audit.get("coverage") or {}).get("documents", 0)
        summary["historical_items"] = (audit.get("coverage") or {}).get("items", 0)
        summary["documents"] = summary["historical_documents"]
    except Exception as exc:
        logger.warning("Automatización: falló la auditoría: %s", str(exc)[:300])
        _set_stage(
            stages,
            "audit",
            status=STATUS_SKIPPED,
            source=SOURCE_INTERNAL,
            detail=f"No se pudo completar la auditoría: {str(exc)[:280]}",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
        )
    await _save_run(org_id, run_id, stages=stages)

    # ── Etapa 3: guardián de margen ────────────────────────────────────────
    stage_started = time.perf_counter()
    _set_stage(stages, "margin", status=STATUS_RUNNING, detail="Evaluando márgenes del catálogo…")
    await _save_run(org_id, run_id, stages=stages)
    try:
        margin = await margin_guardian_service.build_margin_guardian(
            user, target_margin=15, min_margin=8
        )
        margin_summary = margin.get("summary") or {}
        has_data = int(margin_summary.get("items_total") or 0) > 0
        _set_stage(
            stages,
            "margin",
            status=STATUS_COMPLETED if has_data else STATUS_NO_DATA,
            source=SOURCE_INTERNAL,
            detail=(
                f"{margin_summary.get('at_risk', 0)} de {margin_summary.get('items_total', 0)} "
                "productos requieren atención de margen."
                if has_data
                else "Catálogo sin productos activos para evaluar."
            ),
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
            metrics={
                "items": margin_summary.get("items_total", 0),
                "at_risk": margin_summary.get("at_risk", 0),
                "below_cost": margin_summary.get("below_cost", 0),
                "recovery": margin_summary.get("recovery_per_unit", 0),
            },
        )
        results["margin"] = margin
        summary["margin_at_risk"] = margin_summary.get("at_risk", 0)
        summary["margin_recovery"] = margin_summary.get("recovery_per_unit", 0)
        summary["margin_below_cost"] = margin_summary.get("below_cost", 0)
    except Exception as exc:
        logger.warning("Automatización: falló el guardián de margen: %s", str(exc)[:300])
        _set_stage(
            stages,
            "margin",
            status=STATUS_SKIPPED,
            source=SOURCE_INTERNAL,
            detail=f"No se pudo evaluar márgenes: {str(exc)[:280]}",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
        )
    await _save_run(org_id, run_id, stages=stages)

    # ── Etapa 4: validación SII / RCV ──────────────────────────────────────
    stage_started = time.perf_counter()
    _set_stage(stages, "sii_rcv", status=STATUS_RUNNING, detail="Validando RUT y completitud RCV…")
    await _save_run(org_id, run_id, stages=stages)
    try:
        rcv = await rcv_service.rcv_completeness(user)
        rut = await _validate_supplier_rut(user, document)
        has_data = int(rcv.get("total_documents") or 0) > 0 or rut.get("valid") is not None
        detail_parts = []
        if rut.get("rut"):
            detail_parts.append(
                f"RUT {rut['rut']} {'válido' if rut.get('valid') else 'inválido'}"
            )
        if rcv.get("total_documents"):
            detail_parts.append(rcv.get("message") or "")
        _set_stage(
            stages,
            "sii_rcv",
            status=STATUS_COMPLETED if has_data else STATUS_NO_DATA,
            source=SOURCE_INTERNAL,
            detail=" · ".join(part for part in detail_parts if part)
            or "Sin RUT ni registros RCV para validar.",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
            metrics={
                "rut": rut.get("rut"),
                "rut_valid": rut.get("valid"),
                "rcv_period": rcv.get("period"),
                "rcv_total": rcv.get("total_documents", 0),
                "rcv_missing": rcv.get("missing", 0),
                "completeness_pct": rcv.get("completeness_pct", 0),
            },
        )
        results["sii_rcv"] = {"rut": rut, "rcv": rcv}
        summary["sii_rcv"] = {
            "rut": rut.get("rut"),
            "rut_valid": rut.get("valid"),
            "period": rcv.get("period"),
            "total_documents": rcv.get("total_documents", 0),
            "missing": rcv.get("missing", 0),
            "completeness_pct": rcv.get("completeness_pct", 0),
            "message": rcv.get("message"),
        }
    except Exception as exc:
        logger.warning("Automatización: falló la validación SII/RCV: %s", str(exc)[:300])
        _set_stage(
            stages,
            "sii_rcv",
            status=STATUS_SKIPPED,
            source=SOURCE_INTERNAL,
            detail=f"No se pudo validar SII/RCV: {str(exc)[:280]}",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
        )
    await _save_run(org_id, run_id, stages=stages)

    # ── Etapa 5: comparador, negociación y ahorro ──────────────────────────
    stage_started = time.perf_counter()
    _set_stage(
        stages,
        "negotiation",
        status=STATUS_RUNNING,
        detail="Consolidando alternativas y objetivo de negociación…",
    )
    await _save_run(org_id, run_id, stages=stages)
    try:
        comparator = await leak_audit_service.build_comparator(user, limit=15)
        negotiation = await leak_audit_service.build_negotiation(user, limit=15)
        savings = await savings_report_service.build_verified_report(user)
        comparisons = int(comparator.get("total") or 0)
        suppliers = len(negotiation.get("suppliers") or [])
        verified = int(savings.get("count") or 0)
        has_data = comparisons > 0 or suppliers > 0 or verified > 0
        _set_stage(
            stages,
            "negotiation",
            status=STATUS_COMPLETED if has_data else STATUS_NO_DATA,
            source=SOURCE_INTERNAL,
            detail=(
                f"{comparisons} comparaciones · {suppliers} proveedores a negociar · "
                f"{verified} ahorros verificados."
                if has_data
                else "Sin historial suficiente para comparar o negociar."
            ),
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
            metrics={
                "comparisons": comparisons,
                "negotiation_savings": negotiation.get("total_estimated_savings", 0),
                "verified_savings": savings.get("total_amount", 0),
            },
        )
        results["comparator"] = comparator
        results["negotiation"] = negotiation
        results["savings"] = savings
        summary["negotiation_savings"] = negotiation.get("total_estimated_savings", 0)
        summary["verified_savings"] = savings.get("total_amount", 0)
        summary["comparisons"] = comparisons
    except Exception as exc:
        logger.warning("Automatización: falló la negociación: %s", str(exc)[:300])
        _set_stage(
            stages,
            "negotiation",
            status=STATUS_SKIPPED,
            source=SOURCE_INTERNAL,
            detail=f"No se pudo consolidar la negociación: {str(exc)[:280]}",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
        )
    await _save_run(org_id, run_id, stages=stages)

    # ── Etapa 6: Compra Ágil / oportunidades ───────────────────────────────
    stage_started = time.perf_counter()
    _set_stage(
        stages,
        "compra_agil",
        status=STATUS_RUNNING,
        detail="Buscando referencias y oportunidades relacionadas…",
    )
    await _save_run(org_id, run_id, stages=stages)
    try:
        search = None
        if items:
            candidate = items[0].get("original_description") or items[0].get("sku")
            search = str(candidate)[:80] if candidate else None
        radar = await compra_agil_service.list_opportunities(user, search=search, limit=10)
        opportunities = radar.get("opportunities") or []
        catalog_matches = radar.get("catalog_matches") or []
        has_data = bool(opportunities or catalog_matches)
        total_budget = sum(float(row.get("budget_clp") or 0) for row in opportunities)
        _set_stage(
            stages,
            "compra_agil",
            status=STATUS_COMPLETED if has_data else STATUS_NO_DATA,
            source=SOURCE_INTERNAL,
            detail=_agile_stage_detail(opportunities, catalog_matches, radar.get("mode")),
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
            metrics={
                "opportunities": len(opportunities),
                "catalog_matches": len(catalog_matches),
                "mode": radar.get("mode"),
                "search": search,
                "budget_clp": round(total_budget, 2),
            },
        )
        results["compra_agil"] = radar
        summary["agile_opportunities"] = len(opportunities)
        summary["agile_catalog_matches"] = len(catalog_matches)
        summary["agile_budget"] = round(total_budget, 2)
    except Exception as exc:
        logger.warning("Automatización: falló Compra Ágil: %s", str(exc)[:300])
        _set_stage(
            stages,
            "compra_agil",
            status=STATUS_SKIPPED,
            source=SOURCE_INTERNAL,
            detail=f"No se pudo consultar oportunidades: {str(exc)[:280]}",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
        )
    await _save_run(org_id, run_id, stages=stages)

    # ── Cierre: KPIs y origen interno vs IA ────────────────────────────────
    fallback_stages = [stage["id"] for stage in stages if stage.get("status") == STATUS_FALLBACK]
    completed_stages = [
        stage["id"] for stage in stages if stage.get("status") == STATUS_COMPLETED
    ]
    summary.update(
        {
            "currency": currency,
            "ai_used": ai_used,
            "internal_stages": len(completed_stages),
            "fallback_stages": len(fallback_stages),
            "fallback_stage_ids": fallback_stages,
            "stages_total": len(stages),
            "items": len(items),
            "document_status": (document or {}).get("status"),
        }
    )
    await _save_run(
        org_id,
        run_id,
        stages=stages,
        summary=summary,
        results=results,
        status="completed",
        ai_used=ai_used,
        clear_error=True,
    )
    return await get_run(user, run_id)


async def run_now(
    user: dict,
    *,
    document_id: UUID | str | None = None,
    content: bytes | None = None,
    filename: str | None = None,
    mime_type: str | None = None,
    doc_type: str = "quote",
    document_date: str | None = None,
    provider: object | None = None,
) -> dict | None:
    """Crea y ejecuta una corrida de forma secuencial (útil para tests)."""
    run = await prepare_run(
        user,
        document_id=document_id,
        trigger_source="upload" if content is not None else "existing",
        filename=filename,
    )
    return await execute_run(
        user,
        run["id"],
        document_id=document_id,
        content=content,
        filename=filename,
        mime_type=mime_type,
        doc_type=doc_type,
        document_date=document_date,
        provider=provider,
    )
