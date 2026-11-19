from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import date
from typing import Any

import httpx
import pandas as pd
from psycopg.types.json import Jsonb

from src.core.config import settings
from src.core.logging import get_logger
from src.core.url_safety import ensure_safe_outbound_url
from src.db.pool import get_pool
from src.parsers.normalization.dates import parse_flexible_date
from src.services.leak_audit_service import _fetch_latest, _group_latest

logger = get_logger(__name__)

MAX_IMPORT_ROWS = 20_000


def _f(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _normalize_header(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.strip().lower().replace("_", " ").replace("-", " ").split())


def _parse_money(value: Any) -> float | None:
    text = _clean(value)
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


COLUMN_SYNONYMS: dict[str, set[str]] = {
    "external_id": {"codigo", "id", "codigo oportunidad", "nro", "numero", "codigo compra"},
    "title": {"titulo", "nombre", "oportunidad", "nombre oportunidad", "descripcion oportunidad"},
    "buyer": {"comprador", "organismo", "institucion", "entidad", "unidad compra"},
    "region": {"region"},
    "closes": {"cierre", "fecha cierre", "fecha de cierre", "fecha termino"},
    "budget": {"presupuesto", "monto", "presupuesto estimado", "monto disponible"},
    "sku": {"sku", "codigo producto", "codigo item", "cod producto"},
    "item": {"item", "descripcion", "producto", "nombre producto", "detalle"},
    "unit": {"unidad", "unidad medida", "um", "unidad de medida"},
    "quantity": {"cantidad", "qty", "cant"},
}


def _map_header(row: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(row):
        normalized = _normalize_header(cell)
        if not normalized:
            continue
        for field, synonyms in COLUMN_SYNONYMS.items():
            if field not in mapping and normalized in synonyms:
                mapping[field] = index
                break
    return mapping


def _find_header(frame: pd.DataFrame) -> tuple[int, dict[str, int]] | None:
    for index in range(min(len(frame), 15)):
        mapping = _map_header([_clean(cell) for cell in frame.iloc[index].tolist()])
        if "external_id" in mapping and "item" in mapping:
            return index, mapping
    return None


def _cell(row: list[str], mapping: dict[str, int], field: str) -> str:
    index = mapping.get(field)
    if index is None or index >= len(row):
        return ""
    return _clean(row[index])


def _read_frame(content: bytes, filename: str) -> pd.DataFrame:
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix in {"xlsx", "xls"}:
        try:
            return pd.read_excel(io.BytesIO(content), header=None, dtype=str)
        except Exception as exc:
            raise ValueError("No se pudo leer el Excel de oportunidades.") from exc
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("No se pudo decodificar el archivo.")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";"
    return pd.DataFrame(list(csv.reader(io.StringIO(text), delimiter=delimiter)))


def _normalize_api_opportunity(raw: dict) -> dict | None:
    external_id = str(
        raw.get("codigo")
        or raw.get("Codigo")
        or raw.get("id")
        or raw.get("codigoOportunidad")
        or raw.get("codigo_compra")
        or ""
    ).strip()
    if not external_id:
        return None
    title = str(
        raw.get("titulo")
        or raw.get("nombre")
        or raw.get("descripcion")
        or raw.get("Titulo")
        or "Oportunidad sin título"
    ).strip()
    raw_items = raw.get("items") or raw.get("productos") or raw.get("detalle") or []
    items: list[dict] = []
    if isinstance(raw_items, list):
        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            description = str(
                entry.get("descripcion")
                or entry.get("nombre")
                or entry.get("producto")
                or entry.get("item")
                or ""
            ).strip()
            if not description:
                continue
            items.append(
                {
                    "sku": str(entry.get("sku") or entry.get("codigoProducto") or "").strip() or None,
                    "description": description,
                    "unit": str(entry.get("unidad") or entry.get("um") or "unidad").strip(),
                    "quantity": _f(entry.get("cantidad") or entry.get("qty")) or 1.0,
                }
            )
    closes_raw = raw.get("cierre") or raw.get("fechaCierre") or raw.get("fecha_cierre")
    closes = parse_flexible_date(closes_raw) if closes_raw else None
    return {
        "external_id": external_id,
        "title": title,
        "buyer": str(
            raw.get("comprador") or raw.get("organismo") or raw.get("institucion") or ""
        ).strip()
        or None,
        "region": str(raw.get("region") or "").strip() or None,
        "closes_at": closes,
        "budget_clp": _parse_money(raw.get("presupuesto") or raw.get("monto")),
        "items": items,
        "source": "api",
        "metadata": {"raw_keys": sorted(raw.keys())[:40]},
    }


async def _fetch_from_api(search: str | None, limit: int) -> list[dict]:
    if not settings.compra_agil_api_url or not settings.compra_agil_api_key:
        return []
    url = await ensure_safe_outbound_url(settings.compra_agil_api_url)
    params: dict[str, Any] = {"ticket": settings.compra_agil_api_key}
    if search:
        params["q"] = search
    async with httpx.AsyncClient(
        timeout=settings.integration_timeout_seconds,
        follow_redirects=False,
    ) as client:
        response = await client.get(url, params=params)
    if response.status_code >= 400:
        raise ValueError(f"Compra Ágil respondió HTTP {response.status_code}.")
    payload = response.json()
    if isinstance(payload, list):
        raw_items = payload
    else:
        raw_items = (
            payload.get("data")
            or payload.get("items")
            or payload.get("oportunidades")
            or payload.get("lista")
            or payload.get("results")
            or []
        )
    normalized = []
    for entry in raw_items[:limit]:
        if isinstance(entry, dict):
            opportunity = _normalize_api_opportunity(entry)
            if opportunity:
                normalized.append(opportunity)
    return normalized


async def _persist_opportunities(user: dict, opportunities: list[dict]) -> int:
    if not opportunities:
        return 0
    org_id = user["org_id"]
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            for opportunity in opportunities:
                await cur.execute(
                    """
                    INSERT INTO compra_agil_opportunities (
                        org_id, external_id, title, buyer, region, closes_at, budget_clp,
                        source, items, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (org_id, external_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        buyer = EXCLUDED.buyer,
                        region = EXCLUDED.region,
                        closes_at = EXCLUDED.closes_at,
                        budget_clp = EXCLUDED.budget_clp,
                        source = EXCLUDED.source,
                        items = EXCLUDED.items,
                        metadata = compra_agil_opportunities.metadata || EXCLUDED.metadata,
                        updated_at = now()
                    """,
                    (
                        org_id,
                        opportunity["external_id"],
                        opportunity["title"],
                        opportunity.get("buyer"),
                        opportunity.get("region"),
                        opportunity.get("closes_at"),
                        opportunity.get("budget_clp"),
                        opportunity.get("source") or "manual",
                        Jsonb(opportunity.get("items") or []),
                        Jsonb(opportunity.get("metadata") or {}),
                    ),
                )
    return len(opportunities)


async def list_opportunities(
    user: dict,
    *,
    search: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    configured = bool(settings.compra_agil_api_url and settings.compra_agil_api_key)
    api_error = None
    if configured:
        try:
            opportunities = await _fetch_from_api(search, max(limit, 20))
            await _persist_opportunities(user, opportunities)
        except Exception as exc:
            logger.warning("No se pudo consultar Compra Ágil: %s", exc.__class__.__name__)
            api_error = "No se pudo consultar la API de Compra Ágil. Se muestran los datos cargados manualmente."

    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT external_id, title, buyer, region, closes_at, budget_clp, status,
                       source, items, updated_at,
                       jsonb_array_length(items) AS item_count
                FROM compra_agil_opportunities
                WHERE org_id = %s
                ORDER BY coalesce(closes_at, current_date) ASC, updated_at DESC
                LIMIT %s
                """,
                (user["org_id"], max(1, min(limit, 100))),
            )
            rows = await cur.fetchall()

    if search:
        needle = search.strip().lower()
        rows = [
            row
            for row in rows
            if needle in str(row["title"]).lower()
            or needle in str(row.get("buyer") or "").lower()
            or needle in str(row["external_id"]).lower()
        ]

    return {
        "configured": configured,
        "mode": "api" if configured and not api_error else "manual",
        "message": api_error
        or (
            "Radar conectado a la API de Compra Ágil."
            if configured
            else "Modo manual: carga un CSV de oportunidades o configura COMPRA_AGIL_API_URL y "
            "COMPRA_AGIL_API_KEY."
        ),
        "opportunities": [
            {
                "external_id": row["external_id"],
                "title": row["title"],
                "buyer": row["buyer"],
                "region": row["region"],
                "closes_at": row["closes_at"].isoformat() if row["closes_at"] else None,
                "budget_clp": float(row["budget_clp"]) if row["budget_clp"] else None,
                "status": row["status"],
                "source": row["source"],
                "item_count": row["item_count"],
                "items": row["items"],
            }
            for row in rows
        ],
    }


async def import_opportunities(user: dict, content: bytes, filename: str) -> dict[str, Any]:
    frame = _read_frame(content, filename)
    if frame.empty:
        raise ValueError("El archivo está vacío.")
    header = _find_header(frame)
    if header is None:
        raise ValueError(
            "No se reconoció el formato. Se esperan columnas Código, Título, Comprador, "
            "Cierre, Ítem, Unidad y Cantidad."
        )
    header_index, mapping = header
    grouped: dict[str, dict] = {}
    total_items = 0
    for _, raw_row in frame.iloc[header_index + 1 :].iterrows():
        if total_items >= MAX_IMPORT_ROWS:
            raise ValueError(f"El archivo supera el límite de {MAX_IMPORT_ROWS} ítems.")
        values = raw_row.tolist()
        external_id = _cell(values, mapping, "external_id")
        description = _cell(values, mapping, "item")
        if not external_id or not description:
            continue
        opportunity = grouped.setdefault(
            external_id,
            {
                "external_id": external_id,
                "title": _cell(values, mapping, "title") or f"Compra Ágil {external_id}",
                "buyer": _cell(values, mapping, "buyer") or None,
                "region": _cell(values, mapping, "region") or None,
                "closes_at": parse_flexible_date(_cell(values, mapping, "closes")),
                "budget_clp": _parse_money(_cell(values, mapping, "budget")),
                "items": [],
                "source": "manual",
                "metadata": {"filename": filename},
            },
        )
        opportunity["items"].append(
            {
                "sku": _cell(values, mapping, "sku") or None,
                "description": description,
                "unit": _cell(values, mapping, "unit") or "unidad",
                "quantity": _f(_cell(values, mapping, "quantity")) or 1.0,
            }
        )
        total_items += 1

    if not grouped:
        raise ValueError("No se encontraron oportunidades válidas en el archivo.")
    count = await _persist_opportunities(user, list(grouped.values()))
    return {
        "filename": filename,
        "opportunities": count,
        "items": total_items,
        "external_ids": sorted(grouped.keys())[:100],
    }


async def build_quote(
    user: dict,
    external_id: str,
    *,
    target_margin: float = 25.0,
) -> dict[str, Any]:
    target_margin = max(0.0, min(float(target_margin), 90.0))
    currency = (user.get("default_currency") or "CLP").strip().upper()
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT external_id, title, buyer, region, closes_at, budget_clp, status, items
                FROM compra_agil_opportunities
                WHERE org_id = %s AND external_id = %s
                """,
                (user["org_id"], external_id),
            )
            opportunity = await cur.fetchone()
    if opportunity is None:
        raise LookupError("Oportunidad no encontrada.")

    latest = await _fetch_latest(user, 180, currency)
    groups = _group_latest(latest)
    index: dict[str, tuple] = {}
    for key, group in groups.items():
        index[str(key[0]).strip().lower()] = key
        for row in group:
            if row.get("sku"):
                index[str(row["sku"]).strip().lower()] = key

    lines = []
    total_cost = 0.0
    total_sale = 0.0
    for item in opportunity["items"] or []:
        sku = str(item.get("sku") or "").strip().lower()
        description = str(item.get("description") or "").strip()
        group_key = index.get(sku) if sku else None
        if group_key is None:
            needle = description.lower()
            for key, group in groups.items():
                candidate = str(group[0].get("description") or "").lower()
                if needle and (needle in candidate or candidate in needle):
                    group_key = key
                    break
        quantity = _f(item.get("quantity")) or 1.0
        if group_key is None:
            lines.append(
                {
                    "sku": item.get("sku"),
                    "product": description,
                    "unit": item.get("unit") or "unidad",
                    "quantity": quantity,
                    "cost_price": None,
                    "offer_price": None,
                    "total": None,
                    "status": "sin_costo",
                }
            )
            continue
        cheapest = min(groups[group_key], key=lambda row: _f(row["price"]))
        cost = _f(cheapest["price"])
        offer = round(cost / (1 - target_margin / 100), 2) if target_margin < 100 else cost
        subtotal = round(offer * quantity, 2)
        total_cost += cost * quantity
        total_sale += subtotal
        lines.append(
            {
                "sku": item.get("sku") or cheapest.get("sku"),
                "product": description or cheapest["description"],
                "unit": item.get("unit") or cheapest["base_unit"],
                "quantity": quantity,
                "cost_price": round(cost, 2),
                "offer_price": offer,
                "total": subtotal,
                "status": "ok",
                "reference_supplier": cheapest["supplier_name"],
            }
        )

    return {
        "opportunity": {
            "external_id": opportunity["external_id"],
            "title": opportunity["title"],
            "buyer": opportunity["buyer"],
            "region": opportunity["region"],
            "closes_at": opportunity["closes_at"].isoformat() if opportunity["closes_at"] else None,
            "budget_clp": float(opportunity["budget_clp"]) if opportunity["budget_clp"] else None,
            "status": opportunity["status"],
        },
        "currency": currency,
        "target_margin": target_margin,
        "lines": lines,
        "missing": sum(1 for line in lines if line["status"] != "ok"),
        "total_cost": round(total_cost, 2),
        "total_offer": round(total_sale, 2),
        "gross_margin": round(total_sale - total_cost, 2),
    }


def quote_to_csv(quote: dict) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    opportunity = quote["opportunity"]
    writer.writerow(["Oportunidad", opportunity["external_id"], opportunity["title"]])
    writer.writerow(["Comprador", opportunity.get("buyer") or "", "Cierre", opportunity.get("closes_at") or ""])
    writer.writerow([])
    writer.writerow(["SKU", "Producto", "Unidad", "Cantidad", "Costo unitario", "Precio oferta", "Total"])
    for line in quote["lines"]:
        writer.writerow(
            [
                line.get("sku") or "",
                line["product"],
                line["unit"],
                line["quantity"],
                line.get("cost_price") if line.get("cost_price") is not None else "",
                line.get("offer_price") if line.get("offer_price") is not None else "",
                line.get("total") if line.get("total") is not None else "",
            ]
        )
    writer.writerow([])
    writer.writerow(["Costo total", quote["total_cost"], "Oferta total", quote["total_offer"]])
    return buffer.getvalue().encode("utf-8-sig")


def today_iso() -> str:
    return date.today().isoformat()
