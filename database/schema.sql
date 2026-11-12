-- ═════════════════════════════════════════════════════════════════════════════
-- NEXORA — Esquema relacional para Supabase Postgres
-- Ejecuta este archivo en: Supabase Dashboard → SQL Editor → New query.
-- Todas las tablas de negocio están aisladas por org_id (multi-tenant).
-- El backend accede con un rol de Postgres; RLS bloquea anon/authenticated.
-- Requiere PostgreSQL 13+ (gen_random_uuid integrado en el core).
-- ═════════════════════════════════════════════════════════════════════════════

-- ── Organizaciones (tenant) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    price_spike_threshold_pct NUMERIC(6, 2) NOT NULL DEFAULT 10.00
        CHECK (price_spike_threshold_pct >= 0),
    min_confidence NUMERIC(4, 3) NOT NULL DEFAULT 0.750
        CHECK (min_confidence >= 0 AND min_confidence <= 1),
    default_currency TEXT NOT NULL DEFAULT 'CLP',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Usuarios ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    google_id TEXT UNIQUE,
    password_hash TEXT,
    name TEXT NOT NULL DEFAULT '',
    avatar_url TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'owner'
        CHECK (role IN ('owner', 'admin', 'analyst', 'viewer')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_idx ON users (lower(email));
CREATE INDEX IF NOT EXISTS users_org_id_idx ON users (org_id);

-- ── Proveedores ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    tax_id TEXT,
    email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, normalized_name)
);

CREATE INDEX IF NOT EXISTS suppliers_org_id_idx ON suppliers (org_id);

-- ── Documentos ingeridos (cotizaciones, facturas, listas de precios) ─────────
CREATE TABLE IF NOT EXISTS documents_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    original_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    file_size_bytes BIGINT NOT NULL DEFAULT 0,
    doc_type TEXT NOT NULL DEFAULT 'quote'
        CHECK (doc_type IN ('quote', 'invoice', 'price_list')),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'processing', 'processed', 'failed')),
    extraction_provider TEXT,
    extraction_model TEXT,
    raw_text TEXT,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processing_started_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    UNIQUE (org_id, file_hash)
);

CREATE INDEX IF NOT EXISTS documents_log_org_created_idx
    ON documents_log (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS documents_log_org_status_idx
    ON documents_log (org_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS documents_log_supplier_idx
    ON documents_log (supplier_id);

-- ── Histórico de ítems y precios normalizados ────────────────────────────────
CREATE TABLE IF NOT EXISTS items_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents_log(id) ON DELETE CASCADE,
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    sku TEXT,
    original_description TEXT NOT NULL,
    normalized_description TEXT NOT NULL,
    original_unit TEXT,
    base_unit TEXT,
    unit_factor NUMERIC(18, 6) NOT NULL DEFAULT 1 CHECK (unit_factor > 0),
    quantity NUMERIC(18, 4),
    package_size NUMERIC(18, 4),
    original_unit_price NUMERIC(18, 4)
        CHECK (original_unit_price IS NULL OR original_unit_price >= 0),
    normalized_unit_price NUMERIC(18, 6)
        CHECK (normalized_unit_price IS NULL OR normalized_unit_price >= 0),
    currency TEXT NOT NULL DEFAULT 'CLP',
    price_date DATE NOT NULL,
    confidence NUMERIC(4, 3) NOT NULL DEFAULT 0
        CHECK (confidence >= 0 AND confidence <= 1),
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('auto_approved', 'pending', 'approved', 'rejected')),
    source_page INTEGER,
    source_text TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS items_history_org_supplier_sku_date_idx
    ON items_history (org_id, supplier_id, sku, price_date DESC);
CREATE INDEX IF NOT EXISTS items_history_org_description_date_idx
    ON items_history (org_id, normalized_description, price_date DESC);
CREATE INDEX IF NOT EXISTS items_history_document_idx
    ON items_history (document_id);
CREATE INDEX IF NOT EXISTS items_history_org_review_idx
    ON items_history (org_id, review_status);

-- ── Excepciones / revisión humana (Human-in-the-Loop) ────────────────────────
CREATE TABLE IF NOT EXISTS exceptions_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents_log(id) ON DELETE CASCADE,
    item_id UUID REFERENCES items_history(id) ON DELETE SET NULL,
    type TEXT NOT NULL
        CHECK (type IN (
            'low_confidence',
            'price_spike',
            'unit_mismatch',
            'price_mismatch',
            'missing_price',
            'extraction_failed'
        )),
    severity TEXT NOT NULL DEFAULT 'medium'
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'resolved')),
    resolution JSONB,
    notes TEXT,
    resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS exceptions_log_org_status_created_idx
    ON exceptions_log (org_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS exceptions_log_document_idx
    ON exceptions_log (document_id);
CREATE INDEX IF NOT EXISTS exceptions_log_org_type_idx
    ON exceptions_log (org_id, type);

-- ── Trigger updated_at ───────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS organizations_set_updated_at ON organizations;
CREATE TRIGGER organizations_set_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS users_set_updated_at ON users;
CREATE TRIGGER users_set_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS suppliers_set_updated_at ON suppliers;
CREATE TRIGGER suppliers_set_updated_at
    BEFORE UPDATE ON suppliers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS documents_log_set_updated_at ON documents_log;
CREATE TRIGGER documents_log_set_updated_at
    BEFORE UPDATE ON documents_log
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS items_history_set_updated_at ON items_history;
CREATE TRIGGER items_history_set_updated_at
    BEFORE UPDATE ON items_history
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS exceptions_log_set_updated_at ON exceptions_log;
CREATE TRIGGER exceptions_log_set_updated_at
    BEFORE UPDATE ON exceptions_log
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── Seguridad: RLS activado y acceso anónimo revocado ────────────────────────
DO $$
DECLARE
    table_name TEXT;
    has_anon BOOLEAN;
    has_authenticated BOOLEAN;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') INTO has_anon;
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') INTO has_authenticated;

    FOREACH table_name IN ARRAY ARRAY[
        'organizations', 'users', 'suppliers',
        'documents_log', 'items_history', 'exceptions_log'
    ]
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

-- El backend se conecta con el rol de Postgres (o service_role), que omite RLS.
-- Si más adelante usas Supabase Auth en el cliente, agrega políticas basadas en
-- auth.uid() y una tabla de membresías; hoy el aislamiento se aplica en FastAPI.

-- SaaS: planes, suscripciones, equipo, perfil y roles extendidos.
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
    payment_provider TEXT,
    customer_id TEXT,
    external_subscription_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS subscriptions_plan_idx ON subscriptions (plan_id);
CREATE INDEX IF NOT EXISTS subscriptions_customer_idx ON subscriptions (customer_id);

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

CREATE TABLE IF NOT EXISTS payment_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, event_id)
);

CREATE INDEX IF NOT EXISTS payment_events_created_idx ON payment_events (created_at DESC);

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

-- ── Tokens de autenticación (reset password, verificación email) ───────────────
CREATE TABLE IF NOT EXISTS auth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_type TEXT NOT NULL CHECK (token_type IN ('password_reset', 'email_verify')),
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS auth_tokens_user_type_expires_idx
    ON auth_tokens (user_id, token_type, expires_at DESC);

-- ── Log de auditoría ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT '',
    entity_id TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_org_created_idx
    ON audit_events (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_events_action_idx
    ON audit_events (action);

-- ── Facturas / Recibos ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_invoice_id TEXT,
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'paid',
    period_start DATE,
    period_end DATE,
    paid_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_invoice_id)
);

CREATE INDEX IF NOT EXISTS invoices_org_created_idx ON invoices (org_id, created_at DESC);

-- Trigger updated_at para invoices
DROP TRIGGER IF EXISTS invoices_set_updated_at ON invoices;
CREATE TRIGGER invoices_set_updated_at
    BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
-- RLS y permisos para nuevas tablas
DO $$
DECLARE
    table_name TEXT;
    has_anon BOOLEAN;
    has_authenticated BOOLEAN;
    has_app BOOLEAN;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') INTO has_anon;
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') INTO has_authenticated;
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexora_app') INTO has_app;

    FOREACH table_name IN ARRAY ARRAY['auth_tokens', 'audit_events', 'invoices']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        IF has_anon THEN
            EXECUTE format('REVOKE ALL ON TABLE %I FROM anon', table_name);
        END IF;
        IF has_authenticated THEN
            EXECUTE format('REVOKE ALL ON TABLE %I FROM authenticated', table_name);
        END IF;
        IF has_app THEN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %I TO nexora_app', table_name);
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies p
                WHERE p.schemaname = 'public'
                  AND p.tablename = table_name
                  AND p.policyname = 'nexora_app_all'
            ) THEN
                EXECUTE format(
                    'CREATE POLICY nexora_app_all ON %I FOR ALL TO nexora_app USING (true) WITH CHECK (true)',
                    table_name
                );
            END IF;
        END IF;
    END LOOP;
END $$;

-- ═════════════════════════════════════════════════════════════════════════════
-- Suite Enterprise (migración 005)
-- Aprobaciones, alertas, integraciones, API pública, email, onboarding,
-- seguridad, push y white-label.
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE organizations ADD COLUMN IF NOT EXISTS brand_name TEXT NOT NULL DEFAULT '';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS brand_primary_color TEXT NOT NULL DEFAULT '#10b981';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS brand_accent_color TEXT NOT NULL DEFAULT '#059669';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS logo_url TEXT NOT NULL DEFAULT '';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS support_email TEXT NOT NULL DEFAULT '';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS custom_domain TEXT NOT NULL DEFAULT '';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS hide_powered_by BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS sso_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS sso_domain TEXT NOT NULL DEFAULT '';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS sso_required BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS audit_retention_days INTEGER NOT NULL DEFAULT 365;

CREATE TABLE IF NOT EXISTS purchase_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents_log(id) ON DELETE SET NULL,
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    amount NUMERIC(18, 2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
    currency TEXT NOT NULL DEFAULT 'CLP',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    priority TEXT NOT NULL DEFAULT 'normal'
        CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    requested_by UUID REFERENCES users(id) ON DELETE SET NULL,
    decided_by UUID REFERENCES users(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ,
    notes TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS purchase_approvals_org_status_idx
    ON purchase_approvals (org_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS purchase_approvals_document_idx
    ON purchase_approvals (document_id);

CREATE TABLE IF NOT EXISTS notification_channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('email', 'slack', 'whatsapp', 'webhook')),
    target TEXT NOT NULL DEFAULT '',
    events JSONB NOT NULL DEFAULT '[]'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS notification_channels_org_idx
    ON notification_channels (org_id, active);

CREATE TABLE IF NOT EXISTS notification_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    channel_id UUID REFERENCES notification_channels(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'sent', 'failed', 'skipped')),
    recipient TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS notification_deliveries_org_created_idx
    ON notification_deliveries (org_id, created_at DESC);

CREATE TABLE IF NOT EXISTS integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider TEXT NOT NULL
        CHECK (provider IN ('erp', 'sii', 'chilecompra', 'slack', 'webhook', 'google_workspace')),
    name TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    last_sync_at TIMESTAMPTZ,
    last_sync_status TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS integrations_org_provider_idx
    ON integrations (org_id, provider);

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    scopes JSONB NOT NULL DEFAULT '["read"]'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS api_keys_org_idx ON api_keys (org_id, active);

CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    secret TEXT NOT NULL,
    events JSONB NOT NULL DEFAULT '[]'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    last_delivery_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS webhook_subscriptions_org_idx
    ON webhook_subscriptions (org_id, active);

CREATE TABLE IF NOT EXISTS inbound_email_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    address TEXT NOT NULL UNIQUE,
    token_hash TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    last_received_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS inbound_email_tokens_org_idx
    ON inbound_email_tokens (org_id, active);

CREATE TABLE IF NOT EXISTS onboarding_progress (
    org_id UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    steps JSONB NOT NULL DEFAULT '{}'::jsonb,
    completed_at TIMESTAMPTZ,
    dismissed BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ip_address TEXT,
    user_agent TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_sessions_org_created_idx
    ON user_sessions (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS user_sessions_user_created_idx
    ON user_sessions (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL,
    endpoint_hash TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_agent TEXT NOT NULL DEFAULT '',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS push_subscriptions_org_idx
    ON push_subscriptions (org_id, active);

-- ── Historial de búsquedas por usuario ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('chilecompra', 'sii', 'erp', 'slack', 'webhook', 'google_workspace')),
    action TEXT NOT NULL,
    query TEXT NOT NULL DEFAULT '',
    result_summary TEXT NOT NULL DEFAULT '',
    result_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_search_history_user_idx
    ON user_search_history (user_id, provider, action, created_at DESC);

CREATE OR REPLACE FUNCTION trim_user_search_history()
RETURNS TRIGGER AS $$
DECLARE
    v_user_id UUID;
    v_provider TEXT;
    v_action TEXT;
BEGIN
    v_user_id := NEW.user_id;
    v_provider := NEW.provider;
    v_action := NEW.action;

    DELETE FROM user_search_history
    WHERE id IN (
        SELECT id FROM user_search_history
        WHERE user_id = v_user_id
          AND provider = v_provider
          AND action = v_action
        ORDER BY created_at DESC
        OFFSET 3
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_trim_user_search_history ON user_search_history;
CREATE TRIGGER trg_trim_user_search_history
    AFTER INSERT ON user_search_history
    FOR EACH ROW
    EXECUTE FUNCTION trim_user_search_history();

DROP TRIGGER IF EXISTS purchase_approvals_set_updated_at ON purchase_approvals;
CREATE TRIGGER purchase_approvals_set_updated_at
    BEFORE UPDATE ON purchase_approvals
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS notification_channels_set_updated_at ON notification_channels;
CREATE TRIGGER notification_channels_set_updated_at
    BEFORE UPDATE ON notification_channels
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS integrations_set_updated_at ON integrations;
CREATE TRIGGER integrations_set_updated_at
    BEFORE UPDATE ON integrations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS webhook_subscriptions_set_updated_at ON webhook_subscriptions;
CREATE TRIGGER webhook_subscriptions_set_updated_at
    BEFORE UPDATE ON webhook_subscriptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── Catálogo de precios propio ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS price_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    unit TEXT NOT NULL DEFAULT 'unidad',
    cost_price NUMERIC(18, 4) NOT NULL DEFAULT 0 CHECK (cost_price >= 0),
    sale_price NUMERIC(18, 4) NOT NULL DEFAULT 0 CHECK (sale_price >= 0),
    margin_pct NUMERIC(6, 2) GENERATED ALWAYS AS (
        CASE WHEN sale_price > 0
        THEN round(((sale_price - cost_price) / sale_price) * 100, 2)
        ELSE 0 END
    ) STORED,
    category TEXT,
    supplier_name TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, sku)
);

CREATE INDEX IF NOT EXISTS price_catalog_org_idx ON price_catalog (org_id, active);
CREATE INDEX IF NOT EXISTS price_catalog_sku_idx ON price_catalog (org_id, sku);

CREATE OR REPLACE FUNCTION price_catalog_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS price_catalog_set_updated_at ON price_catalog;
CREATE TRIGGER price_catalog_set_updated_at
    BEFORE UPDATE ON price_catalog
    FOR EACH ROW
    EXECUTE FUNCTION price_catalog_set_updated_at();

-- ── Alertas automáticas con umbrales ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL CHECK (alert_type IN ('price_spike', 'exception_pending', 'approval_pending', 'document_pending', 'quota_warning', 'quota_exceeded')),
    threshold_pct NUMERIC(6, 2) CHECK (threshold_pct >= 0),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    channels JSONB NOT NULL DEFAULT '[]'::jsonb,
    email_recipients JSONB NOT NULL DEFAULT '[]'::jsonb,
    slack_channels JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, alert_type)
);

CREATE INDEX IF NOT EXISTS alert_config_org_idx ON alert_config (org_id);
CREATE INDEX IF NOT EXISTS alert_config_enabled_idx ON alert_config (org_id, enabled);

CREATE OR REPLACE FUNCTION alert_config_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS alert_config_set_updated_at ON alert_config;
CREATE TRIGGER alert_config_set_updated_at
    BEFORE UPDATE ON alert_config
    FOR EACH ROW
    EXECUTE FUNCTION alert_config_set_updated_at();

DO $$
DECLARE
    table_name TEXT;
    has_anon BOOLEAN;
    has_authenticated BOOLEAN;
    has_app BOOLEAN;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') INTO has_anon;
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') INTO has_authenticated;
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexora_app') INTO has_app;

    FOREACH table_name IN ARRAY ARRAY[
        'purchase_approvals', 'notification_channels', 'notification_deliveries',
        'integrations', 'api_keys', 'webhook_subscriptions', 'inbound_email_tokens',
        'onboarding_progress', 'user_sessions', 'push_subscriptions', 'user_search_history',
        'price_catalog', 'alert_config'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        IF has_anon THEN
            EXECUTE format('REVOKE ALL ON TABLE %I FROM anon', table_name);
        END IF;
        IF has_authenticated THEN
            EXECUTE format('REVOKE ALL ON TABLE %I FROM authenticated', table_name);
        END IF;
        IF has_app THEN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %I TO nexora_app', table_name);
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies p
                WHERE p.schemaname = 'public'
                  AND p.tablename = table_name
                  AND p.policyname = 'nexora_app_all'
            ) THEN
                EXECUTE format(
                    'CREATE POLICY nexora_app_all ON %I FOR ALL TO nexora_app USING (true) WITH CHECK (true)',
                    table_name
                );
            END IF;
        END IF;
    END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS ai_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    document_id UUID REFERENCES documents_log(id) ON DELETE SET NULL,
    kind TEXT NOT NULL CHECK (kind IN ('document_extraction', 'assistant')),
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    estimated_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
    status TEXT NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'error')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ai_usage_org_created_idx
    ON ai_usage (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_usage_org_kind_created_idx
    ON ai_usage (org_id, kind, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_usage_document_idx
    ON ai_usage (document_id);
