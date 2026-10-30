from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

import pint

from src.parsers.normalization.currency import parse_decimal
from src.parsers.normalization.descriptions import normalize_text

ureg = pint.UnitRegistry()

# (unidad canónica, unidad pint, dimensión, base)
PHYSICAL_UNITS: dict[str, tuple[str, str, str, str]] = {
    "kg": ("kg", "kilogram", "mass", "kg"),
    "kgs": ("kg", "kilogram", "mass", "kg"),
    "kilogramo": ("kg", "kilogram", "mass", "kg"),
    "kilogramos": ("kg", "kilogram", "mass", "kg"),
    "kilo": ("kg", "kilogram", "mass", "kg"),
    "kilos": ("kg", "kilogram", "mass", "kg"),
    "g": ("g", "gram", "mass", "kg"),
    "gr": ("g", "gram", "mass", "kg"),
    "grs": ("g", "gram", "mass", "kg"),
    "gramo": ("g", "gram", "mass", "kg"),
    "gramos": ("g", "gram", "mass", "kg"),
    "ton": ("ton", "metric_ton", "mass", "kg"),
    "tons": ("ton", "metric_ton", "mass", "kg"),
    "tonelada": ("ton", "metric_ton", "mass", "kg"),
    "toneladas": ("ton", "metric_ton", "mass", "kg"),
    "t": ("ton", "metric_ton", "mass", "kg"),
    "lb": ("lb", "pound", "mass", "kg"),
    "lbs": ("lb", "pound", "mass", "kg"),
    "libra": ("lb", "pound", "mass", "kg"),
    "libras": ("lb", "pound", "mass", "kg"),
    "oz": ("oz", "ounce", "mass", "kg"),
    "onza": ("oz", "ounce", "mass", "kg"),
    "onzas": ("oz", "ounce", "mass", "kg"),
    "l": ("l", "liter", "volume", "L"),
    "lt": ("l", "liter", "volume", "L"),
    "lts": ("l", "liter", "volume", "L"),
    "litro": ("l", "liter", "volume", "L"),
    "litros": ("l", "liter", "volume", "L"),
    "ml": ("ml", "milliliter", "volume", "L"),
    "cc": ("ml", "milliliter", "volume", "L"),
    "mililitro": ("ml", "milliliter", "volume", "L"),
    "mililitros": ("ml", "milliliter", "volume", "L"),
    "m3": ("m3", "meter**3", "volume", "L"),
    "metro cubico": ("m3", "meter**3", "volume", "L"),
    "metros cubicos": ("m3", "meter**3", "volume", "L"),
    "gal": ("gal", "gallon", "volume", "L"),
    "galon": ("gal", "gallon", "volume", "L"),
    "galones": ("gal", "gallon", "volume", "L"),
    "m": ("m", "meter", "length", "m"),
    "mt": ("m", "meter", "length", "m"),
    "mts": ("m", "meter", "length", "m"),
    "metro": ("m", "meter", "length", "m"),
    "metros": ("m", "meter", "length", "m"),
    "cm": ("cm", "centimeter", "length", "m"),
    "mm": ("mm", "millimeter", "length", "m"),
    "km": ("km", "kilometer", "length", "m"),
    "m2": ("m2", "meter**2", "area", "m2"),
    "metro cuadrado": ("m2", "meter**2", "area", "m2"),
    "metros cuadrados": ("m2", "meter**2", "area", "m2"),
}

COUNT_UNITS = {
    "unidad",
    "unidades",
    "un",
    "und",
    "u",
    "pza",
    "pzas",
    "pieza",
    "piezas",
    "item",
    "items",
    "each",
    "ea",
    "docena",
    "docenas",
}

PACKAGING_UNITS = {
    "caja",
    "cajas",
    "cj",
    "pack",
    "packs",
    "paquete",
    "paquetes",
    "bolsa",
    "bolsas",
    "saco",
    "sacos",
    "pallet",
    "palet",
    "palets",
    "tarima",
    "tarimas",
    "rollo",
    "rollos",
    "bidon",
    "bidones",
    "tambor",
    "tambores",
    "contenedor",
    "contenedores",
    "display",
    "blister",
}

PACKAGE_PATTERN = re.compile(
    r"(?:x|por)?\s*(\d+(?:[.,]\d+)?)\s*"
    r"(kg|kgs|kilos?|g|gr|grs|gramos?|l|lt|lts|litros?|ml|cc|m3|m2|m|mt|mts|"
    r"un|und|unidades?|pzas?|piezas?)\b",
    re.IGNORECASE,
)
CONTAINER_ONLY_PATTERN = re.compile(r"(?:x|por)\s*(\d+(?:[.,]\d+)?)\b", re.IGNORECASE)


@dataclass(frozen=True)
class UnitNormalization:
    original_unit: str | None
    base_unit: str
    factor: Decimal
    dimension: str
    requires_review: bool
    reason: str | None


def _factor_to_base(canonical: str, pint_unit: str, base_pint: str) -> Decimal:
    magnitude = ureg.Quantity(1, pint_unit).to(base_pint).magnitude
    return Decimal(str(magnitude)).quantize(Decimal("0.000001"))


def _parse_package(
    text: str,
    explicit_size: Decimal | None,
) -> tuple[Decimal | None, str | None]:
    match = PACKAGE_PATTERN.search(text)
    if match:
        size = parse_decimal(match.group(1))
        inner_unit = normalize_text(match.group(2))
        return size, inner_unit
    if explicit_size is not None:
        return explicit_size, None
    match = CONTAINER_ONLY_PATTERN.search(text)
    if match:
        return parse_decimal(match.group(1)), None
    return None, None


def _resolve_physical(unit: str, raw: str) -> UnitNormalization | None:
    normalized = normalize_text(unit)
    if normalized in PHYSICAL_UNITS:
        canonical, pint_unit, dimension, base_unit = PHYSICAL_UNITS[normalized]
        factor = _factor_to_base(canonical, pint_unit, base_unit)
        return UnitNormalization(
            original_unit=raw,
            base_unit=base_unit,
            factor=factor,
            dimension=dimension,
            requires_review=False,
            reason=None,
        )
    return None


def normalize_unit(
    raw_unit: str | None,
    description: str | None = None,
    package_size: object = None,
) -> UnitNormalization:
    raw = (raw_unit or "").strip()
    normalized = normalize_text(raw)
    description_text = normalize_text(description or "")
    explicit_size = parse_decimal(package_size)

    physical = _resolve_physical(normalized, raw)
    if physical:
        return physical

    tokens = normalized.split()
    first = tokens[0] if tokens else ""
    is_packaging = normalized in PACKAGING_UNITS or first in PACKAGING_UNITS

    if is_packaging:
        size, inner_unit = _parse_package(f"{normalized} {description_text}".strip(), explicit_size)
        if size is None:
            return UnitNormalization(
                original_unit=raw or None,
                base_unit="unidad",
                factor=Decimal(1),
                dimension="count",
                requires_review=True,
                reason="Unidad de empaque sin tamaño de contenido (por ejemplo, caja x N).",
            )

        inner_physical = _resolve_physical(inner_unit, inner_unit) if inner_unit else None
        if inner_physical:
            return UnitNormalization(
                original_unit=raw or None,
                base_unit=inner_physical.base_unit,
                factor=(size * inner_physical.factor).quantize(Decimal("0.000001")),
                dimension=inner_physical.dimension,
                requires_review=False,
                reason=None,
            )

        return UnitNormalization(
            original_unit=raw or None,
            base_unit="unidad",
            factor=size.quantize(Decimal("0.000001")),
            dimension="count",
            requires_review=False,
            reason=None,
        )

    if normalized in COUNT_UNITS or normalized == "":
        if normalized == "":
            return UnitNormalization(
                original_unit=None,
                base_unit="unidad",
                factor=Decimal(1),
                dimension="count",
                requires_review=True,
                reason="El documento no informa una unidad para el ítem.",
            )
        if normalized == "docena" or normalized == "docenas":
            return UnitNormalization(
                original_unit=raw,
                base_unit="unidad",
                factor=Decimal(12),
                dimension="count",
                requires_review=False,
                reason=None,
            )
        return UnitNormalization(
            original_unit=raw,
            base_unit="unidad",
            factor=Decimal(1),
            dimension="count",
            requires_review=False,
            reason=None,
        )

    for token in tokens:
        physical = _resolve_physical(token, raw)
        if physical:
            return UnitNormalization(
                original_unit=raw,
                base_unit=physical.base_unit,
                factor=physical.factor,
                dimension=physical.dimension,
                requires_review=False,
                reason=None,
            )

    return UnitNormalization(
        original_unit=raw or None,
        base_unit="unidad",
        factor=Decimal(1),
        dimension="unknown",
        requires_review=True,
        reason=f"Unidad no reconocida: '{raw or 'sin unidad'}'.",
    )
