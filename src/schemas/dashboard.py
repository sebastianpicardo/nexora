from __future__ import annotations

from pydantic import BaseModel

from src.schemas.billing import UsageOut
from src.schemas.documents import DocumentOut
from src.schemas.exceptions import ExceptionOut


class CurrencySpend(BaseModel):
    currency: str
    amount: float


class MonthlyPurchase(BaseModel):
    month: str
    spend: float
    documents: int
    price_alerts: int
    alert_rate: float


class DashboardSummary(BaseModel):
    documents_total: int
    documents_processed: int
    documents_pending: int
    items_total: int
    exceptions_pending: int
    price_alerts_pending: int
    spend_by_currency: list[CurrencySpend]
    monthly_purchases: list[MonthlyPurchase] = []
    quota: UsageOut | None = None
    recent_documents: list[DocumentOut]
    pending_exceptions: list[ExceptionOut]
