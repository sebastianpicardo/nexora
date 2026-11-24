-- NEXORA: límite de usuarios por plan (miembros activos + invitaciones pendientes).
-- Idempotente: seguro de re-ejecutar.

ALTER TABLE plans ADD COLUMN IF NOT EXISTS user_limit INTEGER;

UPDATE plans SET user_limit = 1 WHERE id = 'free' AND (user_limit IS NULL OR user_limit <> 1);
UPDATE plans SET user_limit = 5 WHERE id = 'pro' AND (user_limit IS NULL OR user_limit <> 5);
UPDATE plans SET user_limit = NULL WHERE id = 'enterprise';
