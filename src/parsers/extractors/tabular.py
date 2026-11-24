from __future__ import annotations

import csv
import io
import logging
import re
import unicodedata
from pathlib import Path

import pandas as pd

from src.core.errors import ExtractionError
from src.parsers.extractors.base import ExtractedContent
from src.parsers.schemas import ExtractedDocument, ExtractedItem

logger = logging.getLogger(__name__)

MAX_ROWS_PER_SHEET = 5000
MAX_SHEETS = 20
MAX_IMPORT_ROWS = 20_000
MAX_IMPORT_SHEETS = 30

COLUMN_SYNONYMS: dict[str, set[str]] = {
    "sku": {"sku", "codigo", "cod", "codigo producto", "cod producto", "referencia", "ref", "articulo", "id"},
    "description": {"descripcion", "detalle", "producto", "nombre", "item", "glosa", "desc", "nombre producto"},
    "unit": {"unidad", "um", "unidad medida", "unidad de medida", "medida", "formato", "envase"},
    "quantity": {"cantidad", "qty", "cant", "unidades", "cantidad vendida", "cantidad comprada"},
    "unit_price": {
        "precio unitario",
        "precio unit",
        "p unitario",
        "valor unitario",
        "unitario",
        "precio neto",
        "neto unitario",
        "costo unitario",
        "precio",
        "costo",
    },
    "line_total": {
        "total linea",
        "total de linea",
        "total",
        "monto",
        "valor total",
        "importe",
        "precio total",
        "subtotal linea",
    },
    "currency": {"moneda", "currency"},
    "price_date": {"fecha", "fecha documento", "fecha emision", "fecha compra"},
    "package_size": {"contenido", "cantidad por caja", "pack", "medida envase", "tamano"},
    "supplier_name": {"proveedor", "razon social", "nombre proveedor"},
    "supplier_tax_id": {"rut", "rut proveedor", "rut emisor"},
    "document_number": {"folio", "numero", "numero documento", "nro", "factura", "boleta"},
}

RCV_DOCUMENT_SYNONYMS: dict[str, set[str]] = {
    "folio": {"folio", "n folio", "numero", "nro", "numero documento", "num", "numero de documento"},
    "tipo_doc": {"tipo doc", "tipo documento", "tipo dte", "tipo de documento", "tdoc", "tipo"},
    "fecha": {"fecha", "fecha emision", "fecha documento", "fecha de emision", "fecha docto"},
    "rut": {"rut", "rut proveedor", "rut emisor", "rut del proveedor", "rut de proveedor"},
    "supplier": {"razon social", "proveedor", "nombre proveedor", "nombre", "razon social proveedor"},
    "net": {"neto", "monto neto", "monto neto afecto", "neto afecto", "monto neto de la compra"},
    "tax": {"iva", "monto iva", "iva recuperable"},
    "total": {"total", "monto total", "monto", "total documento", "total de la compra"},
}


def _normalize_header(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.strip().lower().replace("_", " ").replace("-", " ").split())


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _parse_money(value: object) -> float | None:
    text = _clean_cell(value)
    if not text:
        return None
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def _map_header_row(row: list[object]) -> dict[str, int] | None:
    """Mapea una fila de encabezado combinando sinónimos de ítems y de documentos RCV."""
    mapping: dict[str, int] = {}
    for index, cell in enumerate(row):
        normalized = _normalize_header(cell)
        if not normalized:
            continue
        for field, synonyms in COLUMN_SYNONYMS.items():
            if field not in mapping and normalized in synonyms:
                mapping[field] = index
                break
        for field, synonyms in RCV_DOCUMENT_SYNONYMS.items():
            if field not in mapping and normalized in synonyms:
                mapping[field] = index
                break
    return mapping if mapping else None


def _looks_like_item_header(mapping: dict[str, int]) -> bool:
    return "description" in mapping and ("unit_price" in mapping or "line_total" in mapping)


def _looks_like_rcv_document(mapping: dict[str, int]) -> bool:
    """Detecta si el encabezado corresponde a un RCV de documentos (folios/DTE)."""
    return {"folio", "total"}.issubset(set(mapping.keys()))


def _find_header(frame: pd.DataFrame) -> tuple[int, dict[str, int]] | None:
    best: tuple[int, dict[str, int], int] | None = None
    for index in range(min(len(frame), 15)):
        mapping = _map_header_row([_clean_cell(cell) for cell in frame.iloc[index].tolist()])
        if mapping is None:
            continue
        if _looks_like_item_header(mapping) or _looks_like_rcv_document(mapping):
            score = len(mapping)
            if best is None or score > best[2]:
                best = (index, mapping, score)
    if best is None:
        return None
    return best[0], best[1]


def _cell(row: pd.Series, mapping: dict[str, int], field: str) -> object:
    index = mapping.get(field)
    if index is None or index >= len(row):
        return None
    value = row.iloc[index]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _cell_from_list(row: list, mapping: dict[str, int], field: str) -> str:
    index = mapping.get(field)
    if index is None or index >= len(row):
        return ""
    return _clean_cell(row[index])


def _row_to_item(row: pd.Series, mapping: dict[str, int], sheet_index: int) -> ExtractedItem | None:
    description = str(_cell(row, mapping, "description") or "").strip()
    if not description or "total" in _normalize_header(description):
        return None
    return ExtractedItem(
        sku=str(_cell(row, mapping, "sku") or "").strip() or None,
        description=description,
        quantity=_cell(row, mapping, "quantity"),
        unit=str(_cell(row, mapping, "unit") or "").strip() or None,
        unit_price=_cell(row, mapping, "unit_price"),
        line_total=_cell(row, mapping, "line_total"),
        currency=_cell(row, mapping, "currency"),
        package_size=_cell(row, mapping, "package_size"),
        price_date=_cell(row, mapping, "price_date"),
        confidence=0.98,
        evidence_text=description[:500],
        page=sheet_index,
    )


def _row_to_rcv_document(row: list, mapping: dict[str, int], sheet_index: int) -> dict | None:
    folio = _cell_from_list(row, mapping, "folio")
    if not folio or _normalize_header(folio) == "folio":
        return None
    total = _parse_money(_cell_from_list(row, mapping, "total"))
    net = _parse_money(_cell_from_list(row, mapping, "net"))
    tax = _parse_money(_cell_from_list(row, mapping, "tax"))
    if total is None and net is None and tax is None:
        return None
    return {
        "sheet": sheet_index,
        "folio": folio,
        "tipo_doc": _cell_from_list(row, mapping, "tipo_doc"),
        "rut_emisor": _cell_from_list(row, mapping, "rut"),
        "razon_social": _cell_from_list(row, mapping, "supplier"),
        "fecha_documento": _cell_from_list(row, mapping, "fecha"),
        "neto": net,
        "iva": tax,
        "total": total,
    }


def extract_tabular_document(content: bytes, filename: str) -> tuple[ExtractedDocument, dict] | None:
    """Importa Excel/CSV de forma determinística sin enviar filas al LLM.

    Detecta la fila de encabezado y mapea columnas por sinónimos. Soporta dos formatos:

    - RCV de documentos (folios/DTE): ``folio``, ``tipo_dte``, ``rut_emisor``,
      ``razon_social``, ``fecha_documento``, ``neto``, ``iva``, ``total``. Las filas
      parseadas se devuelven en ``metadata["document_rows"]``.
    - RCV de ítems/productos: descripción, SKU, cantidad, precio unitario, total.
      Las filas se exponen como ``ExtractedDocument.items``.

    Devuelve ``(ExtractedDocument, metadata)`` o ``None`` si no encuentra un formato
    tabular reconocible (para caer al extractor generativo).
    """
    suffix = Path(filename).suffix.lower()
    frames: list[tuple[str, pd.DataFrame]] = []
    total_sheets = 1
    try:
        if suffix in {".csv", ".txt"}:
            frames.append((filename, _read_csv(content)))
        else:
            excel = pd.ExcelFile(io.BytesIO(content))
            sheet_names = list(excel.sheet_names)
            total_sheets = len(sheet_names)
            for sheet_name in sheet_names[:MAX_IMPORT_SHEETS]:
                frames.append((sheet_name, excel.parse(sheet_name, header=None, dtype=str)))
    except Exception:
        return None

    items: list[ExtractedItem] = []
    document_rows: list[dict] = []
    processed = 0
    total_rows = 0
    truncated = False
    used_sheets = 0
    supplier_name = None
    supplier_tax_id = None
    document_number = None
    rcv_type: str | None = None

    for sheet_index, (_sheet_name, frame) in enumerate(frames, start=1):
        if frame.empty:
            continue
        header = _find_header(frame)
        if header is None:
            continue
        header_index, mapping = header
        # Prioriza ítems cuando hay descripción + precio; si no, trata como RCV de documentos.
        if _looks_like_item_header(mapping):
            sheet_type = "item"
        elif _looks_like_rcv_document(mapping):
            sheet_type = "document"
        else:
            continue
        rcv_type = rcv_type or sheet_type
        used_sheets += 1
        body = frame.iloc[header_index + 1 :]
        total_rows += len(body)

        for _, row in body.iterrows():
            if processed >= MAX_IMPORT_ROWS:
                truncated = True
                break
            if sheet_type == "document":
                doc = _row_to_rcv_document(row.tolist(), mapping, sheet_index)
                if doc is None:
                    continue
                document_rows.append(doc)
                supplier_name = supplier_name or (doc["razon_social"] or None)
                supplier_tax_id = supplier_tax_id or (doc["rut_emisor"] or None)
                document_number = document_number or (doc["folio"] or None)
            else:
                item = _row_to_item(row, mapping, sheet_index)
                if item is None:
                    continue
                items.append(item)
                supplier_name = supplier_name or (
                    str(_cell(row, mapping, "supplier_name") or "").strip() or None
                )
                supplier_tax_id = supplier_tax_id or (
                    str(_cell(row, mapping, "supplier_tax_id") or "").strip() or None
                )
                document_number = document_number or (
                    str(_cell(row, mapping, "document_number") or "").strip() or None
                )
            processed += 1
        if truncated:
            break

    if not items and not document_rows:
        return None

    notes = [f"Importación tabular determinística: {processed} filas procesadas."]
    if truncated:
        notes.append(
            f"El archivo supera el límite de {MAX_IMPORT_ROWS} filas por importación. "
            "Se procesó el primer lote; divide el archivo o usa el importador RCV por lotes."
        )
    if total_sheets > MAX_IMPORT_SHEETS:
        notes.append(f"Se procesaron solo las primeras {MAX_IMPORT_SHEETS} hojas del archivo.")
    extraction = ExtractedDocument(
        supplier_name=supplier_name,
        supplier_tax_id=supplier_tax_id,
        document_number=document_number,
        items=items,
        confidence=0.98,
        notes=" ".join(notes),
    )
    metadata = {
        "processed_rows": processed,
        "total_rows": total_rows,
        "truncated": truncated,
        "sheets": used_sheets,
        "warnings": notes if truncated or len(frames) > MAX_IMPORT_SHEETS else [],
        "importer": "deterministic_tabular",
        "rcv_type": rcv_type,
        "document_rows": document_rows,
    }
    return extraction, metadata


def _dataframe_to_text(frame: pd.DataFrame) -> str:
    clean = frame.dropna(how="all").dropna(axis=1, how="all")
    if clean.empty:
        return ""
    clean = clean.head(MAX_ROWS_PER_SHEET)
    return clean.to_csv(sep="|", index=False, header=False)


def _read_csv(content: bytes) -> pd.DataFrame:
    text = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ExtractionError("No se pudo decodificar el CSV.")

    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
        separator = dialect.delimiter
    except csv.Error:
        separator = ","

    try:
        return pd.read_csv(
            io.StringIO(text),
            sep=separator,
            header=None,
            dtype=str,
            keep_default_na=False,
        )
    except Exception:
        return pd.read_csv(
            io.StringIO(text),
            sep=None,
            engine="python",
            header=None,
            dtype=str,
            keep_default_na=False,
        )


def extract_tabular(content: bytes, filename: str) -> ExtractedContent:
    suffix = Path(filename).suffix.lower()
    sections: list[str] = []
    sheets = 0

    try:
        if suffix in {".csv", ".txt"}:
            frame = _read_csv(content)
            text = _dataframe_to_text(frame)
            if text:
                sections.append(f"## Archivo: {filename}\n{text}")
            sheets = 1
        else:
            excel = pd.ExcelFile(io.BytesIO(content))
            for sheet_name in excel.sheet_names[:MAX_SHEETS]:
                frame = excel.parse(sheet_name, header=None, dtype=str)
                text = _dataframe_to_text(frame)
                if text:
                    sections.append(f"## Hoja: {sheet_name}\n{text}")
                sheets += 1
    except Exception as exc:
        raise ExtractionError(f"No se pudo leer la planilla: {exc}") from exc

    combined = "\n\n".join(sections)
    if not combined.strip():
        raise ExtractionError("La planilla no contiene filas legibles.")

    return ExtractedContent(
        text="",
        tables_text=combined,
        images=[],
        page_count=sheets,
        is_scanned=False,
    )
