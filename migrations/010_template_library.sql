-- migrations/010_template_library.sql
-- Phase 1: PAM template library + retailer adoption tracking.
-- PAM admins create/publish templates; retailers adopt or fork them.

CREATE TABLE IF NOT EXISTS pam_templates (
    id              SERIAL PRIMARY KEY,
    template_slug   TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,
    category        TEXT NOT NULL CHECK (category IN (
                        'lifecycle', 'scenario_bundle', 'layer2_preset'
                    )),
    industry        TEXT,
    x12_version     TEXT NOT NULL DEFAULT '4010',
    content_yaml    TEXT NOT NULL,
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    version         INTEGER NOT NULL DEFAULT 1,
    created_by      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS retailer_template_adoption (
    id              SERIAL PRIMARY KEY,
    retailer_slug   TEXT NOT NULL,
    template_id     INTEGER NOT NULL REFERENCES pam_templates(id),
    adoption_mode   TEXT NOT NULL CHECK (adoption_mode IN ('ADOPT', 'FORK')),
    adopted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    forked_content  TEXT
);

CREATE INDEX IF NOT EXISTS idx_pam_templates_published
    ON pam_templates (category) WHERE is_published = TRUE;
