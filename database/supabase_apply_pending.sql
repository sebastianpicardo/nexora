-- NEXORA - Aplicacion consolidada de migraciones pendientes (007 a 014)
-- Ejecutar completo en Supabase SQL Editor como owner del esquema.
-- Es idempotente: se puede volver a ejecutar sin duplicar objetos ni borrar datos.
-- Unico cambio de datos: alinea el plan enterprise a 150000 CLP/mes.

BEGIN;

-- ===========================================================================
-- 007_price_catalog.sql
-- ===========================================================================
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

COMMENT ON TABLE price_catalog IS 'Catalogo de precios propio con precio de costo, venta y margen calculado';
COMMENT ON COLUMN price_catalog.margin_pct IS 'Margen de ganancia calculado automaticamente ((venta - costo) / venta * 100)';

-- ===========================================================================
-- 008_alert_config.sql
-- ===========================================================================
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

COMMENT ON TABLE alert_config IS 'Configuracion de alertas automaticas por organizacion';
COMMENT ON COLUMN alert_config.alert_type IS 'Tipo de alerta: price_spike, exception_pending, approval_pending, document_pending, quota_warning, quota_exceeded';
COMMENT ON COLUMN alert_config.threshold_pct IS 'Umbral porcentual para disparar la alerta (ej. 10% de alza de precio)';
COMMENT ON COLUMN alert_config.channels IS 'Canales de notificacion habilitados: email, slack, webhook';
COMMENT ON COLUMN alert_config.email_recipients IS 'Lista de emails de destino';
COMMENT ON COLUMN alert_config.slack_channels IS 'Lista de canales de Slack';

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
        'alert_config'
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

-- ===========================================================================
-- 009_ai_usage.sql
-- ===========================================================================
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

COMMENT ON TABLE ai_usage IS 'Uso de modelos de IA por organizacion, documento y usuario.';
COMMENT ON COLUMN ai_usage.estimated_cost_usd IS 'Costo estimado segun tarifas configuradas; no reemplaza la facturacion del proveedor.';

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

    FOREACH table_name IN ARRAY ARRAY['ai_usage']
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

-- ===========================================================================
-- 010_canonical_products.sql
-- ===========================================================================
CREATE TABLE IF NOT EXISTS canonical_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    base_unit TEXT,
    brand TEXT,
    presentation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, normalized_name, base_unit)
);

CREATE TABLE IF NOT EXISTS product_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    canonical_product_id UUID NOT NULL REFERENCES canonical_products(id) ON DELETE CASCADE,
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    sku TEXT,
    alias_name TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    confidence NUMERIC(4, 3) NOT NULL DEFAULT 1.000
        CHECK (confidence >= 0 AND confidence <= 1),
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS canonical_products_org_name_idx
    ON canonical_products (org_id, normalized_name);
CREATE INDEX IF NOT EXISTS product_aliases_org_canonical_idx
    ON product_aliases (org_id, canonical_product_id);
CREATE INDEX IF NOT EXISTS product_aliases_org_supplier_sku_idx
    ON product_aliases (org_id, supplier_id, sku);

ALTER TABLE items_history
    ADD COLUMN IF NOT EXISTS canonical_product_id UUID REFERENCES canonical_products(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS product_match_confidence NUMERIC(4, 3),
    ADD COLUMN IF NOT EXISTS product_match_confirmed BOOLEAN NOT NULL DEFAULT FALSE;

-- Los items historicos sin producto canonico se consideran coincidencias validas.
-- Evita que datos previos a la migracion 010 desaparezcan de oportunidades y analitica.
UPDATE items_history
SET product_match_confirmed = TRUE
WHERE canonical_product_id IS NULL
  AND product_match_confirmed = FALSE;

CREATE INDEX IF NOT EXISTS items_history_org_canonical_idx
    ON items_history (org_id, canonical_product_id);

CREATE INDEX IF NOT EXISTS items_history_org_product_match_idx
    ON items_history (
        org_id,
        COALESCE(sku, normalized_description),
        base_unit,
        price_date DESC
    );

-- ===========================================================================
-- 011_savings_tracking.sql
-- ===========================================================================
CREATE TABLE IF NOT EXISTS savings_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    opportunity_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'identified'
        CHECK (status IN ('identified', 'contacted', 'negotiated', 'realized', 'dismissed')),
    realized_amount NUMERIC(18, 6) NOT NULL DEFAULT 0
        CHECK (realized_amount >= 0),
    currency TEXT NOT NULL DEFAULT 'CLP',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, opportunity_key)
);

CREATE INDEX IF NOT EXISTS savings_tracking_org_status_idx
    ON savings_tracking (org_id, status, created_at DESC);

-- ===========================================================================
-- 012_ai_privacy.sql
-- ===========================================================================
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS ai_data_consent BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS ai_images_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS ai_text_max_chars INTEGER NOT NULL DEFAULT 200000
    CHECK (ai_text_max_chars >= 1000 AND ai_text_max_chars <= 200000);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS ai_data_retention_days INTEGER NOT NULL DEFAULT 90
    CHECK (ai_data_retention_days >= 1 AND ai_data_retention_days <= 3650);

-- ===========================================================================
-- 013_plan_alignment.sql
-- ===========================================================================
UPDATE plans
SET price_monthly = 149990,
    currency = 'CLP',
    description = 'Para operaciones multi-sucursal y alto volumen.'
WHERE id = 'enterprise';

-- ===========================================================================
-- 014_ai_temporary_errors.sql
-- ===========================================================================
ALTER TABLE documents_log
    DROP CONSTRAINT IF EXISTS documents_log_status_check;

ALTER TABLE documents_log
    ADD CONSTRAINT documents_log_status_check
    CHECK (status IN ('queued', 'processing', 'temporary_error', 'processed', 'failed'));

CREATE INDEX IF NOT EXISTS documents_log_temporary_retry_idx
    ON documents_log (status, updated_at)
    WHERE status = 'temporary_error';

COMMENT ON COLUMN documents_log.status IS
    'queued | processing | temporary_error (IA saturada, reintento pendiente) | processed | failed';

-- ===========================================================================
-- 016_exception_types.sql
-- ===========================================================================
ALTER TABLE exceptions_log DROP CONSTRAINT IF EXISTS exceptions_log_type_check;

ALTER TABLE exceptions_log
    ADD CONSTRAINT exceptions_log_type_check
    CHECK (type IN (
        'low_confidence',
        'price_spike',
        'unit_mismatch',
        'price_mismatch',
        'missing_price',
        'extraction_failed',
        'partial_import',
        'invoice_discrepancy'
    ));

-- ===========================================================================
-- 017_rcv_documents.sql
-- ===========================================================================
CREATE TABLE IF NOT EXISTS rcv_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    period DATE NOT NULL,
    tipo_doc TEXT NOT NULL DEFAULT '33',
    folio TEXT NOT NULL,
    rut_emisor TEXT NOT NULL DEFAULT '',
    supplier_name TEXT,
    net_amount NUMERIC(18, 2),
    tax_amount NUMERIC(18, 2),
    total_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'CLP',
    source_file TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, period, tipo_doc, folio, rut_emisor)
);

CREATE INDEX IF NOT EXISTS rcv_documents_org_period_idx
    ON rcv_documents (org_id, period DESC);
CREATE INDEX IF NOT EXISTS rcv_documents_org_folio_idx
    ON rcv_documents (org_id, folio);

-- ===========================================================================
-- 018_compra_agil.sql
-- ===========================================================================
CREATE TABLE IF NOT EXISTS compra_agil_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    buyer TEXT,
    region TEXT,
    closes_at DATE,
    budget_clp NUMERIC(18, 2),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed', 'awarded', 'dismissed')),
    source TEXT NOT NULL DEFAULT 'manual',
    items JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, external_id)
);

CREATE INDEX IF NOT EXISTS compra_agil_org_closes_idx
    ON compra_agil_opportunities (org_id, closes_at);

-- ===========================================================================
-- 019_savings_evidence.sql
-- ===========================================================================
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS sku TEXT;
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS product TEXT;
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS supplier_before TEXT;
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS supplier_after TEXT;
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS document_before_id UUID
    REFERENCES documents_log(id) ON DELETE SET NULL;
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS document_after_id UUID
    REFERENCES documents_log(id) ON DELETE SET NULL;
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS unit_price_before NUMERIC(18, 4);
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS unit_price_after NUMERIC(18, 4);
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS quantity NUMERIC(18, 4);
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE savings_tracking ADD COLUMN IF NOT EXISTS realized_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS savings_tracking_org_realized_idx
    ON savings_tracking (org_id, realized_at DESC)
    WHERE status = 'realized';

COMMIT;

-- Verificacion rapida: todas las columnas deben devolver true.
SELECT
    to_regclass('public.price_catalog') IS NOT NULL AS price_catalog_ok,
    to_regclass('public.alert_config') IS NOT NULL AS alert_config_ok,
    to_regclass('public.ai_usage') IS NOT NULL AS ai_usage_ok,
    to_regclass('public.canonical_products') IS NOT NULL AS canonical_products_ok,
    to_regclass('public.product_aliases') IS NOT NULL AS product_aliases_ok,
    to_regclass('public.savings_tracking') IS NOT NULL AS savings_tracking_ok,
    EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'organizations'
          AND column_name = 'ai_data_retention_days'
    ) AS organizations_ai_privacy_ok,
    EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'documents_log_status_check'
          AND pg_get_constraintdef(oid) LIKE '%temporary_error%'
    ) AS documents_temporary_error_ok,
    EXISTS (
        SELECT 1 FROM plans WHERE id = 'enterprise' AND price_monthly = 149990
    ) AS enterprise_price_ok,
    EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'exceptions_log_type_check'
          AND pg_get_constraintdef(oid) LIKE '%partial_import%'
    ) AS exception_types_ok,
    to_regclass('public.rcv_documents') IS NOT NULL AS rcv_documents_ok,
    to_regclass('public.compra_agil_opportunities') IS NOT NULL AS compra_agil_ok,
    EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'savings_tracking'
          AND column_name = 'evidence'
    ) AS savings_evidence_ok;

-- ── RLS: política de aplicación (nexora_app) ─────────────────────────────────
-- Garantiza acceso del rol de aplicación a toda tabla pública con RLS activo.
-- Idempotente; debe ejecutarse como dueño de la base.
DO $$
DECLARE
    table_name TEXT;
    has_app BOOLEAN;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexora_app') INTO has_app;
    IF NOT has_app THEN
        RAISE NOTICE 'Rol nexora_app no existe; nada que hacer.';
        RETURN;
    END IF;

    GRANT USAGE ON SCHEMA public TO nexora_app;

    FOR table_name IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND c.relrowsecurity
        ORDER BY c.relname
    LOOP
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO nexora_app',
            table_name
        );
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies p
            WHERE p.schemaname = 'public'
              AND p.tablename = table_name
              AND p.policyname = 'nexora_app_all'
        ) THEN
            EXECUTE format(
                'CREATE POLICY nexora_app_all ON public.%I FOR ALL TO nexora_app '
                'USING (true) WITH CHECK (true)',
                table_name
            );
        END IF;
    END LOOP;

    EXECUTE 'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexora_app';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nexora_app';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
            'GRANT USAGE, SELECT ON SEQUENCES TO nexora_app';
END $$;