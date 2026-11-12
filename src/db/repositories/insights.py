from __future__ import annotations

from datetime import date
from decimal import Decimal
from statistics import mean
from uuid import UUID

from psycopg import AsyncConnection, sql


def _num(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)


async def price_opportunities(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    currency: str,
    days: int = 90,
    min_overprice_pct: float = 10.0,
    limit: int = 100,
) -> dict:
    days = max(1, min(int(days), 730))
    min_overprice_pct = max(0.0, min(float(min_overprice_pct), 1000.0))
    limit = max(1, min(int(limit), 500))

    query = """
        SELECT
            r.id,
            r.document_id,
            r.supplier_id,
            r.supplier_name,
            r.sku,
            r.original_description,
            r.normalized_description,
            r.base_unit,
            r.currency,
            r.quantity,
            r.normalized_unit_price AS current_price,
            r.price_date,
            hist.median_price,
            hist.best_price,
            hist.samples,
            best.supplier_name AS best_supplier_name,
            CASE WHEN hist.median_price > 0
                 THEN ROUND(((r.normalized_unit_price - hist.median_price) / hist.median_price) * 100, 2)
                 ELSE 0 END AS overprice_pct,
            GREATEST(r.normalized_unit_price - hist.median_price, 0) * COALESCE(r.quantity, 0) AS excess_cost,
            GREATEST(r.normalized_unit_price - hist.best_price, 0) * COALESCE(r.quantity, 0) AS potential_savings
        FROM (
            SELECT
                i.*,
                s.name AS supplier_name,
                COALESCE(i.sku, i.normalized_description) AS product_key
            FROM items_history i
            LEFT JOIN suppliers s ON s.id = i.supplier_id
            WHERE i.org_id = %s
              AND i.currency = %s
              AND i.review_status <> 'rejected'
              AND i.normalized_unit_price IS NOT NULL
              AND i.normalized_unit_price > 0
              AND i.price_date >= (current_date - (%s * interval '1 day'))
        ) r
        CROSS JOIN LATERAL (
            SELECT
                percentile_cont(0.5) WITHIN GROUP (ORDER BY h.normalized_unit_price::double precision)::numeric
                    AS median_price,
                MIN(h.normalized_unit_price) AS best_price,
                COUNT(*) AS samples
            FROM items_history h
            WHERE h.org_id = %s
              AND h.currency = %s
              AND h.review_status <> 'rejected'
              AND h.normalized_unit_price IS NOT NULL
              AND h.normalized_unit_price > 0
              AND h.document_id <> r.document_id
              AND COALESCE(h.sku, h.normalized_description) = r.product_key
              AND h.base_unit IS NOT DISTINCT FROM r.base_unit
        ) hist
        LEFT JOIN LATERAL (
            SELECT s2.name AS supplier_name
            FROM items_history h2
            JOIN suppliers s2 ON s2.id = h2.supplier_id
            WHERE h2.org_id = %s
              AND h2.currency = %s
              AND h2.review_status <> 'rejected'
              AND h2.normalized_unit_price = hist.best_price
              AND COALESCE(h2.sku, h2.normalized_description) = r.product_key
              AND h2.base_unit IS NOT DISTINCT FROM r.base_unit
            ORDER BY s2.name
            LIMIT 1
        ) best ON TRUE
        WHERE hist.samples >= 1
          AND hist.median_price > 0
          AND ((r.normalized_unit_price - hist.median_price) / hist.median_price) * 100 >= %s
        ORDER BY potential_savings DESC, overprice_pct DESC
        LIMIT %s
    """
    async with conn.cursor() as cur:
        await cur.execute(
            query,
            (
                str(org_id),
                currency,
                days,
                str(org_id),
                currency,
                str(org_id),
                currency,
                min_overprice_pct,
                limit,
            ),
        )
        rows = list(await cur.fetchall())

    items = []
    total_savings = 0.0
    total_excess = 0.0
    suppliers: dict[str, float] = {}
    for row in rows:
        savings = _num(row.get("potential_savings"))
        total_savings += savings
        total_excess += _num(row.get("excess_cost"))
        supplier_name = row.get("supplier_name") or "Sin proveedor"
        suppliers[supplier_name] = suppliers.get(supplier_name, 0.0) + savings
        items.append(
            {
                "id": str(row["id"]),
                "document_id": str(row["document_id"]),
                "supplier_id": str(row["supplier_id"]) if row.get("supplier_id") else None,
                "supplier_name": row.get("supplier_name"),
                "sku": row.get("sku"),
                "original_description": row.get("original_description"),
                "normalized_description": row.get("normalized_description"),
                "base_unit": row.get("base_unit"),
                "currency": row.get("currency"),
                "quantity": _num(row.get("quantity")),
                "current_price": _num(row.get("current_price")),
                "median_price": _num(row.get("median_price")),
                "best_price": _num(row.get("best_price")),
                "best_supplier_name": row.get("best_supplier_name"),
                "overprice_pct": _num(row.get("overprice_pct")),
                "excess_cost": _num(row.get("excess_cost")),
                "potential_savings": savings,
                "samples": int(row.get("samples") or 0),
                "price_date": row["price_date"].isoformat() if row.get("price_date") else None,
            }
        )

    top_suppliers = sorted(
        (
            {"supplier_name": name, "potential_savings": _round(value)}
            for name, value in suppliers.items()
            if value > 0
        ),
        key=lambda entry: entry["potential_savings"],
        reverse=True,
    )[:5]

    return {
        "currency": currency,
        "days": days,
        "min_overprice_pct": min_overprice_pct,
        "summary": {
            "opportunities": len(items),
            "total_potential_savings": _round(total_savings),
            "total_excess_cost": _round(total_excess),
            "suppliers_affected": len([value for value in suppliers.values() if value > 0]),
        },
        "top_suppliers": top_suppliers,
        "items": items,
    }


async def consumption_forecast(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    currency: str,
    history_months: int = 6,
    horizon: int = 1,
    limit: int = 100,
) -> dict:
    history_months = max(2, min(int(history_months), 24))
    horizon = max(1, min(int(horizon), 6))
    limit = max(1, min(int(limit), 500))

    query = """
        SELECT
            COALESCE(i.sku, i.normalized_description) AS product_key,
            (array_agg(i.original_description ORDER BY i.price_date DESC))[1] AS description,
            i.base_unit,
            i.currency,
            date_trunc('month', i.price_date)::date AS month,
            SUM(COALESCE(i.quantity, 0)) AS quantity,
            SUM(COALESCE(i.normalized_unit_price, 0) * COALESCE(i.quantity, 0)) AS spend,
            AVG(i.normalized_unit_price) AS avg_price
        FROM items_history i
        WHERE i.org_id = %s
          AND i.currency = %s
          AND i.review_status <> 'rejected'
          AND i.price_date >= (date_trunc('month', current_date) - (%s * interval '1 month'))
        GROUP BY 1, 3, 4, 5
        ORDER BY 1, 5
    """
    async with conn.cursor() as cur:
        await cur.execute(query, (str(org_id), currency, history_months))
        rows = list(await cur.fetchall())

    current_month = date.today().replace(day=1)
    grouped: dict[tuple[str, str | None], dict] = {}
    for row in rows:
        month = row.get("month")
        if month is None:
            continue
        if month == current_month:
            continue
        key = (row["product_key"], row.get("base_unit"))
        bucket = grouped.setdefault(
            key,
            {
                "product_key": row["product_key"],
                "description": row.get("description"),
                "base_unit": row.get("base_unit"),
                "currency": row.get("currency"),
                "months": {},
            },
        )
        bucket["months"][month] = {
            "quantity": _num(row.get("quantity")),
            "spend": _num(row.get("spend")),
            "avg_price": _num(row.get("avg_price")),
        }

    items = []
    for bucket in grouped.values():
        months_sorted = sorted(bucket["months"].items())
        if not months_sorted:
            continue
        quantities = [entry[1]["quantity"] for entry in months_sorted]
        spends = [entry[1]["spend"] for entry in months_sorted]
        active_months = [entry[0] for entry in months_sorted if entry[1]["quantity"] > 0]
        if not quantities or sum(quantities) <= 0:
            continue

        avg_qty = mean(quantities)
        last_three = quantities[-3:]
        prev_three = quantities[-6:-3] if len(quantities) > 3 else quantities[:-3]
        recent_avg = mean(last_three)
        baseline_avg = mean(prev_three) if prev_three else recent_avg
        trend_pct = ((recent_avg - baseline_avg) / baseline_avg * 100) if baseline_avg > 0 else 0.0
        trend_factor = max(-0.3, min(0.3, trend_pct / 100))
        projected_monthly = max(0.0, recent_avg * (1 + trend_factor))
        projected_qty = projected_monthly * horizon
        total_qty = sum(quantities)
        total_spend = sum(spends)
        unit_cost = total_spend / total_qty if total_qty > 0 else 0.0
        projected_spend = projected_qty * unit_cost
        last_purchase = active_months[-1].isoformat() if active_months else None

        if trend_pct >= 15:
            trend_label = "sube_fuerte"
        elif trend_pct >= 3:
            trend_label = "sube"
        elif trend_pct <= -15:
            trend_label = "baja_fuerte"
        elif trend_pct <= -3:
            trend_label = "baja"
        else:
            trend_label = "estable"

        items.append(
            {
                "product_key": bucket["product_key"],
                "description": bucket["description"],
                "base_unit": bucket["base_unit"],
                "currency": bucket["currency"],
                "months_with_data": len(months_sorted),
                "avg_monthly_quantity": _round(avg_qty, 2),
                "recent_monthly_quantity": _round(recent_avg, 2),
                "trend_pct": _round(trend_pct, 2),
                "trend": trend_label,
                "projected_quantity": _round(projected_qty, 2),
                "unit_cost": _round(unit_cost, 4),
                "projected_spend": _round(projected_spend, 2),
                "last_purchase": last_purchase,
            }
        )

    items.sort(key=lambda entry: entry["projected_spend"], reverse=True)
    top_items = items[:limit]
    total_projected = sum(entry["projected_spend"] for entry in items)
    rising = len([entry for entry in items if entry["trend"] in {"sube", "sube_fuerte"}])

    return {
        "currency": currency,
        "history_months": history_months,
        "horizon": horizon,
        "summary": {
            "products": len(items),
            "projected_spend": _round(total_projected),
            "products_rising": rising,
            "products_falling": len([entry for entry in items if entry["trend"] in {"baja", "baja_fuerte"}]),
        },
        "items": top_items,
    }


async def analytics_overview(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    currency: str,
    months: int = 6,
) -> dict:
    months = max(1, min(int(months), 24))

    monthly_query = """
        SELECT
            to_char(date_trunc('month', i.price_date), 'YYYY-MM') AS month,
            SUM(COALESCE(i.normalized_unit_price, 0) * COALESCE(i.quantity, 0)) AS spend,
            COUNT(*) AS items,
            AVG(i.normalized_unit_price) AS avg_price
        FROM items_history i
        WHERE i.org_id = %s
          AND i.currency = %s
          AND i.review_status <> 'rejected'
          AND i.price_date >= (date_trunc('month', current_date) - (%s * interval '1 month'))
        GROUP BY 1
        ORDER BY 1
    """
    increases_query = """
        WITH recent AS (
            SELECT
                COALESCE(i.sku, i.normalized_description) AS product_key,
                (array_agg(i.original_description ORDER BY i.price_date DESC))[1] AS description,
                i.base_unit,
                AVG(i.normalized_unit_price) AS avg_price,
                SUM(COALESCE(i.quantity, 0)) AS quantity,
                SUM(COALESCE(i.normalized_unit_price, 0) * COALESCE(i.quantity, 0)) AS spend
            FROM items_history i
            WHERE i.org_id = %s
              AND i.currency = %s
              AND i.review_status <> 'rejected'
              AND i.normalized_unit_price IS NOT NULL
              AND i.price_date >= (current_date - interval '30 days')
            GROUP BY 1, 3
        ),
        baseline AS (
            SELECT
                COALESCE(i.sku, i.normalized_description) AS product_key,
                i.base_unit,
                AVG(i.normalized_unit_price) AS avg_price
            FROM items_history i
            WHERE i.org_id = %s
              AND i.currency = %s
              AND i.review_status <> 'rejected'
              AND i.normalized_unit_price IS NOT NULL
              AND i.price_date >= (current_date - interval '120 days')
              AND i.price_date < (current_date - interval '30 days')
            GROUP BY 1, 2
        )
        SELECT
            r.product_key,
            r.description,
            r.base_unit,
            r.avg_price AS recent_price,
            b.avg_price AS baseline_price,
            CASE WHEN b.avg_price > 0
                 THEN ROUND(((r.avg_price - b.avg_price) / b.avg_price) * 100, 2)
                 ELSE 0 END AS change_pct,
            r.quantity,
            r.spend
        FROM recent r
        JOIN baseline b
          ON b.product_key = r.product_key
         AND b.base_unit IS NOT DISTINCT FROM r.base_unit
        WHERE b.avg_price > 0
        ORDER BY change_pct DESC
        LIMIT 10
    """
    async with conn.cursor() as cur:
        await cur.execute(monthly_query, (str(org_id), currency, months))
        monthly_rows = list(await cur.fetchall())

        await cur.execute(increases_query, (str(org_id), currency, str(org_id), currency))
        increase_rows = list(await cur.fetchall())

        await cur.execute(
            """
            SELECT
                COUNT(DISTINCT COALESCE(sku, normalized_description)) AS products,
                COUNT(DISTINCT supplier_id) FILTER (WHERE supplier_id IS NOT NULL) AS suppliers,
                COUNT(*) AS items,
                AVG(confidence) AS avg_confidence
            FROM items_history
            WHERE org_id = %s
              AND currency = %s
              AND review_status <> 'rejected'
              AND price_date >= (date_trunc('month', current_date) - (%s * interval '1 month'))
            """,
            (str(org_id), currency, months),
        )
        totals = await cur.fetchone() or {}

    monthly = [
        {
            "month": row["month"],
            "spend": _round(_num(row.get("spend"))),
            "items": int(row.get("items") or 0),
            "avg_price": _round(_num(row.get("avg_price")), 4),
        }
        for row in monthly_rows
    ]

    price_index = 100.0
    if len(monthly) >= 2 and monthly[0]["avg_price"] > 0:
        price_index = round((monthly[-1]["avg_price"] / monthly[0]["avg_price"]) * 100, 2)

    change_pct = 0.0
    if len(monthly) >= 2 and monthly[0]["avg_price"] > 0:
        change_pct = round(((monthly[-1]["avg_price"] - monthly[0]["avg_price"]) / monthly[0]["avg_price"]) * 100, 2)

    top_increases = [
        {
            "product_key": row["product_key"],
            "description": row.get("description"),
            "base_unit": row.get("base_unit"),
            "recent_price": _round(_num(row.get("recent_price")), 4),
            "baseline_price": _round(_num(row.get("baseline_price")), 4),
            "change_pct": _round(_num(row.get("change_pct")), 2),
            "quantity": _round(_num(row.get("quantity"))),
            "spend": _round(_num(row.get("spend"))),
        }
        for row in increase_rows
    ]

    return {
        "currency": currency,
        "months": months,
        "summary": {
            "products": int(totals.get("products") or 0),
            "suppliers": int(totals.get("suppliers") or 0),
            "items": int(totals.get("items") or 0),
            "avg_confidence": _round(_num(totals.get("avg_confidence")), 4),
            "price_index": price_index,
            "price_change_pct": change_pct,
        },
        "monthly": monthly,
        "top_increases": top_increases,
    }


async def approval_queue(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    currency: str,
    threshold: float = 0.9,
    days: int = 120,
) -> dict:
    threshold = max(0.0, min(float(threshold), 1.0))
    days = max(1, min(int(days), 730))

    query = """
        SELECT
            i.id,
            i.document_id,
            i.supplier_id,
            s.name AS supplier_name,
            i.sku,
            i.original_description,
            i.normalized_description,
            i.base_unit,
            i.quantity,
            i.normalized_unit_price,
            i.original_unit_price,
            i.currency,
            i.confidence,
            i.price_date,
            d.original_filename,
            COUNT(e.id) FILTER (WHERE e.status = 'pending') AS pending_exceptions,
            COUNT(e.id) FILTER (
                WHERE e.status = 'pending' AND e.severity IN ('high', 'critical')
            ) AS high_severity_exceptions
        FROM items_history i
        LEFT JOIN suppliers s ON s.id = i.supplier_id
        JOIN documents_log d ON d.id = i.document_id
        LEFT JOIN exceptions_log e ON e.item_id = i.id
        WHERE i.org_id = %s
          AND i.currency = %s
          AND i.review_status = 'pending'
          AND i.price_date >= (current_date - (%s * interval '1 day'))
        GROUP BY i.id, s.name, d.original_filename
        ORDER BY i.confidence DESC, i.price_date DESC
        LIMIT 300
    """
    async with conn.cursor() as cur:
        await cur.execute(query, (str(org_id), currency, days))
        rows = list(await cur.fetchall())

    items = []
    auto_eligible = 0
    auto_amount = 0.0
    review_amount = 0.0
    for row in rows:
        confidence = _num(row.get("confidence"))
        high_severity = int(row.get("high_severity_exceptions") or 0)
        pending_exceptions = int(row.get("pending_exceptions") or 0)
        amount = _num(row.get("normalized_unit_price") or row.get("original_unit_price")) * _num(
            row.get("quantity")
        )
        eligible = confidence >= threshold and high_severity == 0
        if eligible:
            auto_eligible += 1
            auto_amount += amount
        else:
            review_amount += amount
        items.append(
            {
                "id": str(row["id"]),
                "document_id": str(row["document_id"]),
                "document_filename": row.get("document_filename"),
                "supplier_name": row.get("supplier_name"),
                "sku": row.get("sku"),
                "description": row.get("original_description"),
                "base_unit": row.get("base_unit"),
                "quantity": _round(_num(row.get("quantity")), 2),
                "unit_price": _round(_num(row.get("normalized_unit_price") or row.get("original_unit_price")), 4),
                "currency": row.get("currency"),
                "amount": _round(amount),
                "confidence": _round(confidence, 4),
                "pending_exceptions": pending_exceptions,
                "high_severity_exceptions": high_severity,
                "auto_eligible": eligible,
                "price_date": row["price_date"].isoformat() if row.get("price_date") else None,
            }
        )

    return {
        "currency": currency,
        "threshold": threshold,
        "days": days,
        "summary": {
            "pending": len(items),
            "auto_eligible": auto_eligible,
            "needs_review": len(items) - auto_eligible,
            "auto_amount": _round(auto_amount),
            "review_amount": _round(review_amount),
        },
        "items": items,
    }


async def auto_approve_items(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    threshold: float,
    item_ids: list[str] | None = None,
) -> list[str]:
    threshold = max(0.0, min(float(threshold), 1.0))
    filters = [
        "i.org_id = %s",
        "i.review_status = 'pending'",
        "i.confidence >= %s",
        """
        NOT EXISTS (
            SELECT 1 FROM exceptions_log e
            WHERE e.item_id = i.id
              AND e.status = 'pending'
              AND e.severity IN ('high', 'critical')
        )
        """,
    ]
    values: list = [str(org_id), threshold]

    if item_ids:
        placeholders = ", ".join(["%s"] * len(item_ids))
        filters.append(f"i.id IN ({placeholders})")
        values.extend([str(item_id) for item_id in item_ids])

    query = sql.SQL(
        "UPDATE items_history i SET review_status = 'auto_approved' WHERE {} RETURNING i.id"
    ).format(sql.SQL(" AND ").join(sql.SQL(fragment) for fragment in filters))

    async with conn.cursor() as cur:
        await cur.execute(query, values)
        rows = list(await cur.fetchall())
    return [str(row["id"]) for row in rows]
