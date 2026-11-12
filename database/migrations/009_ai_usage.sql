-- NEXORA: registro de uso y costo estimado de IA por organización.
-- Ejecutar una vez sobre una base con las migraciones 002 a 008 aplicadas.
-- Es idempotente.

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

COMMENT ON TABLE ai_usage IS 'Uso de modelos de IA por organización, documento y usuario.';
COMMENT ON COLUMN ai_usage.estimated_cost_usd IS 'Costo estimado según tarifas configuradas; no reemplaza la facturación del proveedor.';

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
