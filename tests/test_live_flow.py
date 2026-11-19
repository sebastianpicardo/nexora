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


async def _create_member(org_id: str, email: str, role: str) -> dict:
    await open_pool()
    try:
        async with get_pool().connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO users (org_id, email, name, role, active, email_verified)
                    VALUES (%s, %s, %s, %s, TRUE, TRUE)
                    RETURNING id
                    """,
                    (org_id, email, email.split("@")[0], role),
                )
                row = await cur.fetchone()
            return await users.get_user_with_org(conn, row["id"])
    finally:
        await close_pool()


async def _seed_other_org() -> dict:
    await open_pool()
    try:
        async with get_pool().connection() as conn:
            return await users.create_user_with_org(
                conn,
                email="otra@nexora.test",
                google_id="google-otra",
                name="Otra Empresa",
                avatar_url="",
                organization_name="Otra Empresa",
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
    monkeypatch.setattr(
        "src.parsers.pipeline.extract_tabular_document",
        lambda *args, **kwargs: (None, {}),
    )

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

        items_summary = client.get("/api/items/summary")
        assert items_summary.status_code == 200, items_summary.text
        summary = items_summary.json()
        assert summary["currency"] == "CLP", summary
        assert summary["total_items"] == 2, summary
        assert summary["auto_approved"] == 1, summary
        assert summary["pending"] == 1, summary

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

        exceptions_summary = client.get("/api/exceptions/summary")
        assert exceptions_summary.status_code == 200, exceptions_summary.text
        ex_summary = exceptions_summary.json()
        assert ex_summary["currency"] == "CLP", ex_summary
        assert ex_summary["pending"] == 2, ex_summary
        assert ex_summary["resolved"] == 0, ex_summary

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
        enterprise = next(plan for plan in payload["plans"] if plan["id"] == "enterprise")
        assert enterprise["price_monthly"] == 149990, enterprise
        assert enterprise["currency"] == "CLP", enterprise
        assert enterprise["currency"] == "CLP", enterprise

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

def test_enterprise_suite_end_to_end(live_database):
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

        overview = client.get("/api/enterprise/overview")
        assert overview.status_code == 200, overview.text
        assert overview.json()["roi"]["currency"] == "CLP", overview.text

        approval = client.post(
            "/api/enterprise/approvals",
            json={
                "title": "Compra de prueba",
                "amount": 150000,
                "currency": "CLP",
                "priority": "high",
                "notes": "Aprobación desde test",
            },
        )
        assert approval.status_code == 201, approval.text
        approval_id = approval.json()["id"]
        approved = client.post(
            f"/api/enterprise/approvals/{approval_id}/decision",
            json={"status": "approved", "notes": "OK"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved", approved.text

        channel = client.post(
            "/api/enterprise/notifications/channels",
            json={
                "name": "Compras",
                "channel": "email",
                "target": "compras@nexora.test",
                "events": ["alerts"],
            },
        )
        assert channel.status_code == 201, channel.text
        dispatch = client.post("/api/enterprise/notifications/dispatch")
        assert dispatch.status_code == 200, dispatch.text
        assert dispatch.json()["deliveries"], dispatch.text

        integration = client.post(
            "/api/enterprise/integrations",
            json={"provider": "erp", "name": "ERP Demo", "config": {}},
        )
        assert integration.status_code == 201, integration.text
        sync = client.post(f"/api/enterprise/integrations/{integration.json()['id']}/sync")
        assert sync.status_code == 200, sync.text
        assert sync.json()["success"] is True, sync.text

        api_key = client.post(
            "/api/enterprise/api-keys",
            json={"name": "Integración demo", "scopes": ["read"]},
        )
        assert api_key.status_code == 201, api_key.text
        raw_key = api_key.json()["token"]
        public = client.get("/api/public/v1/summary", headers={"X-API-Key": raw_key})
        assert public.status_code == 200, public.text
        assert public.json()["currency"] == "CLP", public.text

        inbound = client.post("/api/enterprise/inbound-email/tokens", json={"label": "Compras"})
        assert inbound.status_code == 201, inbound.text
        assert inbound.json()["address"].endswith("@inbox.nexora.app"), inbound.text

        demo = client.post("/api/enterprise/onboarding/demo")
        assert demo.status_code == 200, demo.text
        onboarding = client.get("/api/enterprise/onboarding")
        assert onboarding.status_code == 200, onboarding.text
        assert onboarding.json()["steps"]["documents"] is True, onboarding.text
        assert onboarding.json()["demo_seeded"] is True, onboarding.text
        pending_approvals = client.get("/api/enterprise/approvals?status=pending&page_size=10")
        assert pending_approvals.status_code == 200, pending_approvals.text
        assert pending_approvals.json()["total"] >= 2, pending_approvals.text
        scorecards = client.get("/api/enterprise/suppliers/scorecards")
        assert scorecards.status_code == 200, scorecards.text
        assert scorecards.json()["items"], scorecards.text

        branding = client.patch(
            "/api/enterprise/branding",
            json={"brand_name": "NEXORA Demo", "brand_primary_color": "#0ea5e9"},
        )
        assert branding.status_code == 200, branding.text
        assert branding.json()["brand_name"] == "NEXORA Demo", branding.text

        security = client.patch(
            "/api/enterprise/security",
            json={
                "sso_enabled": True,
                "sso_domain": "nexora.test",
                "audit_retention_days": 180,
                "ai_data_consent": False,
                "ai_images_enabled": False,
                "ai_text_max_chars": 5000,
                "ai_data_retention_days": 30,
            },
        )
        assert security.status_code == 200, security.text
        assert security.json()["audit_retention_days"] == 180, security.text
        assert security.json()["ai_data_consent"] is False, security.text
        assert security.json()["ai_images_enabled"] is False, security.text
        assert security.json()["ai_text_max_chars"] == 5000, security.text
        assert security.json()["ai_data_retention_days"] == 30, security.text
        purged = client.post("/api/enterprise/security/purge-audit")
        assert purged.status_code == 200, purged.text
        purged_ai = client.post("/api/enterprise/security/purge-ai")
        assert purged_ai.status_code == 200, purged_ai.text
        assert purged_ai.json()["retention_days"] == 30, purged_ai.text

        push_key = client.get("/api/enterprise/push/public-key")
        assert push_key.status_code == 200, push_key.text
        subscribed = client.post(
            "/api/enterprise/push/subscribe",
            json={"endpoint": "https://push.example.test/abc", "p256dh": "p" * 20, "auth": "a" * 10},
        )
        assert subscribed.status_code == 201, subscribed.text

        for fmt, content_type in (
            ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("pdf", "application/pdf"),
        ):
            exported = client.get(f"/api/enterprise/roi/export?format={fmt}")
            assert exported.status_code == 200, exported.text
            assert exported.headers["content-type"].startswith(content_type), exported.headers

        reset = client.delete("/api/enterprise/onboarding/demo")
        assert reset.status_code == 200, reset.text
        assert reset.json()["documents"] >= 1, reset.text
        after_reset = client.get("/api/enterprise/onboarding")
        assert after_reset.json()["demo_seeded"] is False, after_reset.text

def test_tenant_isolation_and_role_matrix(live_database, monkeypatch):
    owner = asyncio.run(_seed_user())
    viewer = asyncio.run(_create_member(owner["org_id"], "viewer@nexora.test", "viewer"))
    other = asyncio.run(_seed_other_org())
    owner_token = create_access_token(
        user_id=owner["id"],
        email=owner["email"],
        org_id=owner["org_id"],
        role=owner["role"],
        name=owner["name"],
    )
    viewer_token = create_access_token(
        user_id=viewer["id"],
        email=viewer["email"],
        org_id=viewer["org_id"],
        role=viewer["role"],
        name=viewer["name"],
    )
    other_token = create_access_token(
        user_id=other["id"],
        email=other["email"],
        org_id=other["org_id"],
        role=other["role"],
        name=other["name"],
    )

    async def patched_pipeline(**kwargs):
        return await real_run_pipeline(**kwargs, provider=FakeProvider())

    monkeypatch.setattr(document_service, "run_pipeline", patched_pipeline)

    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        client.cookies.set("nexora_token", owner_token)
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
        document_id = ingest.json()["document"]["id"]
        document = _wait_for_document(client, document_id)
        assert document["status"] == "processed", document
        assert client.get("/api/items").json()["total"] == 2
        exception_id = client.get("/api/exceptions?status=pending").json()["items"][0]["id"]

        client.cookies.set("nexora_token", viewer_token)
        visible = client.get("/api/items")
        assert visible.status_code == 200, visible.text
        assert visible.json()["total"] == 2, visible.text
        denied_upload = client.post(
            "/api/documents/ingest",
            files={"file": ("x.csv", b"a\n1\n", "text/csv")},
            data={"doc_type": "invoice"},
        )
        assert denied_upload.status_code == 403, denied_upload.text
        denied_assistant = client.post("/api/assistant/chat", json={"message": "Hola", "history": []})
        assert denied_assistant.status_code == 403, denied_assistant.text
        denied_resolve = client.post(
            f"/api/exceptions/{exception_id}/resolve",
            json={"action": "ignore", "notes": "viewer"},
        )
        assert denied_resolve.status_code == 403, denied_resolve.text

        client.cookies.set("nexora_token", other_token)
        assert client.get("/api/items").json()["total"] == 0
        assert client.get("/api/documents").json()["total"] == 0
        assert client.get(f"/api/documents/{document_id}").status_code == 404
        assert client.get("/api/exceptions?status=pending").json()["total"] == 0


def test_ai_usage_retention_purges_old_rows(live_database):
    user = asyncio.run(_seed_user())

    async def _exercise_retention() -> int:
        from src.db import repositories

        await open_pool()
        try:
            async with get_pool().connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO ai_usage (org_id, kind, provider, model, created_at)
                        VALUES
                            (%s, 'assistant', 'test', 'test', now() - interval '100 days'),
                            (%s, 'assistant', 'test', 'test', now())
                        """,
                        (user["org_id"], user["org_id"]),
                    )
                deleted = await repositories.purge_expired_ai_usage(conn)
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT count(*) AS total FROM ai_usage WHERE org_id = %s",
                        (user["org_id"],),
                    )
                    row = await cur.fetchone()
                assert row["total"] == 1
                return deleted
        finally:
            await close_pool()

    assert asyncio.run(_exercise_retention()) == 1

def test_leak_audit_endpoints_report_real_findings(live_database):
    user = asyncio.run(_seed_user())
    token = create_access_token(
        user_id=user["id"],
        email=user["email"],
        org_id=user["org_id"],
        role=user["role"],
        name=user["name"],
    )

    async def _seed_data() -> None:
        from datetime import date

        await open_pool()
        try:
            async with get_pool().connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO suppliers (org_id, name, normalized_name)
                        VALUES (%s, 'Ferretería Norte', 'ferreteria norte'),
                               (%s, 'Ferretería Sur', 'ferreteria sur')
                        RETURNING id, name
                        """,
                        (user["org_id"], user["org_id"]),
                    )
                    supplier_rows = await cur.fetchall()
                    suppliers = {row["name"]: row["id"] for row in supplier_rows}

                    await cur.execute(
                        """
                        INSERT INTO documents_log (
                            org_id, supplier_id, original_filename, storage_path, file_hash, status
                        )
                        VALUES (%s, %s, 'compras.csv', 'uploads/compras.csv', 'hash-demo', 'processed')
                        RETURNING id
                        """,
                        (user["org_id"], suppliers["Ferretería Norte"]),
                    )
                    document_id = (await cur.fetchone())["id"]

                    from datetime import timedelta

                    for supplier_name, price, quantity, days_ago in (
                        ("Ferretería Norte", 1000, 10, 5),
                        ("Ferretería Sur", 1500, 5, 0),
                    ):
                        await cur.execute(
                            """
                            INSERT INTO items_history (
                                org_id, document_id, supplier_id, sku, original_description,
                                normalized_description, base_unit, quantity, normalized_unit_price,
                                currency, price_date, confidence, review_status
                            )
                            VALUES (%s, %s, %s, 'CAB-1', 'Cable eléctrico', 'Cable eléctrico',
                                    'unidad', %s, %s, 'CLP', %s, 0.95, 'auto_approved')
                            """,
                            (
                                user["org_id"],
                                document_id,
                                suppliers[supplier_name],
                                quantity,
                                price,
                                date.today() - timedelta(days=days_ago),
                            ),
                        )

                    await cur.execute(
                        """
                        INSERT INTO price_catalog (
                            org_id, sku, name, unit, cost_price, sale_price, supplier_name
                        )
                        VALUES
                            (%s, 'CAB-1', 'Cable eléctrico', 'unidad', 1000, 900, 'Ferretería Norte'),
                            (%s, 'CAB-2', 'Cable grueso', 'unidad', 1000, 1050, 'Ferretería Sur')
                        """,
                        (user["org_id"], user["org_id"]),
                    )
        finally:
            await close_pool()

    asyncio.run(_seed_data())

    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        client.cookies.set("nexora_token", token)

        audit = client.get("/api/leaks/audit?days=90")
        assert audit.status_code == 200, audit.text
        payload = audit.json()
        assert payload["summary"]["potential_savings"] > 0, payload
        categories = {finding["category"] for finding in payload["findings"]}
        assert "price_overpay" in categories, categories
        assert "margin_bleed" in categories, categories
        assert payload["coverage"]["documents"] == 1, payload["coverage"]

        comparator = client.get("/api/leaks/comparator")
        assert comparator.status_code == 200, comparator.text
        comparison = comparator.json()["items"][0]
        assert comparison["best_price"] == 1000, comparison
        assert comparison["worst_price"] == 1500, comparison

        negotiation = client.get("/api/leaks/negotiation")
        assert negotiation.status_code == 200, negotiation.text
        supplier = negotiation.json()["suppliers"][0]
        assert supplier["supplier"] == "Ferretería Sur", supplier
        assert supplier["estimated_savings"] > 0, supplier

        weekly = client.get("/api/leaks/weekly-report")
        assert weekly.status_code == 200, weekly.text
        assert weekly.json()["summary"]["documents_processed"] == 1, weekly.text

        weekly_sent = client.post("/api/leaks/weekly-report/send", json={})
        assert weekly_sent.status_code == 200, weekly_sent.text
        assert weekly_sent.json()["deliveries"], weekly_sent.text

        guardian = client.get("/api/leaks/margin-guardian?target_margin=15&min_margin=8")
        assert guardian.status_code == 200, guardian.text
        guardian_items = {item["sku"]: item for item in guardian.json()["items"]}
        assert guardian_items["CAB-1"]["status"] == "bajo_costo", guardian_items["CAB-1"]
        assert guardian_items["CAB-1"]["cost_current"] == 1500, guardian_items["CAB-1"]
        assert guardian_items["CAB-1"]["suggested_sale"] > 1500, guardian_items["CAB-1"]

        pos_csv = client.get("/api/leaks/margin-guardian.csv?only_changes=true")
        assert pos_csv.status_code == 200, pos_csv.text
        assert "CAB-1" in pos_csv.content.decode("utf-8-sig"), pos_csv.text

        tracked = client.post(
            "/api/insights/savings/track",
            json={
                "opportunity_key": "CAB-1-2026-11",
                "status": "realized",
                "title": "Renegociación cable eléctrico",
                "sku": "CAB-1",
                "product": "Cable eléctrico",
                "supplier_before": "Ferretería Sur",
                "supplier_after": "Ferretería Norte",
                "unit_price_before": 1500,
                "unit_price_after": 1000,
                "quantity": 5,
                "evidence": {"source": "test"},
            },
        )
        assert tracked.status_code == 200, tracked.text
        assert tracked.json()["tracking"]["realized_amount"] == 2500.0, tracked.text

        verified = client.get("/api/insights/savings/verified")
        assert verified.status_code == 200, verified.text
        assert verified.json()["count"] == 1, verified.text
        assert verified.json()["total_amount"] == 2500.0, verified.text

        verified_csv = client.get("/api/insights/savings/verified.csv")
        assert verified_csv.status_code == 200, verified_csv.text
        assert "CAB-1" in verified_csv.content.decode("utf-8-sig"), verified_csv.text

        verified_pdf = client.get("/api/insights/savings/verified.pdf")
        assert verified_pdf.status_code == 200, verified_pdf.text
        assert verified_pdf.headers["content-type"].startswith("application/pdf")

        pdf = client.get("/api/leaks/audit.pdf?days=90")
        assert pdf.status_code == 200, pdf.text
        assert pdf.headers["content-type"].startswith("application/pdf"), pdf.headers

        rcv = client.post(
            "/api/leaks/rcv",
            files={
                "file": (
                    "rcv.csv",
                    b"descripcion,unidad,cantidad,precio,total\nCable nuevo,unidad,1,1200,1200\n",
                    "text/csv",
                )
            },
            data={"apply": "false"},
        )
        assert rcv.status_code == 200, rcv.text
        assert rcv.json()["counts"]["nuevos"] == 1, rcv.text

        opportunities_csv = (
            b"codigo,titulo,comprador,cierre,item,unidad,cantidad,sku\n"
            b"CA-1,Reposicion tornillos,Municipalidad Demo,2026-12-31,Cable electrico,unidad,10,CAB-1\n"
            b"CA-1,Reposicion tornillos,Municipalidad Demo,2026-12-31,Producto sin precio,unidad,1,NO-EXISTE\n"
        )
        imported_opportunities = client.post(
            "/api/compra-agil/import",
            files={"file": ("compra_agil.csv", opportunities_csv, "text/csv")},
        )
        assert imported_opportunities.status_code == 200, imported_opportunities.text
        assert imported_opportunities.json()["opportunities"] == 1, imported_opportunities.text

        radar = client.get("/api/compra-agil/opportunities")
        assert radar.status_code == 200, radar.text
        assert radar.json()["mode"] == "manual", radar.text
        assert radar.json()["opportunities"][0]["external_id"] == "CA-1", radar.text

        quote = client.get("/api/compra-agil/CA-1/quote?target_margin=25")
        assert quote.status_code == 200, quote.text
        quote_payload = quote.json()
        assert quote_payload["lines"][0]["cost_price"] == 1000, quote_payload
        assert quote_payload["lines"][0]["offer_price"] == 1333.33, quote_payload
        assert quote_payload["missing"] == 1, quote_payload

        quote_csv = client.get("/api/compra-agil/CA-1/quote.csv?target_margin=25")
        assert quote_csv.status_code == 200, quote_csv.text
        assert "CA-1" in quote_csv.content.decode("utf-8-sig"), quote_csv.text

def test_rcv_completeness_identifies_missing_folios(live_database):
    user = asyncio.run(_seed_user())
    token = create_access_token(
        user_id=user["id"],
        email=user["email"],
        org_id=user["org_id"],
        role=user["role"],
        name=user["name"],
    )

    async def _seed_documents() -> None:
        from psycopg.types.json import Jsonb

        await open_pool()
        try:
            async with get_pool().connection() as conn:
                async with conn.cursor() as cur:
                    for folio in ("100", "102"):
                        await cur.execute(
                            """
                            INSERT INTO documents_log (
                                org_id, original_filename, storage_path, file_hash, status, metadata
                            )
                            VALUES (%s, %s, %s, %s, 'processed', %s)
                            """,
                            (
                                user["org_id"],
                                f"factura-{folio}.xml",
                                f"demo/{folio}.xml",
                                f"rcv-demo-{folio}",
                                Jsonb(
                                    {
                                        "document_number": folio,
                                        "supplier_tax_id": "76.111.222-3",
                                    }
                                ),
                            ),
                        )
        finally:
            await close_pool()

    asyncio.run(_seed_documents())

    today = date.today()
    csv_bytes = (
        "Tipo Doc;Folio;Fecha;RUT Proveedor;Razon Social;Monto Neto;IVA;Total\n"
        f"33;100;{today.isoformat()};76.111.222-3;Ferreteria Norte;1000;190;1190\n"
        f"33;101;{today.isoformat()};76.222.333-4;Ferreteria Sur;2000;380;2380\n"
        f"61;102;{today.isoformat()};76.111.222-3;Ferreteria Norte;-500;-95;-595\n"
    ).encode()

    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        client.cookies.set("nexora_token", token)

        imported = client.post(
            "/api/leaks/rcv/register",
            files={"file": ("rcv.csv", csv_bytes, "text/csv")},
            data={"period": today.strftime("%Y-%m")},
        )
        assert imported.status_code == 200, imported.text
        assert imported.json()["rows"] == 3, imported.text

        completeness = client.get(f"/api/leaks/rcv/completeness?period={today.strftime('%Y-%m')}")
        assert completeness.status_code == 200, completeness.text
        payload = completeness.json()
        assert payload["total_documents"] == 3, payload
        assert payload["with_detail"] == 2, payload
        assert payload["missing"] == 1, payload
        assert payload["missing_documents"][0]["folio"] == "101", payload
        assert "faltan 1" in payload["message"], payload
