from __future__ import annotations

import asyncio
import sys
import time
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
from src.parsers.pipeline import run_pipeline as real_run_pipeline  # noqa: E402
from src.parsers.schemas import ExtractedDocument, ExtractedItem  # noqa: E402
from src.services import document_service  # noqa: E402

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class FakeProvider:
    name = "fake"
    model = "fake-test"

    async def extract_document(self, extracted, *, filename, doc_type_hint):
        return ExtractedDocument(
            doc_type="invoice",
            supplier_name="Proveedor Demo",
            supplier_tax_id="76.111.222-3",
            document_number="F-100",
            document_date=date.today().isoformat(),
            currency="USD",
            confidence=0.95,
            items=[
                ExtractedItem(
                    line_number=1,
                    sku="TOR-1",
                    description="Tornillo acero inoxidable",
                    unit="Caja x 100 unidades",
                    quantity=2,
                    unit_price=50,
                    line_total=100,
                    confidence=0.95,
                ),
                ExtractedItem(
                    line_number=2,
                    sku="PLA-1",
                    description="Plancha acero",
                    unit="kg",
                    quantity=10,
                    unit_price=3,
                    line_total=31,
                    confidence=0.50,
                ),
            ],
        )


async def _seed_user() -> dict:
    await open_pool()
    try:
        async with get_pool().connection() as conn:
            return await users.create_user_with_org(
                conn,
                email="demo@nexora.test",
                google_id="google-demo",
                name="Demo NEXORA",
                avatar_url="",
                price_spike_threshold_pct=10.0,
                min_confidence=0.75,
                default_currency="CLP",
            )
    finally:
        await close_pool()


async def _expire_billing_period(org_id: str) -> None:
    await open_pool()
    try:
        async with get_pool().connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE subscriptions
                    SET current_period_start = date_trunc('month', current_date - interval '2 months')::date,
                        current_period_end = date_trunc('month', current_date - interval '1 month')::date
                    WHERE org_id = %s
                    """,
                    (org_id,),
                )
    finally:
        await close_pool()


async def _remove_plans_and_subscriptions() -> None:
    await open_pool()
    try:
        async with get_pool().connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM subscriptions")
                await cur.execute("DELETE FROM plans")
    finally:
        await close_pool()


def _wait_for_document(client, document_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = client.get(f"/api/documents/{document_id}").json()
        if row["status"] not in {"queued", "processing"}:
            return row
        time.sleep(0.1)
    raise AssertionError(f"El documento {document_id} no terminó de procesarse")


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
    monkeypatch.setattr(settings, "process_in_background", True)
    try:
        apply_schema()
        apply_schema()
        yield
    finally:
        server.cleanup()


def test_full_ingestion_review_and_reprocess_flow(live_database, monkeypatch):
    user = asyncio.run(_seed_user())
    token = create_access_token(
        user_id=user["id"],
        email=user["email"],
        org_id=user["org_id"],
        role=user["role"],
        name=user["name"],
    )

    async def patched_pipeline(**kwargs):
        return await real_run_pipeline(**kwargs, provider=FakeProvider())

    monkeypatch.setattr(document_service, "run_pipeline", patched_pipeline)

    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        client.cookies.set("nexora_token", token)

        me = client.get("/api/auth/me")
        assert me.status_code == 200, me.text
        assert me.json()["user"]["email"] == "demo@nexora.test"

        health = client.get("/health")
        assert health.status_code == 200, health.text

        csv_bytes = (
            b"descripcion,unidad,cantidad,precio,total\n"
            b"Tornillo acero inoxidable,Caja x 100 unidades,2,50,100\n"
            b"Plancha acero,kg,10,3,31\n"
        )
        ingest = client.post(
            "/api/documents/ingest",
            files={"file": ("compras.csv", csv_bytes, "text/csv")},
            data={"doc_type": "invoice", "document_date": date.today().isoformat()},
        )
        assert ingest.status_code == 202, ingest.text
        document = _wait_for_document(client, ingest.json()["document"]["id"])
        assert document["status"] == "processed", document
        assert document["supplier_name"] == "Proveedor Demo", document

        items = client.get("/api/items")
        assert items.status_code == 200, items.text
        by_sku = {row["sku"]: row for row in items.json()["items"]}
        assert by_sku["TOR-1"]["base_unit"] == "unidad", by_sku["TOR-1"]
        assert by_sku["TOR-1"]["normalized_unit_price"] == 0.5, by_sku["TOR-1"]
        assert by_sku["TOR-1"]["review_status"] == "auto_approved", by_sku["TOR-1"]
        assert by_sku["PLA-1"]["review_status"] == "pending", by_sku["PLA-1"]

        org = client.get("/api/organizations/current")
        assert org.status_code == 200, org.text
        assert org.json()["default_currency"] == "CLP", org.text

        suppliers = client.get("/api/suppliers?search=Demo")
        assert suppliers.status_code == 200, suppliers.text
        assert len(suppliers.json()["items"]) == 1, suppliers.text

        exceptions = client.get("/api/exceptions?status=pending")
        assert exceptions.status_code == 200, exceptions.text
        pending = exceptions.json()["items"]
        assert {row["type"] for row in pending} == {"low_confidence", "price_mismatch"}

        low_conf = next(row for row in pending if row["type"] == "low_confidence")
        resolved = client.post(
            f"/api/exceptions/{low_conf['id']}/resolve",
            json={
                "action": "correct",
                "corrections": {"original_unit": "kg", "original_unit_price": 3.5, "quantity": 10},
                "notes": "Precio corregido",
            },
        )
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["status"] == "resolved", resolved.text
        corrected = {row["sku"]: row for row in client.get("/api/items").json()["items"]}
        assert corrected["PLA-1"]["normalized_unit_price"] == 3.5, corrected["PLA-1"]
        assert corrected["PLA-1"]["review_status"] == "approved", corrected["PLA-1"]

        dashboard = client.get("/api/dashboard/summary")
        assert dashboard.status_code == 200, dashboard.text
        summary = dashboard.json()
        assert summary["items_total"] == 2, summary
        assert summary["documents_total"] == 1, summary
        assert summary["exceptions_pending"] == 1, summary
        assert summary["spend_by_currency"] == [{"currency": "USD", "amount": 135.0}], summary

        reprocess = client.post(f"/api/documents/{document['id']}/reprocess")
        assert reprocess.status_code == 200, reprocess.text
        document = _wait_for_document(client, document["id"])
        assert document["status"] == "processed", document
        assert client.get("/api/items").json()["total"] == 2
        assert client.get("/api/exceptions?status=pending").json()["total"] == 2

        async def failing_pipeline(**kwargs):
            raise RuntimeError("fallo simulado de extracción")

        monkeypatch.setattr(document_service, "run_pipeline", failing_pipeline)
        failed_reprocess = client.post(f"/api/documents/{document['id']}/reprocess")
        assert failed_reprocess.status_code == 200, failed_reprocess.text
        document = _wait_for_document(client, document["id"])
        assert document["status"] == "failed", document
        assert "fallo simulado" in document["error_message"], document
        assert client.get("/api/items").json()["total"] == 2

        root = client.get("/")
        assert root.status_code == 200, root.text
        assert root.headers["content-type"].startswith(("text/html", "application/json")), root.headers


def test_empty_database_bootstraps_plans_and_returns_empty_dashboard(live_database):
    user = asyncio.run(_seed_user())
    asyncio.run(_remove_plans_and_subscriptions())
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

        billing = client.get("/api/billing/summary")
        assert billing.status_code == 200, billing.text
        payload = billing.json()
        assert payload["subscription"]["plan_id"] == "free", payload
        assert payload["usage"]["limit"] == 25, payload
        assert {plan["id"] for plan in payload["plans"]} == {"free", "pro", "enterprise"}

        dashboard = client.get("/api/dashboard/summary")
        assert dashboard.status_code == 200, dashboard.text
        summary = dashboard.json()
        assert summary["documents_total"] == 0, summary
        assert summary["items_total"] == 0, summary
        assert summary["exceptions_pending"] == 0, summary
        assert summary["spend_by_currency"] == [], summary
        assert len(summary["monthly_purchases"]) == 6, summary


def test_saas_billing_team_profile_and_exports(live_database):
    owner = asyncio.run(_seed_user())
    asyncio.run(_expire_billing_period(owner["org_id"]))
    owner_token = create_access_token(
        user_id=owner["id"],
        email=owner["email"],
        org_id=owner["org_id"],
        role=owner["role"],
        name=owner["name"],
    )

    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        client.cookies.set("nexora_token", owner_token)

        billing = client.get("/api/billing/summary")
        assert billing.status_code == 200, billing.text
        payload = billing.json()
        assert payload["subscription"]["plan_id"] == "free", payload
        assert payload["usage"]["limit"] == 25, payload
        assert payload["usage"]["period_start"] == date.today().replace(day=1).isoformat(), payload

        team = client.get("/api/team")
        assert team.status_code == 200, team.text
        assert len(team.json()["members"]) == 1, team.text

        invitation = client.post(
            "/api/team/invitations",
            json={"email": "auditor@nexora.test", "role": "user"},
        )
        assert invitation.status_code == 201, invitation.text
        invite_payload = invitation.json()
        assert invite_payload["invite_url"].startswith("http"), invite_payload
        duplicate = client.post(
            "/api/team/invitations",
            json={"email": "auditor@nexora.test", "role": "user"},
        )
        assert duplicate.status_code == 409, duplicate.text

        profile = client.patch(
            "/api/profile",
            json={"job_title": "Jefe de compras", "notify_weekly": False},
        )
        assert profile.status_code == 200, profile.text
        assert profile.json()["job_title"] == "Jefe de compras", profile.text

        dashboard = client.get("/api/dashboard/summary")
        assert dashboard.status_code == 200, dashboard.text
        assert len(dashboard.json()["monthly_purchases"]) == 6, dashboard.text
        assert dashboard.json()["quota"]["limit"] == 25, dashboard.text

        admin_forbidden = client.get("/api/admin/overview")
        assert admin_forbidden.status_code == 403, admin_forbidden.text

        for fmt, content_type in (
            ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("pdf", "application/pdf"),
        ):
            exported = client.get(f"/api/exports/exceptions?format={fmt}&status=pending")
            assert exported.status_code == 200, exported.text
            assert exported.headers["content-type"].startswith(content_type), exported.headers

        changed = client.post("/api/billing/change-plan", json={"plan_id": "pro"})
        assert changed.status_code == 200, changed.text
        assert changed.json()["subscription"]["plan_id"] == "pro", changed.text

    async def _create_invited_and_promote_owner() -> dict:
        await open_pool()
        try:
            async with get_pool().connection() as conn:
                invited = await users.create_user_with_org(
                    conn,
                    email="auditor@nexora.test",
                    google_id="google-auditor",
                    name="Auditor Demo",
                    avatar_url="",
                    price_spike_threshold_pct=10.0,
                    min_confidence=0.75,
                    default_currency="CLP",
                )
                await users.set_user_role(conn, owner["id"], "super_admin")
                return invited
        finally:
            await close_pool()

    invited = asyncio.run(_create_invited_and_promote_owner())
    assert invited["org_id"] == owner["org_id"], invited
    assert invited["role"] == "user", invited

    invited_token = create_access_token(
        user_id=invited["id"],
        email=invited["email"],
        org_id=invited["org_id"],
        role=invited["role"],
        name=invited["name"],
    )

    with TestClient(app) as client:
        client.cookies.set("nexora_token", owner_token)
        pending = client.post(
            "/api/team/invitations",
            json={"email": "auditor2@nexora.test", "role": "auditor"},
        )
        assert pending.status_code == 201, pending.text

    with TestClient(app) as client:
        client.cookies.set("nexora_token", invited_token)
        team = client.get("/api/team")
        assert team.status_code == 200, team.text
        assert len(team.json()["members"]) == 2, team.text
        assert team.json()["invitations"] == [], team.text

    with TestClient(app) as client:
        client.cookies.set("nexora_token", owner_token)
        promoted = client.patch(
            f"/api/team/members/{invited['id']}",
            json={"role": "admin"},
        )
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["role"] == "admin", promoted.text

    with TestClient(app) as client:
        client.cookies.set("nexora_token", invited_token)
        visible = client.get("/api/team")
        assert visible.status_code == 200, visible.text
        assert len(visible.json()["invitations"]) == 1, visible.text
        owner_edit = client.patch(
            f"/api/team/members/{owner['id']}",
            json={"active": False},
        )
        assert owner_edit.status_code == 403, owner_edit.text

    with TestClient(app) as client:
        client.cookies.set("nexora_token", owner_token)
        admin = client.get("/api/admin/overview")
        assert admin.status_code == 200, admin.text
        assert admin.json()["stats"]["organizations_total"] >= 1, admin.text
