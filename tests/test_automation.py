from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("pgserver")

import pgserver  # noqa: E402

from src.core.config import settings  # noqa: E402
from src.core.security import create_access_token  # noqa: E402
from src.db.init_db import apply_schema  # noqa: E402
from src.db.pool import close_pool, get_pool, open_pool  # noqa: E402
from src.db.repositories import users  # noqa: E402
from src.parsers.schemas import ExtractedDocument, ExtractedItem  # noqa: E402
from src.services import automation_service  # noqa: E402
from src.services.native_integrations_service import _validar_rut_chileno  # noqa: E402

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


CSV_WITH_PRICES = (
    b"descripcion,unidad,cantidad,precio,total\n"
    b"Tornillo acero inoxidable,unidad,2,50,100\n"
    b"Plancha acero,kg,10,3,31\n"
)

SAMPLE_PDF = (
    Path(__file__).resolve().parent.parent
    / "samples"
    / "Cotizacion_Ferreteria_20_Items_Nexora.pdf"
)


class SpyProvider:
    """Proveedor LLM espía: registra llamadas y devuelve un documento sintético."""

    name = "spy"
    model = "spy-model"
    last_usage = None

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def extract_document(self, extracted, *, filename, doc_type_hint=None):
        self.calls.append(filename)
        return ExtractedDocument(
            doc_type="invoice",
            supplier_name="Proveedor IA",
            supplier_tax_id="76.111.222-3",
            document_number="IA-1",
            document_date=date.today().isoformat(),
            currency="CLP",
            confidence=0.95,
            items=[
                ExtractedItem(
                    description="Cable eléctrico",
                    unit="unidad",
                    quantity=1,
                    unit_price=1200,
                    line_total=1200,
                    confidence=0.95,
                )
            ],
        )


@pytest.fixture
def live_database(tmp_path: Path, monkeypatch) -> Iterator[None]:
    server = pgserver.get_server(tmp_path / "pgdata", cleanup_mode="delete")
    monkeypatch.setattr(settings, "database_url", server.get_uri())
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "jwt_secret", "j" * 48)
    monkeypatch.setattr(settings, "session_secret", "s" * 48)
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "local_upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "cookie_secure", False)
    monkeypatch.setattr(settings, "process_in_background", False)
    try:
        apply_schema()
        yield
    finally:
        server.cleanup()


async def _seed_user() -> dict:
    await open_pool()
    try:
        async with get_pool().connection() as conn:
            return await users.create_user_with_org(
                conn,
                email="automation@nexora.test",
                google_id="google-automation",
                name="Automatización Demo",
                avatar_url="",
                price_spike_threshold_pct=10.0,
                min_confidence=0.75,
                default_currency="CLP",
            )
    finally:
        await close_pool()


async def _run_now(user: dict, **kwargs):
    await open_pool()
    try:
        return await automation_service.run_now(user, **kwargs)
    finally:
        await close_pool()


def test_automation_deterministic_path_never_calls_ai(live_database):
    user = asyncio.run(_seed_user())
    spy = SpyProvider()

    run = asyncio.run(
        _run_now(
            user,
            content=CSV_WITH_PRICES,
            filename="compras.csv",
            mime_type="text/csv",
            doc_type="quote",
            provider=spy,
        )
    )

    assert run is not None
    assert run["status"] == "completed"
    assert spy.calls == []
    stages = {stage["id"]: stage for stage in run["stages"]}
    assert stages["extraction"]["status"] == automation_service.STATUS_COMPLETED
    assert stages["extraction"]["source"] == automation_service.SOURCE_INTERNAL
    assert stages["extraction"]["metrics"]["items"] == 2
    assert run["summary"]["ai_used"] is False
    # Todas las etapas deben estar presentes para que el usuario vea el pipeline completo.
    assert set(stages) == {stage_id for stage_id, _ in automation_service.STAGE_DEFINITIONS}


def test_automation_pdf_extracts_header_and_20_items_without_ai(live_database):
    user = asyncio.run(_seed_user())
    spy = SpyProvider()

    run = asyncio.run(
        _run_now(
            user,
            content=SAMPLE_PDF.read_bytes(),
            filename=SAMPLE_PDF.name,
            mime_type="application/pdf",
            doc_type="quote",
            provider=spy,
        )
    )

    assert run is not None
    assert run["status"] == "completed"
    assert spy.calls == []
    stages = {stage["id"]: stage for stage in run["stages"]}
    assert stages["extraction"]["status"] == automation_service.STATUS_COMPLETED
    assert stages["extraction"]["source"] == automation_service.SOURCE_INTERNAL
    assert stages["extraction"]["metrics"]["items"] == 20

    document = run["results"]["document"]
    assert "Ferretería Norte" in (document["supplier_name"] or "")
    assert document["supplier_tax_id"] == "76.000.000-0"
    assert _validar_rut_chileno(document["supplier_tax_id"])
    assert document["item_count"] == 20
    assert run["summary"]["document_items"] == 20
    assert run["summary"]["document_supplier"] == document["supplier_name"]


def test_automation_fallback_uses_ai_when_internal_is_incomplete(live_database):
    user = asyncio.run(_seed_user())
    spy = SpyProvider()

    run = asyncio.run(
        _run_now(
            user,
            content=b"producto,cantidad\ncable,1\n",
            filename="sin-precio.csv",
            mime_type="text/csv",
            doc_type="quote",
            provider=spy,
        )
    )

    assert run is not None
    assert run["status"] == "completed"
    assert spy.calls == ["sin-precio.csv"]
    stages = {stage["id"]: stage for stage in run["stages"]}
    assert stages["extraction"]["status"] == automation_service.STATUS_FALLBACK
    assert stages["extraction"]["source"] == automation_service.SOURCE_AI
    assert run["summary"]["ai_used"] is True
    assert stages["audit"]["status"] in {
        automation_service.STATUS_COMPLETED,
        automation_service.STATUS_NO_DATA,
    }


def test_automation_reuses_existing_document_without_ai(live_database):
    user = asyncio.run(_seed_user())
    spy = SpyProvider()

    first = asyncio.run(
        _run_now(
            user,
            content=CSV_WITH_PRICES,
            filename="compras.csv",
            mime_type="text/csv",
            doc_type="quote",
            provider=spy,
        )
    )
    document_id = first["document_id"]
    assert document_id is not None

    spy_second = SpyProvider()
    second = asyncio.run(
        _run_now(user, document_id=document_id, provider=spy_second)
    )

    assert second is not None
    assert second["status"] == "completed"
    assert spy_second.calls == []
    extraction = next(stage for stage in second["stages"] if stage["id"] == "extraction")
    assert extraction["metrics"]["reused"] is True
    assert extraction["status"] == automation_service.STATUS_COMPLETED


def test_automation_api_upload_and_existing_document(live_database):
    user = asyncio.run(_seed_user())
    token = create_access_token(
        user_id=user["id"],
        email=user["email"],
        org_id=user["org_id"],
        role=user["role"],
        name=user["name"],
    )

    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        client.cookies.set("nexora_token", token)

        uploaded = client.post(
            "/api/automation/run/upload",
            files={"file": ("compras.csv", CSV_WITH_PRICES, "text/csv")},
            data={"doc_type": "quote"},
        )
        assert uploaded.status_code == 202, uploaded.text
        run_id = uploaded.json()["run"]["id"]

        detail = client.get(f"/api/automation/runs/{run_id}")
        assert detail.status_code == 200, detail.text
        run = detail.json()["run"]
        assert run["status"] == "completed", run
        document_id = run["document_id"]
        assert document_id

        again = client.post("/api/automation/run", json={"document_id": document_id})
        assert again.status_code == 202, again.text
        second = client.get(f"/api/automation/runs/{again.json()['run']['id']}").json()["run"]
        assert second["status"] == "completed", second
        extraction = next(stage for stage in second["stages"] if stage["id"] == "extraction")
        assert extraction["metrics"]["reused"] is True

        latest = client.get("/api/automation/runs/latest")
        assert latest.status_code == 200, latest.text
        assert latest.json()["run"]["id"]


def test_automation_stage_failure_does_not_abort_pipeline(live_database, monkeypatch):
    user = asyncio.run(_seed_user())
    spy = SpyProvider()

    async def broken_margin(*_args, **_kwargs):
        raise RuntimeError("catálogo no disponible")

    monkeypatch.setattr(
        automation_service.margin_guardian_service,
        "build_margin_guardian",
        broken_margin,
    )

    run = asyncio.run(
        _run_now(
            user,
            content=CSV_WITH_PRICES,
            filename="compras.csv",
            mime_type="text/csv",
            doc_type="quote",
            provider=spy,
        )
    )

    assert run is not None
    assert run["status"] == "completed"
    stages = {stage["id"]: stage for stage in run["stages"]}
    assert stages["extraction"]["status"] == automation_service.STATUS_COMPLETED
    assert stages["margin"]["status"] == automation_service.STATUS_SKIPPED
    assert "catálogo no disponible" in stages["margin"]["detail"]
