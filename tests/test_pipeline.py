from __future__ import annotations

import pytest

from src.core.errors import ExtractionError
from src.parsers.extractors.base import ExtractedContent
from src.parsers.llm.base import LLMProvider
from src.parsers.pipeline import run_pipeline
from src.parsers.schemas import ExtractedDocument, ExtractedItem


class FakeProvider(LLMProvider):
    name = "fake"
    model = "fake-model"

    async def extract_document(
        self,
        content: ExtractedContent,
        *,
        filename: str,
        doc_type_hint: str | None = None,
    ) -> ExtractedDocument:
        return ExtractedDocument(
            supplier_name="Proveedor de prueba",
            currency="CLP",
            confidence=None,
            items=[
                ExtractedItem(
                    description="Caja de cable 12 kg",
                    quantity="1",
                    unit="caja x 12 kg",
                    unit_price="12000",
                    line_total="12000",
                    confidence=0.95,
                )
            ],
        )


async def test_pipeline_normalizes_without_global_confidence():
    result = await run_pipeline(
        content=b"producto,cantidad\ncable,1\n",
        filename="documento.csv",
        mime_type="text/csv",
        doc_type_hint="quote",
        org_settings={"default_currency": "CLP", "min_confidence": 0.75},
        provider=FakeProvider(),
    )

    assert result.provider == "fake"
    assert result.model == "fake-model"
    assert len(result.items) == 1

    item = result.items[0]
    assert item.base_unit == "kg"
    assert item.unit_factor == 12
    assert item.normalized_unit_price == 1000
    assert item.confidence == 0.95
    assert item.flags == []


class RecordingProvider(FakeProvider):
    def __init__(self):
        self.seen = None

    async def extract_document(self, content, *, filename, doc_type_hint=None):
        self.seen = content
        return await super().extract_document(
            content,
            filename=filename,
            doc_type_hint=doc_type_hint,
        )


async def test_pipeline_blocks_ai_without_consent():
    with pytest.raises(ExtractionError, match="no autoriz"):
        await run_pipeline(
            content=b"producto,cantidad\ncable,1\n",
            filename="documento.csv",
            mime_type="text/csv",
            doc_type_hint="quote",
            org_settings={"ai_data_consent": False},
            provider=FakeProvider(),
        )


async def test_pipeline_minimizes_text_sent_to_ai():
    provider = RecordingProvider()
    result = await run_pipeline(
        content=("producto,cantidad\n" + ("cable " * 500) + ",1\n").encode(),
        filename="documento.csv",
        mime_type="text/csv",
        doc_type_hint="quote",
        org_settings={"ai_text_max_chars": 1000, "ai_images_enabled": False},
        provider=provider,
    )

    assert provider.seen is not None
    assert len(provider.seen.combined_text) <= 1000
    assert provider.seen.images == []
    assert len(result.items) == 1
