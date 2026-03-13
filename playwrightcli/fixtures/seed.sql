-- playwrightcli/fixtures/seed.sql
-- Test fixture seed for certPortal requirements verification harness.
--
-- Unblocks all 9 skipped requirement checks:
--   PAM-SUP-03, PAM-SUP-04   — gate badges/buttons  (needs hitl_gate_status row)
--   PAM-HITL-03, PAM-HITL-04 — approve/reject        (needs hitl_queue PENDING row)
--   MER-STATUS-04             — gate status badges    (needs hitl_gate_status row)
--   CHR-SCEN-04               — transaction type      (needs test_occurrences PASS row)
--   CHR-ERR-03, CHR-ERR-04    — error details/patches (needs FAIL row + patch)
--   CHR-PATCH-04              — reject action         (needs patch with applied=FALSE)
--
-- Safe to re-run: ON CONFLICT DO NOTHING for tables with unique constraints;
-- EXISTS guards for tables without unique constraints.
--
-- Scope: retailer_slug='lowes', supplier_slug='acme'
-- (matches dev credentials in migrations/002_users_table.sql)
--
-- Apply:
--   psql "$CERTPORTAL_DB_URL" -f playwrightcli/fixtures/seed.sql

BEGIN;

-- ===========================================================================
-- PASSWORD RESET TEST USER (Step #5 — forgot/reset E2E)
--
-- pw_reset_test: admin role, email set (required for forgot-password to
-- generate a token). Password always reset to 'TestResetPass1!' so the
-- flow step starts from a known state on every run.
-- ON CONFLICT DO UPDATE restores the hash after the test changes it.
-- ===========================================================================

INSERT INTO portal_users (username, hashed_password, role, retailer_slug, supplier_slug, email)
VALUES (
    'pw_reset_test',
    '$2b$12$TRmK9xUX0bGh/qecYvD6eOOzhJMOdOSRJpcNRm02PTDJ46QklIYj6',
    'admin',
    NULL,
    NULL,
    'pw_reset_test@localhost'
)
ON CONFLICT (username) DO UPDATE
    SET hashed_password = '$2b$12$TRmK9xUX0bGh/qecYvD6eOOzhJMOdOSRJpcNRm02PTDJ46QklIYj6',
        email           = 'pw_reset_test@localhost',
        is_active       = TRUE;

-- ===========================================================================
-- SCOPE TEST USERS (Step #3 — multi-tenant scope verification)
--
-- Two additional dev users in a second tenant (target/rival) that must be
-- invisible to the lowes/acme users and vice-versa.
--
-- Passwords (bcrypt rounds=12):
--   rival_supplier  → certportal_rival
--   target_retailer → certportal_target
-- ===========================================================================

INSERT INTO portal_users (username, hashed_password, role, retailer_slug, supplier_slug)
VALUES
    (
        'target_retailer',
        '$2b$12$lvH9FKAs3QocArF1xRqjcehr95Znu562G4Fj79tnDzeWubwdvnoiK',
        'retailer',
        'target',
        NULL
    ),
    (
        'rival_supplier',
        '$2b$12$/7TcxNMlogT0zdneDdiFSeelMjPUm.5eC2NwzpyyLdaewbmsUrOfG',
        'supplier',
        'target',
        'rival'
    )
ON CONFLICT (username) DO NOTHING;

-- ---------------------------------------------------------------------------
-- rival gate status (needed so target_retailer's /supplier-status has a row)
-- ---------------------------------------------------------------------------
INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
VALUES ('rival', 'PENDING', 'PENDING', 'PENDING', 'seed')
ON CONFLICT (supplier_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- rival test occurrences (so rival_supplier sees their own scenarios)
-- Uses transaction_type '855' to distinguish from acme's '850' scenarios.
-- ---------------------------------------------------------------------------
INSERT INTO test_occurrences (
    supplier_slug, retailer_slug, transaction_type, channel,
    status, validated_at, result_json
)
SELECT
    'rival', 'target', '855', 'edi',
    'PASS', NOW() - INTERVAL '3 hours',
    '{"errors": [], "warnings": [], "segments_validated": 18}'
WHERE NOT EXISTS (
    SELECT 1 FROM test_occurrences
    WHERE supplier_slug = 'rival' AND transaction_type = '855' AND status = 'PASS'
);

-- ---------------------------------------------------------------------------
-- rival patch suggestions (so rival_supplier sees their own patches)
-- Uses error_code '855-AK1-01' to distinguish from acme's '850-BEG-01'.
-- ---------------------------------------------------------------------------
INSERT INTO patch_suggestions (
    supplier_slug, retailer_slug, error_code, segment, element,
    summary, patch_s3_key, applied
)
SELECT
    'rival', 'target', '855-AK1-01', 'AK1', 'AK102',
    'Rival scope test patch — this text should be invisible to acme_supplier.',
    'target/rival/patches/seed_rival_patch.json',
    FALSE
WHERE NOT EXISTS (
    SELECT 1 FROM patch_suggestions
    WHERE supplier_slug = 'rival' AND error_code = '855-AK1-01'
);



-- ---------------------------------------------------------------------------
-- inv03_* gate suppliers (Step #4 — gate enforcement test, INV-03)
--
-- inv03_bad: gate_1=PENDING permanently. POST gate_2/complete is always
--   blocked (409) because gate_1 is not COMPLETE. This supplier's state
--   never changes — gate_2 is never advanced — so the illegal test is
--   fully idempotent.
--
-- inv03_ok:  gate_1=COMPLETE. POST gate_1/complete is always legal (gate_1
--   has no prerequisite) and idempotent (COMPLETE→COMPLETE upsert). Used to
--   prove legal transitions are not blocked.
--
-- Both rows use ON CONFLICT DO UPDATE to reset on every re-seed.
-- ---------------------------------------------------------------------------

INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
VALUES ('inv03_bad', 'PENDING', 'PENDING', 'PENDING', 'seed')
ON CONFLICT (supplier_id) DO UPDATE
    SET gate_1 = 'PENDING',
        gate_2 = 'PENDING',
        gate_3 = 'PENDING',
        last_updated_by = 'seed';

INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
VALUES ('inv03_ok', 'COMPLETE', 'PENDING', 'PENDING', 'seed')
ON CONFLICT (supplier_id) DO UPDATE
    SET gate_1 = 'COMPLETE',
        last_updated_by = 'seed';

-- ---------------------------------------------------------------------------
-- hitl_gate_status
-- Unblocks: PAM-SUP-03, PAM-SUP-04, MER-STATUS-04
--
-- supplier_id is the PRIMARY KEY — safe to re-run with ON CONFLICT DO NOTHING.
-- gate_1=COMPLETE, gate_2=PENDING causes the "→ G2" action button to render,
-- which Playwright's :has-text("G2") selector will match.
-- ---------------------------------------------------------------------------

INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
VALUES ('acme', 'COMPLETE', 'PENDING', 'PENDING', 'seed')
ON CONFLICT (supplier_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- hitl_queue
-- Unblocks: PAM-HITL-03, PAM-HITL-04
--
-- queue_id has a UNIQUE constraint — safe to re-run.
-- status='PENDING_APPROVAL' is required for the row to appear in the HITL
-- queue view (portal filters WHERE status = 'PENDING_APPROVAL').
-- ---------------------------------------------------------------------------

INSERT INTO hitl_queue (
    queue_id, retailer_slug, supplier_slug, agent,
    draft, summary, channel, status
)
VALUES (
    'seed-hitl-001',
    'lowes',
    'acme',
    'kelly',
    'Hi [acme contact], this is Kelly from certPortal. Your EDI 850 submission '
        'has been reviewed and we need to confirm a few details before '
        'proceeding to Gate 2. Please reply to this message at your earliest '
        'convenience so we can keep the certification timeline on track.',
    'Kelly draft pending approval — acme Gate 2 dispatch',
    'email',
    'PENDING_APPROVAL'
)
ON CONFLICT (queue_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- test_occurrences — PASS scenario
-- Unblocks: CHR-SCEN-04 (transaction type visible)
--
-- No unique constraint on this table; guard with EXISTS to stay idempotent.
-- The PASS row causes a .scenario-card to render on /scenarios with
-- transaction_type="850" which the verifier checks for in body text.
-- ---------------------------------------------------------------------------

INSERT INTO test_occurrences (
    supplier_slug, retailer_slug, transaction_type, channel,
    status, validated_at, result_json
)
SELECT
    'acme', 'lowes', '850', 'edi',
    'PASS', NOW() - INTERVAL '2 hours',
    '{"errors": [], "warnings": [], "segments_validated": 42}'
WHERE NOT EXISTS (
    SELECT 1 FROM test_occurrences
    WHERE supplier_slug = 'acme'
      AND transaction_type = '850'
      AND status = 'PASS'
);

-- ---------------------------------------------------------------------------
-- test_occurrences — FAIL scenario
-- Unblocks: CHR-ERR-03, CHR-ERR-04
--
-- The FAIL row drives /errors. result_json must include errors[] with the
-- severity/code/segment/element/message keys that chrissy_errors.html
-- renders inside <details class="error-card"> and .error-group elements.
-- The verifier detects these DOM elements (or their text) to PASS CHR-ERR-03.
-- The matching patch_suggestions row (below) drives CHR-ERR-04.
-- ---------------------------------------------------------------------------

INSERT INTO test_occurrences (
    supplier_slug, retailer_slug, transaction_type, channel,
    status, validated_at, result_json
)
SELECT
    'acme', 'lowes', '850', 'edi',
    'FAIL', NOW() - INTERVAL '1 hour',
    '{"errors": [{"severity": "ERROR", "code": "850-BEG-01", "segment": "BEG", "element": "BEG03", "message": "Purchase Order Number is missing or invalid. BEG03 must be a non-empty alphanumeric string matching the retailer PO format."}], "warnings": []}'
WHERE NOT EXISTS (
    SELECT 1 FROM test_occurrences
    WHERE supplier_slug = 'acme'
      AND transaction_type = '850'
      AND status = 'FAIL'
);

-- ---------------------------------------------------------------------------
-- patch_suggestions — pending (applied=FALSE)
-- Unblocks: CHR-PATCH-04 (Reject action visible for pending patch)
--           Also contributes to CHR-ERR-04 (Ryan's Fix section in /errors)
--
-- error_code='850-BEG-01' matches the FAIL test_occurrences row above, so
-- the patch section inside chrissy_errors.html renders for that error group.
-- applied=FALSE causes hx-post="/patches/{id}/mark-applied" and
-- hx-post="/patches/{id}/reject" buttons to render in chrissy_patches.html.
-- ---------------------------------------------------------------------------

INSERT INTO patch_suggestions (
    supplier_slug, retailer_slug, error_code, segment, element,
    summary, patch_s3_key, applied
)
SELECT
    'acme', 'lowes', '850-BEG-01', 'BEG', 'BEG03',
    'Ensure BEG03 contains a valid purchase order number. The value must be '
        'a non-empty alphanumeric string. Example: BEG*00*SA*4500012345**20260101~',
    'lowes/acme/patches/seed_patch_001.json',
    FALSE
WHERE NOT EXISTS (
    SELECT 1 FROM patch_suggestions
    WHERE supplier_slug = 'acme'
      AND error_code = '850-BEG-01'
      AND applied = FALSE
);

-- ---------------------------------------------------------------------------
-- hitl_queue — signal-test-dedicated item (separate from seed-hitl-001)
-- Unblocks: SIG-HITL-01, SIG-HITL-02, SIG-HITL-03
--
-- ON CONFLICT DO UPDATE resets this item to PENDING_APPROVAL on each re-seed
-- so the signal integration test can be re-run after every seed invocation.
-- Kept separate from seed-hitl-001 so the DOM checks (PAM-HITL-03/04) are
-- unaffected when this item is approved by the signal test.
-- ---------------------------------------------------------------------------

INSERT INTO hitl_queue (
    queue_id, retailer_slug, supplier_slug, agent,
    draft, summary, channel, status
)
VALUES (
    'seed-hitl-sig-001',
    'lowes',
    'acme',
    'kelly',
    'Signal integration test draft — approve to verify Kelly dispatch signal write.',
    'Signal test — HITL approve → S3 kelly_approved signal (Step #2)',
    'email',
    'PENDING_APPROVAL'
)
ON CONFLICT (queue_id) DO UPDATE
    SET status      = 'PENDING_APPROVAL',
        resolved_at = NULL,
        resolved_by = NULL;

-- ---------------------------------------------------------------------------
-- patch_suggestions — signal-test-dedicated patch (separate from seed_patch_001)
-- Unblocks: SIG-PATCH-01, SIG-PATCH-02, SIG-PATCH-03
--
-- DELETE + INSERT keeps this patch always fresh with applied=FALSE on each re-seed.
-- Uses error_code='SIG-TEST-01' to distinguish from the DOM-check patch (850-BEG-01).
-- The chrissy_flow signal step clicks the first mark-applied button; because patches
-- are ordered by created_at DESC, this freshly-inserted patch sorts first, leaving
-- the 850-BEG-01 patch pending for CHR-PATCH-04 DOM checks.
-- ---------------------------------------------------------------------------

-- ===========================================================================
-- CERTIFICATION TEST SUPPLIER (Step #8 — CHR-CERT-03/04 full-flow)
--
-- cert_supplier: supplier role, supplier_slug='cert_test', gate_3=CERTIFIED.
-- Seeding this user and gate status lets scope_flow verify that the
-- CERTIFIED badge and certification page both reflect the DB state.
--
-- Password (bcrypt rounds=12): certportal_cert
-- ===========================================================================

INSERT INTO portal_users (username, hashed_password, role, retailer_slug, supplier_slug)
VALUES (
    'cert_supplier',
    '$2b$12$s/9Vxie25QYAyS/kipcTauZUalHs4ubVI6ARkZYi7wNWjwbGpPsRK',
    'supplier',
    'lowes',
    'cert_test'
)
ON CONFLICT (username) DO UPDATE
    SET hashed_password = '$2b$12$s/9Vxie25QYAyS/kipcTauZUalHs4ubVI6ARkZYi7wNWjwbGpPsRK',
        role            = 'supplier',
        retailer_slug   = 'lowes',
        supplier_slug   = 'cert_test',
        is_active       = TRUE;

INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
VALUES ('cert_test', 'CERTIFIED', 'CERTIFIED', 'CERTIFIED', 'seed')
ON CONFLICT (supplier_id) DO UPDATE
    SET gate_1          = 'CERTIFIED',
        gate_2          = 'CERTIFIED',
        gate_3          = 'CERTIFIED',
        last_updated_by = 'seed';

DELETE FROM patch_suggestions
WHERE supplier_slug = 'acme' AND error_code = 'SIG-TEST-01';

INSERT INTO patch_suggestions (
    supplier_slug, retailer_slug, error_code, segment, element,
    summary, patch_s3_key, applied
)
VALUES (
    'acme', 'lowes', 'SIG-TEST-01', 'ISA', 'ISA06',
    'Signal integration test patch — mark applied to verify Moses revalidation signal write.',
    'lowes/acme/patches/seed_sig_patch.json',
    FALSE
);

COMMIT;
