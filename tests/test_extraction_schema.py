from __future__ import annotations

import json

import pytest

from src.parsers.llm.schema_utils import clean_schema
from src.parsers.schemas import ExtractedDocument, ExtractedItem


def test_extracted_item_parses_numbers_and_currency():
    item = ExtractedItem(
        description="  Válvula   de bola  ",
        quantity="1.234,50",
        unit_price="$ 12.500",
        line_total="15.000",
        package_size="12",
        currency="us$",
        confidence=85,
    )

    assert item.description == "Válvula de bola"
    assert item.quantity == pytest.approx(1234.50)
    assert item.unit_price == pytest.approx(12500)
    assert item.line_total == pytest.approx(15000)
    assert item.package_size == pytest.approx(12)
    assert item.currency == "USD"
    assert item.confidence == pytest.approx(0.85)


def test_extracted_item_defaults():
    item = ExtractedItem(description="   ")

    assert item.description == "Ítem sin descripción"
    assert item.confidence == pytest.approx(0.5)
    assert item.currency is None
    assert ExtractedItem(description="A", currency="XYZ").currency is None


def test_extracted_item_clamps_confidence():
    assert ExtractedItem(description="A", confidence=150).confidence == 1.0
    assert ExtractedItem(description="A", confidence=-5).confidence == 0.0


def test_extracted_document_validates_items_and_totals():
    document = ExtractedDocument(
        doc_type="INVOICE",
        currency="US$",
        subtotal="1.000,50",
        tax="190,10",
        total="1.190,60",
        items=[{"description": "Tornillo", "quantity": "10", "unit_price": "2"}],
        confidence=90,
    )

    assert document.doc_type == "invoice"
    assert document.currency == "USD"
    assert len(document.items) == 1
    assert document.items[0].quantity == pytest.approx(10)
    assert document.subtotal == pytest.approx(1000.50)
    assert document.tax == pytest.approx(190.10)
    assert document.total == pytest.approx(1190.60)
    assert document.confidence == pytest.approx(0.9)


def test_extracted_document_rejects_unknown_type_and_non_list_items():
    document = ExtractedDocument(doc_type="receipt", items="not-a-list")

    assert document.doc_type is None
    assert document.items == []
    assert document.confidence is None


def test_clean_schema_inlines_nested_definitions():
    schema = clean_schema(ExtractedDocument.model_json_schema())

    assert "$defs" not in schema
    assert "$ref" not in json.dumps(schema)
    item_schema = schema["properties"]["items"]["items"]
    assert item_schema["type"] == "object"
    assert item_schema["properties"]["description"]["type"] == "string"
    assert item_schema["additionalProperties"] is False
