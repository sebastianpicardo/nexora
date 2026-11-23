from __future__ import annotations

import io
import logging
import re

import pdfplumber

from src.core.errors import ExtractionError
from src.parsers.schemas import ExtractedDocument, ExtractedItem

logger = logging.getLogger(__name__)

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

RUT_RE = re.compile(r"(\d{1,2}\.\d{3}\.\d{3}-[0-9kK])")
RUT_SIMPLE_RE = re.compile(r"(\d{7,8})-([0-9kK])")
PRICE_RE = re.compile(r"[\$]?\s*(\d{1,3}(?:[.\d{3}]*|\d+)(?:[.,]\d{1,2})?)")
DATE_RE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})")
SKU_RE = re.compile(r"\b([A-Z]{2,}[-]?\d{3,})\b")
QUANTITY_RE = re.compile(r"(?:cantidad|qty|qty\.|unidades?|uds?)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
UNIT_RE = re.compile(r"(unidad|und|kg|kg\.|kg|l|lt|litro|m|metro|pcs|pza|pzas)", re.IGNORECASE)


def _clean_money(text: str) -> float | None:
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".")
    try:
        return round(float(text), 4)
    except ValueError:
        return None


def _parse_date(text: str) -> str | None:
    if not text:
        return None
    m = DATE_RE.search(text)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return f"{year:04d}-{month:02d}-{day:02d}"
    except ValueError:
        return None


def _is_non_item_line(line: str) -> bool:
    """Detecta si una línea no es un ítem de producto (ej. encabezados, totales)."""
    non_item_keywords = {
        "total", "subtotal", "neto", "iva", "impuesto", "fecha", "rut",
        "razón", "proveedor", "cliente",
    }
    return any(kw in line.lower() for kw in non_item_keywords)


def _format_table(table: list[list[str | None]]) -> str:
    """Convierte una tabla (lista de filas) a texto plano."""
    rows = []
    for row in table or []:
        cells = [(cell or "").replace("\n", " ").strip() for cell in row]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _extract_supplier(text: str) -> str | None:
    """Extrae RUT y razón social aproximada si aparecen."""
    rut_m = RUT_RE.search(text)
    if rut_m:
        rut = rut_m.group(1)
        # Buscar texto cerca del RUT (razón social probable)
        start = max(0, rut_m.start() - 100)
        end = min(len(text), rut_m.end() + 100)
        context = text[start:end]
        # Limpiar el contexto
        context = re.sub(r"\s+", " ", context).strip()
        return rut, context or None
    return None


def _extract_items(text: str, currency: str) -> list[ExtractedItem]:
    """Extrae ítems usando reglas heurísticas sobre texto de PDF.

    No es un extractor universal: busca líneas con cantidad + precio + total
    y las mapea a ítems. Si no encuentra nada reconocible, devuelve [].
    """
    items: list[ExtractedItem] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        # Saltar líneas que claramente no son ítems
        if _is_non_item_line(line):
            continue

        qty_m = QUANTITY_RE.search(line)
        price_matches = list(PRICE_RE.finditer(line))
        if not qty_m or len(price_matches) < 2:
            continue

        quantity = float(qty_m.group(1).replace(",", "."))
        # Precio unitario y total son los dos primeros precios encontrados
        prices = [float(p.group(1).replace(".", "").replace(",", ".")) for p in price_matches[:2]]
        if len(prices) < 2:
            continue

        unit_price = prices[0]
        line_total = prices[1]

        desc = line[:qty_m.start()].strip()
        if not desc or len(desc) < 3:
            desc = line[qty_m.end():].strip()

        sku_m = SKU_RE.search(desc)
        sku = sku_m.group(1) if sku_m else None

        items.append(
            ExtractedItem(
                description=desc or "Ítem sin descripción",
                sku=sku,
                quantity=quantity,
                unit="unidad",
                unit_price=unit_price,
                line_total=line_total,
                currency=currency,
                confidence=0.85,
                evidence_text=line[:500],
                page=1,
            )
        )

    return items


def extract_pdf_text_document(content: bytes, filename: str) -> tuple[ExtractedDocument, dict] | None:
    """Extrae un PDF de texto de forma determinista (sin IA).

    Intenta extraer encabezado (RUT, fechas, totales) e ítems usando reglas.
    Si no encuentra un formato reconocible, devuelve None para caer al LLM.
    """
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if not pdf.pages:
                return None

            page_texts = []
            table_sections = []

            for index, page in enumerate(pdf.pages):
                text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                page_texts.append(f"## Página {index + 1}\n{text}".strip())

                tables = page.extract_tables()
                for table_index, table in enumerate(tables or [], start=1):
                    formatted = _format_table(table)
                    if formatted:
                        table_sections.append(f"## Tabla {index + 1}.{table_index} (página {index + 1})\n{formatted}")

                if len(text.strip()) < 40:
                    # Página con poco texto, podría ser escaneada
                    pass

            full_text = "\n\n".join(page_texts)
            tables_text = "\n\n".join(table_sections)
            combined = f"{full_text}\n{tables_text}".strip()

            if not combined.strip():
                return None

            # Intentar extraer RUT del emisor
            rut_info = _extract_supplier(combined)

            # Detectar moneda
            currency = "CLP"  # Default para Chile
            if "USD" in combined.upper() or "USD" in combined:
                currency = "USD"
            elif "EUR" in combined.upper():
                currency = "EUR"

            # Extraer ítems
            items = _extract_items(combined, currency)

            if not items:
                return None  # No se pudieron extraer ítems, caer al LLM

            # Extraer totales
            price_matches = list(PRICE_RE.finditer(combined))
            total = None
            subtotal = None
            tax = None
            if len(price_matches) >= 2:
                prices = [float(p.group(1).replace(".", "").replace(",", ".")) for p in price_matches]
                # Asumir que el último precio es el total
                total = prices[-1]
                if len(prices) >= 2:
                    subtotal = prices[-2]

            # Extraer fecha
            date_matches = DATE_RE.findall(combined)
            document_date = None
            if date_matches:
                day, month, year = date_matches[0]
                document_date = f"{year:04d}-{month:02d}-{day:02d}"

            extraction = ExtractedDocument(
                doc_type="invoice",
                supplier_name=None,
                supplier_tax_id=rut_info[0] if rut_info else None,
                document_number=None,
                document_date=document_date,
                currency=currency,
                subtotal=subtotal,
                tax=tax,
                total=total,
                items=items,
                confidence=0.90,
                notes="Importación determinística desde PDF de texto (sin IA)",
                prices_include_tax=False,
                tax_rate=0.19 if currency == "CLP" else 0.0,
            )

            metadata = {
                "importer": "deterministic_pdf",
                "pages_processed": len(pdf.pages),
                "tables_found": len(table_sections),
                "items_extracted": len(items),
                "truncated": False,
            }

            return extraction, metadata

    except ExtractionError:
        raise
    except Exception as exc:
        logger.warning("No se pudo leer el PDF determinísticamente: %s", exc)
        return None