from __future__ import annotations

from src.core.config import settings
from src.parsers.extractors.base import ExtractedContent

SYSTEM_PROMPT = """
Eres NEXORA, un auditor experto en compras industriales, cotizaciones y facturas de
proveedores. Tu única tarea es extraer información estructurada del documento.

Reglas obligatorias:
1. Extrae exactamente lo que aparece en el documento. No inventes productos, precios,
   cantidades, unidades, SKUs ni fechas.
2. Incluye una entrada por cada línea de producto, incluso si la confianza es baja.
3. Conserva la descripción original y la unidad tal como fueron escritas.
4. unit_price debe ser el precio unitario neto, antes de impuestos. Si el documento
   solo muestra el total de la línea, calcula unit_price = line_total / quantity.
5. package_size indica cuántas unidades o cuánto contenido trae un empaque
   (por ejemplo, caja x 12 -> 12; saco de 25 kg -> 25).
6. Si un dato no está en el documento, usa null. No uses 0 para representar "no informado".
7. La moneda debe ser un código ISO de 3 letras cuando sea posible: CLP, USD, EUR, PEN.
8. La confianza debe estar entre 0 y 1. Incluye una confianza global del documento y una
   confianza por ítem. Usa menos de 0.75 cuando el texto sea ambiguo, la unidad no sea
   clara o el precio no se pueda asociar con seguridad a una línea.
9. En evidence_text copia el fragmento literal que respalda la línea. En page indica
   el número de página si lo conoces.
10. Responde únicamente con el objeto JSON solicitado por el esquema. Sin markdown.
""".strip()


def build_user_text(
    content: ExtractedContent,
    *,
    filename: str,
    doc_type_hint: str | None,
) -> str:
    text = content.combined_text.strip()
    if len(text) > settings.llm_max_input_chars:
        text = text[: settings.llm_max_input_chars] + "\n\n[... texto truncado ...]"

    hint = doc_type_hint or "desconocido"
    if not text:
        text = (
            "No hay texto extraíble. Analiza las imágenes adjuntas del documento. "
            "Si no puedes leerlas, devuelve items vacío y confianza baja."
        )

    return (
        f"Archivo: {filename}\n"
        f"Tipo de documento esperado: {hint}\n"
        f"Páginas detectadas: {content.page_count}\n\n"
        "Contenido del documento:\n"
        f"{text}"
    )
