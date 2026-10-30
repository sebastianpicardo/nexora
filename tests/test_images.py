from __future__ import annotations

import io

from PIL import Image

from src.parsers.extractors.images import extract_image


def test_extract_image_normalizes_to_png():
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="JPEG")

    result = extract_image(buffer.getvalue())

    assert result.page_count == 1
    assert result.is_scanned is True
    assert len(result.images) == 1
    assert result.images[0].startswith(b"\x89PNG\r\n\x1a\n")
