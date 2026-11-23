from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import date
from typing import Any

import pandas as pd

from src.db import repositories
from src.db.pool import get_pool
from src.parsers.normalization.dates import parse_flexible_date

MAX_RCV_ROWS = 50_000

RCV_COLUMN_SYNONYMS: dict[str, set[str]] = {
    "tipo_doc": {"tipo doc", "tipo documento", "tipo dte", "tipo de documento", "tdoc", "tipo"},
    "folio": {"folio", "n folio", "numero", "nro", "numero documento", "num", "numero de documento"},
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


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo decodificar el archivo RCV.")


def _read_frame(content: bytes, filename: str) -> pd.DataFrame:
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix in {"xlsx", "xls"}:
        try:
            return pd.read_excel(io.BytesIO(content), header=None, dtype=str)
        except Exception as exc:
            raise ValueError("No se pudo leer el Excel del RCV.") from exc
    text = _decode_text(content)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";"
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    return pd.DataFrame(rows)


def _map_header(row: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(row):
        normalized = _normalize_header(cell)
        if not normalized:
            continue
        for field, synonyms in RCV_COLUMN_SYNONYMS.items():
            if field not in mapping and normalized in synonyms:
                mapping[field] = index
                break
    return mapping


def _find_header(frame: pd.DataFrame) -> tuple[int, dict[str, int]] | None:
    for index in range(min(len(frame), 15)):
        mapping = _map_header([_clean_cell(cell) for cell in frame.iloc[index].tolist()])
        if "folio" in mapping and ("total" in mapping or "net" in mapping or "tax" in mapping):
            return index, mapping
    return None


def _cell(row: list[str], mapping: dict[str, int], field: str) -> str:
    index = mapping.get(field)
    if index is None or index >= len(row):
        return ""
    return _clean_cell(row[index])


def _period_start(value: str | None, fallback: date) -> date:
    if value:
        match = re.fullmatch(r"(\d{4})-(\d{2})", value.strip())
        if match:
            return date(int(match.group(1)), int(match.group(2)), 1)
        parsed = parse_flexible_date(value)
        if parsed:
            return parsed.replace(day=1)
    return fallback.replace(day=1)


async def import_rcv_documents(
    user: dict,
    content: bytes,
    filename: str,
    *,
    period: str | None = None,
) -> dict[str, Any]:
    frame = _read_frame(content, filename)
    if frame.empty:
        raise ValueError("El archivo RCV está vacío.")
    header = _find_header(frame)
    if header is None:
        raise ValueError(
            "No se reconoció el formato del RCV. Se esperan columnas como Folio, Fecha, "
            "RUT Proveedor, Razón Social y Total."
        )
    header_index, mapping = header
    body = frame.iloc[header_index + 1 :]
    org_id = user["org_id"]
    fallback_period = date.today()

    rows: list[tuple] = []
    skipped = 0
    for _, raw_row in body.iterrows():
        values = raw_row.tolist()
        folio = _cell(values, mapping, "folio")
        if not folio or _normalize_header(folio) == "folio":
            continue
        if len(rows) >= MAX_RCV_ROWS:
            raise ValueError(
                f"El RCV supera el límite de {MAX_RCV_ROWS} filas. Divídelo por período."
            )
        row_period = _period_start(period or _cell(values, mapping, "fecha"), fallback_period)
        tipo_doc = re.sub(r"\D", "", _cell(values, mapping, "tipo_doc")) or "33"
        rut = _cell(values, mapping, "rut")
        supplier = _cell(values, mapping, "supplier") or None
        net = _parse_money(_cell(values, mapping, "net"))
        tax = _parse_money(_cell(values, mapping, "tax"))
        total = _parse_money(_cell(values, mapping, "total"))
        if total is None:
            total = (net or 0) + (tax or 0)
            if total == 0:
                skipped += 1
                continue
        rows.append((org_id, row_period, tipo_doc, folio, rut, supplier, net, tax, total))

    if not rows:
        raise ValueError("No se encontraron filas válidas con folio y monto en el RCV.")

    inserted = 0
    updated = 0
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            for row in rows:
                await cur.execute(
                    """
                    INSERT INTO rcv_documents (
                        org_id, period, tipo_doc, folio, rut_emisor, supplier_name,
                        net_amount, tax_amount, total_amount, currency, source_file
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (org_id, period, tipo_doc, folio, rut_emisor)
                    DO UPDATE SET
                        supplier_name = EXCLUDED.supplier_name,
                        net_amount = EXCLUDED.net_amount,
                        tax_amount = EXCLUDED.tax_amount,
                        total_amount = EXCLUDED.total_amount,
                        source_file = EXCLUDED.source_file,
                        updated_at = now()
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (
                        *row,
                        (user.get("default_currency") or "CLP").strip().upper(),
                        filename,
                    ),
                )
                result = await cur.fetchone() or {}
                if result.get("inserted"):
                    inserted += 1
                else:
                    updated += 1
            await repositories.record_audit_event(
                conn,
                org_id=org_id,
                user_id=user["id"],
                action="rcv.documents.import",
                entity_type="rcv_documents",
                entity_id=filename,
                metadata={"rows": len(rows), "inserted": inserted, "updated": updated},
            )

    periods = sorted({row[1].strftime("%Y-%m") for row in rows})
    return {
        "filename": filename,
        "rows": len(rows),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "periods": periods,
    }


async def rcv_completeness(user: dict, period: str | None = None) -> dict[str, Any]:
    org_id = user["org_id"]
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT DISTINCT to_char(period, 'YYYY-MM') AS period
                FROM rcv_documents
                WHERE org_id = %s
                ORDER BY period DESC
                """,
                (org_id,),
            )
            available = [row["period"] for row in await cur.fetchall()]

            selected = period or (available[0] if available else date.today().strftime("%Y-%m"))
            match = re.fullmatch(r"(\d{4})-(\d{2})", selected or "")
            if not match:
                raise ValueError("El período debe tener formato YYYY-MM.")
            period_date = date(int(match.group(1)), int(match.group(2)), 1)

            await cur.execute(
                """
                SELECT
                    r.id, r.period, r.tipo_doc, r.folio, r.rut_emisor, r.supplier_name,
                    r.total_amount, r.currency, d.id AS document_id
                FROM rcv_documents r
                LEFT JOIN LATERAL (
                    SELECT d.id
                    FROM documents_log d
                    WHERE d.org_id = r.org_id
                      AND d.status = 'processed'
                      AND ltrim(regexp_replace(coalesce(d.metadata->>'document_number', ''), '\\D', '', 'g'), '0')
                          = ltrim(regexp_replace(r.folio, '\\D', '', 'g'), '0')
                      AND (
                          r.rut_emisor = ''
                          OR coalesce(d.metadata->>'supplier_tax_id', '') = ''
                          OR regexp_replace(coalesce(d.metadata->>'supplier_tax_id', ''), '\\D', '', 'g')
                             = regexp_replace(r.rut_emisor, '\\D', '', 'g')
                      )
                    ORDER BY d.created_at DESC
                    LIMIT 1
                ) d ON TRUE
                WHERE r.org_id = %s
                  AND date_trunc('month', r.period) = date_trunc('month', %s::date)
                ORDER BY r.tipo_doc, r.folio
                """,
                (org_id, period_date),
            )
            rows = await cur.fetchall()

    total = len(rows)
    with_detail = sum(1 for row in rows if row["document_id"])
    missing = [row for row in rows if not row["document_id"]]
    missing_amount = sum(float(row["total_amount"] or 0) for row in missing)
    currency = rows[0]["currency"] if rows else (user.get("default_currency") or "CLP")

    if total == 0:
        message = (
            f"No hay documentos RCV cargados para {selected}. "
            "Importa el Registro de Compras del SII para medir completitud."
        )
    elif missing:
        message = (
            f"El SII registra {total} documentos de compra en {selected} y tienes detalle de "
            f"{with_detail} — faltan {len(missing)} por cargar."
        )
    else:
        message = (
            f"Completitud total en {selected}: los {total} documentos del RCV tienen detalle en NEXORA."
        )

    return {
        "period": selected,
        "available_periods": available,
        "currency": currency,
        "total_documents": total,
        "with_detail": with_detail,
        "missing": len(missing),
        "completeness_pct": round(with_detail / total * 100, 1) if total else 0.0,
        "missing_amount": round(missing_amount, 2),
        "message": message,
        "missing_documents": [
            {
                "folio": row["folio"],
                "tipo_doc": row["tipo_doc"],
                "rut": row["rut_emisor"],
                "supplier": row["supplier_name"],
                "total": float(row["total_amount"] or 0),
                "date": row["period"].isoformat() if row["period"] else None,
            }
            for row in missing[:100]
        ],
    }
