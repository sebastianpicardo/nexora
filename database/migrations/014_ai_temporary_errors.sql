-- NEXORA - Migración 014: estado temporal para documentos con IA saturada
-- Ejecutar como owner del esquema en Supabase SQL Editor.
-- Permite reintentar documentos cuando Gemini/LLM responde 503 UNAVAILABLE
-- sin mostrarlos como fallo definitivo al usuario.
-- Es idempotente.

ALTER TABLE documents_log
    DROP CONSTRAINT IF EXISTS documents_log_status_check;

ALTER TABLE documents_log
    ADD CONSTRAINT documents_log_status_check
    CHECK (status IN ('queued', 'processing', 'temporary_error', 'processed', 'failed'));

CREATE INDEX IF NOT EXISTS documents_log_temporary_retry_idx
    ON documents_log (status, updated_at)
    WHERE status = 'temporary_error';

COMMENT ON COLUMN documents_log.status IS
    'queued | processing | temporary_error (IA saturada, reintento pendiente) | processed | failed';
