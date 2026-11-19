from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from src.api.deps import CurrentUser, require_roles
from src.services import leak_audit_service as leaks

router = APIRouter(prefix="/api/leaks", tags=["leaks"])

MAX_RCV_BYTES = 25 * 1024 * 1024
RCV_SUFFIXES = (".csv", ".xlsx", ".xls", ".txt")


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


@router.get("/weekly-report")
async def weekly_report(user: CurrentUser) -> dict[str, Any]:
    return await leaks.build_weekly_report(user)


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
