#!/usr/bin/env python3
import os
import sys
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOADS_DIR = PROJECT_ROOT / "client" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

PDF_PATH = UPLOADS_DIR / "sample_invoice.pdf"

items = [
    {"sku": "TOR-M8X40", "description": "Tornillo hexagonal M8 x 40 mm", "unit": "unidad", "qty": 500, "price": 180},
    {"sku": "DIS-45", "description": "Disco de corte 4.5\" para metal", "unit": "unidad", "qty": 80, "price": 1250},
    {"sku": "PLA-A36-3", "description": "Plancha de acero A36 3 mm", "unit": "kg", "qty": 1200, "price": 1180},
]

c = canvas.Canvas(str(PDF_PATH), pagesize=LETTER)
width, height = LETTER
margin = 50

c.setFont("Helvetica-Bold", 16)
c.drawString(margin, height - margin, "NEXORA – Cotización de prueba")
c.setFont("Helvetica", 9)
c.drawString(margin, height - margin - 12, f"Fecha: {date.today().isoformat()}")
c.drawString(margin, height - margin - 24, f"Proveedor: Aceros del Pacífico SpA – RUT: 76.542.310-8")

c.setFillColor(HexColor("#2c3e50"))
c.setFont("Helvetica-Bold", 8)
headers = ["SKU", "Descripción", "Unidad", "Cantidad", "Precio U.", "Importe (CLP)"]
for i, h in enumerate(headers):
    c.drawString(margin + i * 50, height - margin - 42, h)

c.setFont("Helvetica", 7.5)
row_y = height - margin - 55
for idx, it in enumerate(items):
    total = it["qty"] * it["price"]
    vals = [it["sku"], it["description"], it["unit"], str(it["qty"]), f"{it['price']:,}", f"{total:,}"]
    y = row_y - idx * 12
    for j, v in enumerate(vals):
        c.drawString(margin + j * 50, y, v)

total_all = sum(it["qty"] * it["price"] for it in items)
c.setFont("Helvetica-Bold", 9)
c.drawString(margin, 40, f"TOTAL GENERAL: {total_all:,} CLP")

c.showPage()
c.save()

print("PDF generado en:", PDF_PATH)