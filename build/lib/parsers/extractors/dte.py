from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from src.core.errors import ExtractionError
from src.parsers.extractors.base import ExtractedContent
from src.parsers.schemas import ExtractedDocument, ExtractedItem

MAX_DTE_BYTES = 50 * 1024 * 1024

DTE_TYPE_LABELS = {
    "33": "Factura electrónica",
    "34": "Factura no afecta o exenta electrónica",
    "39": "Boleta electrónica",
    "43": "Liquidación factura electrónica",
    "46": "Factura de compra electrónica",
    "52": "Guía de despacho electrónica",
    "56": "Nota de débito electrónica",
    "61": "Nota de crédito electrónica",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first(element: ET.Element, name: str) -> ET.Element | None:
    for child in element.iter():
        if _local(child.tag) == name:
            return child
    return None


def _text(element: ET.Element | None, name: str) -> str | None:
    if element is None:
        return None
    found = _first(element, name)
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _decimal(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace(" ", "")
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(Decimal(cleaned))
    except Exception:
        return None


def _safe_root(content: bytes) -> ET.Element:
    if len(content) > MAX_DTE_BYTES:
        raise ExtractionError("El XML DTE supera el límite de 50 MB.")
    lowered = content[:4096].lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ExtractionError("El XML contiene DTD o entidades no permitidas.")
    try:
        return ET.fromstring(content)
    except ET.ParseError as exc:
        raise ExtractionError(f"No se pudo leer el XML DTE: {exc}") from exc


def extract_xml_text(content: bytes) -> ExtractedContent:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = content.decode(encoding)
            return ExtractedContent(text=text, page_count=1)
        except UnicodeDecodeError:
            continue
    return ExtractedContent(text="", page_count=1)


def extract_dte_document(content: bytes, filename: str) -> tuple[ExtractedDocument, dict] | None:
    """Extrae un DTE chileno de forma determinística, sin IA y sin truncar líneas."""
    root = _safe_root(content)
    dtes = [element for element in root.iter() if _local(element.tag) == "DTE"]
    if not dtes:
        if _local(root.tag) == "Documento":
            dtes = [root]
        else:
            return None

    dte = dtes[0]
    documento = _first(dte, "Documento")
    if documento is None:
        return None

    id_doc = _first(documento, "IdDoc")
    emisor = _first(documento, "Emisor")
    receptor = _first(documento, "Receptor")
    totales = _first(documento, "Totales")

    tipo_dte = _text(id_doc, "TipoDTE") or ""
    folio = _text(id_doc, "Folio")
    fecha = _text(id_doc, "FchEmis")
    currency = _text(id_doc, "TpoMoneda") or _text(totales, "TpoMoneda") or "CLP"

    items: list[ExtractedItem] = []
    for index, detalle in enumerate(
        [child for child in documento if _local(child.tag) == "Detalle"],
        start=1,
    ):
        description = _text(detalle, "NmbItem") or _text(detalle, "DscItem") or "Ítem sin descripción"
        detail = _text(detalle, "DscItem")
        if detail and detail != description:
            description = f"{description} · {detail}"
        quantity = _decimal(_text(detalle, "QtyItem"))
        unit_price = _decimal(_text(detalle, "PrcItem"))
        line_total = _decimal(_text(detalle, "MontoItem"))
        if unit_price is None and line_total is not None and quantity:
            unit_price = round(line_total / quantity, 6)
        items.append(
            ExtractedItem(
                line_number=index,
                sku=_text(detalle, "CodItem") or _text(detalle, "VlrCodigo"),
                description=description,
                quantity=quantity,
                unit=_text(detalle, "UnmdItem") or "unidad",
                unit_price=unit_price,
                line_total=line_total,
                currency=currency,
                confidence=1.0,
                evidence_text=f"{_text(detalle, 'NmbItem') or description} · {line_total or ''}".strip(" ·"),
                page=1,
            )
        )

    tipo_label = DTE_TYPE_LABELS.get(tipo_dte, "Documento tributario electrónico")
    notes = f"{tipo_label} (DTE {tipo_dte or 'sin tipo'}) importado sin IA."
    if len(dtes) > 1:
        notes += f" El archivo contiene {len(dtes)} DTE; se procesó el primero."

    extraction = ExtractedDocument(
        doc_type="invoice",
        supplier_name=_text(emisor, "RznSoc") or _text(emisor, "RznSocLarga"),
        supplier_tax_id=_text(emisor, "RUTEmisor"),
        document_number=folio,
        document_date=fecha,
        currency=currency,
        subtotal=_decimal(_text(totales, "MntNeto")),
        tax=_decimal(_text(totales, "IVA")),
        total=_decimal(_text(totales, "MntTotal")),
        items=items,
        confidence=1.0,
        notes=notes,
        prices_include_tax=False,
        tax_rate=(_decimal(_text(totales, "TasaIVA")) or 19.0) / 100,
    )
    metadata = {
        "importer": "deterministic_dte",
        "dte": True,
        "tipo_dte": tipo_dte,
        "tipo_dte_label": tipo_label,
        "dte_count": len(dtes),
        "receptor_tax_id": _text(receptor, "RUTRecep"),
        "receptor_name": _text(receptor, "RznSocRecep"),
        "filename": filename,
        "truncated": False,
    }
    return extraction, metadata
