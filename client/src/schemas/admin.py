from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AdminStats(BaseModel):
    organizations_total: int
    users_total: int
    documents_month: int
    documents_total: int
    exceptions_pending: int
    mrr: float


class AdminOrganizationOut(BaseModel):
    id: UUID
    name: str
    slug: str
    plan_id: str
    plan_name: str
    subscription_status: str
    users_total: int
    documents_total: int
    documents_month: int
    exceptions_pending: int
    created_at: datetime


class AdminOverview(BaseModel):
    stats: AdminStats
    organizations: list[AdminOrganizationOut]
