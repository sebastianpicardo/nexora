from __future__ import annotations

import io

from PIL import Image

from src.parsers.extractors.base import ExtractedContent


def _to_png(content: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()
    except Exception:
        return content


def extract_image(content: bytes) -> ExtractedContent:
    return ExtractedContent(
        text="",
        tables_text="",
        images=[_to_png(content)],
        page_count=1,
        is_scanned=True,
    )
