from __future__ import annotations

from uuid import uuid4

from src.core.config import settings
from src.services import storage_service


async def test_local_storage_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "local_upload_dir", str(tmp_path))

    org_id = uuid4()
    document_id = uuid4()
    content = b"contenido de prueba"

    storage_path = await storage_service.save_document(
        org_id=org_id,
        document_id=document_id,
        filename="factura de prueba.pdf",
        content=content,
        mime_type="application/pdf",
    )

    stored = tmp_path / str(org_id) / str(document_id) / "factura_de_prueba.pdf"
    assert stored.exists()
    assert storage_path.endswith("factura_de_prueba.pdf")
    assert await storage_service.read_document(storage_path) == content
