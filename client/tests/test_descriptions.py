from __future__ import annotations

from src.parsers.normalization.descriptions import (
    clean_sku,
    normalize_description,
    normalize_supplier_name,
    normalize_text,
    similarity,
)


def test_normalize_text_removes_accents_and_symbols():
    assert normalize_text('Válvula & Cía. 2"') == "valvula y cia 2"


def test_normalize_description_expands_abbreviations():
    assert normalize_description('PZA ACERO INOX 2"') == "pieza acero inoxidable 2"


def test_clean_sku_removes_spaces_and_lowercase():
    assert clean_sku(" ab 12/3 ") == "AB12/3"
    assert clean_sku("") is None


def test_normalize_supplier_name_removes_legal_suffix():
    assert normalize_supplier_name("ACME SpA") == "acme"
    assert normalize_supplier_name("Proveedor Limitada") == "proveedor"


def test_similar_descriptions_have_high_score():
    score = similarity("Válvula de bola 2 pulgadas", "valvula bola 2 pulgadas")

    assert score >= 90
