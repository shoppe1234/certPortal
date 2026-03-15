-- migrations/009_exception_requests.sql
-- Phase 1: Exception request system for supplier onboarding.
-- Suppliers request exemptions from required test scenarios;
-- retailers approve/deny via Meredith's exception queue.

CREATE TABLE IF NOT EXISTS exception_requests (
    id              SERIAL PRIMARY KEY,
    supplier_slug   TEXT NOT NULL,
    retailer_slug   TEXT NOT NULL,
    scenario_id     TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    reason_code     TEXT NOT NULL CHECK (reason_code IN (
                        'NOT_APPLICABLE', 'HANDLED_EXTERNALLY', 'DEFERRED', 'RETAILER_WAIVED'
                    )),
    note            TEXT,
    status          TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'DENIED')),
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT,
    UNIQUE (supplier_slug, retailer_slug, scenario_id, transaction_type, status)
);

CREATE INDEX IF NOT EXISTS idx_exception_requests_pending
    ON exception_requests (retailer_slug) WHERE status = 'PENDING';
