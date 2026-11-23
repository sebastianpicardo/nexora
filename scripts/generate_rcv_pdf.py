"""Generador de PDFs de prueba para RCV SII y documentos de ferretería.

Estos archivos están diseñados para ser procesados 100% por el motor
determinista de NEXORA (pdfplumber + reglas de extracción), sin necesidad
de consumir tokens de IA.

Los PDFs incluyen:
- RUTs chilenos válidos con dígito verificador correcto
- Folios correlativos con saltos intencionales para pruebas de completitud
- Tipos DTE 33 (Factura), 34 (Nota de débito), 61 (Otros)
- IVA 19% sobre precios en CLP
- Fechas en el último período de 90 días
- Estructura tabular compatible con extracción determinista
"""

from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── RUT helpers ────────────────────────────────────────────────────────────

def _dv_rut(rut_number: int) -> str:
    """Calcula el dígito verificador de un RUT (sin punto ni guion)."""
    if rut_number < 0:
        return "0"
    factor = 2
    s = 0
    n = rut_number
    while n > 0:
        s += (n % 10) * factor
        n //= 10
        factor = 2 if factor == 7 else factor + 1
    dv = 11 - (s % 11)
    if dv == 11:
        return "0"
    if dv == 10:
        return "K"
    return str(dv)


def format_rut(rut_number: int, dv: str | None = None) -> str:
    """Formatea un RUT como '12.345.678-K'."""
    dv = dv or _dv_rut(rut_number)
    body = f"{rut_number:,}".replace(",", ".")
    return f"{body}-{dv}"


def fmt_clp(value: float) -> str:
    if float(value).is_integer():
        return f"{value:,.0f}".replace(",", ".")
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Fecha últmoos 90 días ─────────────────────────────────────────────────

END_DATE = date.today()
START_DATE = END_DATE - timedelta(days=90)
PERIOD_LABEL = (
    f"{START_DATE.day}/{START_DATE.month}/{START_DATE.year} - "
    f"{END_DATE.day}/{END_DATE.month}/{END_DATE.year}"
)


# ── Datos de proveedores ─────────────────────────────────────────────────

SUPPLIERS = [
    {"rut": 77777777, "name": "Ferretería Norte Ltda.", "city": "Santiago"},
    {"rut": 80000000, "name": "Construcción Sur Cía. Ltda.", "city": "Concepción"},
    {"rut": 77111111, "name": "Metalúrgica O'Higgins S.A.", "city": "Rancagua"},
    {"rut": 78222222, "name": "Distribuidora El Muelle Ltda.", "city": "Valparaíso"},
    {"rut": 79333333, "name": "Acero y Más Limitada", "city": "Antofagasta"},
]


# ── Generador de PDF ─────────────────────────────────────────────────────

def generate_rcv_pdf(path: Path) -> None:
    """Genera un PDF de prueba de RCV SII con 15 folios (con folio 8 intencionalmente faltante)."""
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
    elements.append(Paragraph("REGISTRO DE COMPRAS Y VENTAS (RCV) SII - Chile", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Período: {PERIOD_LABEL}", normal_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Tipo de documento: Registro de Compras y Ventas (Ley 20.727)", normal_style))
    elements.append(Spacer(1, 12))

    # ── Datos de la tabla ──────────────────────────────────────────────────
    # 15 folios correlativos con un salto intencional (falta el folio 8)
    all_folios = list(range(1, 16))  # 1..15
    missing_folio = 8

    # Encabezados como strings planos (sin Paragraphs para evitar errores de justified)
    headers = ["Folio", "Tipo DTE", "RUT Proveedor", "Razón Social", "Fecha",
               "Neto (CLP)", "IVA 19%", "Total (CLP)", "Días desde emisión"]

    data = [headers]

    i = 0
    while i < len(all_folios):
        folio = all_folios[i]
        supplier = SUPPLIERS[(folio - 1) % len(SUPPLIERS)]
        rut_num = supplier["rut"]
        dv = _dv_rut(rut_num)
        rut_str = format_rut(rut_num, dv)

        # Fecha del documento (últimos 90 días)
        doc_date = START_DATE + timedelta(days=i * 2)
        days_ago = (END_DATE - doc_date).days

        # Precios: neto coherente, IVA 19%, total
        neto = 10_000 + (i * 5_000) + (folio * 1_000)
        ivale = round(neto * 0.19, 2)
        total = round(neto + ivale, 2)

        # Si es el folio faltante intencional, lo reemplazamos por una fila de nota
        if folio == missing_folio:
            row = ["FOLIO 8 (MANCA)", "", "", "Folio intencional omitido para prueba de completitud",
                   "", "", "", "", ""]
        else:
            row = [str(folio), "33", rut_str, supplier["name"],
                   doc_date.strftime("%d/%m/%Y"),
                   fmt_clp(neto), fmt_clp(ivale), fmt_clp(total), str(days_ago)]

        data.append(row)

        # Después del folio 7, agregamos una fila de nota sobre el folio faltante
        if folio == 7:
            data.append([
                "NOTA", "", "", "Un folio intencional está ausente (folio 8) para validar la detección de brechas "
                "en la completitud del RCV por parte del parser determinista.",
                "", "", "", "", ""
            ])

        i += 1

    # Crear la tabla con estilo mínimo para evitar errores de justified/valign
    table = Table(data, colWidths=[
        0.7 * inch, 0.8 * inch, 1.2 * inch, 1.5 * inch, 1.0 * inch,
        1.0 * inch, 0.8 * inch, 0.9 * inch, 0.9 * inch,
    ])

    # Estilo de tabla muy básico - sin justified ni valign problemáticos
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
        f"Generado por NEXORA • Validación determinista • Período: {PERIOD_LABEL}",
        ParagraphStyle("footer", parent=normal_style, fontSize=7, textColor=HexColor("#6c757d"))))

    doc.build(elements)


# ── Generador de CSV compatible ────────────────────────────────────────────

def generate_rcv_csv(path: Path) -> None:
    """Genera un CSV compatible con el PDF RCV para importación/post-procesamiento."""
    header = ["folio", "tipo_dte", "rut_emisor", "razon_social", "fecha_documento",
              "neto", "iva", "total", "dias_desde_emision"]

    all_folios = list(range(1, 16))
    missing_folio = 8

    data = [header]

    i = 0
    while i < len(all_folios):
        folio = all_folios[i]
        supplier = SUPPLIERS[(folio - 1) % len(SUPPLIERS)]
        rut_num = supplier["rut"]
        dv = _dv_rut(rut_num)
        rut_str = format_rut(rut_num, dv)

        doc_date = START_DATE + timedelta(days=i * 2)
        days_ago = (END_DATE - doc_date).days

        neto = 10_000 + (i * 5_000) + (folio * 1_000)
        ivale = round(neto * 0.19, 2)
        total = round(neto + ivale, 2)

        row = [str(folio), "33", rut_str, supplier["name"],
               doc_date.strftime("%d/%m/%Y"),
               str(neto), str(ivale), str(total), str(days_ago)]

        # Si es el folio faltante intencional, lo reemplazamos por una fila de nota
        if folio == missing_folio:
            row = [f"FOLIO {folio} (MANCA)", "", "", "Folio intencional omitido para prueba de completitud",
                   "", "", "", "", ""]

        data.append(row)

        # Después del folio 7, agregamos una nota sobre el folio faltante
        if folio == 7:
            data.append([
                "NOTA", "", "", "Un folio intencional está ausente (folio 8) para validar la detección de brechas "
                "en la completitud del RCV por parte del parser determinista.",
                "", "", "", "", ""
            ])

        i += 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        import csv as csv_module
        writer = csv_module.writer(f)
        writer.writerows(data)


# ── Punto de entrada ──────────────────────────────────────────────────────

if __name__ == "__main__":
    samples_dir = Path(__file__).parent.parent / "samples"
    samples_dir.mkdir(exist_ok=True)

    pdf_path = samples_dir / "Cotizacion_Ferreteria_15_Folios_RCV.pdf"
    csv_path = samples_dir / "Cotizacion_Ferreteria_15_Folios_RCV.csv"

    generate_rcv_pdf(pdf_path)
    generate_rcv_csv(csv_path)

    print(f"PDF generado: {pdf_path.resolve()}")
    print(f"CSV generado:  {csv_path.resolve()}")
    print(f"Período de prueba: {PERIOD_LABEL}")
    print("Folio faltante intencional: 8 (de 15 folios totales)")