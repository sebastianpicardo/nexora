-- NEXORA SaaS: planes, suscripciones, equipo, perfil y roles extendidos.
-- Ejecuta este archivo una vez sobre una base existente creada con schema.sql.

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users
    ADD CONSTRAINT users_role_check
    CHECK (role IN ('super_admin', 'owner', 'admin', 'analyst', 'user', 'auditor', 'viewer'));

ALTER TABLE users ADD COLUMN IF NOT EXISTS job_title TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'America/Santiago';
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_quota BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_weekly BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price_monthly NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (price_monthly >= 0),
    currency TEXT NOT NULL DEFAULT 'USD',
    document_limit INTEGER CHECK (document_limit IS NULL OR document_limit >= 0),
    features JSONB NOT NULL DEFAULT '[]'::jsonb,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO plans (id, name, description, price_monthly, currency, document_limit, features, sort_order)
VALUES
    (
        'free',
        'Free',
        'Para probar la auditoría con un volumen acotado.',
        0,
        'USD',
        25,
        '["25 documentos al mes", "Auditoría de precios", "Dashboard mensual", "Exportaciones básicas"]'::jsonb,
        10
    ),
    (
        'pro',
        'Pro',
        'Para equipos de compras que necesitan control continuo.',
        49,
        'USD',
        500,
        '["500 documentos al mes", "Equipo con roles", "Alertas de cuota", "Exportaciones PDF y Excel", "Historial de 6 meses"]'::jsonb,
        20
    ),
    (
        'enterprise',
        'Enterprise',
        'Para operaciones multi-sucursal y alto volumen.',
        199,
        'USD',
        NULL,
        '["Documentos ilimitados", "Panel multi-tenant", "Auditoría avanzada", "Exportaciones masivas", "Gestión centralizada"]'::jsonb,
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
    active = TRUE;

CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('trialing', 'active', 'past_due', 'canceled')),
    current_period_start DATE NOT NULL DEFAULT date_trunc('month', current_date)::date,
    current_period_end DATE NOT NULL DEFAULT (date_trunc('month', current_date) + interval '1 month')::date,
    trial_ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS subscriptions_plan_idx ON subscriptions (plan_id);

INSERT INTO subscriptions (org_id, plan_id, status, current_period_start, current_period_end)
SELECT
    o.id,
    'free',
    'active',
    date_trunc('month', current_date)::date,
    (date_trunc('month', current_date) + interval '1 month')::date
FROM organizations o
WHERE NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.org_id = o.id)
ON CONFLICT (org_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS team_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user'
        CHECK (role IN ('admin', 'analyst', 'user', 'auditor', 'viewer')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
    token TEXT NOT NULL UNIQUE,
    invited_by UUID REFERENCES users(id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '14 days'),
    accepted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS team_invitations_org_status_idx
    ON team_invitations (org_id, status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS team_invitations_pending_email_idx
    ON team_invitations (org_id, lower(email))
    WHERE status = 'pending';

DROP TRIGGER IF EXISTS plans_set_updated_at ON plans;
CREATE TRIGGER plans_set_updated_at
    BEFORE UPDATE ON plans
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS subscriptions_set_updated_at ON subscriptions;
CREATE TRIGGER subscriptions_set_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS team_invitations_set_updated_at ON team_invitations;
CREATE TRIGGER team_invitations_set_updated_at
    BEFORE UPDATE ON team_invitations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DO $$
DECLARE
    table_name TEXT;
    has_anon BOOLEAN;
    has_authenticated BOOLEAN;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') INTO has_anon;
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') INTO has_authenticated;

    FOREACH table_name IN ARRAY ARRAY['subscriptions', 'team_invitations']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        IF has_anon THEN
            EXECUTE format('REVOKE ALL ON TABLE %I FROM anon', table_name);
        END IF;
        IF has_authenticated THEN
            EXECUTE format('REVOKE ALL ON TABLE %I FROM authenticated', table_name);
        END IF;
    END LOOP;
END $$;
