from __future__ import annotations

from decimal import Decimal

from src.parsers.extractors.base import ExtractedContent
from src.parsers.llm.base import LLMProvider
from src.parsers.pipeline import run_pipeline
from src.parsers.schemas import ExtractedDocument, ExtractedItem


class GrossPriceProvider(LLMProvider):
    name = "fake"
    model = "fake-model"

    async def extract_document(self, content: ExtractedContent, *, filename: str, doc_type_hint: str | None = None):
        return ExtractedDocument(
            supplier_name="Proveedor IVA",
            currency="CLP",
            prices_include_tax=True,
            tax_rate=0.19,
            confidence=0.95,
            items=[
                ExtractedItem(
                    description="Cable eléctrico",
                    quantity=1,
                    unit="unidad",
                    unit_price=1190,
                    line_total=1190,
                    confidence=0.95,
                )
            ],
        )


async def test_gross_prices_are_converted_to_net_for_comparison():
    result = await run_pipeline(
        content=b"texto libre sin encabezado tabular",
        filename="cotizacion.txt",
        mime_type="text/plain",
        doc_type_hint="quote",
        org_settings={"default_currency": "CLP", "min_confidence": 0.75},
        provider=GrossPriceProvider(),
    )

    item = result.items[0]
    assert item.original_unit_price == Decimal("1190")
    assert item.normalized_unit_price == Decimal("1000.000000")
    assert item.metadata["price_condition"] == "gross"
    assert item.metadata["gross_unit_price"] == "1190.0000"
    assert item.metadata["net_unit_price"] == "1000.0000"
    assert item.metadata["tax_rate"] == 0.19
