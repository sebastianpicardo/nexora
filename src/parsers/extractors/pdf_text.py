from __future__ import annotations

import io
import logging
import re
import unicodedata

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
UNIT_RE = re.compile(
    r"(unidad|und|unid|saco|docena|gal[oó]n|galon|kg|m2|m3|metro|m|litro|lt|l|par|pza|rollo|bolsa|caja|c/u)",
    re.IGNORECASE,
)
UNIT_TOKENS = (
    r"(?:und|unidad|unid|un|saco|sacos|docena|docenas|gal[oó]n|galon|galones|gal|kg|kgs|"
    r"m2|m3|mt|m|lt|l|litro|litros|par|pares|pza|pzas|pieza|piezas|rollo|rollos|"
    r"bolsa|bolsas|caja|cajas|c/u)"
)
ITEM_LINE_RE = re.compile(
    rf"^(?P<prefix>.*?)\s+(?P<qty>\d+(?:[.,]\d+)?)\s+(?P<unit>{UNIT_TOKENS})\s+"
    rf"\$?\s*(?P<price>\d[\d.,]*)\s+\$?\s*(?P<total>\d[\d.,]*)\s*$",
    re.IGNORECASE,
)


def _clean_money(text: str) -> float | None:
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".")
    try:
        return round(float(text), 4)
    except ValueError:
        return None


def _parse_number(text: str | None) -> float | None:
    """Convierte montos/cantidades es-CL (miles con '.' y decimales con ',') a float."""
    if text is None:
        return None
    value = re.sub(r"[^\d.,-]", "", str(text))
    if not value:
        return None
    has_dot = "." in value
    has_comma = "," in value
    if has_dot and has_comma:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif has_comma:
        if re.fullmatch(r"\d{1,3}(,\d{3})+", value):
            value = value.replace(",", "")
        else:
            value = value.replace(",", ".")
    elif has_dot and re.fullmatch(r"\d{1,3}(\.\d{3})+", value):
        value = value.replace(".", "")
    try:
        return round(float(value), 4)
    except ValueError:
        return None


def _normalize_cell(text: str | None) -> str:
    raw = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", raw.lower()).split())


TABLE_COLUMN_SYNONYMS: dict[str, set[str]] = {
    "sku": {"sku", "codigo", "cod", "codigo producto", "cod producto"},
    "description": {"descripcion", "producto", "detalle", "nombre", "nombre producto"},
    "quantity": {"cantidad", "qty", "cant", "unidades"},
    "unit": {"unidad", "unidad medida", "um", "und"},
    "unit_price": {
        "precio unitario",
        "precio unit",
        "precio unitivo",
        "valor unitario",
        "precio unitario clp",
        "valor unit",
        "precio",
    },
    "total": {"total", "total clp", "valor total", "subtotal", "subtotal clp"},
}


def _match_table_field(normalized: str) -> str | None:
    for field, synonyms in TABLE_COLUMN_SYNONYMS.items():
        if normalized in synonyms:
            return field
    # Tolerancia a encabezados variables y errores tipográficos frecuentes
    # ("Precio Unitivo (CLP)", "P. Unitario", "Valor Unit. CLP", etc.).
    if "precio" in normalized and ("unit" in normalized or "uni" in normalized):
        return "unit_price"
    if "total" in normalized or "importe" in normalized or "monto" in normalized:
        return "total"
    if "cantidad" in normalized or normalized in {"qty", "cant", "unidades"}:
        return "quantity"
    if (
        "descrip" in normalized
        or "producto" in normalized
        or "detalle" in normalized
        or "glosa" in normalized
    ):
        return "description"
    if normalized.startswith("sku") or "codigo" in normalized or normalized.startswith("cod"):
        return "sku"
    if "unidad" in normalized or normalized in {"um", "und", "un", "unid"}:
        return "unit"
    return None


def _map_table_header(row: list[str | None]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(row):
        normalized = _normalize_cell(cell)
        if not normalized:
            continue
        field = _match_table_field(normalized)
        if field is not None and field not in mapping:
            mapping[field] = index
    return mapping


def _items_from_table(
    table: list[list[str | None]],
    page_number: int,
    currency: str,
) -> list[ExtractedItem]:
    """Extrae ítems de una tabla estructurada detectada por pdfplumber."""
    if not table:
        return []
    header_index = None
    mapping: dict[str, int] = {}
    for index, row in enumerate(table[:4]):
        candidate = _map_table_header(row)
        if "description" in candidate or "sku" in candidate:
            header_index = index
            mapping = candidate
            break
    if header_index is None or "description" not in mapping:
        return []

    def cell(row: list[str | None], field: str) -> str | None:
        position = mapping.get(field)
        if position is None or position >= len(row):
            return None
        value = row[position]
        return str(value).strip() if value is not None else None

    items: list[ExtractedItem] = []
    for row in table[header_index + 1 :]:
        description = cell(row, "description")
        if not description:
            continue
        unit_price = _parse_number(cell(row, "unit_price"))
        line_total = _parse_number(cell(row, "total"))
        quantity = _parse_number(cell(row, "quantity"))
        if unit_price is None and line_total is None:
            continue
        if quantity is None:
            quantity = 1.0
        if unit_price is None and line_total is not None and quantity:
            unit_price = round(line_total / quantity, 4)
        if line_total is None and unit_price is not None:
            line_total = round(unit_price * quantity, 4)
        items.append(
            ExtractedItem(
                description=description,
                sku=cell(row, "sku"),
                quantity=quantity,
                unit=(cell(row, "unit") or "unidad").lower(),
                unit_price=unit_price,
                line_total=line_total,
                currency=currency,
                confidence=0.92,
                evidence_text=" | ".join(str(value or "").strip() for value in row)[:500],
                page=page_number,
            )
        )
    return items


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


def _extract_supplier(text: str) -> tuple[str, str | None] | None:
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

    Acepta filas tabulares con columnas variables y separadores ``|`` o espacios:
    ``[n] [SKU] descripción cantidad unidad precio_unitario total``.
    No es un extractor universal; si no reconoce filas devuelve ``[]`` para que
    ``extraction_policy`` active el fallback de IA.
    """
    items: list[ExtractedItem] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        clean = " ".join(line.replace("|", " ").replace("\t", " ").split())
        if not clean:
            continue
        # Saltar encabezados, totales y filas de documentos RCV (folio + RUT + fecha).
        if _is_non_item_line(clean):
            continue
        if RUT_RE.search(clean) and DATE_RE.search(clean):
            continue

        match = ITEM_LINE_RE.match(clean)
        if match is None:
            continue

        quantity = _parse_number(match.group("qty"))
        unit_price = _parse_number(match.group("price"))
        line_total = _parse_number(match.group("total"))
        if quantity is None or unit_price is None or line_total is None:
            continue
        if line_total <= 0 and unit_price <= 0:
            continue

        prefix = match.group("prefix").strip()
        sku_m = SKU_RE.search(prefix)
        sku = sku_m.group(1) if sku_m else None
        description = prefix
        if sku_m:
            description = description[: sku_m.start()] + " " + description[sku_m.end() :]
        description = re.sub(r"^\s*\d+[.)]?\s+", "", description).strip(" |-")
        description = " ".join(description.split())
        if not description or len(description) < 2:
            continue

        items.append(
            ExtractedItem(
                description=description,
                sku=sku,
                quantity=quantity,
                unit=match.group("unit").lower(),
                unit_price=unit_price,
                line_total=line_total,
                currency=currency,
                confidence=0.88,
                evidence_text=clean[:500],
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
            raw_tables: list[tuple[int, list[list[str | None]]]] = []

            for index, page in enumerate(pdf.pages):
                text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                page_texts.append(f"## Página {index + 1}\n{text}".strip())

                tables = page.extract_tables()
                for table_index, table in enumerate(tables or [], start=1):
                    formatted = _format_table(table)
                    if formatted:
                        table_sections.append(f"## Tabla {index + 1}.{table_index} (página {index + 1})\n{formatted}")
                    raw_tables.append((index + 1, table))

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

            # Extraer ítems: primero tablas estructuradas y luego heurística de líneas.
            items: list[ExtractedItem] = []
            for page_number, table in raw_tables:
                items.extend(_items_from_table(table, page_number, currency))
            if not items:
                items = _extract_items(combined, currency)

            if not items:
                return None  # No se pudieron extraer ítems, caer al LLM

            # Extraer totales: primero una línea explícita "Total", luego la suma de líneas.
            total = None
            tax = None
            for line in combined.splitlines():
                normalized_line = line.strip()
                if not normalized_line or "precio unitario" in normalized_line.lower():
                    continue
                if re.search(r"\btotal\b", normalized_line, re.IGNORECASE):
                    matches = list(PRICE_RE.finditer(normalized_line))
                    if matches:
                        candidate = _parse_number(matches[-1].group(1))
                        if candidate is not None and candidate > 0:
                            total = candidate
                            break
            if total is None:
                total = round(sum(float(item.line_total or 0) for item in items), 2)
            subtotal = total

            # Extraer fecha
            date_matches = DATE_RE.findall(combined)
            document_date = None
            if date_matches:
                day, month, year = date_matches[0]
                document_date = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

            supplier_name = None
            supplier_match = re.search(
                r"proveedor\s*:\s*([^\n]+?)(?:\s+rut|\n|$)", combined, re.IGNORECASE
            )
            if supplier_match:
                supplier_name = supplier_match.group(1).strip() or None

            extraction = ExtractedDocument(
                doc_type="invoice",
                supplier_name=supplier_name,
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