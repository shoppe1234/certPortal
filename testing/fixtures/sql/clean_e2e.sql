-- testing/fixtures/sql/clean_e2e.sql
-- Removes all E2E test artefacts: lifecycle rows, test_occurrences, patches,
-- hitl_queue, and portal_users added during E2E-03 new-supplier onboarding.
-- Run before each E2E test to ensure a clean state.

-- Lifecycle engine rows (PO-E2E-* pattern)
DELETE FROM lifecycle_events  WHERE po_number LIKE 'PO-E2E-%';
DELETE FROM po_lifecycle       WHERE po_number LIKE 'PO-E2E-%';

-- Test outcome rows created during E2E runs
DELETE FROM test_occurrences   WHERE supplier_slug = 'bolt';
DELETE FROM patch_suggestions  WHERE supplier_slug = 'bolt';

-- HITL queue items from E2E flows
DELETE FROM hitl_queue
    WHERE queue_id LIKE 'e2e-%'
       OR supplier_slug = 'bolt';

-- E2E-03: remove the bolt_supplier user if it was created
DELETE FROM portal_users WHERE username = 'bolt_supplier';

-- E2E-03: remove bolt gate status
DELETE FROM hitl_gate_status WHERE supplier_id = 'bolt';
