-- migrations/008_retailer_specs_v2.sql
-- Wizard refactoring Phase A: Extend retailer_specs for wizard-generated artifacts.
--
-- Apply after migrations/007_wizard_sessions.sql.
-- All statements are idempotent (ADD COLUMN IF NOT EXISTS).

ALTER TABLE retailer_specs ADD COLUMN IF NOT EXISTS x12_version TEXT;
ALTER TABLE retailer_specs ADD COLUMN IF NOT EXISTS transaction_types TEXT[];
ALTER TABLE retailer_specs ADD COLUMN IF NOT EXISTS artifacts_s3_prefix TEXT;
ALTER TABLE retailer_specs ADD COLUMN IF NOT EXISTS lifecycle_ref TEXT;
ALTER TABLE retailer_specs ADD COLUMN IF NOT EXISTS layer2_configured BOOLEAN DEFAULT FALSE;
