from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.core.errors import ExtractionError
from src.parsers.extractors.base import ExtractedContent
from src.parsers.extractors.dte import extract_dte_document, extract_xml_text
from src.parsers.extractors.images import extract_image
from src.parsers.extractors.pdf_text import extract_pdf_text_document
from src.parsers.extractors.tabular import extract_tabular, extract_tabular_document
from src.parsers.llm.factory import extract_with_fallback
from src.parsers.normalization.currency import normalize_currency, parse_decimal, quantize_money
from src.parsers.normalization.dates import parse_flexible_date
from src.parsers.normalization.descriptions import clean_sku, normalize_description
from src.parsers.normalization.pricing import validate_line_total
from src.parsers.normalization.units import normalize_unit
from src.parsers.schemas import AuditFlag, ExtractionResult, NormalizationResult, NormalizedItem
from src.services.extraction_policy import RESOLUTION_AI_FALLBACK, RESOLUTION_INTERNAL, extraction_policy

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
TABULAR_EXTENSIONS = {".xlsx", ".xls", ".csv", ".txt"}
XML_EXTENSIONS = {".xml", ".dte"}


def extract_local(content: bytes, filename: str, mime_type: str | None = None) -> ExtractedContent:
    """Extrae contenido de un archivo de forma determinista (sin IA).

    Orden de preferencia:
    1. PDF de texto (pdfplumber) - extrae texto y tablas directamente
    2. XML/DTE - parseo XML nativo
    3. Excel/CSV - importación tabular determinística
    4. Imágenes - extrae texto vía OCR si está disponible

    Nota: PDF escaneado (sin texto) retorna contenido vacío con imágenes
    para que el pipeline decida si enviar a IA como fallback.
    """
    suffix = Path(filename).suffix.lower()
    if suffix in XML_EXTENSIONS or mime_type in {"application/xml", "text/xml"}:
        return extract_xml_text(content)
    if suffix == ".pdf" or mime_type == "application/pdf":
        return extract_pdf_text_document(content)
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
                    f"El total de la línea no coincide con cantidad × precio unitario "
                    f"(diferencia {total_delta:.2f}%)."
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


async def _run_deterministic(
    *,
    content: bytes,
    filename: str,
    mime_type: str | None,
) -> ExtractionResult:
    """Ejecuta la extracción determinística según el tipo de archivo."""
    suffix = Path(filename).suffix.lower()

    if suffix in TABULAR_EXTENSIONS:
        result = await asyncio.to_thread(extract_tabular_document, content, filename)
        if result is not None:
            extraction, table_meta = result
            if extraction.items:
                return ExtractionResult(
                    result=extraction,
                    source=RESOLUTION_INTERNAL,
                    fallback_reason=None,
                    ai_used=False,
                    attempts=[
                        {
                            "stage": "deterministic_tabular",
                            "success": True,
                            "reason": None,
                            "detail": f"{len(extraction.items)} ítems extraídos",
                        }
                    ],
                )

    if suffix in XML_EXTENSIONS or mime_type in {"application/xml", "text/xml"}:
        result = await asyncio.to_thread(extract_dte_document, content, filename)
        if result is not None:
            extraction, table_meta = result
            return ExtractionResult(
                result=extraction,
                source=RESOLUTION_INTERNAL,
                fallback_reason=None,
                ai_used=False,
                attempts=[
                    {
                        "stage": "deterministic_dte",
                        "success": True,
                        "reason": None,
                        "detail": None,
                    }
                ],
            )

    if suffix == ".pdf" or mime_type == "application/pdf":
        result = await asyncio.to_thread(extract_pdf_text_document, content)
        if result is not None:
            extraction, metadata = result
            if extraction.items:
                return ExtractionResult(
                    result=extraction,
                    source=RESOLUTION_INTERNAL,
                    fallback_reason=None,
                    ai_used=False,
                    attempts=[
                        {
                            "stage": "deterministic_pdf",
                            "success": True,
                            "reason": None,
                            "detail": f"{len(extraction.items)} ítems extraídos",
                        }
                    ],
                )

    # No se pudo extraer nada determinísticamente
    return ExtractionResult(
        result=None,
        source=RESOLUTION_INTERNAL,
        fallback_reason="no_items",
        ai_used=False,
        attempts=[
            {
                "stage": "deterministic",
                "success": False,
                "reason": "no_items",
                "detail": f"No se reconoció formato tabular en {filename}",
            }
        ],
    )


async def _run_ai(
    *,
    content: bytes,
    filename: str,
    mime_type: str | None,
    org_settings: dict,
    doc_type_hint: str | None,
    provider: Any | None,
) -> ExtractionResult:
    """Ejecuta la extracción vía LLM como fallback."""
    extracted = await asyncio.to_thread(extract_local, content, filename, mime_type)

    if not bool(org_settings.get("ai_data_consent", True)):
        raise ExtractionError("La organización no autorizó el envío de documentos a proveedores de IA.")
    if not bool(org_settings.get("ai_images_enabled", True)):
        extracted.images = []
    raw_max_chars = org_settings.get("ai_text_max_chars")
    if raw_max_chars is not None:
        max_chars = max(1000, min(int(raw_max_chars), 200_000))
        combined = extracted.combined_text
        if len(combined) > max_chars:
            extracted.text = combined[:max_chars]
            extracted.tables_text = ""

    if provider is not None:
        extraction = await provider.extract_document(
            extracted,
            filename=filename,
            doc_type_hint=doc_type_hint,
        )
        provider_name = provider.name
        usage = getattr(provider, "last_usage", None)
        return ExtractionResult(
            result=extraction,
            source=RESOLUTION_AI_FALLBACK,
            fallback_reason=None,
            ai_used=True,
            attempts=[
                {
                    "stage": f"ai:{provider_name}",
                    "success": True,
                    "reason": None,
                    "detail": provider_name,
                    "model": getattr(provider, "model", provider_name),
                    "usage": usage,
                }
            ],
        )
    else:
        result_extraction, provider_name, usage = await extract_with_fallback(
            extracted,
            filename=filename,
            doc_type_hint=doc_type_hint,
        )
        return ExtractionResult(
            result=result_extraction,
            source=RESOLUTION_AI_FALLBACK,
            fallback_reason=None,
            ai_used=True,
            attempts=[
                {
                    "stage": f"ai:{provider_name}",
                    "success": True,
                    "reason": None,
                    "detail": provider_name,
                    "model": provider_name,
                    "usage": usage,
                }
            ],
        )


async def run_pipeline(
    *,
    content: bytes,
    filename: str,
    mime_type: str | None,
    doc_type_hint: str | None,
    org_settings: dict,
    upload_date: date | None = None,
    provider: Any = None,
) -> NormalizationResult:
    """Ejecuta el pipeline de extracción con patrón deterministic-first.

    Flujo:
    1. Extrae contenido de forma determinista (PDF de texto, Excel/CSV, XML/DTE).
    2. Si el resultado es usable (tiene ítems con precios), lo usa directamente.
    3. Si el resultado está vacío o incompleto, recurre a IA como fallback.
    4. Registra el origen (internal_process / ai_fallback) y la razón del fallback.
    """
    policy = extraction_policy()

    result = await policy.run(
        internal=lambda: _run_deterministic(
            content=content,
            filename=filename,
            mime_type=mime_type,
        ),
        ai=lambda: _run_ai(
            content=content,
            filename=filename,
            mime_type=mime_type,
            org_settings=org_settings,
            doc_type_hint=doc_type_hint,
            provider=provider,
        ),
        min_confidence=0.0,
        required_fields=["items"],
        validate=lambda doc: len(doc.items) > 0 if doc else False,
    )

    if result.result is None:
        # No se pudo extraer nada ni por vía determinista ni por IA
        raise ExtractionError(
            "No se pudo extraer contenido del documento. "
            f"Razón del fallback: {result.fallback_reason or 'desconocida'}"
        )

    extraction = result.result
    if result.ai_used:
        ai_attempt = next(
            (attempt for attempt in result.attempts if str(attempt.get("stage", "")).startswith("ai:")),
            {},
        )
        provider_name = ai_attempt.get("detail") or "llm"
        model_name = ai_attempt.get("model") or provider_name
        usage = ai_attempt.get("usage")
    else:
        deterministic_stage = next(
            (
                str(attempt.get("stage", ""))
                for attempt in result.attempts
                if str(attempt.get("stage", "")).startswith("deterministic_")
            ),
            "",
        )
        provider_name = deterministic_stage.removeprefix("deterministic_") or "deterministic"
        model_name = "deterministic"
        usage = None

    default_currency = str(org_settings.get("default_currency") or "CLP")
    raw_min_confidence = org_settings.get("min_confidence")
    min_confidence = 0.75 if raw_min_confidence is None else float(raw_min_confidence)
    price_date_fallback = upload_date or date.today()
    document_date = parse_flexible_date(extraction.document_date) or price_date_fallback
    document_confidence = extraction.confidence if extraction.confidence is not None else 1.0

    table_meta: dict | None = None
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

        confidence = max(0.0, min(1.0, min(item.confidence, document_confidence)))
        currency = normalize_currency(item.currency or extraction.currency, default_currency)

        tax_rate = extraction.tax_rate
        if tax_rate is None:
            tax_rate = 0.19 if currency.upper() == "CLP" else 0.0
        prices_include_tax = bool(extraction.prices_include_tax)
        net_unit_price = unit_price
        if prices_include_tax and unit_price is not None and tax_rate > 0:
            net_unit_price = quantize_money(unit_price / (1 + Decimal(str(tax_rate))), places=6)

        normalized_price = None
        if net_unit_price is not None and unit.factor > 0:
            normalized_price = quantize_money(net_unit_price / unit.factor, places=6)

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
                    "price_condition": "gross" if prices_include_tax else "net",
                    "tax_rate": float(tax_rate) if tax_rate else 0.0,
                    "gross_unit_price": (
                        str(quantize_money(unit_price, places=4)) if unit_price is not None else None
                    ),
                    "net_unit_price": (
                        str(quantize_money(net_unit_price, places=4))
                        if net_unit_price is not None else None
                    ),
                    # Campos de trazabilidad deterministic-first
                    "extraction_source": result.source,
                    "fallback_reason": result.fallback_reason,
                    "ai_used": result.ai_used,
                    "extraction_attempts": result.attempts,
                },
            )
        )

    warnings = list((table_meta or {}).get("warnings") or []) if table_meta else []
    if table_meta and table_meta.get("truncated"):
        warnings.append(
            "El archivo se importó parcialmente por límite de filas. "
            "Revisa la nota del documento antes de confiar en los totales."
        )
    evidence_lines = [item.evidence_text for item in extraction.items if item.evidence_text]
    raw_text = "\n".join(evidence_lines)[:200_000] if evidence_lines else (extraction.notes or "")

    return NormalizationResult(
        extraction=extraction,
        items=normalized_items,
        raw_text=raw_text,
        provider=provider_name,
        model=model_name,
        usage=usage,
        warnings=warnings,
        # Nuevos campos de trazabilidad deterministic-first
        extraction_source=result.source,
        fallback_reason=result.fallback_reason,
        ai_used=result.ai_used,
    )