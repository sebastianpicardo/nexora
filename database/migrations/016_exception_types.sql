-- ══════════════════════════════════════════════════════════════════════════════
-- NEXORA — Migración 016: nuevos tipos de excepción para importación y
-- conciliación de facturas. Idempotente.
-- ══════════════════════════════════════════════════════════════════════════════

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
