"""Generador de PDF de ferretería con 20 ítems para testing de extracción determinista.

Este PDF está diseñado con una estructura que el motor determinista de NEXORA
(pdfplumber + regex) puede reconocer y extraer automáticamente sin necesidad
de consumir tokens de IA.

Patrones que el parser busca (src/parsers/extractors/pdf_text.py):
- Líneas con quantity + price + total
- SKU: patron [A-Z]{2,}[-]?\d{3,}
- Precios con formato $1.234,56 o 1234.56
- Fechas en formato dd/mm/yyyy o similares
- RUTs chilenos
"""

import csv
import os
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

# ── RUT helpers ────────────────────────────────────────────────────────────

def _dv_rut(rut_number: int) -> str:
    if rut_number < 0:
        return "0"
    factor = 2
    s = 0
    n = rut_number
    while n > 0:
        s += (n % 10) * factor
        n //= 10
        factor = factor % 7 + 2
    dv = 11 - (s % 11)
    if dv == 11:
        return "0"
    if dv == 10:
        return "K"
    return str(dv)


def format_rut(rut_number: int, dv: str | None = None) -> str:
    dv = dv or _dv_rut(rut_number)
    return f"{rut_number:0}.{dv}"


# ── Fechas ─────────────────────────────────────────────────────────────────

END_DATE = date.today()
START_DATE = END_DATE - timedelta(days=90)

# 20 artículos de ferretería/construcción
ARTICLES_20 = [
    {"sku": "TOR-001", "desc": "Tornillo hexagonal M8x30", "unit": "und", "base_unit": "kg", "factor": 0.01},
    {"sku": "TAL-002", "desc": "Taladro inalámbrico 18V", "unit": "und", "base_unit": "kg", "factor": 0.5},
    {"sku": "CEM-003", "desc": "Cemento Portland 42.5", "unit": "saco", "base_unit": "kg", "factor": 0.025},
    {"sku": "LIM-004", "desc": "Lija P120 x 230mm", "unit": "docena", "base_unit": "kg", "factor": 0.15},
    {"sku": "PINT-005", "desc": "Pintura esmalte blanco 3.6L", "unit": "galón", "base_unit": "L", "factor": 3.6},
    {"sku": "CLV-006", "desc": "Clavo galvanizado 4", "unit": "kg", "base_unit": "kg", "factor": 1.0},
    {"sku": "BRU-007", "desc": "Broca para madera 6mm", "unit": "und", "base_unit": "kg", "factor": 0.02},
    {"sku": "PAS-008", "desc": "Pasador rollo 5x30", "unit": "und", "base_unit": "kg", "factor": 0.005},
    {"sku": "ARR-009", "desc": "Arandela DIN 125 8.4", "unit": "und", "base_unit": "kg", "factor": 0.001},
    {"sku": "SUP-010", "desc": "Soporte para tubería 1'", "unit": "und", "base_unit": "kg", "factor": 0.1},
    {"sku": "CORT-011", "desc": "Cortafuegos portátil", "unit": "und", "base_unit": "kg", "factor": 0.5},
    {"sku": "SEL-012", "desc": "Seleccionador de circuito", "unit": "und", "base_unit": "kg", "factor": 0.05},
    {"sku": "ISL-013", "desc": "Isolante para cable", "unit": "und", "base_unit": "kg", "factor": 0.01},
    {"sku": "CON-014", "desc": "Conector RJ45", "unit": "und", "base_unit": "kg", "factor": 0.005},
    {"sku": "TUB-015", "desc": "Tubería PVC 1/2\"", "unit": "m", "base_unit": "m", "factor": 1.0},
    {"sku": "ELE-016", "desc": "Lámpara led 20W", "unit": "und", "base_unit": "kg", "factor": 0.2},
    {"sku": "PIS-017", "desc": "Piso de goma antideslizante", "unit": "m2", "base_unit": "m2", "factor": 1.0},
    {"sku": "PINT-018", "desc": "Sellador acrílico 300ml", "unit": "und", "base_unit": "L", "factor": 0.3},
    {"sku": "FER-019", "desc": "Fierro angular 50x50", "unit": "kg", "base_unit": "kg", "factor": 1.0},
    {"sku": "PAS-020", "desc": "Pasador cilíndrico 10x30", "unit": "und", "base_unit": "kg", "factor": 0.008},
]

# Precios y cantidades realistas para cada ítem
ITEM_PRICES = [
    # (cantidad, precio_unitivo_neto)
    (2, 1200),    # Tornillo
    (1, 85000),   # Taladro
    (5, 3500),    # Cemento
    (3, 1500),    # Lija
    (1, 25000),   # Pintura
    (10, 850),    # Clavo
    (2, 3200),    # Broca
    (5, 450),     # Pasador
    (20, 120),    # Arandela
    (1, 5500),    # Soporte
    (1, 18000),   # Cortafuegos
    (2, 6500),    # Seleccionador
    (3, 250),     # Isolante
    (1, 1200),    # Conector
    (5, 4.50),    # Tubería (por metro)
    (1, 35000),   # Lámpara
    (2, 8500),    # Piso goma
    (1, 380),     # Sellador
    (2, 4500),    # Fierro angular
    (3, 180),     # Pasador cilíndrico
]


# ── Generador de PDF ─────────────────────────────────────────────────────

def generate_ferreteria_pdf_20items(path: Path) -> None:
    """Genera un PDF de ferretería con 20 ítems reconocible por el parser determinista."""
    doc = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    normal_style = styles["Normal"]

    elements = []

    # ── Título ─────────────────────────────────────────────────────────────
    elements.append(Paragraph("COTIZACIÓN FERRETERÍA 20 ITENS - Nexora", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Fecha: {END_DATE.strftime('%d/%m/%Y')}", normal_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Proveedor: Ferretería Norte Ltda. RUT 76.000.000-0", normal_style))
    elements.append(Spacer(1, 12))

    # ── Encabezado de tabla ────────────────────────────────────────────────
    # Columnas: ítem, SKU, descripción, cantidad, unidad, precio_unitivo, total
    header = ["Ítem", "SKU", "Descripción", "Cantidad", "Unidad", "Precio Unitivo (CLP)", "Total (CLP)"]

    data = [header]

    for i, article in enumerate(ARTICLES_20):
        qty, unit_price = ITEM_PRICES[i]
        total = round(qty * unit_price, 2)

        row = [
            str(i + 1),  # Ítem número
            article["sku"],
            article["desc"],
            str(qty),
            article["unit"],
            f"{unit_price:,.0f}",
            f"{total:,.0f}",
        ]
        data.append(row)

    table = Table(data, colWidths=[
        0.4 * inch,   # Ítem
        0.8 * inch,   # SKU
        2.5 * inch,   # Descripción
        0.6 * inch,   # Cantidad
        0.7 * inch,   # Unidad
        1.5 * inch,   # Precio unitivo
        1.5 * inch,   # Total
    ])

    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1b4f72")),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#aaaaaa")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f8f9fa"), white]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ])

    table.setStyle(style)
    elements.append(table)
    elements.append(Spacer(1, 24))

    # ── Pie de página ──────────────────────────────────────────────────────
    elements.append(Paragraph(
        "Generado por NEXORA • Estructura compatible con extracción determinista pdfplumber • "
        f"IVA 19% sobre precios en CLP",
        ParagraphStyle("footer", parent=normal_style, fontSize=7, textColor=HexColor("#6c757d"))))

    doc.build(elements)


# ── Generador de CSV compatible ────────────────────────────────────────────

def generate_ferreteria_csv_20items(path: Path) -> None:
    """Genera un CSV compatible con el PDF de 20 ítems de ferretería."""
    header = ["ítem", "SKU", "descripción", "cantidad", "unidad", "precio_unitivo_neto", "total"]

    data = [header]

    for i, article in enumerate(ARTICLES_20):
        qty, unit_price = ITEM_PRICES[i]
        total = round(qty * unit_price, 2)

        row = [
            str(i + 1),
            article["sku"],
            article["desc"],
            str(qty),
            article["unit"],
            str(unit_price),
            str(total),
        ]
        data.append(row)

    with open(path, "w", newline="", encoding="utf-8") as f:
        import csv as csv_module
        writer = csv_module.writer(f)
        writer.writerows(data)


# ── Punto de entrada ──────────────────────────────────────────────────────

if __name__ == "__main__":
    samples_dir = Path(__file__).parent.parent / "samples"
    samples_dir.mkdir(exist_ok=True)

    pdf_path = samples_dir / "Cotizacion_Ferreteria_20_Items_Nexora.pdf"
    csv_path = samples_dir / "Cotizacion_Ferreteria_20_Items_Nexora.csv"

    generate_ferreteria_pdf_20items(pdf_path)
    generate_ferreteria_csv_20items(csv_path)

    print(f"PDF generado: {pdf_path.resolve()}")
    print(f"CSV generado:  {csv_path.resolve()}")
    print(f"Total ítems: {len(ARTICLES_20)}")
    print(f"Período de referencia: últimos 90 días hasta {END_DATE.strftime('%d/%m/%Y')}")