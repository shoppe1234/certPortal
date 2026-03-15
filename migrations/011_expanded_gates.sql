-- migrations/011_expanded_gates.sql
-- Phase 1: Expand gate model for 6-step onboarding flow.
-- Adds Gate A (specs acknowledged) and Gate B (contact info) columns
-- to hitl_gate_status. Creates supplier_onboarding profile table.

ALTER TABLE hitl_gate_status
    ADD COLUMN IF NOT EXISTS gate_a TEXT NOT NULL DEFAULT 'PENDING',
    ADD COLUMN IF NOT EXISTS gate_b TEXT NOT NULL DEFAULT 'PENDING';

-- Supplier onboarding profile data (one row per supplier)
CREATE TABLE IF NOT EXISTS supplier_onboarding (
    supplier_slug   TEXT PRIMARY KEY,
    retailer_slug   TEXT NOT NULL,
    -- Step 1: Specs acknowledged
    specs_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    -- Step 2: Company + Contact
    company_name    TEXT,
    contact_name    TEXT,
    contact_email   TEXT,
    contact_phone   TEXT,
    -- Step 3: Connection + EDI Identity (test)
    connection_method TEXT,
    test_vendor_number TEXT,
    test_edi_qualifier TEXT,
    test_isa_id     TEXT,
    test_gs_id      TEXT,
    -- Step 4: Item data
    items_json      JSONB,
    items_complete  BOOLEAN NOT NULL DEFAULT FALSE,
    -- Step 6: Go-live (production IDs)
    prod_vendor_number TEXT,
    prod_edi_qualifier TEXT,
    prod_isa_id     TEXT,
    prod_gs_id      TEXT,
    prod_connection_method TEXT,
    prod_confirmed  BOOLEAN NOT NULL DEFAULT FALSE,
    -- Metadata
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
