from __future__ import annotations

from psycopg import AsyncConnection

PLANS_SEED_SQL = """
    INSERT INTO plans (id, name, description, price_monthly, currency, document_limit, features, sort_order)
    VALUES
        (
            'free',
            'Free',
            'Para probar la auditoría con un volumen acotado.',
            0,
            'USD',
            25,
            jsonb_build_array(
                '25 documentos al mes',
                'Auditoría de precios',
                'Dashboard mensual',
                'Exportaciones básicas'
            ),
            10
        ),
        (
            'pro',
            'Pro',
            'Para equipos de compras que necesitan control continuo.',
            49,
            'USD',
            500,
            jsonb_build_array(
                '500 documentos al mes',
                'Equipo con roles',
                'Alertas de cuota',
                'Exportaciones PDF y Excel',
                'Historial de 6 meses'
            ),
            20
        ),
        (
            'enterprise',
            'Enterprise',
            'Para operaciones multi-sucursal y alto volumen.',
            199,
            'USD',
            NULL,
            jsonb_build_array(
                'Documentos ilimitados',
                'Panel multi-tenant',
                'Auditoría avanzada',
                'Exportaciones masivas',
                'Gestión centralizada'
            ),
            30
        )
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        price_monthly = EXCLUDED.price_monthly,
        currency = EXCLUDED.currency,
        document_limit = EXCLUDED.document_limit,
        features = EXCLUDED.features,
        sort_order = EXCLUDED.sort_order,
        active = TRUE
"""


async def ensure_default_plans(conn: AsyncConnection) -> None:
    async with conn.cursor() as cur:
        await cur.execute(PLANS_SEED_SQL)
