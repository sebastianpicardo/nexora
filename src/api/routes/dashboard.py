from __future__ import annotations

import calendar
import uuid
from datetime import date

from fastapi import APIRouter

from src.api.deps import CurrentUser
from src.db import repositories
from src.db.pool import get_pool
from src.schemas.billing import UsageOut
from src.schemas.dashboard import CurrencySpend, DashboardSummary, MonthlyPurchase
from src.schemas.documents import DocumentOut
from src.schemas.exceptions import ExceptionOut

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _int(value) -> int:
    return int(value or 0)


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(user: CurrentUser):
    org_id = user["org_id"]
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    (SELECT count(*) FROM documents_log WHERE org_id = %s) AS documents_total,
                    (SELECT count(*) FROM documents_log
                     WHERE org_id = %s AND status = 'processed') AS documents_processed,
                    (SELECT count(*) FROM documents_log
                     WHERE org_id = %s AND status IN ('queued', 'processing')) AS documents_pending,
                    (SELECT count(*) FROM items_history WHERE org_id = %s) AS items_total,
                    (SELECT count(*) FROM exceptions_log
                     WHERE org_id = %s AND status = 'pending') AS exceptions_pending,
                    (SELECT count(*) FROM exceptions_log
                     WHERE org_id = %s AND status = 'pending' AND type = 'price_spike') AS price_alerts_pending
                """,
                (org_id, org_id, org_id, org_id, org_id, org_id),
            )
            counts = await cur.fetchone() or {}

            await cur.execute(
                """
                SELECT currency,
                       coalesce(sum(
                           coalesce(original_unit_price, normalized_unit_price, 0) * coalesce(quantity, 0)
                       ), 0) AS amount
                FROM items_history
                WHERE org_id = %s
                  AND review_status <> 'rejected'
                  AND price_date >= date_trunc('month', current_date)::date
                GROUP BY currency
                ORDER BY amount DESC
                """,
                (org_id,),
            )
            spend_rows = await cur.fetchall() or []

            await cur.execute(
                """
                WITH months AS (
                    SELECT generate_series(
                        date_trunc('month', current_date) - interval '5 months',
                        date_trunc('month', current_date),
                        interval '1 month'
                    )::date AS month
                )
                SELECT
                    to_char(m.month, 'YYYY-MM') AS month,
                    coalesce((
                        SELECT sum(
                            coalesce(i.original_unit_price, i.normalized_unit_price, 0) * coalesce(i.quantity, 0)
                        )
                        FROM items_history i
                        WHERE i.org_id = %s
                          AND i.currency = %s
                          AND i.review_status <> 'rejected'
                          AND i.price_date >= m.month
                          AND i.price_date < (m.month + interval '1 month')::date
                    ), 0) AS spend,
                    (
                        SELECT count(*)
                        FROM documents_log d
                        WHERE d.org_id = %s
                          AND d.created_at >= m.month
                          AND d.created_at < (m.month + interval '1 month')::date
                    ) AS documents,
                    (
                        SELECT count(*)
                        FROM exceptions_log e
                        WHERE e.org_id = %s
                          AND e.type = 'price_spike'
                          AND e.created_at >= m.month
                          AND e.created_at < (m.month + interval '1 month')::date
                    ) AS price_alerts
                FROM months m
                ORDER BY m.month
                """,
                (org_id, user["default_currency"], org_id, org_id),
            )
            monthly_rows = await cur.fetchall() or []

        documents = await repositories.list_documents(conn, org_id, page=1, page_size=5)
        exceptions = await repositories.list_exceptions(conn, org_id, status="pending", page=1, page_size=5)
        billing = await repositories.get_billing(conn, org_id)
        if billing is None:
            # Fallback: plan free por si la suscripción no existe
            today = date.today()
            first_of_month = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_of_month = today.replace(day=last_day)
            billing = {
                "subscription": {
                    "id": str(uuid.uuid4()),
                    "org_id": str(org_id),
                    "plan_id": "free",
                    "status": "active",
                    "current_period_start": first_of_month.isoformat(),
                    "current_period_end": end_of_month.isoformat(),
                },
                "usage": {
                    "used": 0,
                    "limit": 25,
                    "remaining": 25,
                    "percentage": 0.0,
                    "unlimited": False,
                    "period_start": first_of_month.isoformat(),
                    "period_end": end_of_month.isoformat(),
                },
            }

    monthly = []
    for row in monthly_rows:
        documents_count = _int(row.get("documents"))
        alerts = _int(row.get("price_alerts"))
        monthly.append(
            MonthlyPurchase(
                month=str(row.get("month") or ""),
                spend=float(row.get("spend") or 0),
                documents=documents_count,
                price_alerts=alerts,
                alert_rate=round((alerts / documents_count) * 100, 1) if documents_count else 0,
            )
        )

    return DashboardSummary(
        documents_total=_int(counts.get("documents_total")),
        documents_processed=_int(counts.get("documents_processed")),
        documents_pending=_int(counts.get("documents_pending")),
        items_total=_int(counts.get("items_total")),
        exceptions_pending=_int(counts.get("exceptions_pending")),
        price_alerts_pending=_int(counts.get("price_alerts_pending")),
        spend_by_currency=[
            CurrencySpend(currency=row["currency"], amount=float(row.get("amount") or 0)) for row in spend_rows
        ],
        monthly_purchases=monthly,
        quota=UsageOut(**billing["usage"]),
        recent_documents=[DocumentOut.model_validate(row) for row in documents["items"]],
        pending_exceptions=[ExceptionOut.model_validate(row) for row in exceptions["items"]],
    )
