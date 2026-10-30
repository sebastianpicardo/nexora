from __future__ import annotations

from decimal import Decimal

from src.parsers.normalization.currency import (
    normalize_currency,
    parse_decimal,
    percentage_change,
    quantize_money,
)


def test_parse_latin_number():
    assert parse_decimal("1.234,56") == Decimal("1234.56")


def test_parse_anglo_number():
    assert parse_decimal("1,234.56") == Decimal("1234.56")


def test_parse_thousands_without_decimals():
    assert parse_decimal("1.234") == Decimal("1234")


def test_parse_single_decimal_comma():
    assert parse_decimal("12,50") == Decimal("12.50")


def test_parse_negative_parentheses():
    assert parse_decimal("(1.234,50)") == Decimal("-1234.50")


def test_parse_numeric_values():
    assert parse_decimal(12.5) == Decimal("12.5")
    assert parse_decimal(10) == Decimal("10")


def test_parse_empty_values():
    assert parse_decimal(None) is None
    assert parse_decimal("") is None


def test_currency_aliases():
    assert normalize_currency("US$") == "USD"
    assert normalize_currency("Dólares") == "USD"
    assert normalize_currency("Pesos") == "CLP"
    assert normalize_currency(None) == "CLP"
    assert normalize_currency("COP") == "CLP"


def test_quantize_money_rounds_half_up():
    assert quantize_money(Decimal("1.235"), 2) == Decimal("1.24")
    assert quantize_money(None) is None


def test_percentage_change():
    assert percentage_change(Decimal("120"), Decimal("100")) == 20.0
    assert percentage_change(Decimal("80"), Decimal("100")) == -20.0
    assert percentage_change(Decimal("100"), Decimal("0")) is None
