from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import CurrentUser, is_org_admin, is_super_admin, require_roles
from src.core.config import settings
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.team import (
    AcceptInvitationRequest,
    InvitationOut,
    InviteRequest,
    MemberUpdateRequest,
    TeamMemberOut,
    TeamResponse,
)

router = APIRouter(prefix="/api/team", tags=["team"])

ADMIN_ROLES = {"owner", "admin", "super_admin"}


def _invite_url(token: str) -> str:
    return f"{settings.frontend_origin}/?invite={token}"


def _invitation_out(row: dict) -> InvitationOut:
    return InvitationOut(
        id=row["id"],
        email=row["email"],
        role=row["role"],
        status=row["status"],
        expires_at=row["expires_at"],
        created_at=row["created_at"],
        invite_url=_invite_url(row["token"]),
    )


async def _team_response(conn, user: dict) -> TeamResponse:
    members = await repositories.list_users(conn, user["org_id"])
    invitations = await repositories.list_invitations(conn, user["org_id"]) if is_org_admin(user) else []
    return TeamResponse(
        members=[TeamMemberOut.model_validate(row) for row in members],
        invitations=[_invitation_out(row) for row in invitations],
        permissions={"can_manage": is_org_admin(user)},
    )


@router.get("", response_model=TeamResponse)
async def get_team(user: CurrentUser):
    async with get_pool().connection() as conn:
        return await _team_response(conn, user)


@router.post("/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def invite_member(
    payload: InviteRequest,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        existing = await repositories.get_user_by_email(conn, payload.email)
        if existing is not None:
            if existing["org_id"] == user["org_id"]:
                raise HTTPException(status_code=409, detail="Ese email ya pertenece a tu equipo")
            raise HTTPException(
                status_code=409,
                detail="Ese email ya está asociado a otra organización",
            )

        pending = await repositories.get_pending_by_email(conn, user["org_id"], payload.email)
        if pending is not None:
            raise HTTPException(status_code=409, detail="Ya existe una invitación pendiente para ese email")

        row = await repositories.create_invitation(
            conn,
            org_id=user["org_id"],
            email=payload.email,
            role=payload.role,
            invited_by=user["id"],
        )
        return _invitation_out(row)


@router.patch("/members/{member_id}", response_model=TeamMemberOut)
async def update_member(
    member_id: UUID,
    payload: MemberUpdateRequest,
    user: dict = Depends(require_roles("owner", "admin")),
):
    if str(member_id) == str(user["id"]):
        raise HTTPException(status_code=409, detail="No puedes cambiar tu propio rol o estado")

    async with get_pool().connection() as conn:
        member = await repositories.get_member(conn, user["org_id"], member_id)
        if member is None:
            raise HTTPException(status_code=404, detail="Miembro no encontrado")

        if member["role"] in {"owner", "super_admin"} and not is_super_admin(user):
            raise HTTPException(
                status_code=403,
                detail="Solo un super administrador puede modificar al propietario de la organización",
            )

        becomes_limited = (payload.role is not None and payload.role not in ADMIN_ROLES) or payload.active is False
        if member["role"] in ADMIN_ROLES and becomes_limited:
            admins = await repositories.count_active_admins(conn, user["org_id"])
            if admins <= 1:
                raise HTTPException(
                    status_code=409,
                    detail="La organización debe conservar al menos un administrador activo",
                )

        updated = await repositories.update_member(
            conn,
            org_id=user["org_id"],
            user_id=member_id,
            role=payload.role,
            active=payload.active,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Miembro no encontrado")
        return TeamMemberOut.model_validate(updated)


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invitation_id: UUID,
    user: dict = Depends(require_roles("owner", "admin")),
):
    async with get_pool().connection() as conn:
        revoked = await repositories.revoke_invitation(conn, user["org_id"], invitation_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    return None


@router.post("/invitations/accept", response_model=TeamMemberOut)
async def accept_invitation(payload: AcceptInvitationRequest, user: CurrentUser):
    async with get_pool().connection() as conn:
        invitation = await repositories.get_invitation_by_token(conn, payload.token)
        if invitation is None:
            raise HTTPException(status_code=404, detail="Invitación inválida o expirada")
        if invitation["email"].lower() != user["email"].lower():
            raise HTTPException(status_code=403, detail="La invitación corresponde a otro email")
        if invitation["org_id"] != user["org_id"]:
            raise HTTPException(
                status_code=409,
                detail="Tu cuenta ya pertenece a otra organización. Contacta a un administrador.",
            )
        await repositories.mark_invitation_accepted(conn, invitation["id"])
        member = await repositories.get_member(conn, user["org_id"], user["id"])
        if member is None:
            raise HTTPException(status_code=404, detail="Miembro no encontrado")
        return TeamMemberOut.model_validate(member)
