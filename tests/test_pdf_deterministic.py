from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.parsers.extractors.pdf_text import extract_pdf_text_document
from src.parsers.pipeline import run_pipeline
from src.parsers.schemas import ExtractedDocument, ExtractedItem
from src.services import rcv_service
from src.services.native_integrations_service import _validar_rut_chileno

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PDF = ROOT / "samples" / "Cotizacion_Ferreteria_20_Items_Nexora.pdf"
RCV_CSV = ROOT / "samples" / "Cotizacion_Ferreteria_15_Folios_RCV.csv"


class SpyProvider:
    name = "spy"
    model = "spy-model"
    last_usage = None

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def extract_document(self, extracted, *, filename, doc_type_hint=None):
        self.calls.append(filename)
        return ExtractedDocument(
            doc_type="invoice",
            supplier_name="Proveedor IA",
            currency="CLP",
            confidence=0.9,
            items=[
                ExtractedItem(
                    description="Producto recuperado por IA",
                    unit="unidad",
                    quantity=1,
                    unit_price=1200,
                    line_total=1200,
                    confidence=0.9,
                )
            ],
        )


def test_pdf_cotizacion_20_items_is_deterministic():
    result = extract_pdf_text_document(SAMPLE_PDF.read_bytes(), SAMPLE_PDF.name)

    assert result is not None, "El PDF de cotización debe resolverse sin IA"
    document, metadata = result
    assert len(document.items) == 20
    assert document.supplier_name and "Ferretería Norte" in document.supplier_name
    assert document.supplier_tax_id == "76.000.000-0"
    assert _validar_rut_chileno(document.supplier_tax_id)
    assert document.document_date and len(document.document_date) == 10
    assert document.currency == "CLP"
    assert metadata["importer"] == "deterministic_pdf"

    skus = {item.sku for item in document.items}
    assert {"TOR-001", "TUB-015", "PAS-020"} <= skus

    units = {item.unit for item in document.items}
    assert {"und", "saco", "docena", "galón", "kg", "m", "m2"} <= units

    tuberia = next(item for item in document.items if item.sku == "TUB-015")
    assert tuberia.quantity == 5
    assert tuberia.unit_price == 1200
    assert tuberia.line_total == pytest.approx(6000)

    assert document.total == pytest.approx(sum(item.line_total for item in document.items))


def test_pipeline_falls_back_to_ai_when_internal_has_no_items():
    spy = SpyProvider()
    result = asyncio.run(
        run_pipeline(
            content=b"documento sin tabla ni precios\n",
            filename="sin-datos.txt",
            mime_type="text/plain",
            doc_type_hint="invoice",
            org_settings={"default_currency": "CLP", "min_confidence": 0.0},
            provider=spy,
        )
    )

    assert spy.calls == ["sin-datos.txt"]
    assert result.ai_used is True
    assert result.extraction_source == "ai_fallback"
    assert result.provider == "spy"


def test_rcv_sample_ruts_have_valid_check_digit():
    frame = rcv_service._read_frame(RCV_CSV.read_bytes(), RCV_CSV.name)
    header = rcv_service._find_header(frame)
    assert header is not None
    header_index, mapping = header

    checked = 0
    for _, raw_row in frame.iloc[header_index + 1 :].iterrows():
        values = raw_row.tolist()
        folio = rcv_service._cell(values, mapping, "folio")
        if not folio or not folio.isdigit():
            continue
        rut = rcv_service._cell(values, mapping, "rut")
        assert rut, f"Folio {folio} sin RUT"
        assert _validar_rut_chileno(rut), f"RUT inválido en folio {folio}: {rut}"
        checked += 1

    assert checked >= 14
