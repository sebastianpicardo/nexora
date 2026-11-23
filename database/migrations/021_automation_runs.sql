-- ══════════════════════════════════════════════════════════════════════════════
-- NEXORA — Migración 021: ejecuciones del pipeline automático.
-- Persiste el avance por etapa, los KPIs y los resultados completos para que la
-- página de Automatización pueda mostrarlos sin reprocesar. Idempotente.
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS automation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents_log(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),
    trigger_source TEXT NOT NULL DEFAULT 'existing'
        CHECK (trigger_source IN ('upload', 'existing')),
    filename TEXT,
    requested_by UUID REFERENCES users(id) ON DELETE SET NULL,
    stages JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    results JSONB NOT NULL DEFAULT '{}'::jsonb,
    ai_used BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS automation_runs_org_created_idx
    ON automation_runs (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS automation_runs_org_document_idx
    ON automation_runs (org_id, document_id, created_at DESC);

DROP TRIGGER IF EXISTS automation_runs_set_updated_at ON automation_runs;
CREATE TRIGGER automation_runs_set_updated_at
    BEFORE UPDATE ON automation_runs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DO $$
DECLARE
    has_app BOOLEAN;
BEGIN
    ALTER TABLE automation_runs ENABLE ROW LEVEL SECURITY;
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexora_app') INTO has_app;
    IF has_app THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE automation_runs TO nexora_app;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies p
            WHERE p.schemaname = 'public'
              AND p.tablename = 'automation_runs'
              AND p.policyname = 'nexora_app_all'
        ) THEN
            CREATE POLICY nexora_app_all ON automation_runs
                FOR ALL TO nexora_app USING (true) WITH CHECK (true);
        END IF;
    END IF;
END $$;
