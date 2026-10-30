from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.core.errors import ExtractionError
from src.parsers.extractors.base import ExtractedContent
from src.parsers.extractors.images import extract_image
from src.parsers.extractors.pdf import extract_pdf
from src.parsers.extractors.tabular import extract_tabular
from src.parsers.llm.base import LLMProvider
from src.parsers.llm.factory import get_llm_provider
from src.parsers.normalization.currency import normalize_currency, parse_decimal, quantize_money
from src.parsers.normalization.dates import parse_flexible_date
from src.parsers.normalization.descriptions import clean_sku, normalize_description
from src.parsers.normalization.pricing import validate_line_total
from src.parsers.normalization.units import normalize_unit
from src.parsers.schemas import AuditFlag, ExtractedDocument, NormalizationResult, NormalizedItem

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
TABULAR_EXTENSIONS = {".xlsx", ".xls", ".csv", ".txt"}


def extract_local(content: bytes, filename: str, mime_type: str | None = None) -> ExtractedContent:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" or mime_type == "application/pdf":
        return extract_pdf(content)
    if suffix in TABULAR_EXTENSIONS:
        return extract_tabular(content, filename)
    if suffix in IMAGE_EXTENSIONS:
        return extract_image(content)
    raise ExtractionError(f"Formato no soportado: {suffix or mime_type or 'desconocido'}")


def _flags_for_item(
    *,
    confidence: float,
    min_confidence: float,
    unit_requires_review: bool,
    unit_reason: str | None,
    unit_evidence: dict,
    unit_price: Decimal | None,
    normalized_price: Decimal | None,
    line_total: Decimal | None,
    quantity: Decimal | None,
) -> list[AuditFlag]:
    flags: list[AuditFlag] = []

    if confidence < min_confidence:
        flags.append(
            AuditFlag(
                type="low_confidence",
                severity="medium" if confidence >= 0.6 else "high",
                reason=f"Confianza de extracción {confidence:.2f} por debajo del mínimo {min_confidence:.2f}.",
                evidence={"confidence": confidence, "min_confidence": min_confidence},
            )
        )

    if unit_requires_review:
        flags.append(
            AuditFlag(
                type="unit_mismatch",
                severity="high",
                reason=unit_reason or "No se pudo normalizar la unidad del ítem.",
                evidence=unit_evidence,
            )
        )

    if unit_price is None or normalized_price is None:
        flags.append(
            AuditFlag(
                type="missing_price",
                severity="high",
                reason="El ítem no tiene un precio unitario utilizable.",
                evidence={"unit_price": str(unit_price) if unit_price is not None else None},
            )
        )

    total_ok, total_delta = validate_line_total(unit_price, quantity, line_total)
    if not total_ok:
        flags.append(
            AuditFlag(
                type="price_mismatch",
                severity="medium",
                reason=(
                    f"El total de la línea no coincide con cantidad × precio unitario (diferencia {total_delta:.2f}%)."
                ),
                evidence={
                    "unit_price": str(unit_price) if unit_price is not None else None,
                    "quantity": str(quantity) if quantity is not None else None,
                    "line_total": str(line_total) if line_total is not None else None,
                    "difference_pct": total_delta,
                },
            )
        )

    return flags


async def run_pipeline(
    *,
    content: bytes,
    filename: str,
    mime_type: str | None,
    doc_type_hint: str | None,
    org_settings: dict,
    upload_date: date | None = None,
    provider: LLMProvider | None = None,
) -> NormalizationResult:
    extracted = await asyncio.to_thread(extract_local, content, filename, mime_type)
    llm = provider or get_llm_provider()
    extraction: ExtractedDocument = await llm.extract_document(
        extracted,
        filename=filename,
        doc_type_hint=doc_type_hint,
    )

    default_currency = str(org_settings.get("default_currency") or "CLP")
    raw_min_confidence = org_settings.get("min_confidence")
    min_confidence = 0.75 if raw_min_confidence is None else float(raw_min_confidence)
    price_date_fallback = upload_date or date.today()
    document_date = parse_flexible_date(extraction.document_date) or price_date_fallback
    document_confidence = extraction.confidence if extraction.confidence is not None else 1.0

    normalized_items: list[NormalizedItem] = []
    for item in extraction.items:
        original_description = " ".join(item.description.split())
        normalized_description = normalize_description(original_description)
        sku = clean_sku(item.sku)

        unit = normalize_unit(item.unit, original_description, item.package_size)
        quantity = parse_decimal(item.quantity)
        unit_price = parse_decimal(item.unit_price)
        line_total = parse_decimal(item.line_total)
        package_size = parse_decimal(item.package_size)

        if unit_price is None and line_total is not None and quantity is not None and quantity > 0:
            unit_price = quantize_money(line_total / quantity)

        normalized_price = None
        if unit_price is not None and unit.factor > 0:
            normalized_price = quantize_money(unit_price / unit.factor, places=6)

        confidence = max(0.0, min(1.0, min(item.confidence, document_confidence)))
        currency = normalize_currency(item.currency or extraction.currency, default_currency)
        price_date = parse_flexible_date(item.price_date) or document_date

        flags = _flags_for_item(
            confidence=confidence,
            min_confidence=min_confidence,
            unit_requires_review=unit.requires_review,
            unit_reason=unit.reason,
            unit_evidence={
                "original_unit": item.unit,
                "base_unit": unit.base_unit,
                "factor": str(unit.factor),
                "reason": unit.reason,
            },
            unit_price=unit_price,
            normalized_price=normalized_price,
            line_total=line_total,
            quantity=quantity,
        )

        normalized_items.append(
            NormalizedItem(
                sku=sku,
                original_description=original_description,
                normalized_description=normalized_description,
                original_unit=item.unit,
                base_unit=unit.base_unit,
                unit_factor=unit.factor,
                quantity=quantity,
                package_size=package_size,
                original_unit_price=quantize_money(unit_price, places=4),
                normalized_unit_price=normalized_price,
                currency=currency,
                price_date=price_date,
                confidence=confidence,
                source_page=item.page,
                source_text=item.evidence_text,
                flags=flags,
                metadata={
                    "line_number": item.line_number,
                    "line_total": str(line_total) if line_total is not None else None,
                    "unit_dimension": unit.dimension,
                    "unit_reason": unit.reason,
                    "extraction_confidence": extraction.confidence,
                },
            )
        )

    return NormalizationResult(
        extraction=extraction,
        items=normalized_items,
        raw_text=extracted.combined_text[:200_000],
        provider=llm.name,
        model=llm.model,
    )
