from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CURRENCY_ALIASES = {
    "CLP": "CLP",
    "PESO": "CLP",
    "PESOS": "CLP",
    "PESO CHILENO": "CLP",
    "USD": "USD",
    "US$": "USD",
    "US DOLAR": "USD",
    "DOLAR": "USD",
    "DOLARES": "USD",
    "EUR": "EUR",
    "EURO": "EUR",
    "EUROS": "EUR",
    "PEN": "PEN",
    "SOL": "PEN",
    "SOLES": "PEN",
    "ARS": "ARS",
    "MXN": "MXN",
    "UF": "UF",
}


def _decimal_from_text(value: str) -> Decimal | None:
    text = value.strip()
    if not text:
        return None

    negative = text.startswith("(") and text.endswith(")") or text.startswith("-")
    text = re.sub(r"[^\d.,-]", "", text)
    text = text.replace("-", "")
    if not text:
        return None

    has_dot = "." in text
    has_comma = "," in text

    if has_dot and has_comma:
        decimal_sep = "." if text.rfind(".") > text.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        text = text.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif has_dot or has_comma:
        separator = "." if has_dot else ","
        parts = text.split(separator)
        if len(parts) > 2:
            text = "".join(parts[:-1]) + "." + parts[-1] if len(parts[-1]) <= 2 else "".join(parts)
        else:
            integer_part, fractional_part = parts
            if len(fractional_part) == 3 and integer_part and integer_part != "0":
                text = integer_part + fractional_part
            else:
                text = integer_part + "." + fractional_part

    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    return -result if negative else result


def parse_decimal(value: object) -> Decimal | None:
    """Convierte números y strings de precios/cantidades a Decimal.

    Soporta formatos latinos ($1.234,56), anglosajones (1,234.56), CLP sin
    decimales y valores numéricos provenientes del LLM.
    """
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        return _decimal_from_text(value)
    return None


def normalize_currency(value: object, default: str = "CLP") -> str:
    if value is None:
        return default
    raw = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in raw if not unicodedata.combining(char)).strip().upper()
    if not text:
        return default
    text = next((alias for alias in CURRENCY_ALIASES if text.startswith(alias)), text)
    return CURRENCY_ALIASES.get(text, default)


def quantize_money(value: Decimal | None, places: int = 4) -> Decimal | None:
    if value is None:
        return None
    exponent = Decimal(1).scaleb(-places)
    return value.quantize(exponent, rounding=ROUND_HALF_UP)


def format_money(value: Decimal | None, currency: str = "CLP") -> str:
    if value is None:
        return "—"
    if currency == "CLP":
        return f"${value:,.0f}".replace(",", ".")
    return f"{value:,.2f}"


def percentage_change(current: Decimal, baseline: Decimal) -> float | None:
    if baseline == 0:
        return None
    return float((current - baseline) / baseline * 100)
