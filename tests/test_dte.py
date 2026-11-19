from __future__ import annotations

from decimal import Decimal

from src.parsers.extractors.dte import extract_dte_document
from src.parsers.pipeline import run_pipeline

DTE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DTE xmlns="http://www.sii.cl/SiiDte" version="1.0">
  <Documento ID="F123T33">
    <Encabezado>
      <IdDoc>
        <TipoDTE>33</TipoDTE>
        <Folio>123</Folio>
        <FchEmis>2026-11-01</FchEmis>
      </IdDoc>
      <Emisor>
        <RUTEmisor>76.111.222-3</RUTEmisor>
        <RznSoc>Ferretería Los Andes</RznSoc>
      </Emisor>
      <Receptor>
        <RUTRecep>77.000.111-2</RUTRecep>
        <RznSocRecep>Constructora Sur</RznSocRecep>
      </Receptor>
      <Totales>
        <MntNeto>10000</MntNeto>
        <TasaIVA>19</TasaIVA>
        <IVA>1900</IVA>
        <MntTotal>11900</MntTotal>
      </Totales>
    </Encabezado>
    <Detalle>
      <NmbItem>Tornillo acero 6mm</NmbItem>
      <CodItem>TOR-1</CodItem>
      <QtyItem>10</QtyItem>
      <UnmdItem>unidad</UnmdItem>
      <PrcItem>500</PrcItem>
      <MontoItem>5000</MontoItem>
    </Detalle>
    <Detalle>
      <NmbItem>Servicio de corte</NmbItem>
      <DscItem>Servicio exento</DscItem>
      <QtyItem>1</QtyItem>
      <PrcItem>5000</PrcItem>
      <MontoItem>5000</MontoItem>
      <IndExe>1</IndExe>
    </Detalle>
  </Documento>
</DTE>
""".encode()


def test_dte_parser_extracts_header_and_lines_without_ai():
    result = extract_dte_document(DTE_XML, "factura.xml")

    assert result is not None
    document, metadata = result
    assert document.doc_type == "invoice"
    assert document.supplier_name == "Ferretería Los Andes"
    assert document.supplier_tax_id == "76.111.222-3"
    assert document.document_number == "123"
    assert document.document_date == "2026-11-01"
    assert document.subtotal == 10000
    assert document.tax == 1900
    assert document.total == 11900
    assert document.prices_include_tax is False
    assert document.tax_rate == 0.19
    assert len(document.items) == 2
    first = document.items[0]
    assert first.sku == "TOR-1"
    assert first.description == "Tornillo acero 6mm"
    assert first.quantity == 10
    assert first.unit == "unidad"
    assert first.unit_price == 500
    assert first.line_total == 5000
    assert metadata["tipo_dte"] == "33"
    assert metadata["truncated"] is False


async def test_pipeline_uses_deterministic_dte_even_without_ai_consent():
    result = await run_pipeline(
        content=DTE_XML,
        filename="factura.xml",
        mime_type="application/xml",
        doc_type_hint="invoice",
        org_settings={"default_currency": "CLP", "min_confidence": 0.75, "ai_data_consent": False},
    )

    assert result.provider == "dte"
    assert result.model == "deterministic"
    assert len(result.items) == 2
    assert result.items[0].normalized_unit_price == Decimal("500")
    assert result.items[0].flags == []
    assert result.extraction.document_number == "123"


def test_dte_parser_does_not_truncate_large_invoices():
    lines = "".join(
        f"""
        <Detalle>
          <NmbItem>Producto {index}</NmbItem>
          <QtyItem>1</QtyItem>
          <UnmdItem>unidad</UnmdItem>
          <PrcItem>100</PrcItem>
          <MontoItem>100</MontoItem>
        </Detalle>"""
        for index in range(1, 401)
    )
    content = DTE_XML.decode("utf-8").replace("</Documento>", f"{lines}</Documento>").encode("utf-8")

    result = extract_dte_document(content, "factura-grande.xml")

    assert result is not None
    document, metadata = result
    assert len(document.items) == 402
    assert metadata["truncated"] is False
