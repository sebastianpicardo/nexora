-- NEXORA: seguimiento de ahorro detectado y realizado por organizacion.
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
