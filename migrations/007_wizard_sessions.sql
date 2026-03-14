-- migrations/007_wizard_sessions.sql
-- Wizard refactoring Phase A: Multi-session wizard persistence (AD-5, AD-6).
--
-- Apply after migrations/005_password_reset.sql.
-- All statements are idempotent (IF NOT EXISTS).
--
-- Supports multiple active sessions per retailer.
-- Wizard state is stored as JSONB — strict validation only at finalization.

CREATE TABLE IF NOT EXISTS wizard_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    retailer_slug   TEXT NOT NULL,
    wizard_type     TEXT NOT NULL CHECK (wizard_type IN ('lifecycle', 'layer2')),
    session_name    TEXT,
    step_number     INT DEFAULT 0,
    state_json      JSONB DEFAULT '{}',
    x12_version     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- Index for listing sessions by retailer and type, most recent first.
-- Filters on completed_at to separate active vs completed sessions.
CREATE INDEX IF NOT EXISTS idx_wizard_sessions_retailer_type
    ON wizard_sessions (retailer_slug, wizard_type, completed_at);
