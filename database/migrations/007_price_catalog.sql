-- ══════════════════════════════════════════════════════════════════════════════
-- NEXORA — Migración 007: catálogo de precios propio con margen
-- Ejecutar como owner del esquema en Supabase SQL Editor.
-- Permite a cada organización mantener su propio catálogo de productos con
-- precio de costo, precio de venta y margen calculado automáticamente.
-- Es idempotente.
-- ══════════════════════════════════════════════════════════════════════════════

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

COMMENT ON TABLE price_catalog IS 'Catálogo de precios propio con precio de costo, venta y margen calculado';
COMMENT ON COLUMN price_catalog.margin_pct IS 'Margen de ganancia calculado automáticamente ((venta - costo) / venta * 100)';
