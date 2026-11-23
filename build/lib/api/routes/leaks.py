from __future__ import annotations

import secrets as pysecrets
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.api.deps import CurrentUser, require_roles
from src.core.config import settings
from src.services import leak_audit_service as leaks
from src.services import (
    margin_guardian_service,
    purchase_optimizer_service,
    rcv_service,
    weekly_digest_service,
)

router = APIRouter(prefix="/api/leaks", tags=["leaks"])

MAX_RCV_BYTES = 25 * 1024 * 1024
RCV_SUFFIXES = (".csv", ".xlsx", ".xls", ".txt")


class OptimalCartItem(BaseModel):
    sku: str | None = None
    product: str | None = None
    quantity: float = Field(default=1, gt=0)


class OptimalPurchaseIn(BaseModel):
    items: list[OptimalCartItem] = Field(min_length=1)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    freight_by_supplier: dict[str, float] = Field(default_factory=dict)
    min_order_by_supplier: dict[str, float] = Field(default_factory=dict)


class WeeklyDigestIn(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    channel_id: str | None = Field(default=None, max_length=80)


@router.get("/audit")
async def audit(
    user: CurrentUser,
    days: int = Query(default=90, ge=7, le=365),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
) -> dict[str, Any]:
    return await leaks.build_audit(user, days=days, currency=currency)


@router.get("/audit.pdf")
async def audit_pdf(
    user: CurrentUser,
    days: int = Query(default=90, ge=7, le=365),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
):
    data = await leaks.build_audit(user, days=days, currency=currency)
    content = leaks.audit_to_pdf(data, org_name=str(user.get("org_name") or ""))
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="auditoria_express_nexora.pdf"'},
    )


@router.get("/comparator")
async def comparator(
    user: CurrentUser,
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=40, ge=1, le=100),
) -> dict[str, Any]:
    return await leaks.build_comparator(user, search=q, limit=limit)


@router.get("/negotiation")
async def negotiation(
    user: CurrentUser,
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    return await leaks.build_negotiation(user, limit=limit)


@router.get("/margin-guardian")
async def margin_guardian(
    user: CurrentUser,
    target_margin: float = Query(default=15, ge=0, le=90),
    min_margin: float = Query(default=8, ge=0, le=90),
) -> dict[str, Any]:
    return await margin_guardian_service.build_margin_guardian(
        user,
        target_margin=target_margin,
        min_margin=min_margin,
    )


@router.get("/margin-guardian.csv")
async def margin_guardian_export(
    user: CurrentUser,
    only_changes: bool = Query(default=False),
):
    filename, content, _rows = await margin_guardian_service.pos_export(
        user,
        only_changes=only_changes,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/optimal-purchase")
async def optimal_purchase(
    payload: OptimalPurchaseIn,
    user: CurrentUser,
) -> dict[str, Any]:
    try:
        return await purchase_optimizer_service.optimize_purchase(user, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/weekly-report")
async def weekly_report(user: CurrentUser) -> dict[str, Any]:
    return await leaks.build_weekly_report(user)


@router.post("/weekly-report/send")
async def send_weekly_report(
    payload: WeeklyDigestIn,
    user: dict = Depends(require_roles("owner", "admin")),
) -> dict[str, Any]:
    return await weekly_digest_service.send_weekly_digest(
        user,
        email=payload.email,
        channel_id=payload.channel_id,
    )


@router.post("/weekly-report/run")
async def run_weekly_report(
    org_id: str | None = Query(default=None, max_length=80),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
) -> dict[str, Any]:
    expected = settings.cron_secret
    if not expected or not x_cron_secret or not pysecrets.compare_digest(x_cron_secret, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Secreto de cron inválido.")
    return await weekly_digest_service.run_scheduled_digests(org_id)


@router.post("/rcv")
async def rcv_import(
    file: UploadFile = File(...),
    apply: bool = Form(default=False),
    user: dict = Depends(require_roles("owner", "admin", "analyst")),
) -> dict[str, Any]:
    filename = file.filename or "rcv.csv"
    if not filename.lower().endswith(RCV_SUFFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no soportado. Sube un archivo CSV o Excel del RCV.",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío.")
    if len(content) > MAX_RCV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El archivo supera el límite de 25 MB. Divídelo en partes.",
        )
    try:
        return await leaks.rcv_import(user, content, filename, apply=apply)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/rcv/register")
async def rcv_register(
    file: UploadFile = File(...),
    period: str | None = Form(default=None, max_length=7),
    user: dict = Depends(require_roles("owner", "admin", "analyst")),
) -> dict[str, Any]:
    filename = file.filename or "rcv.csv"
    if not filename.lower().endswith(RCV_SUFFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no soportado. Sube el Registro de Compras en CSV o Excel.",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío.")
    if len(content) > MAX_RCV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El archivo supera el límite de 25 MB. Divídelo por período.",
        )
    try:
        return await rcv_service.import_rcv_documents(
            user,
            content,
            filename,
            period=period,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/rcv/completeness")
async def rcv_completeness(
    user: CurrentUser,
    period: str | None = Query(default=None, max_length=7),
) -> dict[str, Any]:
    try:
        return await rcv_service.rcv_completeness(user, period=period)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
