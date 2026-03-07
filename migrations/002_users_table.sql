-- migrations/002_users_table.sql
-- Sprint 2: DB-backed portal authentication
--
-- Creates the portal_users table and seeds the three development users.
-- Passwords are bcrypt-hashed (rounds=12). Plaintext for reference:
--   pam_admin        → certportal_admin
--   lowes_retailer   → certportal_retailer
--   acme_supplier    → certportal_supplier
--
-- Run once per environment:
--   psql "$CERTPORTAL_DB_URL" -f migrations/002_users_table.sql

BEGIN;

-- ---------------------------------------------------------------------------
-- Table: portal_users
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS portal_users (
    id              SERIAL          PRIMARY KEY,
    username        TEXT            NOT NULL UNIQUE,
    hashed_password TEXT            NOT NULL,
    role            TEXT            NOT NULL CHECK (role IN ('admin', 'retailer', 'supplier')),
    retailer_slug   TEXT,           -- NULL for admin role
    supplier_slug   TEXT,           -- NULL for admin and retailer roles
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE portal_users IS
    'Portal authentication users. Passwords stored as bcrypt (rounds=12) hashes. '
    'Created by migration 002 (Sprint 2).';

COMMENT ON COLUMN portal_users.role IS
    'admin: full cross-tenant access (Pam portal). '
    'retailer: scoped to own retailer_slug (Meredith portal). '
    'supplier: scoped to own supplier_slug (Chrissy portal).';

-- ---------------------------------------------------------------------------
-- Index: fast username lookups on login
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_portal_users_username
    ON portal_users (username)
    WHERE is_active = TRUE;

-- ---------------------------------------------------------------------------
-- Trigger: keep updated_at current
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION _set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_portal_users_updated_at ON portal_users;
CREATE TRIGGER trg_portal_users_updated_at
    BEFORE UPDATE ON portal_users
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();

-- ---------------------------------------------------------------------------
-- Seed: three development users (safe to re-run via ON CONFLICT DO NOTHING)
--
-- IMPORTANT: These are DEVELOPMENT credentials only.
--   Replace with secure randomised passwords in every non-dev environment.
--   Use /change-password endpoint (Sprint 3) or direct UPDATE after seeding.
-- ---------------------------------------------------------------------------

INSERT INTO portal_users (username, hashed_password, role, retailer_slug, supplier_slug)
VALUES
    (
        'pam_admin',
        '$2b$12$zm9vZ9thChmd45pNMC35lOh4MFdDmcuYrFiehnlYv.mnTMhD4GNU6',
        'admin',
        NULL,
        NULL
    ),
    (
        'lowes_retailer',
        '$2b$12$GFviKss9RDxqxa1wmxt8dO9Quy/tf9eWmbzck6Uh.SrAmywWWjSgW',
        'retailer',
        'lowes',
        NULL
    ),
    (
        'acme_supplier',
        '$2b$12$WWdvIWgYMYgKw/Ju1Sc7YuD665.oOkA31RDKArlzTR9VmiaMHOTZS',
        'supplier',
        'lowes',
        'acme'
    )
ON CONFLICT (username) DO NOTHING;

COMMIT;
