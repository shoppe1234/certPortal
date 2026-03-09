-- testing/fixtures/sql/reset_gates.sql
-- Resets acme supplier gates to PENDING.
-- Run before PAM-03, E2E-01, E2E-02, E2E-03 to ensure a clean gate state.
-- Uses UPSERT so it works even if no acme row exists yet.

INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
VALUES ('acme', 'PENDING', 'PENDING', 'PENDING', 'test_reset')
ON CONFLICT (supplier_id) DO UPDATE
    SET gate_1        = 'PENDING',
        gate_2        = 'PENDING',
        gate_3        = 'PENDING',
        last_updated  = NOW(),
        last_updated_by = 'test_reset';
