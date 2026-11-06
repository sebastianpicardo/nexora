from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from psycopg.errors import UniqueViolation

from src.api.deps import CurrentUser, require_roles
from src.core.config import settings
from src.core.logging import get_logger
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.enterprise import (
    ApiKeyCreate,
    ApiKeyOut,
    ApprovalCreate,
    ApprovalDecision,
    ApprovalUpdate,
    BrandingUpdate,
    InboundTokenCreate,
    IntegrationCreate,
    IntegrationUpdate,
    NotificationChannelCreate,
    NotificationChannelUpdate,
    OnboardingUpdate,
    PushSubscriptionIn,
    PushUnsubscribeIn,
    SecurityUpdate,
    WebhookCreate,
)
from src.services import document_service, notification_service, storage_service
from src.services.export_service import build_excel, build_pdf

logger = get_logger(__name__)
router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])
inbound_router = APIRouter(prefix="/api/inbound-email", tags=["inbound-email"])

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
ONBOARDING_STEPS = [
    ("branding", "Personaliza tu marca"),
    ("documents", "Carga tu primer documento"),
    ("suppliers", "Registra proveedores"),
    ("team", "Invita a tu equipo"),
    ("integrations", "Conecta una integración"),
    ("approvals", "Crea una aprobación de compra"),
    ("notifications", "Configura alertas"),
    ("pwa", "Activa notificaciones push"),
]


def _org_branding(org: dict) -> dict:
    return {
        "brand_name": org.get("brand_name") or "",
        "brand_primary_color": org.get("brand_primary_color") or "#10b981",
        "brand_accent_color": org.get("brand_accent_color") or "#059669",
        "logo_url": org.get("logo_url") or "",
        "support_email": org.get("support_email") or "",
        "custom_domain": org.get("custom_domain") or "",
        "hide_powered_by": bool(org.get("hide_powered_by")),
    }


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _require_org(conn, org_id) -> dict:
    org = await repositories.get_organization(conn, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organización no encontrada")
    return org


@router.get("/overview")
async def enterprise_overview(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
):
    active_currency = (currency or user["default_currency"] or "CLP").strip().upper()
    async with get_pool().connection() as conn:
        roi = await repositories.get_roi(conn, user["org_id"], currency=active_currency, months=6)
        scorecards = await repositories.list_supplier_scorecards(
            conn, user["org_id"], currency=active_currency, limit=5
        )
        alerts = await repositories.list_alerts(conn, user["org_id"], currency=active_currency)
    return {
        "roi": roi,
        "scorecards": scorecards,
        "alerts": alerts,
    }


@router.get("/roi")
async def enterprise_roi(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    months: int = Query(default=6, ge=1, le=24),
):
    active_currency = (currency or user["default_currency"] or "CLP").strip().upper()
    async with get_pool().connection() as conn:
        return await repositories.get_roi(
            conn,
            user["org_id"],
            currency=active_currency,
            months=months,
        )


@router.get("/roi/export")
async def export_roi(
    user: CurrentUser,
    fmt: Literal["pdf", "xlsx"] = Query(default="pdf", alias="format"),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    months: int = Query(default=6, ge=1, le=24),
):
    active_currency = (currency or user["default_currency"] or "CLP").strip().upper()
    async with get_pool().connection() as conn:
        org = await _require_org(conn, user["org_id"])
        roi = await repositories.get_roi(conn, user["org_id"], currency=active_currency, months=months)
        scorecards = await repositories.list_supplier_scorecards(
            conn, user["org_id"], currency=active_currency, limit=20
        )
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="enterprise.roi_export",
            entity_type="organization",
            entity_id=str(user["org_id"]),
            metadata={"format": fmt, "currency": active_currency, "months": months},
        )

    money = lambda value: f"{active_currency} {float(value or 0):,.0f}"  # noqa: E731
    rows = [
        ["Compra auditada", money(roi["audited_spend"])],
        ["Ahorro estimado", money(roi["estimated_savings"])],
        ["Exposición pendiente", money(roi["potential_exposure"])],
        ["Tasa de ahorro", f"{roi['savings_rate_pct']:.2f}%"],
        ["Documentos auditados", roi["documents"]],
        ["Ítems normalizados", roi["items"]],
        ["Proveedores", roi["suppliers"]],
        ["Horas manuales ahorradas", roi["manual_hours_saved"]],
        ["Confianza promedio", f"{roi['avg_confidence'] * 100:.1f}%"],
        ["", ""],
        ["Proveedor", "Score / Compra / Ahorro"],
        *[
            [
                row["name"],
                f"{row['score']} · {money(row['spend'])} · {money(row['savings'])}",
            ]
            for row in scorecards
        ],
        ["", ""],
        ["Mes", "Compra / Ahorro / Documentos"],
        *[
            [
                row["month"],
                f"{money(row['spend'])} · {money(row['savings'])} · {row['documents']}",
            ]
            for row in roi["monthly"]
        ],
    ]
    headers = ["Métrica", "Valor"]
    subtitle = (
        f"{org['name']} · {active_currency} · últimos {months} meses · "
        f"Generado el {date.today().isoformat()}"
    )
    if fmt == "pdf":
        content = build_pdf("Reporte ejecutivo de ROI", subtitle, headers, rows, column_widths=[110 * 2.5, 160 * 2.5])
        media_type = "application/pdf"
        extension = "pdf"
    else:
        content = build_excel("ROI ejecutivo", headers, rows)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        extension = "xlsx"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="nexora-roi-{date.today().isoformat()}.{extension}"'},
    )


@router.get("/suppliers/scorecards")
async def supplier_scorecards(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    limit: int = Query(default=50, ge=1, le=200),
):
    active_currency = (currency or user["default_currency"] or "CLP").strip().upper()
    async with get_pool().connection() as conn:
        rows = await repositories.list_supplier_scorecards(
            conn,
            user["org_id"],
            currency=active_currency,
            limit=limit,
        )
    return {"currency": active_currency, "items": rows}


@router.get("/alerts")
async def enterprise_alerts(
    user: CurrentUser,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
):
    active_currency = (currency or user["default_currency"] or "CLP").strip().upper()
    async with get_pool().connection() as conn:
        rows = await repositories.list_alerts(conn, user["org_id"], currency=active_currency)
    return {"currency": active_currency, "items": rows}


@router.get("/approvals")
async def list_approvals(
    user: CurrentUser,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    async with get_pool().connection() as conn:
        return await repositories.list_approvals(
            conn,
            user["org_id"],
            status=status_filter,
            page=page,
            page_size=page_size,
        )


@router.post("/approvals", status_code=status.HTTP_201_CREATED)
async def create_approval(
    payload: ApprovalCreate,
    user: dict = Depends(require_roles("owner", "admin", "analyst", "user")),
):
    async with get_pool().connection() as conn:
        if payload.document_id:
            document = await repositories.get_document(conn, user["org_id"], payload.document_id)
            if document is None:
                raise HTTPException(status_code=404, detail="Documento no encontrado")
        if payload.supplier_id:
            supplier = await repositories.get_supplier(conn, user["org_id"], payload.supplier_id)
            if supplier is None:
                raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        row = await repositories.create_approval(
            conn,
            org_id=user["org_id"],
            document_id=payload.document_id,
            supplier_id=payload.supplier_id,
            title=payload.title,
            amount=payload.amount,
            currency=payload.currency,
            priority=payload.priority,
            requested_by=user["id"],
            notes=payload.notes,
            metadata=payload.metadata,
        )
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="approval.create",
            entity_type="purchase_approval",
            entity_id=str(row["id"]),
        )
    return row


@router.patch("/approvals/{approval_id}")
async def update_approval(
    approval_id: UUID,
    payload: ApprovalUpdate,
    user: dict = Depends(require_roles("owner", "admin", "analyst", "user")),
):
    async with get_pool().connection() as conn:
        current = await repositories.get_approval(conn, user["org_id"], approval_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Aprobación no encontrada")
        if current["status"] != "pending":
            raise HTTPException(status_code=409, detail="La aprobación ya fue decidida")
        row = await repositories.update_approval(
            conn,
            org_id=user["org_id"],
            approval_id=approval_id,
            fields=payload.model_dump(exclude_unset=True),
        )
    return row


@router.post("/approvals/{approval_id}/decision")
async def decide_approval(
    approval_id: UUID,
    payload: ApprovalDecision,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        row = await repositories.decide_approval(
            conn,
            org_id=user["org_id"],
            approval_id=approval_id,
            status=payload.status,
            decided_by=user["id"],
            notes=payload.notes,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Aprobación no encontrada o ya decidida")
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action=f"approval.{payload.status}",
            entity_type="purchase_approval",
            entity_id=str(approval_id),
            metadata={"notes": payload.notes or ""},
        )
    return row


@router.get("/notifications/channels")
async def list_notification_channels(user: CurrentUser):
    async with get_pool().connection() as conn:
        return {"items": await repositories.list_notification_channels(conn, user["org_id"])}


@router.post("/notifications/channels", status_code=status.HTTP_201_CREATED)
async def create_notification_channel(
    payload: NotificationChannelCreate,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        row = await repositories.create_notification_channel(
            conn,
            org_id=user["org_id"],
            name=payload.name,
            channel=payload.channel,
            target=payload.target,
            events=payload.events,
        )
    return row


@router.patch("/notifications/channels/{channel_id}")
async def update_notification_channel(
    channel_id: UUID,
    payload: NotificationChannelUpdate,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        row = await repositories.update_notification_channel(
            conn,
            org_id=user["org_id"],
            channel_id=channel_id,
            fields=payload.model_dump(exclude_unset=True),
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    return row


@router.delete("/notifications/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_channel(
    channel_id: UUID,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        deleted = await repositories.delete_notification_channel(conn, user["org_id"], channel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    return None


@router.post("/notifications/dispatch")
async def dispatch_notifications(
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        org = await _require_org(conn, user["org_id"])
        result = await notification_service.dispatch_alerts(
            conn,
            org_id=user["org_id"],
            org_name=org["name"],
            currency=org["default_currency"],
        )
    return result


@router.post("/notifications/channels/{channel_id}/test")
async def test_notification_channel(
    channel_id: UUID,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        org = await _require_org(conn, user["org_id"])
        result = await notification_service.dispatch_alerts(
            conn,
            org_id=user["org_id"],
            org_name=org["name"],
            currency=org["default_currency"],
            channel_id=channel_id,
        )
    if not result["deliveries"]:
        raise HTTPException(status_code=404, detail="Canal no encontrado o inactivo")
    return result


@router.get("/notifications/deliveries")
async def notification_deliveries(user: CurrentUser, limit: int = Query(default=50, ge=1, le=200)):
    async with get_pool().connection() as conn:
        return {"items": await repositories.list_notification_deliveries(conn, user["org_id"], limit=limit)}


@router.get("/integrations")
async def list_integrations(user: CurrentUser):
    async with get_pool().connection() as conn:
        return {"items": await repositories.list_integrations(conn, user["org_id"])}


@router.post("/integrations", status_code=status.HTTP_201_CREATED)
async def create_integration(
    payload: IntegrationCreate,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        row = await repositories.create_integration(
            conn,
            org_id=user["org_id"],
            provider=payload.provider,
            name=payload.name,
            config=payload.config,
            active=payload.active,
        )
    return row


@router.patch("/integrations/{integration_id}")
async def update_integration(
    integration_id: UUID,
    payload: IntegrationUpdate,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        row = await repositories.update_integration(
            conn,
            org_id=user["org_id"],
            integration_id=integration_id,
            fields=payload.model_dump(exclude_unset=True),
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    return row


@router.post("/integrations/{integration_id}/sync")
async def sync_integration(
    integration_id: UUID,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        rows = await repositories.list_integrations(conn, user["org_id"])
        integration = next((row for row in rows if str(row["id"]) == str(integration_id)), None)
        if integration is None:
            raise HTTPException(status_code=404, detail="Integración no encontrada")
        config = integration.get("config") or {}
        url = config.get("health_url") or config.get("endpoint")
        if not url:
            result = await repositories.touch_integration_sync(
                conn,
                org_id=user["org_id"],
                integration_id=integration_id,
                status="Configurada, sin endpoint de prueba",
            )
            return {"success": True, "integration": result, "detail": "Integración guardada."}
        headers = {}
        if config.get("token"):
            headers["Authorization"] = f"Bearer {config['token']}"
        try:
            async with httpx.AsyncClient(timeout=settings.integration_timeout_seconds) as client:
                response = await client.get(str(url), headers=headers)
                response.raise_for_status()
            sync_status = f"Conexión OK ({response.status_code})"
            success = True
        except Exception as exc:
            sync_status = f"Error de conexión: {exc}"[:200]
            success = False
        result = await repositories.touch_integration_sync(
            conn,
            org_id=user["org_id"],
            integration_id=integration_id,
            status=sync_status,
        )
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="integration.sync",
            entity_type="integration",
            entity_id=str(integration_id),
            metadata={"status": sync_status, "success": success},
        )
    return {"success": success, "integration": result, "detail": sync_status}


@router.delete("/integrations/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: UUID,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        deleted = await repositories.delete_integration(conn, user["org_id"], integration_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    return None


@router.get("/api-keys")
async def list_api_keys(user: CurrentUser):
    async with get_pool().connection() as conn:
        return {"items": await repositories.list_api_keys(conn, user["org_id"])}


@router.post("/api-keys", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    user: dict = Depends(require_roles("owner", "admin")),
):
    token = f"nx_live_{secrets.token_urlsafe(32)}"
    key_prefix = token[:16]
    async with get_pool().connection() as conn:
        row = await repositories.create_api_key(
            conn,
            org_id=user["org_id"],
            name=payload.name,
            key_prefix=key_prefix,
            key_hash=_hash(token),
            scopes=payload.scopes,
            created_by=user["id"],
        )
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="api_key.create",
            entity_type="api_key",
            entity_id=str(row["id"]),
        )
    return ApiKeyOut(**row, token=token)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        revoked = await repositories.revoke_api_key(conn, user["org_id"], key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="API key no encontrada")
    return None


@router.get("/webhooks")
async def list_webhooks(user: CurrentUser):
    async with get_pool().connection() as conn:
        return {"items": await repositories.list_webhooks(conn, user["org_id"])}


@router.post("/webhooks", status_code=status.HTTP_201_CREATED)
async def create_webhook(
    payload: WebhookCreate,
    user: dict = Depends(require_roles("owner", "admin")),
):
    secret = payload.secret or secrets.token_hex(24)
    async with get_pool().connection() as conn:
        row = await repositories.create_webhook(
            conn,
            org_id=user["org_id"],
            url=payload.url,
            secret=secret,
            events=payload.events,
        )
    return {**row, "secret": secret}


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(
    webhook_id: UUID,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        rows = await repositories.list_webhooks(conn, user["org_id"])
    webhook = next((row for row in rows if str(row["id"]) == str(webhook_id)), None)
    if webhook is None:
        raise HTTPException(status_code=404, detail="Webhook no encontrado")
    payload = {"event": "webhook.test", "organization_id": str(user["org_id"]), "sent_at": date.today().isoformat()}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(webhook.get("secret", "").encode("utf-8"), body, hashlib.sha256).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=settings.integration_timeout_seconds) as client:
            response = await client.post(
                webhook["url"],
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Nexora-Signature": f"sha256={signature}",
                },
            )
            response.raise_for_status()
        return {"success": True, "status_code": response.status_code}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo entregar el webhook: {exc}") from exc


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        deleted = await repositories.delete_webhook(conn, user["org_id"], webhook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook no encontrado")
    return None


@router.get("/inbound-email/tokens")
async def list_inbound_tokens(user: CurrentUser):
    async with get_pool().connection() as conn:
        return {"items": await repositories.list_inbound_tokens(conn, user["org_id"])}


@router.post("/inbound-email/tokens", status_code=status.HTTP_201_CREATED)
async def create_inbound_token(
    payload: InboundTokenCreate,
    user: dict = Depends(require_roles("owner", "admin")),
):
    token = secrets.token_urlsafe(24)
    address = f"{token}@{settings.inbound_email_domain}"
    async with get_pool().connection() as conn:
        row = await repositories.create_inbound_token(
            conn,
            org_id=user["org_id"],
            address=address,
            token_hash=_hash(token),
            created_by=user["id"],
        )
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="inbound_email.token_create",
            entity_type="inbound_email",
            entity_id=str(row["id"]),
            metadata={"label": payload.label},
        )
    return {**row, "token": token, "domain": settings.inbound_email_domain}


@router.get("/onboarding")
async def get_onboarding(user: CurrentUser):
    async with get_pool().connection() as conn:
        org = await _require_org(conn, user["org_id"])
        progress = await repositories.get_onboarding(conn, user["org_id"])
        counts = await repositories.demo_counts(conn, user["org_id"])
        integrations = await repositories.list_integrations(conn, user["org_id"])
        approvals = await repositories.list_approvals(conn, user["org_id"], page=1, page_size=1)
        channels = await repositories.list_notification_channels(conn, user["org_id"])
        push = await repositories.list_push_subscriptions(conn, user["org_id"])
    manual = progress.get("steps") if isinstance(progress.get("steps"), dict) else {}
    inferred = {
        "branding": bool(org.get("brand_name")),
        "documents": counts["documents"] > 0,
        "suppliers": counts["suppliers"] > 0,
        "team": counts["users"] > 1,
        "integrations": bool(integrations),
        "approvals": bool(approvals["total"]),
        "notifications": any(channel.get("active") for channel in channels),
        "pwa": bool(push),
    }
    steps = {
        key: bool(inferred.get(key)) or bool(manual.get(key))
        for key, _label in ONBOARDING_STEPS
    }
    completed = sum(1 for value in steps.values() if value)
    return {
        "steps": steps,
        "labels": [{"key": key, "label": label, "done": steps[key]} for key, label in ONBOARDING_STEPS],
        "completed": completed,
        "total": len(ONBOARDING_STEPS),
        "percentage": round((completed / len(ONBOARDING_STEPS)) * 100),
        "dismissed": bool(progress.get("dismissed")),
        "demo_seeded": bool(manual.get("demo")),
    }


@router.patch("/onboarding")
async def update_onboarding(
    payload: OnboardingUpdate,
    user: dict = Depends(require_roles("owner", "admin", "analyst", "user")),
):
    async with get_pool().connection() as conn:
        return await repositories.update_onboarding(
            conn,
            org_id=user["org_id"],
            steps=payload.steps,
            dismissed=payload.dismissed,
            completed=payload.completed,
        )


@router.post("/onboarding/demo")
async def seed_demo_data(
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        existing = await repositories.get_document_by_hash(conn, user["org_id"], f"demo-{user['org_id']}")
        if existing is not None:
            return {"success": True, "already_seeded": True, "document_id": str(existing["id"])}

        supplier = await repositories.get_or_create_supplier(
            conn,
            org_id=user["org_id"],
            name="Proveedor Demo NEXORA",
            tax_id="76.000.000-0",
            email="demo@proveedor.cl",
        )
        document_id = uuid4()
        await repositories.create_document(
            conn,
            document_id=document_id,
            org_id=user["org_id"],
            supplier_id=supplier["id"],
            uploaded_by=user["id"],
            original_filename="demo-cotizacion.csv",
            storage_path=f"demo/{document_id}.csv",
            file_hash=f"demo-{user['org_id']}",
            mime_type="text/csv",
            file_size_bytes=0,
            doc_type="invoice",
            metadata={"demo": True},
        )
        items = [
            ("DEMO-001", "Tornillo acero inoxidable", "unidad", 120, Decimal("0.85"), "auto_approved"),
            ("DEMO-002", "Plancha acero 2mm", "kg", 80, Decimal("3.40"), "auto_approved"),
            ("DEMO-003", "Guantes de seguridad", "par", 40, Decimal("2.10"), "pending"),
        ]
        created_items = []
        for sku, description, unit, quantity, price, review_status in items:
            row = await repositories.insert_item(
                conn,
                org_id=user["org_id"],
                document_id=document_id,
                supplier_id=supplier["id"],
                sku=sku,
                original_description=description,
                normalized_description=description.lower(),
                original_unit=unit,
                base_unit=unit,
                unit_factor=Decimal("1"),
                quantity=Decimal(quantity),
                package_size=None,
                original_unit_price=price,
                normalized_unit_price=price,
                currency=user["default_currency"],
                price_date=date.today(),
                confidence=Decimal("0.92"),
                review_status=review_status,
                source_page=1,
                source_text=f"{sku} · {description}",
                metadata={"demo": True},
            )
            created_items.append(row)
        await repositories.create_exception(
            conn,
            org_id=user["org_id"],
            document_id=document_id,
            item_id=created_items[2]["id"],
            type="low_confidence",
            severity="medium",
            reason="Confianza de extracción bajo el umbral configurado.",
            evidence={"confidence": 0.55, "demo": True},
        )
        await repositories.create_exception(
            conn,
            org_id=user["org_id"],
            document_id=document_id,
            item_id=created_items[1]["id"],
            type="price_spike",
            severity="high",
            reason="Alza de precio detectada contra el histórico.",
            evidence={"historical_median": 2.80, "demo": True},
        )
        await repositories.mark_processed(
            conn,
            org_id=user["org_id"],
            document_id=document_id,
            supplier_id=supplier["id"],
            extraction_provider="demo",
            extraction_model="demo",
            raw_text="Datos demo generados por NEXORA",
            metadata={"demo": True, "item_count": len(items)},
        )
        progress = await repositories.get_onboarding(conn, user["org_id"])
        manual = progress.get("steps") if isinstance(progress.get("steps"), dict) else {}
        manual["demo"] = True
        await repositories.update_onboarding(
            conn,
            org_id=user["org_id"],
            steps=manual,
            dismissed=False,
            completed=False,
        )
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="onboarding.demo_seed",
            entity_type="organization",
            entity_id=str(user["org_id"]),
        )
    return {"success": True, "already_seeded": False, "document_id": str(document_id)}


@router.get("/security")
async def enterprise_security(user: CurrentUser):
    async with get_pool().connection() as conn:
        org = await _require_org(conn, user["org_id"])
        sessions = await repositories.list_user_sessions(conn, user["org_id"], limit=25)
        audit = await repositories.list_audit_events(conn, user["org_id"], page=1, page_size=1)
    return {
        "sso_enabled": bool(org.get("sso_enabled")),
        "sso_domain": org.get("sso_domain") or "",
        "sso_required": bool(org.get("sso_required")),
        "audit_retention_days": int(org.get("audit_retention_days") or 365),
        "sessions": sessions,
        "audit_events": audit["total"],
        "branding": _org_branding(org),
    }


@router.get("/branding")
async def get_branding(user: CurrentUser):
    async with get_pool().connection() as conn:
        org = await _require_org(conn, user["org_id"])
    return _org_branding(org)


@router.patch("/branding")
async def update_branding(
    payload: BrandingUpdate,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        org = await repositories.update_organization(
            conn,
            user["org_id"],
            payload.model_dump(exclude_unset=True),
        )
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="organization.branding",
            entity_type="organization",
            entity_id=str(user["org_id"]),
        )
    if org is None:
        raise HTTPException(status_code=404, detail="Organización no encontrada")
    return _org_branding(org)


@router.patch("/security")
async def update_security(
    payload: SecurityUpdate,
    user: dict = Depends(require_roles("owner", "admin")),
):
    if payload.sso_required and payload.sso_enabled is False:
        raise HTTPException(status_code=422, detail="SSO obligatorio requiere SSO habilitado.")
    async with get_pool().connection() as conn:
        org = await repositories.update_organization(
            conn,
            user["org_id"],
            payload.model_dump(exclude_unset=True),
        )
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="organization.security",
            entity_type="organization",
            entity_id=str(user["org_id"]),
        )
    if org is None:
        raise HTTPException(status_code=404, detail="Organización no encontrada")
    return {
        "sso_enabled": bool(org.get("sso_enabled")),
        "sso_domain": org.get("sso_domain") or "",
        "sso_required": bool(org.get("sso_required")),
        "audit_retention_days": int(org.get("audit_retention_days") or 365),
    }


@router.post("/security/purge-audit")
async def purge_audit(
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        org = await _require_org(conn, user["org_id"])
        deleted = await repositories.purge_audit_events(
            conn,
            user["org_id"],
            int(org.get("audit_retention_days") or 365),
        )
        await repositories.record_audit_event(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            action="audit.purge",
            entity_type="organization",
            entity_id=str(user["org_id"]),
            metadata={"deleted": deleted},
        )
    return {"success": True, "deleted": deleted}


@router.get("/sessions")
async def list_sessions(user: CurrentUser):
    async with get_pool().connection() as conn:
        return {"items": await repositories.list_user_sessions(conn, user["org_id"], limit=100)}


@router.get("/push/public-key")
async def push_public_key(user: CurrentUser):
    return {
        "enabled": bool(settings.vapid_public_key and settings.vapid_private_key),
        "public_key": settings.vapid_public_key,
    }


@router.post("/push/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe_push(payload: PushSubscriptionIn, user: CurrentUser):
    async with get_pool().connection() as conn:
        row = await repositories.save_push_subscription(
            conn,
            org_id=user["org_id"],
            user_id=user["id"],
            endpoint=payload.endpoint,
            endpoint_hash=_hash(payload.endpoint),
            p256dh=payload.p256dh,
            auth=payload.auth,
            user_agent="",
        )
    return row


@router.post("/push/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe_push(payload: PushUnsubscribeIn, user: CurrentUser):
    async with get_pool().connection() as conn:
        await repositories.delete_push_subscription(conn, user["id"], _hash(payload.endpoint))
    return None


@router.post("/push/test")
async def test_push(user: CurrentUser):
    if not (settings.vapid_public_key and settings.vapid_private_key):
        return {"configured": False, "sent": 0, "detail": "VAPID no configurado."}
    try:
        from pywebpush import webpush
    except ImportError:
        return {"configured": False, "sent": 0, "detail": "pywebpush no instalado."}

    async with get_pool().connection() as conn:
        subscriptions = await repositories.list_push_subscriptions(conn, user["org_id"])
    sent = 0
    errors = 0
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription["endpoint"],
                    "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]},
                },
                data=json.dumps({"title": "NEXORA", "body": "Notificaciones push activas."}),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
            )
            sent += 1
        except Exception:
            errors += 1
    return {"configured": True, "sent": sent, "errors": errors}


@inbound_router.post("/receive", status_code=status.HTTP_202_ACCEPTED)
async def receive_inbound_email(
    background_tasks: BackgroundTasks,
    token: str = Form(...),
    file: UploadFile = File(...),
    from_email: str = Form(default=""),
    doc_type: str = Form(default="invoice"),
):
    async with get_pool().connection() as conn:
        inbound = await repositories.get_inbound_token_by_hash(conn, _hash(token))
    if inbound is None:
        raise HTTPException(status_code=401, detail="Token de ingesta inválido o inactivo")
    if doc_type not in {"quote", "invoice", "price_list"}:
        raise HTTPException(status_code=422, detail="doc_type inválido")

    filename = file.filename or "documento"
    suffix = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Formato no permitido: {suffix or 'sin extensión'}")
    content = await file.read(settings.max_upload_bytes + 1)
    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"El archivo supera el límite de {settings.max_upload_mb} MB")

    import filetype

    kind = filetype.guess(content)
    mime_type = kind.mime if kind else (file.content_type or "application/octet-stream")
    file_hash = hashlib.sha256(content).hexdigest()
    org_id = inbound["org_id"]

    async with get_pool().connection() as conn:
        duplicate = await repositories.get_document_by_hash(conn, org_id, file_hash)
        if duplicate is not None:
            await repositories.touch_inbound_token(conn, inbound["id"])
            return {"success": True, "duplicate": True, "document_id": str(duplicate["id"])}
        billing = await repositories.get_billing(conn, org_id)
    if billing["usage"]["exceeded"]:
        raise HTTPException(status_code=403, detail="La organización alcanzó el límite de documentos de su plan.")

    document_id = uuid4()
    storage_path = await storage_service.save_document(
        org_id=org_id,
        document_id=document_id,
        filename=filename,
        content=content,
        mime_type=mime_type,
    )
    try:
        async with get_pool().connection() as conn:
            await repositories.create_document(
                conn,
                document_id=document_id,
                org_id=org_id,
                supplier_id=None,
                uploaded_by=None,
                original_filename=filename,
                storage_path=storage_path,
                file_hash=file_hash,
                mime_type=mime_type,
                file_size_bytes=len(content),
                doc_type=doc_type,
                metadata={"inbound_email": from_email},
            )
            await repositories.touch_inbound_token(conn, inbound["id"])
            await repositories.record_audit_event(
                conn,
                org_id=org_id,
                user_id=None,
                action="inbound_email.received",
                entity_type="document",
                entity_id=str(document_id),
                metadata={"from": from_email, "filename": filename},
            )
    except UniqueViolation:
        return {"success": True, "duplicate": True, "document_id": str(document_id)}
    if settings.process_in_background:
        background_tasks.add_task(document_service.process_document, document_id)
    return {"success": True, "duplicate": False, "document_id": str(document_id)}
