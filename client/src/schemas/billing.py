from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlanOut(BaseModel):
    id: str
    name: str
    description: str
    price_monthly: float
    currency: str
    document_limit: int | None = None
    features: list[str] = []
    sort_order: int = 0


class SubscriptionOut(BaseModel):
    id: UUID | None = None
    plan_id: str
    plan_name: str
    status: str
    current_period_start: date
    current_period_end: date
    trial_ends_at: datetime | None = None


class UsageOut(BaseModel):
    used: int
    limit: int | None = None
    remaining: int | None = None
    percentage: float = 0
    unlimited: bool = False
    period_start: date
    period_end: date
    warning: bool = False
    exceeded: bool = False


class BillingSummary(BaseModel):
    subscription: SubscriptionOut
    usage: UsageOut
    plans: list[PlanOut]


class ChangePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1, max_length=40)
