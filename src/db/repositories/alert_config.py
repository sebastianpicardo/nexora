from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection


async def list_alert_config(
    conn: AsyncConnection,
    org_id: UUID | str,
) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, alert_type, threshold_pct, enabled, channels,
                   email_recipients, slack_channels, last_triggered_at,
                   created_at, updated_at
            FROM alert_config
            WHERE org_id = %s
            ORDER BY alert_type ASC
            """,
            (str(org_id),),
        )
        return list(await cur.fetchall())


async def get_alert_config(
    conn: AsyncConnection,
    org_id: UUID | str,
    alert_type: str,
) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, alert_type, threshold_pct, enabled, channels,
                   email_recipients, slack_channels, last_triggered_at,
                   created_at, updated_at
            FROM alert_config
            WHERE org_id = %s AND alert_type = %s
            """,
            (str(org_id), alert_type),
        )
        return await cur.fetchone()


async def create_or_update_alert_config(
    conn: AsyncConnection,
    *,
    org_id: UUID | str,
    alert_type: str,
    threshold_pct: float | None = None,
    enabled: bool | None = None,
    channels: list[str] | None = None,
    email_recipients: list[str] | None = None,
    slack_channels: list[str] | None = None,
) -> dict:
    existing = await get_alert_config(conn, org_id, alert_type)
    if existing:
        updates = []
        values = []
        if threshold_pct is not None:
            updates.append("threshold_pct = %s")
            values.append(threshold_pct)
        if enabled is not None:
            updates.append("enabled = %s")
            values.append(enabled)
        if channels is not None:
            from psycopg.types.json import Jsonb
            updates.append("channels = %s")
            values.append(Jsonb(channels))
        if email_recipients is not None:
            from psycopg.types.json import Jsonb
            updates.append("email_recipients = %s")
            values.append(Jsonb(email_recipients))
        if slack_channels is not None:
            from psycopg.types.json import Jsonb
            updates.append("slack_channels = %s")
            values.append(Jsonb(slack_channels))
        if not updates:
            return existing
        values.extend([str(org_id), alert_type])
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                UPDATE alert_config
                SET {', '.join(updates)}, updated_at = now()
                WHERE org_id = %s AND alert_type = %s
                RETURNING id, alert_type, threshold_pct, enabled, channels,
                          email_recipients, slack_channels, last_triggered_at,
                          created_at, updated_at
                """,
                values,
            )
            return await cur.fetchone()
    else:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO alert_config (
                    org_id, alert_type, threshold_pct, enabled,
                    channels, email_recipients, slack_channels
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, alert_type, threshold_pct, enabled, channels,
                          email_recipients, slack_channels, last_triggered_at,
                          created_at, updated_at
                """,
                (
                    str(org_id), alert_type,
                    threshold_pct, enabled if enabled is not None else True,
                    channels or [], email_recipients or [], slack_channels or [],
                ),
            )
            return await cur.fetchone()


async def delete_alert_config(
    conn: AsyncConnection,
    org_id: UUID | str,
    alert_type: str,
) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM alert_config WHERE org_id = %s AND alert_type = %s",
            (str(org_id), alert_type),
        )
        return cur.rowcount > 0


async def get_org_alert_configs(
    conn: AsyncConnection,
    org_id: UUID | str,
) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, alert_type, threshold_pct, enabled, channels,
                   email_recipients, slack_channels, last_triggered_at,
                   created_at, updated_at
            FROM alert_config
            WHERE org_id = %s
            ORDER BY alert_type ASC
            """,
            (str(org_id),),
        )
        return list(await cur.fetchall())


async def update_alert_triggered_at(
    conn: AsyncConnection,
    alert_config_id: UUID | str,
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE alert_config
            SET last_triggered_at = now(), updated_at = now()
            WHERE id = %s
            """,
            (str(alert_config_id),),
        )
