-- ══════════════════════════════════════════════════════════════════════════════
-- NEXORA — Migración 008: alertas automáticas con umbrales
-- Ejecutar como owner del esquema en Supabase SQL Editor.
-- Permite a cada organización configurar umbrales de alerta y recibir
-- notificaciones automáticas por email, Slack o webhook cuando se disparan.
-- Es idempotente.
-- ══════════════════════════════════════════════════════════════════════════════

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

COMMENT ON TABLE alert_config IS 'Configuración de alertas automáticas por organización';
COMMENT ON COLUMN alert_config.alert_type IS 'Tipo de alerta: price_spike, exception_pending, approval_pending, document_pending, quota_warning, quota_exceeded';
COMMENT ON COLUMN alert_config.threshold_pct IS 'Umbral porcentual para disparar la alerta (ej. 10% de alza de precio)';
COMMENT ON COLUMN alert_config.channels IS 'Canales de notificación habilitados: email, slack, webhook';
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
