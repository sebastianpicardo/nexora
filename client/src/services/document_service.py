from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from src.core.config import settings
from src.core.errors import NexoraError
from src.db import repositories
from src.db.pool import get_pool
from src.parsers.normalization.dates import parse_flexible_date
from src.parsers.pipeline import run_pipeline
from src.services import audit_service, storage_service

logger = logging.getLogger(__name__)


def _json_safe(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


async def _process_claimed_document(doc: dict) -> None:
    org_id = doc["org_id"]
    document_id = doc["id"]

    async with get_pool().connection() as conn:
        org = await repositories.get_organization(conn, org_id)
    if org is None:
        logger.error("Documento %s sin organización", document_id)
        return

    requested_date = parse_flexible_date((doc.get("metadata") or {}).get("requested_document_date"))
    upload_date = requested_date or (doc["created_at"].date() if doc.get("created_at") else date.today())

    try:
        file_bytes = await storage_service.read_document(doc["storage_path"])
        result = await run_pipeline(
            content=file_bytes,
            filename=doc["original_filename"],
            mime_type=doc["mime_type"],
            doc_type_hint=doc["doc_type"],
            org_settings={
                "price_spike_threshold_pct": float(org["price_spike_threshold_pct"]),
                "min_confidence": float(org["min_confidence"]),
                "default_currency": org["default_currency"],
            },
            upload_date=upload_date,
        )
    except Exception as exc:
        logger.exception("Error procesando documento %s", document_id)
        message = str(exc) if isinstance(exc, NexoraError) else f"Error inesperado: {exc}"
        async with get_pool().connection() as conn:
            await repositories.mark_failed(
                conn,
                org_id=org_id,
                document_id=document_id,
                error_message=message,
            )
            await repositories.create_exception(
                conn,
                org_id=org_id,
                document_id=document_id,
                item_id=None,
                type="extraction_failed",
                severity="high",
                reason="No se pudo extraer la información del documento.",
                evidence={
                    "filename": doc["original_filename"],
                    "error": message[:1000],
                },
            )
        return

    try:
        async with get_pool().connection() as conn:
            await repositories.reset_document_children(
                conn,
                org_id=org_id,
                document_id=document_id,
            )

            supplier_id = doc.get("supplier_id")
            extraction = result.extraction
            if not supplier_id and extraction.supplier_name:
                supplier = await repositories.get_or_create_supplier(
                    conn,
                    org_id=org_id,
                    name=extraction.supplier_name,
                    tax_id=extraction.supplier_tax_id,
                )
                supplier_id = supplier["id"]

            inserted: list[tuple[dict, list]] = []
            for item in result.items:
                flags = await audit_service.audit_item(
                    conn,
                    org_id=org_id,
                    document_id=document_id,
                    supplier_id=supplier_id,
                    item=item,
                    price_spike_threshold_pct=float(org["price_spike_threshold_pct"]),
                    lookback_days=settings.price_lookback_days,
                    min_history_samples=settings.min_history_samples,
                )
                review_status = "pending" if flags else "auto_approved"
                row = await repositories.insert_item(
                    conn,
                    org_id=org_id,
                    document_id=document_id,
                    supplier_id=supplier_id,
                    sku=item.sku,
                    original_description=item.original_description,
                    normalized_description=item.normalized_description,
                    original_unit=item.original_unit,
                    base_unit=item.base_unit,
                    unit_factor=item.unit_factor,
                    quantity=item.quantity,
                    package_size=item.package_size,
                    original_unit_price=item.original_unit_price,
                    normalized_unit_price=item.normalized_unit_price,
                    currency=item.currency,
                    price_date=item.price_date,
                    confidence=item.confidence,
                    review_status=review_status,
                    source_page=item.source_page,
                    source_text=item.source_text,
                    metadata=item.metadata,
                )
                inserted.append((row, flags))

            for row, flags in inserted:
                for flag in flags:
                    await repositories.create_exception(
                        conn,
                        org_id=org_id,
                        document_id=document_id,
                        item_id=row["id"],
                        type=flag.type,
                        severity=flag.severity,
                        reason=flag.reason,
                        evidence=flag.evidence,
                    )

            if not result.items:
                await repositories.create_exception(
                    conn,
                    org_id=org_id,
                    document_id=document_id,
                    item_id=None,
                    type="extraction_failed",
                    severity="high",
                    reason="El documento se procesó pero no se extrajeron líneas de producto.",
                    evidence={
                        "filename": doc["original_filename"],
                        "notes": extraction.notes,
                        "confidence": extraction.confidence,
                    },
                )

            metadata = {
                "document_number": extraction.document_number,
                "document_date": extraction.document_date,
                "currency": extraction.currency,
                "subtotal": extraction.subtotal,
                "tax": extraction.tax,
                "total": extraction.total,
                "confidence": extraction.confidence,
                "notes": extraction.notes,
                "supplier_tax_id": extraction.supplier_tax_id,
                "item_count": len(result.items),
            }
            await repositories.mark_processed(
                conn,
                org_id=org_id,
                document_id=document_id,
                supplier_id=supplier_id,
                extraction_provider=result.provider,
                extraction_model=result.model,
                raw_text=result.raw_text,
                metadata={key: _json_safe(value) for key, value in metadata.items()},
            )
    except Exception as exc:
        logger.exception("Error persistiendo documento %s", document_id)
        async with get_pool().connection() as conn:
            await repositories.mark_failed(
                conn,
                org_id=org_id,
                document_id=document_id,
                error_message=f"Error guardando resultados: {exc}",
            )


async def process_document(document_id: UUID | str) -> None:
    async with get_pool().connection() as conn:
        doc = await repositories.claim_document_by_id(conn, document_id)
    if not doc:
        logger.info("Documento %s no está en cola; se omite", document_id)
        return
    await _process_claimed_document(doc)


async def process_pending_once() -> bool:
    async with get_pool().connection() as conn:
        doc = await repositories.claim_next_queued(conn)
    if not doc:
        return False
    logger.info("Procesando documento en cola %s", doc["id"])
    await _process_claimed_document(doc)
    return True
