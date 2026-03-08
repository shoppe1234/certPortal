-- Sprint 6: Password reset tokens (ADR-023)
--
-- Apply after 004_revoked_tokens.sql.
-- All statements are idempotent (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).

-- Add nullable email column to portal_users.
-- Existing rows (including dev seed users) will have email = NULL.
ALTER TABLE portal_users ADD COLUMN IF NOT EXISTS email TEXT;

-- Table for time-limited, single-use password reset tokens.
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token      TEXT PRIMARY KEY,
    username   TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used       BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for username lookups (e.g. pending reset check before generating a new token).
CREATE INDEX IF NOT EXISTS idx_prt_username
    ON password_reset_tokens (username);

-- Index for cleanup queries (DELETE WHERE expires_at < NOW()).
CREATE INDEX IF NOT EXISTS idx_prt_expires_at
    ON password_reset_tokens (expires_at);
