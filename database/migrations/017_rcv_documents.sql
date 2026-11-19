-- ══════════════════════════════════════════════════════════════════════════════
-- NEXORA — Migración 017: documentos declarados en el RCV del SII.
-- Permite medir completitud contra los documentos con detalle en NEXORA.
-- Idempotente.
-- ══════════════════════════════════════════════════════════════════════════════

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
