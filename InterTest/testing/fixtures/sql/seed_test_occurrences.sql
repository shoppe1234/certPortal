-- testing/fixtures/sql/seed_test_occurrences.sql
-- Seeds one PASS and one FAIL test_occurrence row for acme/lowes 850.
-- Used by CHR-01 (dashboard counts), CHR-03 (errors page), and E2E tests.
-- Safe to re-run — existing rows with same PO/tx are unchanged.

INSERT INTO test_occurrences (
    supplier_slug, retailer_slug, transaction_type, channel, status, result_json
)
VALUES
    (
        'acme', 'lowes', '850', 'gs1', 'PASS',
        '{"status":"PASS","po_number":"PO-TEST-PASS","errors":[],"warnings":[]}'
    ),
    (
        'acme', 'lowes', '850', 'gs1', 'FAIL',
        '{"status":"FAIL","po_number":"PO-TEST-FAIL","errors":[
            {"code":"E001","segment":"BEG","element":"BEG03",
             "message":"PO number exceeds 22 character maximum: PO-2026-THIS-IS-WAY-TOO-LONG-001"},
            {"code":"E002","segment":"ISA","element":"ISA13",
             "message":"ISA13 must be a 9-digit numeric control number"}
        ],"warnings":[]}'
    );
