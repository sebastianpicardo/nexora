from __future__ import annotations

from decimal import Decimal

from src.parsers.normalization.units import normalize_unit


def test_physical_unit_kg():
    result = normalize_unit("kg")

    assert result.base_unit == "kg"
    assert result.factor == Decimal("1")
    assert result.dimension == "mass"
    assert result.requires_review is False


def test_grams_are_converted_to_kg():
    result = normalize_unit("g")

    assert result.base_unit == "kg"
    assert result.factor == Decimal("0.001")


def test_volume_is_converted_to_liters():
    result = normalize_unit("m3")

    assert result.base_unit == "L"
    assert result.factor == Decimal("1000")
    assert result.dimension == "volume"


def test_package_with_physical_content():
    result = normalize_unit("caja x 12 kg")

    assert result.base_unit == "kg"
    assert result.factor == Decimal("12")
    assert result.requires_review is False


def test_package_with_count_content():
    result = normalize_unit("caja x 24 unidades")

    assert result.base_unit == "unidad"
    assert result.factor == Decimal("24")
    assert result.dimension == "count"


def test_package_size_from_description():
    result = normalize_unit("caja", description="Contiene 6 unidades")

    assert result.base_unit == "unidad"
    assert result.factor == Decimal("6")


def test_package_without_size_requires_review():
    result = normalize_unit("caja")

    assert result.base_unit == "unidad"
    assert result.factor == Decimal("1")
    assert result.requires_review is True
    assert "empaque" in result.reason.lower()


def test_dozen_is_normalized_to_twelve_units():
    result = normalize_unit("docena")

    assert result.base_unit == "unidad"
    assert result.factor == Decimal("12")
    assert result.requires_review is False


def test_unknown_unit_requires_review():
    result = normalize_unit("fardo")

    assert result.base_unit == "unidad"
    assert result.dimension == "unknown"
    assert result.requires_review is True


def test_missing_unit_requires_review():
    result = normalize_unit(None)

    assert result.base_unit == "unidad"
    assert result.requires_review is True
