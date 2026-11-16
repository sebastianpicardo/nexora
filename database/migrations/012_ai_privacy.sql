ALTER TABLE organizations ADD COLUMN IF NOT EXISTS ai_data_consent BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS ai_images_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS ai_text_max_chars INTEGER NOT NULL DEFAULT 200000
    CHECK (ai_text_max_chars >= 1000 AND ai_text_max_chars <= 200000);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS ai_data_retention_days INTEGER NOT NULL DEFAULT 90
    CHECK (ai_data_retention_days >= 1 AND ai_data_retention_days <= 3650);
