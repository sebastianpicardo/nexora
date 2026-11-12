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


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)


async def price_opportunities(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    currency: str,
    days: int = 90,
    min_overprice_pct: float = 10.0,
    min_samples: int = 2,
    limit: int = 100,
) -> dict:
    days = max(1, min(int(days), 730))
    min_overprice_pct = max(0.0, min(float(min_overprice_pct), 1000.0))
    min_samples = max(1, int(min_samples))
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
                COALESCE(NULLIF(i.normalized_description, ''), i.sku) AS product_key
            FROM items_history i
            LEFT JOIN suppliers s ON s.id = i.supplier_id
            WHERE i.org_id = %s
              AND i.currency = %s
              AND i.review_status <> 'rejected'
              AND i.normalized_unit_price IS NOT NULL
              AND i.normalized_unit_price > 0
              AND i.price_date <= current_date
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
              AND h.base_unit IS NOT DISTINCT FROM r.base_unit
              AND h.price_date <= r.price_date
              AND h.price_date >= (r.price_date - (%s * interval '1 day'))
              AND (
                  h.normalized_description = r.normalized_description
                  OR (
                      h.supplier_id IS NOT DISTINCT FROM r.supplier_id
                      AND r.sku IS NOT NULL
                      AND h.sku = r.sku
                  )
              )
        ) hist
        LEFT JOIN LATERAL (
            SELECT s2.name AS supplier_name
            FROM items_history h2
            JOIN suppliers s2 ON s2.id = h2.supplier_id
            WHERE h2.org_id = %s
              AND h2.currency = %s
              AND h2.review_status <> 'rejected'
              AND h2.normalized_unit_price = hist.best_price
              AND h2.base_unit IS NOT DISTINCT FROM r.base_unit
              AND h2.price_date <= r.price_date
              AND h2.price_date >= (r.price_date - (%s * interval '1 day'))
              AND (
                  h2.normalized_description = r.normalized_description
                  OR (
                      h2.supplier_id IS NOT DISTINCT FROM r.supplier_id
                      AND r.sku IS NOT NULL
                      AND h2.sku = r.sku
                  )
              )
            ORDER BY s2.name
            LIMIT 1
        ) best ON TRUE
        WHERE hist.samples >= %s
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
                days,
                str(org_id),
                currency,
                days,
                min_samples,
                min_overprice_pct,
                limit,
            ),
        )
        rows = list(await cur.fetchall())

    items = []
    total_savings = 0.0
    total_savings_min = 0.0
    total_excess = 0.0
    suppliers: dict[str, float] = {}
    for row in rows:
        savings = _num(row.get("potential_savings"))
        savings_min = _num(row.get("excess_cost"))
        total_savings += savings
        total_savings_min += savings_min
        total_excess += savings_min
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
                "excess_cost": savings_min,
                "savings_min": savings_min,
                "savings_max": savings,
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
        "min_samples": min_samples,
        "summary": {
            "opportunities": len(items),
            "total_potential_savings": _round(total_savings),
            "total_conservative_savings": _round(total_savings_min),
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
            COALESCE(NULLIF(i.normalized_description, ''), i.sku) AS product_key,
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
          AND i.price_date <= current_date
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
    skipped_low_history = 0
    for bucket in grouped.values():
        months_sorted = sorted(bucket["months"].items())
        if not months_sorted:
            continue
        months_with_data = len(months_sorted)
        if months_with_data < 3:
            skipped_low_history += 1
            continue

        first_month = months_sorted[0][0]
        last_month = months_sorted[-1][0]
        span = (last_month.year - first_month.year) * 12 + (last_month.month - first_month.month) + 1
        quantities: list[float] = []
        spends: list[float] = []
        active_months: list[date] = []
        for offset in range(span):
            month = _add_months(first_month, offset)
            entry = bucket["months"].get(month)
            quantity = _num(entry.get("quantity")) if entry else 0.0
            spend = _num(entry.get("spend")) if entry else 0.0
            quantities.append(quantity)
            spends.append(spend)
            if entry:
                active_months.append(month)

        if sum(quantities) <= 0:
            continue

        avg_qty = mean(quantities)
        last_three = quantities[-3:]
        prev_three = quantities[-6:-3] if len(quantities) >= 6 else []
        recent_avg = mean(last_three)
        baseline_avg = mean(prev_three) if len(prev_three) == 3 else recent_avg
        trend_pct = (
            ((recent_avg - baseline_avg) / baseline_avg * 100)
            if len(prev_three) == 3 and baseline_avg > 0
            else 0.0
        )
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
                "months_with_data": months_with_data,
                "months_analyzed": span,
                "trend_confidence": "alta" if months_with_data >= 6 else "media",
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
            "skipped_low_history": skipped_low_history,
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
          AND i.price_date <= current_date
          AND i.price_date >= (date_trunc('month', current_date) - (%s * interval '1 month'))
        GROUP BY 1
        ORDER BY 1
    """
    increases_query = """
        WITH recent AS (
            SELECT
                COALESCE(NULLIF(i.normalized_description, ''), i.sku) AS product_key,
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
              AND i.price_date <= current_date
              AND i.price_date >= (current_date - interval '30 days')
            GROUP BY 1, 3
        ),
        baseline AS (
            SELECT
                COALESCE(NULLIF(i.normalized_description, ''), i.sku) AS product_key,
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
    basket_query = """
        WITH monthly_products AS (
            SELECT
                COALESCE(NULLIF(i.normalized_description, ''), i.sku) AS product_key,
                i.base_unit,
                date_trunc('month', i.price_date)::date AS month,
                AVG(i.normalized_unit_price) AS avg_price,
                SUM(COALESCE(i.normalized_unit_price, 0) * COALESCE(i.quantity, 0)) AS spend
            FROM items_history i
            WHERE i.org_id = %s
              AND i.currency = %s
              AND i.review_status <> 'rejected'
              AND i.normalized_unit_price IS NOT NULL
              AND i.normalized_unit_price > 0
              AND i.price_date <= current_date
              AND i.price_date >= (date_trunc('month', current_date) - (%s * interval '1 month'))
            GROUP BY 1, 2, 3
        ),
        bounds AS (
            SELECT MIN(month) AS first_month, MAX(month) AS last_month
            FROM monthly_products
        ),
        matched AS (
            SELECT
                b.product_key,
                b.base_unit,
                b.avg_price AS base_price,
                r.avg_price AS last_price,
                GREATEST(b.spend, r.spend, 1) AS weight
            FROM monthly_products b
            JOIN bounds p ON b.month = p.first_month
            JOIN monthly_products r
              ON r.product_key = b.product_key
             AND r.base_unit IS NOT DISTINCT FROM b.base_unit
             AND r.month = p.last_month
            WHERE p.first_month < p.last_month
              AND b.avg_price > 0
              AND r.avg_price > 0
        )
        SELECT
            COALESCE(
                SUM((last_price / base_price) * weight) / NULLIF(SUM(weight), 0) * 100,
                100
            ) AS price_index,
            COUNT(*) AS products
        FROM matched
    """
    async with conn.cursor() as cur:
        await cur.execute(monthly_query, (str(org_id), currency, months))
        monthly_rows = list(await cur.fetchall())

        await cur.execute(increases_query, (str(org_id), currency, str(org_id), currency))
        increase_rows = list(await cur.fetchall())

        await cur.execute(basket_query, (str(org_id), currency, months))
        basket = await cur.fetchone() or {}

        await cur.execute(
            """
            SELECT
                COUNT(DISTINCT COALESCE(NULLIF(normalized_description, ''), sku)) AS products,
                COUNT(DISTINCT supplier_id) FILTER (WHERE supplier_id IS NOT NULL) AS suppliers,
                COUNT(*) AS items,
                AVG(confidence) AS avg_confidence
            FROM items_history
            WHERE org_id = %s
              AND currency = %s
              AND review_status <> 'rejected'
              AND price_date <= current_date
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

    price_index = _round(_num(basket.get("price_index")) or 100.0)
    price_index_products = int(basket.get("products") or 0)
    change_pct = _round(price_index - 100.0)
    if price_index_products == 0:
        price_index = 100.0
        change_pct = 0.0

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
            "price_index_products": price_index_products,
            "price_index_basis": "canasta comparable ponderada por gasto",
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
    max_amount: float = 500000.0,
) -> dict:
    threshold = max(0.0, min(float(threshold), 1.0))
    days = max(1, min(int(days), 730))
    max_amount = max(0.0, float(max_amount))

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
            d.original_filename AS document_filename,
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
          AND i.price_date <= current_date
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
        eligible = confidence >= threshold and high_severity == 0 and amount <= max_amount
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
        "max_amount": max_amount,
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
    max_amount: float = 500000.0,
    item_ids: list[str] | None = None,
) -> list[str]:
    threshold = max(0.0, min(float(threshold), 1.0))
    max_amount = max(0.0, float(max_amount))
    filters = [
        "i.org_id = %s",
        "i.review_status = 'pending'",
        "i.confidence >= %s",
        """(
            COALESCE(i.normalized_unit_price, i.original_unit_price, 0)
            * COALESCE(i.quantity, 0)
        ) <= %s""",
        """
        NOT EXISTS (
            SELECT 1 FROM exceptions_log e
            WHERE e.item_id = i.id
              AND e.status = 'pending'
              AND e.severity IN ('high', 'critical')
        )
        """,
    ]
    values: list = [str(org_id), threshold, max_amount]

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
