-- =============================================================================
-- MIGRATION: 001_lifecycle_tables.sql
-- Creates the three lifecycle tables for the certPortal lifecycle_engine.
-- Run once against CERTPORTAL_DB_URL Postgres instance.
--
-- Tables:
--   po_lifecycle        — one row per PO number; current state
--   lifecycle_events    — append-only audit trail (mirrors INV-05)
--   lifecycle_violations — all failed transitions and validation errors
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- po_lifecycle: one row per purchase order — the primary state record
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS po_lifecycle (
    id                     INTEGER      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    po_number              TEXT         NOT NULL UNIQUE,
    partner_id             TEXT         NOT NULL,           -- 'lowes' for Lowe's
    current_state          TEXT         NOT NULL,           -- order_to_cash.yaml state name
    is_terminal            BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ordered_qty            NUMERIC,                         -- from 850 PO1
    changed_qty            NUMERIC,                         -- from 860 POC
    accepted_qty           NUMERIC,                         -- from 855 ACK
    shipped_qty            NUMERIC,                         -- from 856 SN1
    invoiced_qty           NUMERIC,                         -- from 810 IT1
    n1_qualifier_inbound   TEXT,                            -- expect '93'
    n1_qualifier_outbound  TEXT                             -- expect '94' or '92'
);

CREATE INDEX IF NOT EXISTS idx_po_lifecycle_partner
    ON po_lifecycle(partner_id);

CREATE INDEX IF NOT EXISTS idx_po_lifecycle_state
    ON po_lifecycle(current_state);

-- ---------------------------------------------------------------------------
-- lifecycle_events: full audit trail — INSERT ONLY, never UPDATE or DELETE
-- Mirrors INV-05 (MONICA-MEMORY.md append-only pattern)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lifecycle_events (
    id               INTEGER      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    po_number        TEXT         NOT NULL REFERENCES po_lifecycle(po_number),
    partner_id       TEXT         NOT NULL,
    event_type       TEXT         NOT NULL,     -- state name triggered
    transaction_set  TEXT         NOT NULL,     -- '850','860','855','865','856','810'
    direction        TEXT         NOT NULL,     -- 'inbound' or 'outbound'
    source_file      TEXT         NOT NULL,
    correlation_id   TEXT         NOT NULL,     -- from pyedi_core pipeline
    prior_state      TEXT,                     -- NULL for the first document in lifecycle
    new_state        TEXT         NOT NULL,
    qty_at_event     NUMERIC,
    payload_snapshot JSONB,                     -- key fields captured at this event
    processed_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_le_po
    ON lifecycle_events(po_number);

CREATE INDEX IF NOT EXISTS idx_le_corrId
    ON lifecycle_events(correlation_id);

CREATE INDEX IF NOT EXISTS idx_le_type
    ON lifecycle_events(event_type);

-- ---------------------------------------------------------------------------
-- lifecycle_violations: every failed transition or validation failure
-- Also written to S3 for Monica (INV-02)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lifecycle_violations (
    id               INTEGER      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    po_number        TEXT,                      -- NULL if PO# could not be extracted
    partner_id       TEXT,
    transaction_set  TEXT         NOT NULL,
    source_file      TEXT         NOT NULL,
    correlation_id   TEXT         NOT NULL,
    violation_type   TEXT         NOT NULL,
        -- 'invalid_transition' | 'quantity_chain' | 'missing_po'
        -- 'duplicate_terminal' | 'n1_qualifier'   | 'po_continuity'
        -- 'unexpected_first_doc'
    violation_detail TEXT         NOT NULL,
    current_state    TEXT,
    attempted_event  TEXT         NOT NULL,
    failed_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMIT;
