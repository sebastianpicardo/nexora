from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

import pandas as pd

from src.core.errors import ExtractionError
from src.parsers.extractors.base import ExtractedContent

logger = logging.getLogger(__name__)

MAX_ROWS_PER_SHEET = 2000
MAX_SHEETS = 10


def _dataframe_to_text(frame: pd.DataFrame) -> str:
    clean = frame.dropna(how="all").dropna(axis=1, how="all")
    if clean.empty:
        return ""
    clean = clean.head(MAX_ROWS_PER_SHEET)
    return clean.to_csv(sep="|", index=False, header=False)


def _read_csv(content: bytes) -> pd.DataFrame:
    text = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ExtractionError("No se pudo decodificar el CSV.")

    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
        separator = dialect.delimiter
    except csv.Error:
        separator = ","

    try:
        return pd.read_csv(
            io.StringIO(text),
            sep=separator,
            header=None,
            dtype=str,
            keep_default_na=False,
        )
    except Exception:
        return pd.read_csv(
            io.StringIO(text),
            sep=None,
            engine="python",
            header=None,
            dtype=str,
            keep_default_na=False,
        )


def extract_tabular(content: bytes, filename: str) -> ExtractedContent:
    suffix = Path(filename).suffix.lower()
    sections: list[str] = []
    sheets = 0

    try:
        if suffix in {".csv", ".txt"}:
            frame = _read_csv(content)
            text = _dataframe_to_text(frame)
            if text:
                sections.append(f"## Archivo: {filename}\n{text}")
            sheets = 1
        else:
            excel = pd.ExcelFile(io.BytesIO(content))
            for sheet_name in excel.sheet_names[:MAX_SHEETS]:
                frame = excel.parse(sheet_name, header=None, dtype=str)
                text = _dataframe_to_text(frame)
                if text:
                    sections.append(f"## Hoja: {sheet_name}\n{text}")
                sheets += 1
    except Exception as exc:
        raise ExtractionError(f"No se pudo leer la planilla: {exc}") from exc

    combined = "\n\n".join(sections)
    if not combined.strip():
        raise ExtractionError("La planilla no contiene filas legibles.")

    return ExtractedContent(
        text="",
        tables_text=combined,
        images=[],
        page_count=sheets,
        is_scanned=False,
    )
