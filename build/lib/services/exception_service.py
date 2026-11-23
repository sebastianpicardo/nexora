from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection

from src.core.errors import ConflictError, NotFoundError, ValidationError
from src.db import repositories
from src.parsers.normalization.currency import normalize_currency, parse_decimal, quantize_money
from src.parsers.normalization.dates import parse_flexible_date
from src.parsers.normalization.descriptions import clean_sku, normalize_description
from src.parsers.normalization.units import normalize_unit
from src.schemas.exceptions import ExceptionResolveRequest


async def resolve_exception(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    user_id: UUID | str,
    exception_id: UUID | str,
    payload: ExceptionResolveRequest,
    default_currency: str = "CLP",
) -> dict:
    exception = await repositories.get_exception(conn, org_id, exception_id)
    if exception is None:
        raise NotFoundError("Excepción no encontrada")
    if exception["status"] != "pending":
        raise ConflictError("La excepción ya fue resuelta")

    item = None
    if exception.get("item_id"):
        item = await repositories.get_item(conn, org_id, exception["item_id"])

    if payload.action == "correct":
        if item is None:
            raise ValidationError("Esta excepción no tiene un ítem editable.")
        if payload.corrections is None:
            raise ValidationError("Debes enviar las correcciones del ítem.")

        correction = payload.corrections
        original_description = correction.original_description or item["original_description"]
        original_unit = correction.original_unit if correction.original_unit is not None else item["original_unit"]
        package_size = (
            parse_decimal(correction.package_size)
            if correction.package_size is not None
            else parse_decimal(item.get("package_size"))
        )
        unit = normalize_unit(original_unit, original_description, package_size)

        quantity = (
            parse_decimal(correction.quantity)
            if correction.quantity is not None
            else parse_decimal(item.get("quantity"))
        )
        unit_price = (
            parse_decimal(correction.original_unit_price)
            if correction.original_unit_price is not None
            else parse_decimal(item.get("original_unit_price"))
        )
        normalized_price = None
        if unit_price is not None and unit.factor > 0:
            normalized_price = quantize_money(unit_price / unit.factor, places=6)

        fields = {
            "sku": clean_sku(correction.sku) if correction.sku is not None else item.get("sku"),
            "original_description": original_description,
            "normalized_description": correction.normalized_description or normalize_description(original_description),
            "original_unit": original_unit,
            "base_unit": unit.base_unit,
            "unit_factor": unit.factor,
            "quantity": quantity,
            "package_size": package_size,
            "original_unit_price": quantize_money(unit_price, places=4),
            "normalized_unit_price": normalized_price,
            "currency": normalize_currency(
                correction.currency or item.get("currency"),
                default_currency,
            ),
            "price_date": parse_flexible_date(correction.price_date) or item.get("price_date"),
            "review_status": "approved",
        }
        updated_item = await repositories.update_item_fields(
            conn,
            org_id=org_id,
            item_id=item["id"],
            fields=fields,
        )
        if updated_item is None:
            raise NotFoundError("Ítem no encontrado")
        status = "resolved"
    elif payload.action == "approve":
        if item is not None:
            await repositories.update_item_fields(
                conn,
                org_id=org_id,
                item_id=item["id"],
                fields={"review_status": "approved"},
            )
        status = "approved"
    else:
        if item is not None:
            await repositories.update_item_fields(
                conn,
                org_id=org_id,
                item_id=item["id"],
                fields={"review_status": "rejected"},
            )
        status = "rejected"

    resolution = {
        "action": payload.action,
        "corrections": payload.corrections.model_dump(mode="json") if payload.corrections else None,
    }
    updated = await repositories.resolve_exception(
        conn,
        org_id=org_id,
        exception_id=exception_id,
        status=status,
        resolution=resolution,
        notes=payload.notes,
        resolved_by=user_id,
    )
    if updated is None:
        raise ConflictError("La excepción ya fue resuelta")
    return updated
