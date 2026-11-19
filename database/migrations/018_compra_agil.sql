-- ══════════════════════════════════════════════════════════════════════════════
-- NEXORA — Migración 018: Radar de Compra Ágil.
-- Guarda oportunidades públicas y sus ítems para cotizar contra el catálogo.
-- Idempotente.
-- ══════════════════════════════════════════════════════════════════════════════

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
