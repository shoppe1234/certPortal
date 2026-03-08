-- migrations/004_revoked_tokens.sql
-- Sprint 5: JWT revocation storage (ADR-021).
--
-- Idempotent: CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS.
-- Run after migrations/003_patch_reject.sql.
--
-- Cleanup (deferred to Sprint 6):
--   DELETE FROM revoked_tokens WHERE expires_at < NOW();

CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti        TEXT PRIMARY KEY,
    revoked_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expires_at
    ON revoked_tokens (expires_at);
