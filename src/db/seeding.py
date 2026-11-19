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
            'CLP',
            25,
            jsonb_build_array(
                '25 documentos al mes',
                'Auditoría de precios',
                'Dashboard mensual',
                'Exportaciones básicas',
                '1 usuario'
            ),
            10
        ),
        (
            'pro',
            'Pro',
            'Para ferreterías y distribuidores que necesitan control continuo.',
            39990,
            'CLP',
            500,
            jsonb_build_array(
                '500 documentos al mes',
                'Hasta 5 usuarios con roles',
                'Alertas de cuota y precio',
                'Exportaciones PDF y Excel',
                'Historial de 12 meses',
                'Copiloto de IA con cuota mensual'
            ),
            20
        ),
        (
            'enterprise',
            'Enterprise',
            'Para operaciones multi-sucursal y alto volumen.',
            149990,
            'CLP',
            NULL,
            jsonb_build_array(
                'Documentos ilimitados',
                'Usuarios y sucursales ilimitadas',
                'Panel multi-tenant',
                'Auditoría avanzada y RCV',
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
