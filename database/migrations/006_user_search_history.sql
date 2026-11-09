-- ══════════════════════════════════════════════════════════════════════════════
-- NEXORA — Migración 006: historial de búsquedas por usuario
-- Ejecutar como owner del esquema en Supabase SQL Editor.
-- Guarda las últimas 3 búsquedas por usuario para precargar datos
-- (ChileCompra precios/proveedores, SII RUT, etc.).
-- Es idempotente.
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS user_search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('chilecompra', 'sii', 'erp', 'slack', 'webhook', 'google_workspace')),
    action TEXT NOT NULL,
    query TEXT NOT NULL DEFAULT '',
    result_summary TEXT NOT NULL DEFAULT '',
    result_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_search_history_user_idx ON user_search_history (user_id, provider, action, created_at DESC);
CREATE INDEX IF NOT EXISTS user_search_history_created_idx ON user_search_history (created_at DESC);

-- Función para mantener solo las últimas 3 búsquedas por usuario/proveedor/acción
CREATE OR REPLACE FUNCTION trim_user_search_history()
RETURNS TRIGGER AS $$
DECLARE
    v_user_id UUID;
    v_provider TEXT;
    v_action TEXT;
BEGIN
    v_user_id := NEW.user_id;
    v_provider := NEW.provider;
    v_action := NEW.action;

    DELETE FROM user_search_history
    WHERE id IN (
        SELECT id FROM user_search_history
        WHERE user_id = v_user_id
          AND provider = v_provider
          AND action = v_action
        ORDER BY created_at DESC
        OFFSET 3
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_trim_user_search_history ON user_search_history;
CREATE TRIGGER trg_trim_user_search_history
    AFTER INSERT ON user_search_history
    FOR EACH ROW
    EXECUTE FUNCTION trim_user_search_history();

-- Comentarios para documentación
COMMENT ON TABLE user_search_history IS 'Historial de búsquedas de integraciones por usuario (últimas 3 por proveedor/acción)';
COMMENT ON COLUMN user_search_history.provider IS 'Proveedor consultado: chilecompra, sii, erp, etc.';
COMMENT ON COLUMN user_search_history.action IS 'Acción ejecutada: search_items, search_suppliers, validate_rut, etc.';
COMMENT ON COLUMN user_search_history.query IS 'Término de búsqueda ingresado por el usuario';
COMMENT ON COLUMN user_search_history.result_summary IS 'Resumen legible de los resultados';
COMMENT ON COLUMN user_search_history.result_data IS 'Datos completos del resultado para precargar';
