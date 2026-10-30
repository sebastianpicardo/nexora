from __future__ import annotations

import uuid
from uuid import UUID

from psycopg import AsyncConnection

from src.db.seeding import ensure_default_plans

PLAN_SELECT = """
    SELECT id, name, description, price_monthly, currency, document_limit, features, sort_order
    FROM plans
"""

SUBSCRIPTION_SELECT = """
    SELECT
        s.id,
        s.org_id,
        s.plan_id,
        s.status,
        s.current_period_start,
        s.current_period_end,
        s.trial_ends_at,
        p.name AS plan_name,
        p.document_limit,
        p.price_monthly,
        p.currency AS plan_currency,
        p.features
    FROM subscriptions s
    JOIN plans p ON p.id = s.plan_id
"""


async def list_plans(conn: AsyncConnection) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(f"{PLAN_SELECT} WHERE active = TRUE ORDER BY sort_order, price_monthly")
        return list(await cur.fetchall())


async def get_plan(conn: AsyncConnection, plan_id: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(f"{PLAN_SELECT} WHERE id = %s AND active = TRUE", (plan_id,))
        return await cur.fetchone()


async def ensure_subscription(conn: AsyncConnection, org_id: UUID | str) -> None:
    await ensure_default_plans(conn)
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO subscriptions (org_id, plan_id, status)
            VALUES (%s, 'free', 'active')
            ON CONFLICT (org_id) DO NOTHING
            """,
            (str(org_id),),
        )


async def get_subscription(conn: AsyncConnection, org_id: UUID | str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(f"{SUBSCRIPTION_SELECT} WHERE s.org_id = %s", (str(org_id),))
        return await cur.fetchone()


async def get_billing(conn: AsyncConnection, org_id: UUID | str) -> dict:
    subscription = await get_subscription(conn, org_id)
    if subscription is None:
        await ensure_subscription(conn, org_id)
        subscription = await get_subscription(conn, org_id)
    if subscription is None:
        # Fallback: devolver un plan free por defecto si algo falló
        from datetime import datetime, timedelta
        today = datetime.now().date()
        first_of_month = today.replace(day=1)
        end_of_month = (first_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        return {
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
                "warning": False,
                "exceeded": False,
            },
        }

    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE subscriptions
            SET current_period_start = date_trunc('month', current_date)::date,
                current_period_end = (date_trunc('month', current_date) + interval '1 month')::date
            WHERE org_id = %s AND current_period_end <= current_date
            """,
            (str(org_id),),
        )
        renewed = cur.rowcount > 0
    if renewed:
        subscription = await get_subscription(conn, org_id)
        if subscription is None:
            raise RuntimeError("No se pudo renovar la suscripción")

    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT count(*) AS total
            FROM documents_log
            WHERE org_id = %s
              AND created_at >= %s::date
              AND created_at < %s::date
            """,
            (
                str(org_id),
                subscription["current_period_start"],
                subscription["current_period_end"],
            ),
        )
        row = await cur.fetchone()
        used = int(row["total"]) if row else 0

    limit = subscription["document_limit"]
    unlimited = limit is None
    remaining = None if unlimited else max(int(limit) - used, 0)
    percentage = 0.0 if unlimited else round((used / int(limit)) * 100, 1) if int(limit) > 0 else 100.0

    return {
        "subscription": subscription,
        "usage": {
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "percentage": percentage,
            "unlimited": unlimited,
            "period_start": subscription["current_period_start"],
            "period_end": subscription["current_period_end"],
            "warning": not unlimited and percentage >= 80,
            "exceeded": not unlimited and used >= int(limit),
        },
    }


async def change_plan(conn: AsyncConnection, org_id: UUID | str, plan_id: str) -> dict | None:
    plan = await get_plan(conn, plan_id)
    if plan is None:
        return None

    await ensure_subscription(conn, org_id)
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE subscriptions
            SET plan_id = %s,
                status = 'active',
                current_period_start = date_trunc('month', current_date)::date,
                current_period_end = (date_trunc('month', current_date) + interval '1 month')::date
            WHERE org_id = %s
            RETURNING id
            """,
            (plan_id, str(org_id)),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return await get_billing(conn, org_id)


async def count_period_documents(conn: AsyncConnection, org_id: UUID | str) -> int:
    billing = await get_billing(conn, org_id)
    return int(billing["usage"]["used"])


async def get_platform_stats(conn: AsyncConnection) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                (SELECT count(*) FROM organizations) AS organizations_total,
                (SELECT count(*) FROM users WHERE active = TRUE) AS users_total,
                (SELECT count(*) FROM documents_log
                 WHERE created_at >= date_trunc('month', current_date)) AS documents_month,
                (SELECT count(*) FROM documents_log) AS documents_total,
                (SELECT count(*) FROM exceptions_log WHERE status = 'pending') AS exceptions_pending,
                (SELECT coalesce(sum(p.price_monthly), 0)
                 FROM subscriptions s
                 JOIN plans p ON p.id = s.plan_id
                 WHERE s.status = 'active') AS mrr
            """
        )
        row = await cur.fetchone()
    return dict(row) if row else {}


async def list_organization_overviews(conn: AsyncConnection) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                o.id,
                o.name,
                o.slug,
                o.created_at,
                coalesce(s.plan_id, 'free') AS plan_id,
                coalesce(p.name, 'Free') AS plan_name,
                coalesce(s.status, 'active') AS subscription_status,
                (SELECT count(*) FROM users u WHERE u.org_id = o.id AND u.active = TRUE) AS users_total,
                (SELECT count(*) FROM documents_log d WHERE d.org_id = o.id) AS documents_total,
                (SELECT count(*) FROM documents_log d
                 WHERE d.org_id = o.id
                   AND d.created_at >= date_trunc('month', current_date)) AS documents_month,
                (SELECT count(*) FROM exceptions_log e
                 WHERE e.org_id = o.id AND e.status = 'pending') AS exceptions_pending
            FROM organizations o
            LEFT JOIN subscriptions s ON s.org_id = o.id
            LEFT JOIN plans p ON p.id = s.plan_id
            ORDER BY o.created_at DESC
            """
        )
        return list(await cur.fetchall())
