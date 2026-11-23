from __future__ import annotations

import io
import logging

import fitz
import pdfplumber

from src.core.config import settings
from src.core.errors import ExtractionError
from src.parsers.extractors.base import ExtractedContent

logger = logging.getLogger(__name__)


def _format_table(table: list[list[str | None]]) -> str:
    rows = []
    for row in table or []:
        cells = [(cell or "").replace("\n", " ").strip() for cell in row]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _render_pages(content: bytes, page_indexes: list[int]) -> list[bytes]:
    images: list[bytes] = []
    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        logger.warning("No se pudo abrir el PDF con PyMuPDF: %s", exc)
        return images

    for index in page_indexes[: settings.llm_max_pages]:
        try:
            page = document.load_page(index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            images.append(pixmap.tobytes("png"))
        except Exception as exc:
            logger.warning("No se pudo renderizar la página %s: %s", index + 1, exc)
    document.close()
    return images


def extract_pdf(content: bytes) -> ExtractedContent:
    page_texts: list[str] = []
    table_sections: list[str] = []
    low_text_pages: list[int] = []

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if not pdf.pages:
                raise ExtractionError("El PDF no contiene páginas legibles.")
            page_count = len(pdf.pages)

            for index, page in enumerate(pdf.pages):
                text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                page_texts.append(f"## Página {index + 1}\n{text}".strip())

                tables = page.extract_tables()
                for table_index, table in enumerate(tables or [], start=1):
                    formatted = _format_table(table)
                    if formatted:
                        table_sections.append(f"## Tabla {index + 1}.{table_index} (página {index + 1})\n{formatted}")

                if len(text.strip()) < 40:
                    low_text_pages.append(index)
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"No se pudo leer el PDF: {exc}") from exc

    text = "\n\n".join(page_texts)
    tables_text = "\n\n".join(table_sections)
    total_text = f"{text}\n{tables_text}".strip()
    is_scanned = len(total_text) < 120 or len(low_text_pages) >= max(1, page_count // 2)

    images: list[bytes] = []
    if is_scanned or low_text_pages:
        indexes = low_text_pages if low_text_pages else list(range(page_count))
        images = _render_pages(content, indexes)

    if not total_text and not images:
        raise ExtractionError(
            "El PDF no tiene texto extraíble y no se pudo renderizar para visión. "
            "Verifica que no esté protegido o dañado."
        )

    return ExtractedContent(
        text=text,
        tables_text=tables_text,
        images=images,
        page_count=page_count,
        is_scanned=is_scanned,
    )
