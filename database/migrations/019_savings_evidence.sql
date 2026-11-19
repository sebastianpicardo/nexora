-- ══════════════════════════════════════════════════════════════════════════════
-- NEXORA — Migración 019: evidencia auditable del ahorro verificado.
-- Idempotente.
-- ══════════════════════════════════════════════════════════════════════════════

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
