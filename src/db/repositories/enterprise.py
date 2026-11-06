from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

ROI_MONTHS = 6


async def get_roi(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    currency: str,
    months: int = ROI_MONTHS,
) -> dict:
    months = max(1, min(int(months), 24))
    median_expr = """
        CASE
            WHEN jsonb_typeof(e.evidence->'historical_median') = 'number'
            THEN (e.evidence->>'historical_median')::numeric
            ELSE 0
        END
    """
    savings_expr = f"""
        GREATEST(COALESCE(i.normalized_unit_price, 0) - COALESCE({median_expr}, 0), 0)
        * GREATEST(COALESCE(i.quantity, 0), 0)
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                COALESCE(SUM(
                    COALESCE(i.original_unit_price, i.normalized_unit_price, 0)
                    * COALESCE(i.quantity, 0)
                ), 0) AS audited_spend,
                COUNT(DISTINCT i.document_id) AS documents,
                COUNT(DISTINCT i.supplier_id) FILTER (WHERE i.supplier_id IS NOT NULL) AS suppliers,
                COUNT(*) AS items,
                COALESCE(AVG(i.confidence), 0) AS avg_confidence
            FROM items_history i
            WHERE i.org_id = %s
              AND i.currency = %s
              AND i.review_status <> 'rejected'
              AND i.price_date >= (date_trunc('month', current_date) - interval '1 month' * %s)::date
            """,
            (str(org_id), currency, months),
        )
        totals = await cur.fetchone() or {}

        await cur.execute(
            f"""
            SELECT
                COALESCE(SUM(
                    CASE WHEN e.status IN ('approved', 'resolved') THEN {savings_expr} ELSE 0 END
                ), 0) AS estimated_savings,
                COALESCE(SUM(
                    CASE WHEN e.status = 'pending' THEN {savings_expr} ELSE 0 END
                ), 0) AS potential_exposure,
                COUNT(*) FILTER (WHERE e.status = 'pending') AS pending_exceptions,
                COUNT(*) FILTER (WHERE e.status IN ('approved', 'resolved')) AS resolved_exceptions
            FROM exceptions_log e
            LEFT JOIN items_history i ON i.id = e.item_id
            WHERE e.org_id = %s
              AND e.type = 'price_spike'
              AND e.created_at >= (date_trunc('month', current_date) - interval '1 month' * %s)
              AND (i.currency = %s OR i.currency IS NULL)
            """,
            (str(org_id), months, currency),
        )
        exception_totals = await cur.fetchone() or {}

        await cur.execute(
            f"""
            WITH months AS (
                SELECT generate_series(
                    date_trunc('month', current_date) - interval '1 month' * (%s - 1),
                    date_trunc('month', current_date),
                    interval '1 month'
                )::date AS month
            )
            SELECT
                to_char(m.month, 'YYYY-MM') AS month,
                COALESCE((
                    SELECT SUM(
                        COALESCE(i.original_unit_price, i.normalized_unit_price, 0)
                        * COALESCE(i.quantity, 0)
                    )
                    FROM items_history i
                    WHERE i.org_id = %s
                      AND i.currency = %s
                      AND i.review_status <> 'rejected'
                      AND i.price_date >= m.month
                      AND i.price_date < (m.month + interval '1 month')::date
                ), 0) AS spend,
                COALESCE((
                    SELECT SUM({savings_expr})
                    FROM exceptions_log e
                    LEFT JOIN items_history i ON i.id = e.item_id
                    WHERE e.org_id = %s
                      AND e.type = 'price_spike'
                      AND e.status IN ('approved', 'resolved')
                      AND e.created_at >= m.month
                      AND e.created_at < (m.month + interval '1 month')
                      AND (i.currency = %s OR i.currency IS NULL)
                ), 0) AS savings,
                (
                    SELECT COUNT(*)
                    FROM exceptions_log e
                    WHERE e.org_id = %s
                      AND e.type = 'price_spike'
                      AND e.created_at >= m.month
                      AND e.created_at < (m.month + interval '1 month')
                ) AS price_alerts,
                (
                    SELECT COUNT(*)
                    FROM documents_log d
                    WHERE d.org_id = %s
                      AND d.created_at >= m.month
                      AND d.created_at < (m.month + interval '1 month')
                ) AS documents
            FROM months m
            ORDER BY m.month
            """,
            (months, str(org_id), currency, str(org_id), currency, str(org_id), str(org_id)),
        )
        monthly = list(await cur.fetchall())

    documents = int(totals.get("documents") or 0)
    resolved = int(exception_totals.get("resolved_exceptions") or 0)
    savings = float(exception_totals.get("estimated_savings") or 0)
    spend = float(totals.get("audited_spend") or 0)
    return {
        "currency": currency,
        "months": months,
        "audited_spend": spend,
        "documents": documents,
        "suppliers": int(totals.get("suppliers") or 0),
        "items": int(totals.get("items") or 0),
        "avg_confidence": float(totals.get("avg_confidence") or 0),
        "estimated_savings": savings,
        "potential_exposure": float(exception_totals.get("potential_exposure") or 0),
        "pending_exceptions": int(exception_totals.get("pending_exceptions") or 0),
        "resolved_exceptions": resolved,
        "manual_hours_saved": round(documents * 0.25 + resolved * 0.08, 1),
        "savings_rate_pct": round((savings / spend) * 100, 2) if spend else 0,
        "monthly": [
            {
                "month": row["month"],
                "spend": float(row.get("spend") or 0),
                "savings": float(row.get("savings") or 0),
                "price_alerts": int(row.get("price_alerts") or 0),
                "documents": int(row.get("documents") or 0),
            }
            for row in monthly
        ],
    }


async def list_supplier_scorecards(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    currency: str,
    limit: int = 50,
) -> list[dict]:
    median_expr = """
        CASE
            WHEN jsonb_typeof(e.evidence->'historical_median') = 'number'
            THEN (e.evidence->>'historical_median')::numeric
            ELSE 0
        END
    """
    savings_expr = f"""
        GREATEST(COALESCE(i.normalized_unit_price, 0) - COALESCE({median_expr}, 0), 0)
        * GREATEST(COALESCE(i.quantity, 0), 0)
    """
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            WITH item_stats AS (
                SELECT
                    i.supplier_id,
                    COUNT(DISTINCT i.document_id) AS documents,
                    COUNT(*) AS items,
                    COALESCE(SUM(
                        COALESCE(i.normalized_unit_price, 0) * COALESCE(i.quantity, 0)
                    ), 0) AS spend,
                    COALESCE(AVG(i.confidence), 0) AS avg_confidence
                FROM items_history i
                WHERE i.org_id = %s
                  AND i.currency = %s
                  AND i.review_status <> 'rejected'
                  AND i.supplier_id IS NOT NULL
                GROUP BY i.supplier_id
            ),
            exception_stats AS (
                SELECT
                    i.supplier_id,
                    COUNT(*) AS total_exceptions,
                    COUNT(*) FILTER (WHERE e.status = 'pending') AS pending_exceptions,
                    COUNT(*) FILTER (WHERE e.type = 'price_spike') AS price_alerts,
                    COALESCE(SUM(
                        CASE WHEN e.status IN ('approved', 'resolved') THEN {savings_expr} ELSE 0 END
                    ), 0) AS savings
                FROM exceptions_log e
                JOIN items_history i ON i.id = e.item_id
                WHERE e.org_id = %s AND i.currency = %s
                GROUP BY i.supplier_id
            ),
            scored AS (
                SELECT
                    s.id,
                    s.name,
                    COALESCE(st.documents, 0) AS documents,
                    COALESCE(st.items, 0) AS items,
                    COALESCE(st.spend, 0) AS spend,
                    COALESCE(st.avg_confidence, 0) AS avg_confidence,
                    COALESCE(ex.total_exceptions, 0) AS total_exceptions,
                    COALESCE(ex.pending_exceptions, 0) AS pending_exceptions,
                    COALESCE(ex.price_alerts, 0) AS price_alerts,
                    COALESCE(ex.savings, 0) AS savings,
                    GREATEST(
                        0,
                        LEAST(
                            100,
                            ROUND(
                                55
                                + COALESCE(st.avg_confidence, 0) * 35
                                - LEAST(COALESCE(ex.total_exceptions, 0) * 2.5, 35)
                                - LEAST(COALESCE(ex.pending_exceptions, 0) * 3, 20)
                            )
                        )
                    )::int AS score
                FROM suppliers s
                LEFT JOIN item_stats st ON st.supplier_id = s.id
                LEFT JOIN exception_stats ex ON ex.supplier_id = s.id
                WHERE s.org_id = %s
            )
            SELECT
                id, name, documents, items, spend, avg_confidence,
                total_exceptions, pending_exceptions, price_alerts, savings, score,
                ROW_NUMBER() OVER (ORDER BY score DESC, spend DESC, name ASC)::int AS rank
            FROM scored
            ORDER BY rank
            LIMIT %s
            """,
            (str(org_id), currency, str(org_id), currency, str(org_id), limit),
        )
        return list(await cur.fetchall())


async def list_alerts(conn: AsyncConnection, org_id: UUID | str, *, currency: str) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM exceptions_log
                 WHERE org_id = %s AND status = 'pending') AS pending_exceptions,
                (SELECT COUNT(*) FROM exceptions_log
                 WHERE org_id = %s AND status = 'pending' AND severity = 'critical') AS critical_exceptions,
                (SELECT COUNT(*) FROM exceptions_log
                 WHERE org_id = %s AND status = 'pending' AND type = 'price_spike') AS price_alerts,
                (SELECT COUNT(*) FROM purchase_approvals
                 WHERE org_id = %s AND status = 'pending') AS pending_approvals,
                (SELECT COALESCE(SUM(amount), 0) FROM purchase_approvals
                 WHERE org_id = %s AND status = 'pending' AND currency = %s) AS approval_amount,
                (SELECT COUNT(*) FROM documents_log
                 WHERE org_id = %s AND status IN ('queued', 'processing')) AS documents_pending
            """,
            (str(org_id), str(org_id), str(org_id), str(org_id), str(org_id), currency, str(org_id)),
        )
        row = await cur.fetchone() or {}

    alerts: list[dict] = []
    if int(row.get("critical_exceptions") or 0) > 0:
        alerts.append(
            {
                "id": "critical-exceptions",
                "tone": "critical",
                "title": f"{int(row['critical_exceptions'])} excepción(es) críticas",
                "body": "Requieren revisión inmediata en la bandeja HITL.",
                "action": "exceptions",
            }
        )
    if int(row.get("price_alerts") or 0) > 0:
        alerts.append(
            {
                "id": "price-alerts",
                "title": f"{int(row['price_alerts'])} alerta(s) de alza de precio",
                "tone": "warning",
                "body": "Revisa el impacto estimado antes de aprobar la compra.",
                "action": "exceptions",
            }
        )
    if int(row.get("pending_approvals") or 0) > 0:
        alerts.append(
            {
                "id": "pending-approvals",
                "title": f"{int(row['pending_approvals'])} compra(s) por aprobar",
                "tone": "info",
                "body": f"Monto pendiente: {currency} {float(row.get('approval_amount') or 0):,.0f}.",
                "action": "approvals",
            }
        )
    if int(row.get("documents_pending") or 0) > 0:
        alerts.append(
            {
                "id": "documents-pending",
                "title": f"{int(row['documents_pending'])} documento(s) en proceso",
                "tone": "info",
                "body": "La extracción continúa en segundo plano.",
                "action": "documents",
            }
        )
    if not alerts:
        alerts.append(
            {
                "id": "all-clear",
                "title": "Sin alertas críticas",
                "tone": "ok",
                "body": "No hay excepciones ni aprobaciones pendientes.",
                "action": "dashboard",
            }
        )
    return alerts


APPROVAL_SELECT = """
    SELECT
        a.*,
        s.name AS supplier_name,
        d.original_filename AS document_filename,
        requester.name AS requested_by_name,
        decider.name AS decided_by_name
    FROM purchase_approvals a
    LEFT JOIN suppliers s ON s.id = a.supplier_id
    LEFT JOIN documents_log d ON d.id = a.document_id
    LEFT JOIN users requester ON requester.id = a.requested_by
    LEFT JOIN users decider ON decider.id = a.decided_by
"""


async def list_approvals(
    conn: AsyncConnection,
    org_id: UUID | str,
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    filters = ["a.org_id = %s"]
    values: list = [str(org_id)]
    if status:
        filters.append("a.status = %s")
        values.append(status)
    where = " AND ".join(filters)
    offset = (page - 1) * page_size
    async with conn.cursor() as cur:
        await cur.execute(f"SELECT count(*) AS total FROM purchase_approvals a WHERE {where}", values)
        count_row = await cur.fetchone()
        total = int(count_row["total"]) if count_row else 0
        await cur.execute(
            f"""
            {APPROVAL_SELECT}
            WHERE {where}
            ORDER BY
                CASE a.status WHEN 'pending' THEN 0 ELSE 1 END,
                CASE a.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
                a.created_at DESC
            LIMIT %s OFFSET %s
            """,
            [*values, page_size, offset],
        )
        rows = list(await cur.fetchall())
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def get_approval(conn: AsyncConnection, org_id: UUID | str, approval_id: UUID | str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(f"{APPROVAL_SELECT} WHERE a.org_id = %s AND a.id = %s", (str(org_id), str(approval_id)))
        return await cur.fetchone()


async def create_approval(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    document_id: UUID | str | None,
    supplier_id: UUID | str | None,
    title: str,
    amount: float,
    currency: str,
    priority: str,
    requested_by: UUID | str,
    notes: str,
    metadata: dict | None = None,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO purchase_approvals (
                org_id, document_id, supplier_id, title, amount, currency,
                priority, requested_by, notes, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                str(org_id),
                str(document_id) if document_id else None,
                str(supplier_id) if supplier_id else None,
                title.strip(),
                amount,
                currency,
                priority,
                str(requested_by),
                notes.strip(),
                Jsonb(metadata or {}),
            ),
        )
        row = await cur.fetchone()
        assert row is not None
    result = await get_approval(conn, org_id, row["id"])
    assert result is not None
    return result


async def update_approval(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    approval_id: UUID | str,
    fields: dict,
) -> dict | None:
    allowed = {"title", "amount", "currency", "priority", "notes", "metadata"}
    updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
    if not updates:
        return await get_approval(conn, org_id, approval_id)
    assignments = []
    values: list = []
    for key, value in updates.items():
        assignments.append(f"{key} = %s")
        values.append(Jsonb(value) if key == "metadata" else value)
    values.extend([str(org_id), str(approval_id)])
    async with conn.cursor() as cur:
        await cur.execute(
            f"UPDATE purchase_approvals SET {', '.join(assignments)} WHERE org_id = %s AND id = %s RETURNING id",
            values,
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return await get_approval(conn, org_id, approval_id)


async def decide_approval(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    approval_id: UUID | str,
    status: str,
    decided_by: UUID | str,
    notes: str | None = None,
) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE purchase_approvals
            SET status = %s,
                decided_by = %s,
                decided_at = now(),
                notes = CASE WHEN %s::text IS NULL OR %s::text = '' THEN notes ELSE %s::text END
            WHERE org_id = %s AND id = %s AND status = 'pending'
            RETURNING id
            """,
            (status, str(decided_by), notes, notes, notes, str(org_id), str(approval_id)),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return await get_approval(conn, org_id, approval_id)


async def list_notification_channels(conn: AsyncConnection, org_id: UUID | str) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM notification_channels WHERE org_id = %s ORDER BY created_at ASC",
            (str(org_id),),
        )
        return list(await cur.fetchall())


async def create_notification_channel(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    name: str,
    channel: str,
    target: str,
    events: list[str],
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO notification_channels (org_id, name, channel, target, events)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (str(org_id), name.strip(), channel, target.strip(), Jsonb(events)),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def update_notification_channel(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    channel_id: UUID | str,
    fields: dict,
) -> dict | None:
    allowed = {"name", "channel", "target", "events", "active"}
    updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
    if not updates:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM notification_channels WHERE org_id = %s AND id = %s",
                (str(org_id), str(channel_id)),
            )
            return await cur.fetchone()
    assignments = []
    values: list = []
    for key, value in updates.items():
        assignments.append(f"{key} = %s")
        values.append(Jsonb(value) if key == "events" else value)
    values.extend([str(org_id), str(channel_id)])
    async with conn.cursor() as cur:
        await cur.execute(
            f"UPDATE notification_channels SET {', '.join(assignments)} WHERE org_id = %s AND id = %s RETURNING *",
            values,
        )
        return await cur.fetchone()


async def delete_notification_channel(conn: AsyncConnection, org_id: UUID | str, channel_id: UUID | str) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM notification_channels WHERE org_id = %s AND id = %s",
            (str(org_id), str(channel_id)),
        )
        return cur.rowcount > 0


async def record_notification_delivery(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    channel_id: UUID | str | None,
    event_type: str,
    status: str,
    recipient: str,
    payload: dict,
    error: str | None = None,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO notification_deliveries (
                org_id, channel_id, event_type, status, recipient, payload, error
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                str(org_id),
                str(channel_id) if channel_id else None,
                event_type,
                status,
                recipient[:500],
                Jsonb(payload),
                error[:2000] if error else None,
            ),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def list_notification_deliveries(conn: AsyncConnection, org_id: UUID | str, limit: int = 50) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT d.*, c.name AS channel_name, c.channel
            FROM notification_deliveries d
            LEFT JOIN notification_channels c ON c.id = d.channel_id
            WHERE d.org_id = %s
            ORDER BY d.created_at DESC
            LIMIT %s
            """,
            (str(org_id), limit),
        )
        return list(await cur.fetchall())


async def list_integrations(conn: AsyncConnection, org_id: UUID | str) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute("SELECT * FROM integrations WHERE org_id = %s ORDER BY created_at ASC", (str(org_id),))
        return list(await cur.fetchall())


async def create_integration(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    provider: str,
    name: str,
    config: dict,
    active: bool = True,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO integrations (org_id, provider, name, config, active)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (str(org_id), provider, name.strip(), Jsonb(config), active),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def update_integration(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    integration_id: UUID | str,
    fields: dict,
) -> dict | None:
    allowed = {"name", "config", "active"}
    updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
    if not updates:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM integrations WHERE org_id = %s AND id = %s",
                (str(org_id), str(integration_id)),
            )
            return await cur.fetchone()
    assignments = []
    values: list = []
    for key, value in updates.items():
        assignments.append(f"{key} = %s")
        values.append(Jsonb(value) if key == "config" else value)
    values.extend([str(org_id), str(integration_id)])
    async with conn.cursor() as cur:
        await cur.execute(
            f"UPDATE integrations SET {', '.join(assignments)} WHERE org_id = %s AND id = %s RETURNING *",
            values,
        )
        return await cur.fetchone()


async def touch_integration_sync(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    integration_id: UUID | str,
    status: str,
) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE integrations
            SET last_sync_at = now(), last_sync_status = %s
            WHERE org_id = %s AND id = %s
            RETURNING *
            """,
            (status[:200], str(org_id), str(integration_id)),
        )
        return await cur.fetchone()


async def delete_integration(conn: AsyncConnection, org_id: UUID | str, integration_id: UUID | str) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM integrations WHERE org_id = %s AND id = %s",
            (str(org_id), str(integration_id)),
        )
        return cur.rowcount > 0


async def list_api_keys(conn: AsyncConnection, org_id: UUID | str) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, name, key_prefix, scopes, active, last_used_at, revoked_at, created_at
            FROM api_keys
            WHERE org_id = %s
            ORDER BY created_at DESC
            """,
            (str(org_id),),
        )
        return list(await cur.fetchall())


async def create_api_key(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    name: str,
    key_prefix: str,
    key_hash: str,
    scopes: list[str],
    created_by: UUID | str,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO api_keys (org_id, name, key_prefix, key_hash, scopes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, name, key_prefix, scopes, active, created_at
            """,
            (str(org_id), name.strip(), key_prefix, key_hash, Jsonb(scopes), str(created_by)),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def revoke_api_key(conn: AsyncConnection, org_id: UUID | str, key_id: UUID | str) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE api_keys
            SET active = FALSE, revoked_at = now()
            WHERE org_id = %s AND id = %s AND active = TRUE
            """,
            (str(org_id), str(key_id)),
        )
        return cur.rowcount > 0


async def get_api_key_by_hash(conn: AsyncConnection, key_hash: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE api_keys
            SET last_used_at = now()
            WHERE key_hash = %s AND active = TRUE AND revoked_at IS NULL
            RETURNING id, org_id, name, scopes
            """,
            (key_hash,),
        )
        return await cur.fetchone()


async def list_webhooks(conn: AsyncConnection, org_id: UUID | str) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, url, events, active, last_delivery_at, created_at
            FROM webhook_subscriptions
            WHERE org_id = %s
            ORDER BY created_at DESC
            """,
            (str(org_id),),
        )
        return list(await cur.fetchall())


async def create_webhook(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    url: str,
    secret: str,
    events: list[str],
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO webhook_subscriptions (org_id, url, secret, events)
            VALUES (%s, %s, %s, %s)
            RETURNING id, url, events, active, created_at
            """,
            (str(org_id), url.strip(), secret, Jsonb(events)),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def delete_webhook(conn: AsyncConnection, org_id: UUID | str, webhook_id: UUID | str) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM webhook_subscriptions WHERE org_id = %s AND id = %s",
            (str(org_id), str(webhook_id)),
        )
        return cur.rowcount > 0


async def list_inbound_tokens(conn: AsyncConnection, org_id: UUID | str) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, address, active, last_received_at, created_at
            FROM inbound_email_tokens
            WHERE org_id = %s
            ORDER BY created_at DESC
            """,
            (str(org_id),),
        )
        return list(await cur.fetchall())


async def create_inbound_token(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    address: str,
    token_hash: str,
    created_by: UUID | str,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO inbound_email_tokens (org_id, address, token_hash, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id, address, active, created_at
            """,
            (str(org_id), address, token_hash, str(created_by)),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def get_inbound_token_by_hash(conn: AsyncConnection, token_hash: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, org_id, address
            FROM inbound_email_tokens
            WHERE token_hash = %s AND active = TRUE
            """,
            (token_hash,),
        )
        return await cur.fetchone()


async def touch_inbound_token(conn: AsyncConnection, token_id: UUID | str) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE inbound_email_tokens SET last_received_at = now() WHERE id = %s",
            (str(token_id),),
        )


async def get_onboarding(conn: AsyncConnection, org_id: UUID | str) -> dict:
    async with conn.cursor() as cur:
        await cur.execute("SELECT * FROM onboarding_progress WHERE org_id = %s", (str(org_id),))
        row = await cur.fetchone()
        if row is not None:
            return row
        await cur.execute(
            """
            INSERT INTO onboarding_progress (org_id, steps)
            VALUES (%s, '{}'::jsonb)
            ON CONFLICT (org_id) DO UPDATE SET updated_at = now()
            RETURNING *
            """,
            (str(org_id),),
        )
        created = await cur.fetchone()
        assert created is not None
        return created


async def update_onboarding(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    steps: dict | None,
    dismissed: bool | None,
    completed: bool | None,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO onboarding_progress (org_id, steps, dismissed, completed_at)
            VALUES (%s, %s, COALESCE(%s, FALSE), CASE WHEN %s THEN now() ELSE NULL END)
            ON CONFLICT (org_id) DO UPDATE SET
                steps = CASE WHEN %s::jsonb IS NULL THEN onboarding_progress.steps ELSE %s::jsonb END,
                dismissed = COALESCE(%s, onboarding_progress.dismissed),
                completed_at = CASE
                    WHEN %s IS TRUE THEN now()
                    WHEN %s IS FALSE THEN NULL
                    ELSE onboarding_progress.completed_at
                END,
                updated_at = now()
            RETURNING *
            """,
            (
                str(org_id),
                Jsonb(steps or {}),
                dismissed,
                bool(completed),
                Jsonb(steps) if steps is not None else None,
                Jsonb(steps or {}) if steps is not None else None,
                dismissed,
                completed,
                completed,
            ),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def record_user_session(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    user_id: UUID | str,
    ip_address: str | None,
    user_agent: str,
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO user_sessions (org_id, user_id, ip_address, user_agent)
            VALUES (%s, %s, %s, %s)
            """,
            (str(org_id), str(user_id), ip_address, user_agent[:500]),
        )


async def list_user_sessions(conn: AsyncConnection, org_id: UUID | str, limit: int = 50) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT s.*, u.name AS user_name, u.email AS user_email
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.org_id = %s
            ORDER BY s.created_at DESC
            LIMIT %s
            """,
            (str(org_id), limit),
        )
        return list(await cur.fetchall())


async def purge_audit_events(conn: AsyncConnection, org_id: UUID | str, retention_days: int) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            DELETE FROM audit_events
            WHERE org_id = %s
              AND created_at < now() - interval '1 day' * %s
            """,
            (str(org_id), max(int(retention_days), 1)),
        )
        return cur.rowcount


async def save_push_subscription(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    user_id: UUID | str,
    endpoint: str,
    endpoint_hash: str,
    p256dh: str,
    auth: str,
    user_agent: str,
) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO push_subscriptions (
                org_id, user_id, endpoint, endpoint_hash, p256dh, auth, user_agent
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (endpoint_hash) DO UPDATE SET
                org_id = EXCLUDED.org_id,
                user_id = EXCLUDED.user_id,
                p256dh = EXCLUDED.p256dh,
                auth = EXCLUDED.auth,
                user_agent = EXCLUDED.user_agent,
                active = TRUE
            RETURNING id, endpoint, active, created_at
            """,
            (
                str(org_id),
                str(user_id),
                endpoint,
                endpoint_hash,
                p256dh,
                auth,
                user_agent[:500],
            ),
        )
        row = await cur.fetchone()
        assert row is not None
        return row


async def delete_push_subscription(conn: AsyncConnection, user_id: UUID | str, endpoint_hash: str) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM push_subscriptions WHERE user_id = %s AND endpoint_hash = %s",
            (str(user_id), endpoint_hash),
        )
        return cur.rowcount > 0


async def list_push_subscriptions(conn: AsyncConnection, org_id: UUID | str) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, user_id, endpoint, p256dh, auth
            FROM push_subscriptions
            WHERE org_id = %s AND active = TRUE
            """,
            (str(org_id),),
        )
        return list(await cur.fetchall())


async def demo_counts(conn: AsyncConnection, org_id: UUID | str) -> dict:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM documents_log WHERE org_id = %s) AS documents,
                (SELECT COUNT(*) FROM suppliers WHERE org_id = %s) AS suppliers,
                (SELECT COUNT(*) FROM items_history WHERE org_id = %s) AS items,
                (SELECT COUNT(*) FROM users WHERE org_id = %s AND active = TRUE) AS users
            """,
            (str(org_id), str(org_id), str(org_id), str(org_id)),
        )
        row = await cur.fetchone() or {}
    return {key: int(value or 0) for key, value in row.items()}
