-- NEXORA: autenticación con contraseña y pagos.
-- Ejecuta este archivo una vez sobre una base creada con schema.sql + 002_saas.sql.

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS payment_provider TEXT;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS customer_id TEXT;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS external_subscription_id TEXT;

CREATE INDEX IF NOT EXISTS subscriptions_customer_idx ON subscriptions (customer_id);

CREATE TABLE IF NOT EXISTS payment_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, event_id)
);

CREATE INDEX IF NOT EXISTS payment_events_created_idx ON payment_events (created_at DESC);
