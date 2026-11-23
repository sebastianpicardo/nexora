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


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1, max_length=40)


class CheckoutOut(BaseModel):
    provider: str
    session_id: str
    checkout_url: str
    plan_id: str
    amount: float
    currency: str


class InvoiceOut(BaseModel):
    id: UUID
    provider: str
    provider_invoice_id: str | None = None
    amount: float
    currency: str
    status: str
    period_start: date | None = None
    period_end: date | None = None
    paid_at: datetime | None = None
    created_at: datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceOut]


class WebhookAck(BaseModel):
    success: bool = True
    received: bool = True
    duplicate: bool = False
