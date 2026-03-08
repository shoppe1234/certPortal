-- migrations/003_patch_reject.sql
-- Sprint 4: supplier can reject a patch suggestion without applying it (ADR-019).
--
-- Idempotent: ADD COLUMN IF NOT EXISTS means safe to re-run.

ALTER TABLE patch_suggestions
    ADD COLUMN IF NOT EXISTS rejected BOOLEAN NOT NULL DEFAULT FALSE;
