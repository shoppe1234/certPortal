-- migrations/001_app_tables.sql
-- Sprint 1: Application-layer tables (certportal portal + agent schema).
--
-- Idempotent: all statements use CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS.
-- Run after lifecycle_engine/migrations/001_lifecycle_tables.sql and
-- migrations/002_users_table.sql.
--
-- Tables created here:
--   retailer_specs, test_occurrences, patch_suggestions,
--   monica_memory, hitl_gate_status, seen_scenarios, hitl_queue

CREATE TABLE IF NOT EXISTS retailer_specs (
    id             SERIAL PRIMARY KEY,
    retailer_slug  TEXT NOT NULL,
    spec_version   TEXT NOT NULL,
    thesis_s3_key  TEXT NOT NULL,
    source_pdf_key TEXT,
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS test_occurrences (
    id               SERIAL PRIMARY KEY,
    supplier_slug    TEXT NOT NULL,
    retailer_slug    TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    channel          TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL', 'PARTIAL')),
    validated_at     TIMESTAMPTZ DEFAULT now(),
    result_json      JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS patch_suggestions (
    id            SERIAL PRIMARY KEY,
    supplier_slug TEXT NOT NULL,
    retailer_slug TEXT NOT NULL,
    error_code    TEXT NOT NULL,
    segment       TEXT NOT NULL,
    element       TEXT,
    summary       TEXT NOT NULL,
    patch_s3_key  TEXT NOT NULL,
    applied       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS monica_memory (
    id            SERIAL PRIMARY KEY,
    timestamp     TIMESTAMPTZ NOT NULL,
    agent         TEXT NOT NULL,
    direction     TEXT NOT NULL CHECK (direction IN ('Q', 'A')),
    message       TEXT NOT NULL,
    retailer_slug TEXT,
    supplier_slug TEXT
);

CREATE TABLE IF NOT EXISTS hitl_gate_status (
    supplier_id     TEXT PRIMARY KEY,
    gate_1          TEXT NOT NULL DEFAULT 'PENDING',
    gate_2          TEXT NOT NULL DEFAULT 'PENDING',
    gate_3          TEXT NOT NULL DEFAULT 'PENDING',
    last_updated    TIMESTAMPTZ DEFAULT now(),
    last_updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seen_scenarios (
    id            SERIAL PRIMARY KEY,
    supplier_slug TEXT NOT NULL,
    retailer_slug TEXT NOT NULL,
    scenario_id   TEXT NOT NULL,
    UNIQUE (supplier_slug, retailer_slug, scenario_id)
);

CREATE TABLE IF NOT EXISTS hitl_queue (
    id            SERIAL PRIMARY KEY,
    queue_id      TEXT UNIQUE NOT NULL,
    retailer_slug TEXT NOT NULL,
    supplier_slug TEXT NOT NULL,
    agent         TEXT NOT NULL,
    draft         TEXT NOT NULL,
    summary       TEXT,
    thread_id     TEXT,
    channel       TEXT,
    status        TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
    queued_at     TIMESTAMPTZ DEFAULT now(),
    resolved_at   TIMESTAMPTZ,
    resolved_by   TEXT
);
