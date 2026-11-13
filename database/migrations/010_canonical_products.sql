-- NEXORA: catálogo canónico de productos y aliases por proveedor.
-- Permite comparar precios entre proveedores sin depender solo de SKU o texto.
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

CREATE INDEX IF NOT EXISTS items_history_org_canonical_idx
    ON items_history (org_id, canonical_product_id);

CREATE INDEX IF NOT EXISTS items_history_org_product_match_idx
    ON items_history (
        org_id,
        COALESCE(sku, normalized_description),
        base_unit,
        price_date DESC
    );
