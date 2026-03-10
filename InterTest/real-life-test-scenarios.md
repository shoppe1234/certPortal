# certPortal — Real-Life Test Scenarios (HITL Guided)
**Version:** 1.2 | **Date:** 2026-03-10 | **Sprint Coverage:** Sprint 1–6
**Revision 1.2 changes:**
- Added Anti-Hallucination Protocol section with ground-truth verification anchors
- Added Scenario Dependency Graph — enforced execution ordering
- Added Pre-Flight Environment Checklist (run before any scenario)
- Added DB-snapshot ground-truth verification step to every AgentBot prompt preamble
- Updated sprint coverage to Sprint 1–6 (matching CLAUDE.md)

**Revision 1.1 changes:**
- Each HITL Checkpoint bullet now tagged `[AUTO]` (code-assertable) or `[HITL]` (requires human judgment)
- CHR-04: Added S3 signal assertion for `mark-applied` (`signals/moses_revalidate_{patch_id}_{ts}.json`)
- CHR-04: Corrected `reject` assertion — sets `rejected=TRUE` (migration 003 column), not `applied=FALSE`
- E2E-01/03: Added Meredith gate endpoint note — `POST /suppliers/{id}/approve-gate/{gate}` (not `/gate/{gate}/complete`)
- CHR-01: Added `GET /certification` step (Chrissy has dedicated certification status page)
- E2E-03: Corrected user-creation to use `POST /register` with Form data (not `/users` with JSON body)

> **How to use this file:**
> Copy the "AgentBot Prompt" block for any scenario and paste it to your testing agentBot.
> The bot executes steps and pauses at every **HITL Checkpoint**. You confirm each checkpoint before it continues.
> Credentials: see `migrations/002_users_table.sql` for dev seeds.
> Environment: **local dev only** — Pam `:8000`, Meredith `:8001`, Chrissy `:8002`

---

## Anti-Hallucination Protocol

Every agentBot prompt in this document embeds these safeguards to prevent fabricated results:

### Ground-Truth Anchoring Rules

1. **Never assume — always query.** Before asserting any outcome, the agent must perform the actual HTTP call or SQL query. No assertion may be reported as PASS based on expectation alone.
2. **DB-is-truth.** After every write operation (POST, PUT, DELETE), the agent must run a verification SQL query against the database to confirm the write landed. The HTTP response alone is insufficient — the DB row must exist.
3. **S3-is-truth.** After every S3 signal write, the agent must `list_objects_v2` or `head_object` to confirm the file exists. The portal's 200 response does not prove S3 receipt.
4. **Cross-verify at HITL gates.** Every `[AUTO]` checkpoint includes a SQL query or S3 check. The operator must run these independently (via psql/mc/console) — not trust the agent's report.
5. **No phantom PO numbers.** The agent must never invent PO numbers. Every PO number used in assertions must trace back to a seed INSERT, an EDI fixture, or a prior step's output.
6. **Diff before/after.** For state-mutating scenarios (PAM-02, PAM-03, CHR-04, E2E-*), the agent must snapshot the relevant table rows BEFORE the mutation step and re-query AFTER to show the delta.

### Agent Self-Check Protocol

At the start of every scenario prompt, the agent must:

```
SELF-CHECK (run before Step 1):
  1. Confirm all PREREQUISITE services are reachable (health endpoints, DB, S3)
  2. Run the SEED SQL and verify row counts match expectations
  3. Log the current DB state of tables under test (SELECT COUNT(*) FROM <table>)
  4. If any prerequisite fails → STOP immediately, report the failure, do NOT proceed
```

### Operator Verification Strategy

The operator's role at HITL checkpoints:
- `[AUTO]` items: The test code asserts these automatically. The operator confirms by running the listed SQL query independently (via psql CLI or DB console) as a cross-check.
- `[HITL]` items: Require human judgment (visual inspection, tone assessment, UX review). The agent cannot assess these — only the operator can.
- **If the agent reports a PASS but the operator's independent SQL/S3 check disagrees → the test FAILS.** The operator's independent verification is the final authority.

---

## Pre-Flight Environment Checklist

Run this once before starting any scenario group. Failures here cascade to 100% of tests.

```
PRE-FLIGHT CHECKLIST (operator runs manually)
────────────────────────────────────────────────
[ ] PostgreSQL running:
      psql $CERTPORTAL_DB_URL -c "SELECT 1" -q

[ ] All 6 migrations applied (in order):
      psql $CERTPORTAL_DB_URL -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
      Expected tables: hitl_gate_status, hitl_queue, lifecycle_events, monica_memory,
                       password_reset_tokens, patch_suggestions, po_lifecycle,
                       portal_users, retailer_specs, revoked_tokens, test_occurrences

[ ] MinIO running:
      curl -s http://localhost:9000/minio/health/live && echo " OK"

[ ] S3 buckets exist + fixtures uploaded:
      python testing/integration/setup_minio.py
      (Idempotent — safe to re-run)

[ ] .env points at MinIO (not OVHcloud):
      grep OVH_S3_ENDPOINT .env
      Expected: http://localhost:9000

[ ] All 3 portals running:
      curl -s http://localhost:8000/health  → {"status":"ok","portal":"pam",...}
      curl -s http://localhost:8001/health  → {"status":"ok","portal":"meredith",...}
      curl -s http://localhost:8002/health  → {"status":"ok","portal":"chrissy",...}

[ ] Dev seed users exist:
      psql $CERTPORTAL_DB_URL -c "SELECT username, role FROM portal_users ORDER BY username;"
      Expected: acme_supplier (supplier), lowes_retailer (retailer), pam_admin (admin)

[ ] pytest collects without errors:
      pytest testing/integration/ --collect-only -q
      Expected: 138 tests collected, 0 errors
```

---

## Scenario Dependency Graph

Execute scenarios in this order to satisfy prerequisites. Scenarios at the same depth level are independent and can run in parallel.

```
Level 0 (no dependencies — can run first):
  PAM-01    Auth baseline
  MER-01    Retailer baseline
  CHR-01    Supplier baseline

Level 1 (depends on Level 0):
  PAM-02    (requires PAM-01 ✓)  HITL queue
  PAM-03    (requires PAM-01 ✓)  Gate progression
  PAM-04    (requires PAM-01 ✓)  Password reset
  MER-02    (requires MER-01 ✓)  Spec upload
  MER-03    (requires MER-01 ✓)  YAML wizard
  MER-04    (requires MER-01 ✓)  Token refresh + change password
  CHR-02    (requires CHR-01 ✓)  Moses PASS

Level 2 (depends on Level 1):
  CHR-03    (requires CHR-02 ✓)  Moses FAIL + errors
  CHR-05    (requires CHR-02 ✓)  855/856/810 submission

Level 3 (depends on Level 2):
  CHR-04    (requires CHR-03 ✓)  Patch apply/reject

Level 4 (cross-portal — depends on multiple prior levels):
  E2E-01    (requires PAM-01 + MER-01 + CHR-01 + CHR-02 ✓)  Full order-to-cash
  E2E-02    (requires CHR-03 + CHR-04 ✓)                     Failure recovery loop
  E2E-03    (requires PAM-01 + MER-01 ✓)                     New supplier onboarding
```

---

## Dev Seed Credentials (Local Only)

| User | Password | Role | Portal | Slug |
|---|---|---|---|---|
| `pam_admin` | `certportal_admin` | admin | Pam :8000 | — |
| `lowes_retailer` | `certportal_retailer` | retailer | Meredith :8001 | retailer_slug: `lowes` |
| `acme_supplier` | `certportal_supplier` | supplier | Chrissy :8002 | supplier_slug: `acme`, retailer_slug: `lowes` |

---

## Table of Contents

| ID | Scenario | Perspective | Priority |
|---|---|---|---|
| [PAM-01](#pam-01) | Auth, Token Claims, Logout + Revocation | Platform | P0 |
| [PAM-02](#pam-02) | HITL Queue — Approve and Reject | Platform | P0 |
| [PAM-03](#pam-03) | Supplier Gate Progression + Violation Guard | Platform | P0 |
| [PAM-04](#pam-04) | Monica Memory + Forgot-Password Flow | Platform | P1 |
| [MER-01](#mer-01) | Retailer Login, Dashboard, Spec Board | Retailer | P0 |
| [MER-02](#mer-02) | Spec Upload → Dwight S3 Signal | Retailer | P1 |
| [MER-03](#mer-03) | YAML Wizard — All 3 Paths (Andy Trigger) | Retailer | P1 |
| [MER-04](#mer-04) | Token Refresh + Change Password | Retailer | P1 |
| [CHR-01](#chr-01) | Supplier Login, Dashboard, Gate Status | Supplier | P0 |
| [CHR-02](#chr-02) | Moses 850 PO Validation — PASS | Supplier | P0 |
| [CHR-03](#chr-03) | Moses 850 PO Validation — FAIL + Errors View | Supplier | P0 |
| [CHR-04](#chr-04) | Ryan Patch — Apply and Reject | Supplier | P1 |
| [CHR-05](#chr-05) | 855 Ack + 856 ASN + 810 Invoice Submission | Supplier | P0 |
| [E2E-01](#e2e-01) | Full Order-to-Cash (850→855→856→810→Certified) | All 3 | P0 |
| [E2E-02](#e2e-02) | Failure Recovery Loop (FAIL→Patch→Re-validate→PASS) | All 3 | P0 |
| [E2E-03](#e2e-03) | New Supplier Onboarding from Scratch | All 3 | P1 |

---

## Platform Scenarios (Pam — Admin Portal)

---

### PAM-01

**Admin Login, Token Claims, Logout + Revocation**
**Portal:** Pam (Admin) | **Port:** `http://localhost:8000` | **Role:** admin

---

> #### AgentBot Prompt — PAM-01
> *Paste the block below in its entirety to your testing agentBot.*

```
You are a certPortal testing agent executing scenario PAM-01.
Portal: http://localhost:8000 (Admin — Pam)
Your job: execute each numbered step, verify outcomes, and STOP at every HITL Checkpoint.
At a HITL Checkpoint, display the checklist, wait for the operator to type CONTINUE or FAIL <reason>.

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual HTTP call and inspecting the response.
  - After every write (POST), verify with a follow-up read (GET or SQL) that the state changed.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.
  - If a prerequisite is not met, STOP immediately and report which prerequisite failed.

────────────────────────────────
PREREQUISITES (verify before Step 1)
────────────────────────────────
- Pam portal is running:  uvicorn portals.pam:app --port 8000
- CERTPORTAL_DB_URL points to a seeded Postgres instance
- Migration 002 has been applied (portal_users table exists with pam_admin)
- The revoked_tokens table exists (migration 003 or equivalent)

SELF-CHECK — run before Step 1:
  GET http://localhost:8000/health → must return 200
  SQL: SELECT COUNT(*) FROM portal_users WHERE username='pam_admin'; → must return 1
  SQL: SELECT COUNT(*) FROM revoked_tokens; → note the count (baseline for later comparison)
  If ANY self-check fails → STOP, report the failure, do NOT proceed.

────────────────────────────────
INPUTS
────────────────────────────────
  base_url   : http://localhost:8000
  username   : pam_admin
  password   : certportal_admin
  wrong_pass : wrong_password_123

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Health Check
  GET http://localhost:8000/health
  Assert: HTTP 200, body = {"status":"ok","portal":"pam","version":"1.0.0"}

STEP 2 — Login Page Renders
  GET http://localhost:8000/login
  Assert: HTTP 200, HTML contains "certPortal · Admin", color #00ff88 visible in CSS

STEP 3 — Wrong Password Rejected
  POST http://localhost:8000/token
  form: username=pam_admin, password=wrong_password_123
  Assert: Response redirects to /login?error=Invalid+username+or+password
  (or HTTP 400/401 with error detail)

STEP 4 — Supplier Credential Rejected on Admin Portal
  POST http://localhost:8000/token/api
  form: username=acme_supplier, password=certportal_supplier
  Note: token issues OK (supplier can get a token via API endpoint)
  Now: GET http://localhost:8000/retailers with that token as Bearer
  Assert: HTTP 403 Forbidden

--- HITL CHECKPOINT 1 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Step 3 showed the correct error redirect (wrong password rejected)
  [AUTO] [ ] Step 4 returned HTTP 403 when supplier token used on admin route
  [AUTO] [ ] No authentication bypass occurred
Operator types CONTINUE or FAIL <reason> before you proceed.
─────────────────────────

STEP 5 — Valid Admin Login (API token endpoint)
  POST http://localhost:8000/token/api
  form: username=pam_admin, password=certportal_admin
  Assert: HTTP 200, response body has {"access_token": "<jwt>", "token_type": "bearer"}
  Decode the JWT (base64 split on '.', decode middle segment):
    Assert: sub = "pam_admin"
    Assert: role = "admin"
    Assert: type = "access"
    Assert: jti is present (non-empty string)
    Assert: exp - iat ≈ 28800 seconds (8 hours ± 60s)
  Save this token as ADMIN_TOKEN for subsequent steps.

STEP 6 — Dashboard Access
  GET http://localhost:8000/
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 200

STEP 7 — Token Refresh
  POST http://localhost:8000/token/refresh
  (This requires a valid refresh_token cookie from a browser login flow)
  Via browser: POST /token with admin credentials, capture refresh_token cookie.
  Then: POST /token/refresh with refresh_token cookie set
  Assert: HTTP 200, new access_token issued, access_token cookie reset

--- HITL CHECKPOINT 2 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] JWT claims from Step 5 look correct (sub, role, type, jti all present)
  [AUTO] [ ] Dashboard in Step 6 loaded without error
  [AUTO] [ ] Token refresh in Step 7 issued a new access_token
  [AUTO] [ ] Run SQL:
      SELECT jti FROM revoked_tokens ORDER BY revoked_at DESC LIMIT 5;
      (Should be empty at this point — nothing revoked yet)
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 8 — Logout + JTI Revocation
  Via browser login: POST /token → get access_token cookie
  POST http://localhost:8000/logout  (with access_token cookie set)
  Assert: 302 redirect to /login, cookies cleared in response headers
  Immediately: GET http://localhost:8000/  (with the now-revoked token in header)
  Assert: HTTP 401 Unauthorized, detail contains "revoked" or "invalid"

--- HITL CHECKPOINT 3 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] After logout, the old token is rejected with 401
  [AUTO] [ ] Run SQL: SELECT COUNT(*) FROM revoked_tokens WHERE jti = '<jti_from_step5>';
      Expected: COUNT = 1
  [AUTO] [ ] Confirm expires_at in revoked_tokens matches the original token exp
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES (report each)
────────────────────────────────
  [ ] Health endpoint returns {"status":"ok"}
  [ ] Wrong password redirects to error page
  [ ] Supplier token blocked on admin routes (403)
  [ ] Admin JWT contains sub, role=admin, type=access, jti
  [ ] Refresh token endpoint issues new access_token
  [ ] Logout revokes JTI; subsequent request returns 401
  [ ] revoked_tokens table has 1 row for the logout JTI
```

---

### PAM-02

**HITL Queue — Approve and Reject Kelly Drafts**
**Portal:** Pam (Admin) | **Port:** `http://localhost:8000` | **Role:** admin

---

> #### AgentBot Prompt — PAM-02

```
You are a certPortal testing agent executing scenario PAM-02.
Portal: http://localhost:8000 (Admin — Pam)
STOP at every HITL Checkpoint and wait for operator confirmation.

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual HTTP call and inspecting the response.
  - After every write (POST approve/reject), verify with SQL that the DB row changed.
  - After S3 signal write, verify with list_objects that the file exists in S3.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- PAM-01 completed successfully (admin login confirmed working)
- hitl_queue table exists (migration 001_app_tables.sql applied)
- S3AgentWorkspace is reachable (MinIO or AWS, bucket: certportal-workspaces)

SELF-CHECK — run before Step 1:
  GET http://localhost:8000/health → must return 200
  SQL: SELECT COUNT(*) FROM hitl_queue; → note baseline count
  If ANY self-check fails → STOP, report the failure, do NOT proceed.

────────────────────────────────
INPUTS / SEED PAYLOAD
────────────────────────────────
Insert these two rows into hitl_queue before running steps:

  SQL — seed two test items:
  INSERT INTO hitl_queue (queue_id, retailer_slug, supplier_slug, agent, draft, summary, channel, status)
  VALUES
    ('test-hitl-approve-001', 'lowes', 'acme', 'kelly',
     'Dear ACME team, your 850 PO-2026-001 failed segment BEG03 validation. Please resubmit.',
     '850 BEG03 validation failure notification', 'email', 'PENDING_APPROVAL'),
    ('test-hitl-reject-001', 'lowes', 'acme', 'kelly',
     'URGENT: Your entire EDI mapping is wrong. Throw everything away.',
     'Overly aggressive draft — should be rejected', 'email', 'PENDING_APPROVAL');

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Get Admin Token
  POST http://localhost:8000/token/api
  form: username=pam_admin, password=certportal_admin
  Save as ADMIN_TOKEN.

STEP 2 — View HITL Queue
  GET http://localhost:8000/hitl-queue
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 200
  Assert: Response contains both queue_id values from seed data
  Assert: Both items show status = 'PENDING_APPROVAL'

--- HITL CHECKPOINT 1 --- [HITL]
Pause here. Ask the operator to:
  [HITL] [ ] Review the two queued items displayed
  [HITL] [ ] Confirm item 'test-hitl-approve-001' contains a reasonable email draft
  [HITL] [ ] Confirm item 'test-hitl-reject-001' contains an inappropriate/aggressive draft
  [HITL] [ ] Decide: approve 001, reject 002
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 3 — Approve First Item
  POST http://localhost:8000/hitl-queue/test-hitl-approve-001/approve
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 200, body = {"status":"approved","queue_id":"test-hitl-approve-001","resolved_by":"pam_admin"}

STEP 4 — Verify S3 Dispatch Signal Written
  Check S3 path: lowes/acme/signals/kelly_approved_test-hitl-approve-001.json
  Assert: File exists in certportal-workspaces bucket
  Assert: JSON contains keys: queue_id, draft, channel="email", approved_by="pam_admin", approved_at (epoch int)

STEP 5 — Reject Second Item
  POST http://localhost:8000/hitl-queue/test-hitl-reject-001/reject
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 200, body = {"status":"rejected","queue_id":"test-hitl-reject-001","resolved_by":"pam_admin"}

STEP 6 — Queue is Now Clear
  GET http://localhost:8000/hitl-queue
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: Neither test item appears in PENDING_APPROVAL list

--- HITL CHECKPOINT 2 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Run SQL: SELECT queue_id, status, resolved_by, resolved_at
               FROM hitl_queue
               WHERE queue_id IN ('test-hitl-approve-001','test-hitl-reject-001');
      Expected: approve row has status='APPROVED', reject row has status='REJECTED'
      Both rows have resolved_by='pam_admin' and resolved_at IS NOT NULL
  [AUTO] [ ] Confirm the S3 signal file exists only for the APPROVED item (not for reject)
  [AUTO] [ ] Confirm no S3 signal was written for the rejected item
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 7 — 404 on Non-Existent Queue Item
  POST http://localhost:8000/hitl-queue/does-not-exist/approve
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 404, detail = "Queue item does-not-exist not found"

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] Both seeded queue items visible under PENDING_APPROVAL
  [ ] Approve sets status=APPROVED, writes S3 signal with correct keys
  [ ] Reject sets status=REJECTED, does NOT write S3 signal
  [ ] Queue view no longer shows resolved items
  [ ] Approving non-existent item returns 404
  [ ] resolved_by = 'pam_admin' on both rows
```

---

### PAM-03

**Supplier Gate Progression + GateOrderViolation Enforcement**
**Portal:** Pam (Admin) | **Port:** `http://localhost:8000` | **Role:** admin

---

> #### AgentBot Prompt — PAM-03

```
You are a certPortal testing agent executing scenario PAM-03.
Portal: http://localhost:8000 (Admin — Pam)
This test validates gate_enforcer.py (INV-03) — gate order must be 1 → 2 → 3 → CERTIFIED.

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual HTTP call and inspecting the response.
  - After every gate completion POST, verify via SQL that the DB row changed state.
  - When testing 409 rejections, confirm the DB did NOT change (gate state unchanged).
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- hitl_gate_status table exists and is seeded via migration 001_app_tables.sql
- gate_enforcer.py logic is active in Pam routes
- Supplier under test: supplier_id = "acme"

SELF-CHECK — run before Step 1:
  GET http://localhost:8000/health → must return 200
  SQL: SELECT gate_1, gate_2, gate_3 FROM hitl_gate_status WHERE supplier_id='acme';
    → must return a row (any state — seed will reset to PENDING)
  If ANY self-check fails → STOP, report the failure, do NOT proceed.

────────────────────────────────
INPUTS
────────────────────────────────
  admin_user : pam_admin / certportal_admin
  supplier   : acme

SEED — ensure acme starts at PENDING on all gates:
  INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
  VALUES ('acme', 'PENDING', 'PENDING', 'PENDING', 'test_seed')
  ON CONFLICT (supplier_id) DO UPDATE
    SET gate_1='PENDING', gate_2='PENDING', gate_3='PENDING', last_updated_by='test_seed';

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Get Admin Token
  POST http://localhost:8000/token/api
  form: username=pam_admin, password=certportal_admin
  Save as ADMIN_TOKEN.

STEP 2 — View Suppliers List
  GET http://localhost:8000/suppliers
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 200, acme supplier appears with gate_1=PENDING, gate_2=PENDING, gate_3=PENDING

STEP 3 — GATE ORDER VIOLATION: Skip to Gate 2 Before Gate 1 (Negative Test)
  POST http://localhost:8000/suppliers/acme/gate/2/complete
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 409 Conflict
  Assert: detail contains "GateOrderViolation" or "Gate 1 must be COMPLETE before Gate 2"

--- HITL CHECKPOINT 1 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Step 3 returned HTTP 409 (not 200)
  [AUTO] [ ] The error message clearly explains the gate order constraint
  [AUTO] [ ] Run SQL: SELECT gate_1, gate_2, gate_3 FROM hitl_gate_status WHERE supplier_id='acme';
      Expected: all three are still 'PENDING' (violation was blocked, no state change)
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 4 — Complete Gate 1 (Valid)
  POST http://localhost:8000/suppliers/acme/gate/1/complete
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 200, body = {"status":"ok","supplier_id":"acme","gate":1,"new_state":"COMPLETE"}

STEP 5 — GATE ORDER VIOLATION: Skip to Gate 3 Before Gate 2
  POST http://localhost:8000/suppliers/acme/gate/3/complete
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 409 Conflict

STEP 6 — Complete Gate 2 (Valid)
  POST http://localhost:8000/suppliers/acme/gate/2/complete
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 200, body = {"status":"ok","supplier_id":"acme","gate":2,"new_state":"COMPLETE"}

STEP 7 — Complete Gate 3 (Valid)
  POST http://localhost:8000/suppliers/acme/gate/3/complete
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 200, body = {"status":"ok","supplier_id":"acme","gate":3,"new_state":"COMPLETE"}

--- HITL CHECKPOINT 2 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Run SQL: SELECT gate_1, gate_2, gate_3 FROM hitl_gate_status WHERE supplier_id='acme';
      Expected: gate_1='COMPLETE', gate_2='COMPLETE', gate_3='COMPLETE'
  [AUTO] [ ] Two GateOrderViolation 409s were returned (Step 3 and Step 5)
  [AUTO] [ ] Gate 1, 2, 3 completed in strict sequence without errors
  [AUTO] [ ] last_updated_by = 'pam_admin' on all transitions
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 8 — Certify Supplier (Gate 3 → CERTIFIED)
  POST http://localhost:8000/suppliers/acme/gate/3/certify
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 200, body = {"status":"certified","supplier_id":"acme"}

STEP 9 — INVALID GATE NUMBER
  POST http://localhost:8000/suppliers/acme/gate/4/complete
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 400, detail = "gate must be 1, 2, or 3"

--- HITL CHECKPOINT 3 ---
Pause here. Ask the operator to verify:
  [AUTO] [ ] Run SQL: SELECT gate_3 FROM hitl_gate_status WHERE supplier_id='acme';
      Expected: gate_3 = 'CERTIFIED'
  [AUTO] [ ] Invalid gate number 4 returned HTTP 400
  [HITL] [ ] Navigate to http://localhost:8002/ or http://localhost:8002/certification as acme_supplier
      Confirm the certification badge or "CERTIFIED" status is visible on the dashboard
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] Skipping gate order returns 409 GateOrderViolation (twice — gates 2 and 3)
  [ ] Gates complete in sequence: 1 → 2 → 3 without errors
  [ ] Gate 3 certifies to CERTIFIED state
  [ ] Invalid gate number (4) returns 400
  [ ] DB reflects: gate_1=COMPLETE, gate_2=COMPLETE, gate_3=CERTIFIED
  [ ] Supplier certification badge visible in Chrissy portal
```

---

### PAM-04

**Monica Memory Review + Forgot-Password Reset Flow**
**Portal:** Pam (Admin) | **Port:** `http://localhost:8000` | **Role:** admin

---

> #### AgentBot Prompt — PAM-04

```
You are a certPortal testing agent executing scenario PAM-04.
Portal: http://localhost:8000 (Admin — Pam)
Tests: Monica memory log pagination + forgot-password token email flow.

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual HTTP call and inspecting the response.
  - After password reset, verify via SQL that the token row was marked used.
  - After password change, verify by attempting login with BOTH old and new passwords.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- monica_memory table exists (migration 001_app_tables.sql)
- Email (SMTP) configured in environment OR email sending is mocked/logged
- password_reset_tokens table exists (migration for ADR-023)
- pam_admin user has an email address in portal_users.email

SELF-CHECK — run before Step 1:
  GET http://localhost:8000/health → must return 200
  SQL: SELECT COUNT(*) FROM monica_memory; → note baseline count
  SQL: SELECT COUNT(*) FROM password_reset_tokens; → note baseline count
  If ANY self-check fails → STOP, report the failure, do NOT proceed.

SEED — insert 5 monica_memory rows for pagination test:
  INSERT INTO monica_memory (timestamp, agent, direction, message, retailer_slug, supplier_slug)
  VALUES
    (now()-interval '5 min', 'moses',  'Q', 'Validating 850 for acme/lowes', 'lowes', 'acme'),
    (now()-interval '4 min', 'moses',  'A', 'PASS: 850 PO-2026-001 valid',   'lowes', 'acme'),
    (now()-interval '3 min', 'ryan',   'Q', 'Generating patch for BEG03',     'lowes', 'acme'),
    (now()-interval '2 min', 'ryan',   'A', 'Patch generated: remove ISA13',  'lowes', 'acme'),
    (now()-interval '1 min', 'monica', 'A', 'Escalated to HITL queue',        'lowes', 'acme');

────────────────────────────────
INPUTS
────────────────────────────────
  admin_user  : pam_admin / certportal_admin
  reset_user  : pam_admin  (for password reset flow)

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Get Admin Token
  POST http://localhost:8000/token/api
  form: username=pam_admin, password=certportal_admin
  Save as ADMIN_TOKEN.

STEP 2 — Monica Memory (default page)
  GET http://localhost:8000/monica-memory
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 200
  Assert: Response includes all 5 seeded entries (or pagination shows page=1, limit=50)
  Assert: Entries sorted by timestamp DESC (most recent first)

STEP 3 — Monica Memory Pagination
  GET http://localhost:8000/monica-memory?page=1&limit=2
  Header: Authorization: Bearer <ADMIN_TOKEN>
  Assert: HTTP 200
  Assert: Response shows 2 entries
  Assert: total_pages = ceil(total_count / 2)

--- HITL CHECKPOINT 1 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Monica memory log shows entries from moses, ryan, and monica agents
  [AUTO] [ ] Entries are in reverse chronological order
  [AUTO] [ ] Pagination correctly limits to 2 items per page
  [AUTO] [ ] Run SQL: SELECT COUNT(*) FROM monica_memory; — confirm ≥ 5 rows
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 4 — Forgot Password: Submit Unknown Username
  GET http://localhost:8000/forgot-password
  Assert: HTTP 200, form renders
  POST http://localhost:8000/forgot-password
  form: username=nonexistent_user
  Assert: Redirect to /login?msg=reset_sent  (no user enumeration — same response regardless)

STEP 5 — Forgot Password: Submit Valid Admin Username
  POST http://localhost:8000/forgot-password
  form: username=pam_admin
  Assert: Redirect to /login?msg=reset_sent
  (If email is mocked, verify mock received 1 email with a reset link URL)
  Capture reset token from: SELECT token FROM password_reset_tokens
                             WHERE username='pam_admin' ORDER BY created_at DESC LIMIT 1;
  Save as RESET_TOKEN.

STEP 6 — Reset Password Page (valid token)
  GET http://localhost:8000/reset-password?token=<RESET_TOKEN>
  Assert: HTTP 200, form shows "New Password" and "Confirm New Password" fields

STEP 7 — Reset Password: Mismatched Passwords
  POST http://localhost:8000/reset-password
  form: token=<RESET_TOKEN>, new_password=NewPass123!, confirm_password=DifferentPass!
  Assert: Redirect to /reset-password?token=...&error=Passwords+do+not+match

STEP 8 — Reset Password: Too Short
  POST http://localhost:8000/reset-password
  form: token=<RESET_TOKEN>, new_password=short, confirm_password=short
  Assert: Redirect with error "Password+must+be+at+least+8+characters"

STEP 9 — Reset Password: Valid Reset
  POST http://localhost:8000/reset-password
  form: token=<RESET_TOKEN>, new_password=NewAdminPass1!, confirm_password=NewAdminPass1!
  Assert: Redirect to /login?msg=password_changed

--- HITL CHECKPOINT 2 ---
Pause here. Ask the operator to verify:
  [HITL] [ ] Check actual email inbox for pam_admin — confirm reset email arrived with a valid reset link
      (Required only if SMTP is live; if email is mocked/logged, verify mock output instead)
  [AUTO] [ ] Run SQL: SELECT used FROM password_reset_tokens WHERE token='<RESET_TOKEN>';
      Expected: used = TRUE
  [AUTO] [ ] POST /token/api with pam_admin / NewAdminPass1! succeeds → HTTP 200 with token
  [AUTO] [ ] POST /token/api with pam_admin / certportal_admin (old pass) fails → 401
  [AUTO] [ ] Non-existent username returned the same response as valid username (no enumeration)

IMPORTANT — Reset password back to original for other tests:
  UPDATE portal_users SET hashed_password='$2b$12$zm9vZ9thChmd45pNMC35lOh4MFdDmcuYrFiehnlYv.mnTMhD4GNU6'
  WHERE username='pam_admin';
  (This restores certportal_admin)

Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] Monica memory shows seeded entries in DESC order with correct pagination
  [ ] Forgot-password returns same redirect for valid AND invalid usernames
  [ ] Valid reset token renders form; expired/used token redirects to forgot-password
  [ ] Mismatched / short passwords return specific error messages
  [ ] Valid password reset marks token as used and allows login with new password
  [ ] Old password rejected after reset
```

---

## Retailer Scenarios (Meredith — Retailer Portal)

---

### MER-01

**Retailer Login, Dashboard, Supplier Certification Board**
**Portal:** Meredith (Retailer) | **Port:** `http://localhost:8001` | **Role:** retailer

---

> #### AgentBot Prompt — MER-01

```
You are a certPortal testing agent executing scenario MER-01.
Portal: http://localhost:8001 (Retailer — Meredith)
STOP at every HITL Checkpoint and wait for operator confirmation.

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual HTTP call and inspecting the response.
  - Cross-portal rejection tests (Step 3, Step 8) must verify the EXACT status code — do not assume.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- Meredith portal running: uvicorn portals.meredith:app --port 8001
- lowes_retailer user seeded (migration 002)
- retailer_specs table exists; hitl_gate_status table exists

SELF-CHECK — run before Step 1:
  GET http://localhost:8001/health → must return 200
  SQL: SELECT COUNT(*) FROM portal_users WHERE username='lowes_retailer'; → must return 1
  If ANY self-check fails → STOP, report the failure, do NOT proceed.

SEED — at least one spec so the dashboard has something to show:
  INSERT INTO retailer_specs (retailer_slug, spec_version, thesis_s3_key)
  VALUES ('lowes', 'v2.0-test', 'lowes/system/THESIS.md')
  ON CONFLICT DO NOTHING;

────────────────────────────────
INPUTS
────────────────────────────────
  base_url : http://localhost:8001
  username : lowes_retailer
  password : certportal_retailer

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Health Check
  GET http://localhost:8001/health
  Assert: HTTP 200, body = {"status":"ok","portal":"meredith","version":"1.0.0"}

STEP 2 — Login Page
  GET http://localhost:8001/login
  Assert: HTTP 200, HTML contains "certPortal · Retailer", color #4f6ef7 in CSS

STEP 3 — Admin Portal Blocked for Retailer Credentials
  POST http://localhost:8000/token/api  (Pam — port 8000)
  form: username=lowes_retailer, password=certportal_retailer
  Assert: HTTP 401 or redirect with "Admin role required for this portal"

STEP 4 — Valid Retailer Login via API Token
  POST http://localhost:8001/token/api
  form: username=lowes_retailer, password=certportal_retailer
  Assert: HTTP 200, {"access_token":"<jwt>","token_type":"bearer"}
  Decode JWT:
    Assert: sub = "lowes_retailer"
    Assert: role = "retailer"
    Assert: retailer_slug = "lowes"
    Assert: supplier_slug is null or absent
  Save as RETAILER_TOKEN.

--- HITL CHECKPOINT 1 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Retailer credentials rejected on Admin portal (Step 3)
  [AUTO] [ ] JWT from Step 4 has role=retailer and retailer_slug=lowes
  [AUTO] [ ] supplier_slug is NOT present in the token (retailers don't have supplier scope)
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 5 — Dashboard
  GET http://localhost:8001/
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Assert: HTTP 200
  Assert: Response context includes spec (from retailer_specs), supplier_count, certified_count

STEP 6 — Spec Setup Page
  GET http://localhost:8001/spec-setup
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Assert: HTTP 200
  Assert: The seeded spec (lowes, v2.0-test) appears in the specs list

STEP 7 — YAML Wizard Page
  GET http://localhost:8001/yaml-wizard
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Assert: HTTP 200
  Assert: supported_bundles contains "general_merchandise" with ["850","855","856","810","997"]
  Assert: supported_bundles contains "transportation"

--- HITL CHECKPOINT 2 ---
Pause here. Ask the operator to verify visually (open browser at http://localhost:8001):
  [HITL] [ ] Log in as lowes_retailer / certportal_retailer — confirm light theme (#f8f9fc background, #4f6ef7 accent)
  [AUTO] [ ] Dashboard shows correct supplier_count and certified_count from DB
  [AUTO] [ ] Spec setup page lists the seeded spec (v2.0-test)
  [AUTO] [ ] YAML wizard shows both bundle types
  [AUTO] [ ] Navigation links visible: Spec Setup, YAML Wizard
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 8 — Supplier-Only Route Blocked for Retailer
  GET http://localhost:8002/scenarios   (Chrissy — port 8002)
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Assert: HTTP 403 Forbidden (retailer token rejected on supplier portal)

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] Health endpoint returns {"status":"ok","portal":"meredith"}
  [ ] Retailer login succeeds, JWT has role=retailer and retailer_slug=lowes
  [ ] Retailer credentials blocked on Admin portal (Pam)
  [ ] Dashboard shows spec, supplier_count, certified_count
  [ ] YAML wizard lists supported transaction bundles
  [ ] Retailer token blocked on supplier portal (403)
```

---

### MER-02

**EDI Spec Upload → Dwight Agent S3 Signal**
**Portal:** Meredith (Retailer) | **Port:** `http://localhost:8001` | **Role:** retailer

---

> #### AgentBot Prompt — MER-02

```
You are a certPortal testing agent executing scenario MER-02.
Portal: http://localhost:8001 (Retailer — Meredith)
Tests: Spec upload triggers Dwight agent via S3 workspace signal (INV-07).

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual HTTP call and inspecting the response.
  - After upload trigger, verify the S3 signal exists via list_objects_v2 — do not trust HTTP 200 alone.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- MER-01 completed (retailer login confirmed working)
- S3AgentWorkspace reachable (certportal-workspaces bucket)
- A test PDF exists or its S3 key is known (upload it manually first if needed)

MANUAL SETUP (operator does this before Step 1):
  Upload a small test PDF to certportal-raw-edi bucket:
  Key: lowes/system/test_spec_v2.pdf  (content can be a dummy 1-page PDF)
  Note the S3 key — it will be used as pdf_s3_key input.

────────────────────────────────
INPUTS
────────────────────────────────
  base_url    : http://localhost:8001
  username    : lowes_retailer
  password    : certportal_retailer
  pdf_s3_key  : lowes/system/test_spec_v2.pdf
  retailer_slug: lowes

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Get Retailer Token
  POST http://localhost:8001/token/api
  form: username=lowes_retailer, password=certportal_retailer
  Save as RETAILER_TOKEN.

STEP 2 — Missing Required Fields (Negative Test)
  POST http://localhost:8001/spec-setup/upload
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Header: Content-Type: application/json
  Body: {}
  Assert: HTTP 400, detail = "pdf_s3_key and retailer_slug required"

STEP 3 — Valid Spec Upload Trigger
  POST http://localhost:8001/spec-setup/upload
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Header: Content-Type: application/json
  Body:
    {
      "pdf_s3_key": "lowes/system/test_spec_v2.pdf",
      "retailer_slug": "lowes"
    }
  Assert: HTTP 200
  Assert: Body = {"status":"queued","message":"Dwight spec analysis queued via workspace signal.",
                  "retailer_slug":"lowes","pdf_s3_key":"lowes/system/test_spec_v2.pdf"}

--- HITL CHECKPOINT 1 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Step 2 returned HTTP 400 (missing fields rejected)
  [AUTO] [ ] Step 3 returned HTTP 200 with status="queued"
  [AUTO] [ ] Check S3 bucket certportal-workspaces for path: lowes/system/signals/dwight_trigger_<ts>.json
      File should exist and contain:
        {"type": "dwight_spec_analysis", "pdf_s3_key": "lowes/system/test_spec_v2.pdf",
         "retailer_slug": "lowes"}
  [AUTO] [ ] Confirm Dwight was NOT called directly — only the S3 signal was written (INV-07)
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 4 — Retailer Slug Fallback from JWT Claims
  POST http://localhost:8001/spec-setup/upload
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Header: Content-Type: application/json
  Body: {"pdf_s3_key": "lowes/system/test_spec_v2.pdf"}
  (No retailer_slug in body — should fall back to JWT claim)
  Assert: HTTP 200, retailer_slug = "lowes" in response (resolved from token)

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] Empty payload returns 400
  [ ] Valid payload returns 200 with status="queued"
  [ ] S3 signal file written to lowes/system/signals/dwight_trigger_<ts>.json
  [ ] Signal contains correct type, pdf_s3_key, retailer_slug
  [ ] retailer_slug falls back to JWT claim when not in request body
  [ ] Dwight agent not imported or called directly (INV-07 preserved)
```

---

### MER-03

**YAML Wizard — All 3 Andy Ingestion Paths**
**Portal:** Meredith (Retailer) | **Port:** `http://localhost:8001` | **Role:** retailer

---

> #### AgentBot Prompt — MER-03

```
You are a certPortal testing agent executing scenario MER-03.
Portal: http://localhost:8001 (Retailer — Meredith)
Tests: YAML Wizard Path 1 (PDF→YAML), Path 2 (Upload YAML), Path 3 (Wizard form).
Andy agent triggered via S3 workspace signal on all paths (INV-07, NC-02).

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual HTTP call and inspecting the response.
  - After each path trigger, verify the S3 signal exists — do not trust HTTP 200 alone.
  - For Path 2 invalid YAML, verify NO S3 signal was written (negative verification).
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- MER-01 completed (retailer login working)
- S3AgentWorkspace reachable

PATH 2 YAML PAYLOAD (valid transaction YAML structure per TRD Section 4):
  Save this as test_850.yaml locally:
  ---
  transaction:
    id: "850"
    name: "Purchase Order"
    functional_group: "PO"
    direction: inbound
    version: "004010"
    shared_refs:
      envelope: shared/envelope.yaml
      common: shared/common_segments.yaml
      codelists: shared/codelists.yaml
    heading:
      BEG:
        name: "Beginning Segment for Purchase Order"
        position: 20
        usage: mandatory
        max_use: 1
        elements:
          BEG01: {name: "Transaction Set Purpose Code", type: ID, fixed_value: "00", usage: mandatory}
          BEG02: {name: "Purchase Order Type Code", type: ID, usage: mandatory}
          BEG03: {name: "Purchase Order Number", type: AN, min_max: "1/22", usage: mandatory}
    business_rules:
      - "BEG03 is the primary key (NC-03)"
  ---

────────────────────────────────
INPUTS
────────────────────────────────
  base_url   : http://localhost:8001
  username   : lowes_retailer
  password   : certportal_retailer

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Get Retailer Token
  POST http://localhost:8001/token/api
  form: username=lowes_retailer, password=certportal_retailer
  Save as RETAILER_TOKEN.

STEP 2 — YAML Wizard Page Loads with Correct Bundles
  GET http://localhost:8001/yaml-wizard
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Assert: HTTP 200
  Assert: general_merchandise bundle contains: 850, 855, 856, 810, 997
  Assert: transportation bundle present

STEP 3 — Path 1: PDF → YAML (LLM-assisted Andy trigger)
  POST http://localhost:8001/yaml-wizard/path1
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Header: Content-Type: application/json
  Body: {"retailer_slug":"lowes","pdf_s3_key":"lowes/system/test_spec_v2.pdf","bundle":"general_merchandise"}
  Assert: HTTP 200, body contains {"status":"queued","path":1}
  Check S3: lowes/system/signals/andy_path1_trigger_<ts>.json must exist
  Assert signal contains: type="andy_yaml_path1", retailer_slug="lowes"

--- HITL CHECKPOINT 1 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Path 1 returned status=queued
  [AUTO] [ ] S3 signal exists at lowes/system/signals/andy_path1_trigger_<ts>.json
  [AUTO] [ ] Signal JSON contains the expected fields
  [AUTO] [ ] Andy was NOT directly imported or called (INV-07)
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 4 — Path 2: Upload YAML → Andy Validates
  POST http://localhost:8001/yaml-wizard/path2
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Header: Content-Type: application/json
  Body: {"retailer_slug":"lowes","yaml_content":"<contents of test_850.yaml>","transaction_id":"850"}
  Assert: HTTP 200, body contains {"status":"queued","path":2}
  Check S3: lowes/system/signals/andy_path2_trigger_<ts>.json must exist

STEP 5 — Path 2: Invalid YAML (schema validator gate)
  POST http://localhost:8001/yaml-wizard/path2
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Header: Content-Type: application/json
  Body: {"retailer_slug":"lowes","yaml_content":"not_valid: [yaml: that: fails: schema","transaction_id":"850"}
  Assert: HTTP 400 or 422 (validation error before S3 write)
  (If schema_validators/ is not yet wired to Path 2, accept HTTP 200 with validation_status=FAIL in response)

STEP 6 — Path 3: Wizard Form → YAML
  POST http://localhost:8001/yaml-wizard/path3
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Header: Content-Type: application/json
  Body: {"retailer_slug":"lowes","transaction_id":"850","bundle":"general_merchandise",
         "fields":{"po_number_element":"BEG03","direction":"inbound","version":"004010"}}
  Assert: HTTP 200, body contains {"status":"queued","path":3}
  Check S3: lowes/system/signals/andy_path3_trigger_<ts>.json must exist

--- HITL CHECKPOINT 2 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] All three S3 signals exist (path1, path2, path3)
  [AUTO] [ ] Each signal has the correct type field: andy_yaml_path1, andy_yaml_path2, andy_yaml_path3
  [AUTO] [ ] Path 2 with invalid YAML was rejected before writing to S3 (no orphan signal)
  [AUTO] [ ] No direct Andy agent import anywhere in portal code (grep: "from agents.andy import")
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] YAML wizard page shows both supported bundles
  [ ] All 3 paths return status=queued
  [ ] Each path writes a correctly-typed S3 workspace signal
  [ ] Path 2 rejects malformed YAML before writing to S3
  [ ] Andy agent invoked via signal only (INV-07 preserved)
```

---

### MER-04

**Token Refresh + Change Password (Retailer)**
**Portal:** Meredith (Retailer) | **Port:** `http://localhost:8001` | **Role:** retailer

---

> #### AgentBot Prompt — MER-04

```
You are a certPortal testing agent executing scenario MER-04.
Portal: http://localhost:8001 (Retailer — Meredith)
Tests: Access token refresh via refresh_token cookie + change-password endpoint.

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual HTTP call and inspecting the response.
  - After password change, verify by attempting login with BOTH old and new passwords.
  - Decode and compare JWT tokens to confirm iat/sub/role — do not assume identity carries over.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- MER-01 completed
- Change-password endpoint exists at POST /change-password (Sprint 3 ADR-022)

────────────────────────────────
INPUTS
────────────────────────────────
  base_url   : http://localhost:8001
  username   : lowes_retailer
  password   : certportal_retailer
  new_pass   : RetailerNewPass1!

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Browser Login to Obtain Refresh Token Cookie
  POST http://localhost:8001/token  (form login, not /token/api)
  form: username=lowes_retailer, password=certportal_retailer
  Assert: 302 redirect to /
  Assert: Response headers set both access_token and refresh_token cookies (httponly)
  Capture the refresh_token cookie value.

STEP 2 — Refresh Access Token
  POST http://localhost:8001/token/refresh
  Cookie: refresh_token=<captured_value>
  Assert: HTTP 200, body contains {"access_token":"<new_jwt>","token_type":"bearer"}
  Assert: New access_token is different from the original
  Decode new JWT:
    Assert: sub = "lowes_retailer", role = "retailer"
    Assert: iat is more recent than original token

--- HITL CHECKPOINT 1 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Token refresh returned a new (different) access_token
  [AUTO] [ ] New token has same sub and role as original
  [AUTO] [ ] New token iat is ≥ original iat
  [AUTO] [ ] New access_token cookie set in response headers
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 3 — Change Password
  (Requires: current access_token)
  POST http://localhost:8001/change-password
  Header: Authorization: Bearer <RETAILER_TOKEN>
  Header: Content-Type: application/json
  Body: {"current_password":"certportal_retailer","new_password":"RetailerNewPass1!",
         "confirm_password":"RetailerNewPass1!"}
  Assert: HTTP 200, {"status":"ok","message":"Password changed successfully"}

STEP 4 — Old Password Now Rejected
  POST http://localhost:8001/token/api
  form: username=lowes_retailer, password=certportal_retailer
  Assert: HTTP 401 Unauthorized

STEP 5 — New Password Works
  POST http://localhost:8001/token/api
  form: username=lowes_retailer, password=RetailerNewPass1!
  Assert: HTTP 200 with valid token

--- HITL CHECKPOINT 2 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Old password rejected (Step 4 returned 401)
  [AUTO] [ ] New password accepted (Step 5 returned 200 with token)
  [AUTO] [ ] Run SQL: SELECT updated_at FROM portal_users WHERE username='lowes_retailer';
      updated_at should be within the last minute

RESET password for subsequent tests:
  POST http://localhost:8001/change-password  (with new token from Step 5)
  Body: {"current_password":"RetailerNewPass1!","new_password":"certportal_retailer",
         "confirm_password":"certportal_retailer"}
  OR: UPDATE portal_users SET hashed_password='$2b$12$GFviKss9RDxqxa1wmxt8dO9Quy/tf9eWmbzck6Uh.SrAmywWWjSgW'
      WHERE username='lowes_retailer';

Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] Refresh token issues new access_token with same identity claims
  [ ] New access_token cookie set with correct httponly/samesite flags
  [ ] Password change succeeds; old password rejected immediately
  [ ] updated_at timestamp updated in portal_users
```

---

## Supplier Scenarios (Chrissy — Supplier Portal)

---

### CHR-01

**Supplier Login, Dashboard, Gate Status Display**
**Portal:** Chrissy (Supplier) | **Port:** `http://localhost:8002` | **Role:** supplier

---

> #### AgentBot Prompt — CHR-01

```
You are a certPortal testing agent executing scenario CHR-01.
Portal: http://localhost:8002 (Supplier — Chrissy)
STOP at every HITL Checkpoint and wait for operator confirmation.

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual HTTP call and inspecting the response.
  - Verify supplier_slug scoping: acme must NOT see other suppliers' data.
  - Cross-portal rejection tests must verify the EXACT status code — do not assume.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- Chrissy portal running: uvicorn portals.chrissy:app --port 8002
- acme_supplier seeded (migration 002): supplier_slug=acme, retailer_slug=lowes
- hitl_gate_status has a row for acme (any gate values)
- test_occurrences table has ≥1 row for acme (seed below)

SELF-CHECK — run before Step 1:
  GET http://localhost:8002/health → must return 200
  SQL: SELECT COUNT(*) FROM portal_users WHERE username='acme_supplier'; → must return 1
  SQL: SELECT COUNT(*) FROM hitl_gate_status WHERE supplier_id='acme'; → must return 1
  If ANY self-check fails → STOP, report the failure, do NOT proceed.

SEED:
  INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
  VALUES ('acme', 'COMPLETE', 'PENDING', 'PENDING', 'test_seed')
  ON CONFLICT (supplier_id) DO UPDATE
    SET gate_1='COMPLETE', gate_2='PENDING', gate_3='PENDING';

  INSERT INTO test_occurrences (supplier_slug, retailer_slug, transaction_type, channel, status, result_json)
  VALUES
    ('acme','lowes','850','gs1','PASS','{"errors":[],"po_number":"PO-2026-001"}'),
    ('acme','lowes','850','gs1','FAIL','{"errors":[{"code":"E001","segment":"BEG","element":"BEG03",
      "message":"PO number too long (max 22 chars)"}],"po_number":"PO-2026-002"}');

────────────────────────────────
INPUTS
────────────────────────────────
  base_url : http://localhost:8002
  username : acme_supplier
  password : certportal_supplier

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Health Check
  GET http://localhost:8002/health
  Assert: HTTP 200, {"status":"ok","portal":"chrissy","version":"1.0.0"}

STEP 2 — Retailer Portal Blocks Supplier Credentials
  POST http://localhost:8001/token/api  (Meredith — port 8001)
  form: username=acme_supplier, password=certportal_supplier
  Assert: HTTP 401 or redirect with "Retailer or admin role required"

STEP 3 — Valid Supplier Login
  POST http://localhost:8002/token/api
  form: username=acme_supplier, password=certportal_supplier
  Assert: HTTP 200, {"access_token":"<jwt>","token_type":"bearer"}
  Decode JWT:
    Assert: sub = "acme_supplier"
    Assert: role = "supplier"
    Assert: supplier_slug = "acme"
    Assert: retailer_slug = "lowes"
  Save as SUPPLIER_TOKEN.

--- HITL CHECKPOINT 1 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Supplier credentials blocked on Meredith retailer portal (Step 2)
  [AUTO] [ ] JWT has role=supplier, supplier_slug=acme, retailer_slug=lowes
  [AUTO] [ ] Both supplier_slug AND retailer_slug present in token (unlike retailer token)
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 4 — Dashboard
  GET http://localhost:8002/
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 200
  Assert: Context includes supplier dict with gate_1='COMPLETE', gate_2='PENDING', gate_3='PENDING'
  Assert: total_tests = 2, passed_tests = 1, progress_pct = 50

STEP 5 — Scenarios List
  GET http://localhost:8002/scenarios
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 200
  Assert: Both seeded test_occurrences appear (PASS and FAIL rows for acme)
  Assert: No rows from other suppliers visible (supplier_slug scoping enforced)

STEP 5b — Certification Page
  GET http://localhost:8002/certification
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 200
  Assert: Page shows current gate status for acme (gate_1=COMPLETE, gate_2=PENDING, gate_3=PENDING)
  Assert: "CERTIFIED" badge/text visible when gate_3 = 'CERTIFIED', hidden otherwise

--- HITL CHECKPOINT 2 ---
Pause here. Ask the operator to verify visually (open http://localhost:8002 in browser):
  [HITL] [ ] Log in as acme_supplier / certportal_supplier — confirm warm theme (#fffbf7 background, #f59e0b accent)
  [AUTO] [ ] Gate 1 shows as COMPLETE (green/checked), Gates 2 and 3 show as PENDING
  [AUTO] [ ] Progress shows "1 of 2 passed" or equivalent (50%)
  [AUTO] [ ] Scenarios page shows 2 rows — one PASS, one FAIL
  [AUTO] [ ] No rows from other suppliers visible
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 6 — Admin Portal Blocked for Supplier
  GET http://localhost:8000/retailers
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 403 Forbidden

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] Health returns {"status":"ok","portal":"chrissy"}
  [ ] Supplier credentials blocked on retailer portal
  [ ] JWT contains sub, role=supplier, supplier_slug, retailer_slug
  [ ] Dashboard shows correct gate states and pass/fail counts
  [ ] Scenarios scoped to acme only
  [ ] Supplier token blocked on admin portal (403)
```

---

### CHR-02

**Moses EDI Validation — 850 Purchase Order PASS**
**Portal:** Chrissy (Supplier) | **Port:** `http://localhost:8002` | **Role:** supplier
**Agent:** Moses (CLI) | **Arch:** INV-01, NC-03

---

> #### AgentBot Prompt — CHR-02

```
You are a certPortal testing agent executing scenario CHR-02.
Tests: Moses validates a well-formed 850 PO and records PASS in test_occurrences.
Uses Moses CLI: python -m agents.moses --retailer lowes --supplier acme --edi-key <key> --tx 850 --channel gs1

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual CLI command and inspecting stdout/stderr.
  - After Moses runs, verify via SQL that the test_occurrences row was written — do not trust CLI output alone.
  - Verify S3 result file exists via head_object — do not assume it was written.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- Moses agent is importable: python -c "from agents import moses; print('ok')"
- THESIS.md exists in S3 at: lowes/acme/THESIS.md  (required — hard failure without it)
- certportal-raw-edi S3 bucket accessible
- test_occurrences table exists

SELF-CHECK — run before Step 1:
  SQL: SELECT COUNT(*) FROM test_occurrences WHERE supplier_slug='acme' AND transaction_type='850';
    → note baseline count (will increase by 1 after Step 2)
  If ANY self-check fails → STOP, report the failure, do NOT proceed.

MANUAL SETUP (operator completes before Step 1):
  1. Upload THESIS.md to certportal-raw-edi bucket at path: lowes/acme/THESIS.md
     (Content: any valid markdown file describing Lowe's EDI specs)
  2. Save the EDI content below as test_850_pass.edi and upload to certportal-raw-edi:
     Key: lowes/acme/850/test_850_pass.edi

────────────────────────────────
VALID 850 EDI PAYLOAD
────────────────────────────────
File: test_850_pass.edi
Content:
  ISA*00*          *00*          *ZZ*LOWES          *ZZ*ACMECORP       *260308*1200*^*00401*000000001*0*P*>~
  GS*PO*LOWES*ACMECORP*20260308*1200*1*X*004010~
  ST*850*0001~
  BEG*00*SA*PO-2026-001**20260308~
  PO1*1*100*EA*10.00**VP*SKU-LOWES-001~
  CTT*1~
  SE*4*0001~
  GE*1*1~
  IEA*1*000000001~

────────────────────────────────
INPUTS
────────────────────────────────
  retailer_slug : lowes
  supplier_slug : acme
  edi_s3_key    : lowes/acme/850/test_850_pass.edi
  transaction   : 850
  channel       : gs1
  po_number     : PO-2026-001

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Pre-Check: Verify THESIS.md in S3
  Confirm: certportal-raw-edi bucket contains lowes/acme/THESIS.md
  If missing: Moses will raise ThesisMissing — scenario cannot proceed.

--- HITL CHECKPOINT 1 --- [AUTO]
Pause here. Ask the operator to confirm:
  [AUTO] [ ] THESIS.md has been uploaded to the correct S3 path: lowes/acme/THESIS.md
  [AUTO] [ ] test_850_pass.edi has been uploaded to: lowes/acme/850/test_850_pass.edi
  [AUTO] [ ] Both files are accessible from the certportal-raw-edi bucket
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 2 — Run Moses CLI
  python -m agents.moses \
    --retailer lowes \
    --supplier acme \
    --edi-key lowes/acme/850/test_850_pass.edi \
    --tx 850 \
    --channel gs1
  Assert: Process exits 0
  Assert: stdout contains "PASS" or ValidationResult.status = "PASS"
  Assert: No "ThesisMissing" exception in stderr

STEP 3 — Verify DB Record Written
  SQL: SELECT status, transaction_type, channel, result_json
       FROM test_occurrences
       WHERE supplier_slug='acme' AND retailer_slug='lowes'
         AND transaction_type='850'
       ORDER BY validated_at DESC LIMIT 1;
  Assert: status = 'PASS'
  Assert: transaction_type = '850'
  Assert: channel = 'gs1'
  Assert: result_json->'errors' is an empty array []

STEP 4 — Verify S3 Result Written
  Assert: S3 object exists at lowes/acme/<correlation_id>_result.json (or similar)
  Assert: JSON contains status='PASS', po_number='PO-2026-001'

--- HITL CHECKPOINT 2 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] Moses exited without errors
  [AUTO] [ ] test_occurrences has a new PASS row for acme/lowes/850
  [AUTO] [ ] result_json shows empty errors array
  [AUTO] [ ] S3 result file exists in the acme workspace
  [AUTO] [ ] GET http://localhost:8002/scenarios as acme_supplier — new PASS scenario appears in list
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] Moses CLI exits 0
  [ ] test_occurrences: status=PASS, errors=[]
  [ ] S3 result written to supplier workspace
  [ ] PASS scenario visible in Chrissy /scenarios view
  [ ] Monica log entry written (check monica_memory table)
  [ ] No ThesisMissing exception
```

---

### CHR-03

**Moses EDI Validation — 850 FAIL + Errors Page View**
**Portal:** Chrissy (Supplier) | **Port:** `http://localhost:8002` | **Role:** supplier
**Agent:** Moses + Ryan (triggered by FAIL)

---

> #### AgentBot Prompt — CHR-03

```
You are a certPortal testing agent executing scenario CHR-03.
Tests: Moses flags a malformed 850, records FAIL, Ryan generates patch suggestion,
supplier sees errors in Chrissy /errors page.

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual call and inspecting the response.
  - After FAIL recording, verify via SQL that result_json contains the expected error codes.
  - When checking /errors page, verify EACH error field (code, segment, element, message) — not just HTTP 200.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- CHR-02 completed (THESIS.md in S3, Moses working)
- Ryan agent importable and wired to Moses FAIL signal
- pyedi_core validation is active (not stubbed) OR inject a manual FAIL row

NOTE: If pyedi_core is still stubbed (Sprint 1), Moses always returns PASS.
In that case, use the DIRECT DB SEED approach:
  INSERT INTO test_occurrences (supplier_slug, retailer_slug, transaction_type, channel, status, result_json)
  VALUES ('acme','lowes','850','gs1','FAIL',
    '{"errors":[
      {"code":"E001","segment":"BEG","element":"BEG03",
       "message":"PO number exceeds 22 character maximum: PO-2026-THIS-IS-WAY-TOO-LONG-001"},
      {"code":"E002","segment":"ISA","element":"ISA13",
       "message":"ISA13 must be numeric 9-digit control number"}
    ],"po_number":"PO-2026-THIS-IS-WAY-TOO-LONG-001"}');

  INSERT INTO patch_suggestions (supplier_slug, retailer_slug, error_code, segment, element,
                                  summary, patch_s3_key)
  VALUES
    ('acme','lowes','E001','BEG','BEG03',
     'Truncate PO number to 22 characters maximum', 'lowes/acme/patches/patch_beg03_001.yaml'),
    ('acme','lowes','E002','ISA','ISA13',
     'Replace ISA13 with sequential 9-digit numeric control number', 'lowes/acme/patches/patch_isa13_001.yaml');

────────────────────────────────
INPUTS
────────────────────────────────
  If NOT using stub — upload this malformed 850:
  File: test_850_fail.edi
    ISA*00*          *00*          *ZZ*LOWES          *ZZ*ACMECORP       *260308*1200*^*00401*BADCTRL*0*P*>~
    GS*PO*LOWES*ACMECORP*20260308*1200*1*X*004010~
    ST*850*0001~
    BEG*00*SA*PO-2026-THIS-IS-WAY-TOO-LONG-001**20260308~
    PO1*1*100*EA*10.00**VP*SKU-LOWES-001~
    CTT*1~
    SE*4*0001~
    GE*1*1~
    IEA*1*BADCTRL~

  edi_s3_key : lowes/acme/850/test_850_fail.edi

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Get Supplier Token
  POST http://localhost:8002/token/api
  form: username=acme_supplier, password=certportal_supplier
  Save as SUPPLIER_TOKEN.

STEP 2 — Run Moses (or use DB seed)
  If pyedi_core is active:
    python -m agents.moses --retailer lowes --supplier acme
      --edi-key lowes/acme/850/test_850_fail.edi --tx 850 --channel gs1
    Assert: Process exits 0 (Moses succeeds even on FAIL — it records the result)
    Assert: stdout contains "FAIL" or ValidationResult.status = "FAIL"
  Else (stub mode):
    Run the INSERT SQL from PREREQUISITES above.

STEP 3 — Verify FAIL in DB
  SQL: SELECT status, result_json FROM test_occurrences
       WHERE supplier_slug='acme' AND status='FAIL'
       ORDER BY validated_at DESC LIMIT 1;
  Assert: status = 'FAIL'
  Assert: result_json->'errors' is an array with ≥ 1 error object
  Assert: Each error has: code, segment, element, message fields

--- HITL CHECKPOINT 1 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] FAIL row exists in test_occurrences with error details
  [AUTO] [ ] If Moses ran: stdout showed FAIL status + error codes
  [AUTO] [ ] If stub mode: DB seed looks correct
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 4 — Ryan Signal Check (Moses triggers Ryan on FAIL — INV-01)
  If full Moses ran: Check S3 for ryan trigger signal in workspace
  Assert: S3 object exists at lowes/acme/signals/ryan_trigger_<ts>.json
  Assert: Signal contains: po_number, error_codes[], transaction_type='850'
  (If stub mode: check patch_suggestions table has rows from the seed)

STEP 5 — Supplier Views Errors Page
  GET http://localhost:8002/errors
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 200
  Assert: Response contains error groups with transaction_type='850', errors array
  Assert: Errors show code, segment, element, message
  Assert: Patches from patch_suggestions are associated with the error group

STEP 6 — Supplier Views Patches Page
  GET http://localhost:8002/patches
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 200
  Assert: Seeded patches appear: error_code E001 (BEG03) and E002 (ISA13)
  Assert: applied = false for both

--- HITL CHECKPOINT 2 ---
Pause here. Ask the operator to verify (Chrissy portal in browser):
  [AUTO] [ ] GET http://localhost:8002/errors as acme_supplier — returns HTTP 200
  [AUTO] [ ] Error page shows the FAIL record with 2 errors (BEG03 and ISA13)
  [AUTO] [ ] Each error has: code, segment, element, and message fields
  [HITL] [ ] Visually confirm: each error message is human-readable and actionable
      (e.g. "PO number exceeds 22 character maximum" — not a raw code or stack trace)
  [AUTO] [ ] Patch suggestions linked to errors are present for E001 and E002
  [AUTO] [ ] No errors from other suppliers visible (acme scoping enforced)
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] test_occurrences has FAIL row with detailed error array in result_json
  [ ] Ryan trigger signal written to S3 on FAIL (INV-01 — no direct call)
  [ ] /errors page shows FAIL test_occurrences with error details
  [ ] /patches page shows Ryan's suggestions (applied=false)
  [ ] Error scoping: only acme supplier's errors visible
```

---

### CHR-04

**Ryan Patch — Apply and Reject**
**Portal:** Chrissy (Supplier) | **Port:** `http://localhost:8002` | **Role:** supplier

---

> #### AgentBot Prompt — CHR-04

```
You are a certPortal testing agent executing scenario CHR-04.
Tests: Supplier applies one patch and rejects another from Ryan's suggestions.

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual HTTP call and inspecting the response.
  - After mark-applied, verify via SQL that applied=TRUE in DB — do not trust HTTP 200 alone.
  - After reject, verify via SQL that rejected=TRUE (separate column from applied).
  - Verify S3 revalidation signal exists for applied patch — do not assume.
  - Cross-supplier access test (Step 7): verify the EXACT status code (403/404) — do not assume.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- CHR-03 completed (patch_suggestions table has ≥2 rows for acme)
- Patch endpoints exist: POST /patches/{id}/mark-applied, POST /patches/{id}/reject
- Capture patch IDs from DB:
    SQL: SELECT id, error_code, summary, applied FROM patch_suggestions
         WHERE supplier_slug='acme' ORDER BY created_at DESC LIMIT 2;
    Save: PATCH_ID_1 (BEG03 patch), PATCH_ID_2 (ISA13 patch)

────────────────────────────────
INPUTS
────────────────────────────────
  base_url     : http://localhost:8002
  username     : acme_supplier
  password     : certportal_supplier
  PATCH_ID_1   : (from DB query above — BEG03 truncation patch)
  PATCH_ID_2   : (from DB query above — ISA13 control number patch)

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Get Supplier Token
  POST http://localhost:8002/token/api
  form: username=acme_supplier, password=certportal_supplier
  Save as SUPPLIER_TOKEN.

STEP 2 — View Patches List
  GET http://localhost:8002/patches
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 200, both patches appear with applied=false

STEP 3 — View Patch Content (S3 YAML)
  GET http://localhost:8002/patches/<PATCH_ID_1>/content  (or equivalent endpoint)
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 200
  Assert: Response contains the patch YAML content from S3 key patch_s3_key

--- HITL CHECKPOINT 1 --- [HITL]
Pause here. Ask the operator to:
  [HITL] [ ] Review the content of PATCH_ID_1 (BEG03 truncation) — does it make sense?
  [HITL] [ ] Confirm the patch makes logical sense for the error it addresses
  [HITL] [ ] Review PATCH_ID_2 (ISA13 control number) — decide to reject this one
  [AUTO] [ ] Confirm both patches show applied=false in the DB
Operator types CONTINUE (apply P1, reject P2) or FAIL <reason>.
─────────────────────────

STEP 4 — Apply Patch 1 (BEG03)
  POST http://localhost:8002/patches/<PATCH_ID_1>/mark-applied
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 200, {"status":"applied","patch_id":<PATCH_ID_1>}
  SQL verify: SELECT applied FROM patch_suggestions WHERE id=<PATCH_ID_1>;
  Assert: applied = TRUE
  Assert: S3 signal written to certportal-workspaces at:
    lowes/acme/signals/moses_revalidate_<PATCH_ID_1>_<ts>.json
    Signal triggers Moses to re-validate after patch is applied (INV-01 — no direct call)

STEP 5 — Reject Patch 2 (ISA13)
  POST http://localhost:8002/patches/<PATCH_ID_2>/reject
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 200, {"status":"rejected","patch_id":<PATCH_ID_2>}
  SQL verify: SELECT rejected FROM patch_suggestions WHERE id=<PATCH_ID_2>;
  Assert: rejected = TRUE  (migration 003 adds the 'rejected' BOOLEAN column)
  Note: applied remains FALSE — the patch was neither applied nor marked invalid;
        'rejected' is the separate column tracking operator refusal.

STEP 6 — Patch List Reflects Changes
  GET http://localhost:8002/patches
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: PATCH_ID_1 shows applied=true
  Assert: PATCH_ID_2 shows rejected or is removed from list

STEP 7 — Cross-Supplier Access Denied (Security Check)
  SQL: INSERT INTO patch_suggestions (supplier_slug, retailer_slug, error_code, segment, element,
                                       summary, patch_s3_key)
       VALUES ('other_supplier','lowes','E003','ST','ST01','Dummy patch','lowes/other/patches/dummy.yaml');
  Save as OTHER_PATCH_ID.
  POST http://localhost:8002/patches/<OTHER_PATCH_ID>/mark-applied
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 403 or 404 (acme cannot apply another supplier's patch)

--- HITL CHECKPOINT 2 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] PATCH_ID_1 shows applied=TRUE in DB
  [AUTO] [ ] PATCH_ID_2 shows rejected=TRUE in DB (migration 003 column — distinct from applied)
  [AUTO] [ ] S3 signal moses_revalidate_<PATCH_ID_1>_<ts>.json exists in certportal-workspaces
  [AUTO] [ ] Step 7 returned 403/404 for cross-supplier patch access
  [AUTO] [ ] Patches list in portal reflects the applied/rejected states
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] Patch content endpoint returns YAML from S3
  [ ] mark-applied sets applied=TRUE in DB
  [ ] reject sets rejected state in DB
  [ ] Patches list reflects current states
  [ ] Attempting to modify another supplier's patch returns 403/404
```

---

### CHR-05

**855 PO Acknowledgment + 856 ASN + 810 Invoice Submission**
**Portal:** Chrissy (Supplier) | **Port:** `http://localhost:8002`
**Agent:** Moses (CLI, one run per transaction type)

---

> #### AgentBot Prompt — CHR-05

```
You are a certPortal testing agent executing scenario CHR-05.
Tests: Supplier submits 855 Ack, 856 ASN, and 810 Invoice — all validated by Moses.
PO number PO-2026-001 must exist in test_occurrences (from CHR-02 850 PASS).

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual CLI command and inspecting stdout/stderr.
  - After each Moses run, verify via SQL that the test_occurrences row was written.
  - Verify all 3 transaction types (855, 856, 810) have individual PASS rows — do not batch-report.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- CHR-02 completed (850 PASS exists for PO-2026-001)
- lifecycle_engine is wired (or po_lifecycle table seeded for PO-2026-001)
- THESIS.md in S3 at lowes/acme/THESIS.md

SEED po_lifecycle if lifecycle_engine not yet built (Sprint 1 stub):
  INSERT INTO po_lifecycle (po_number, partner_id, current_state, ordered_qty)
  VALUES ('PO-2026-001','lowes','po_acknowledged',100)
  ON CONFLICT (po_number) DO NOTHING;

MANUAL FILE UPLOAD (operator uploads all 3 files before Step 1):

  File 1: test_855_pass.edi → S3 key: lowes/acme/855/test_855_pass.edi
  ISA*00*          *00*          *ZZ*ACMECORP       *ZZ*LOWES          *260308*1300*^*00401*000000002*0*P*>~
  GS*PR*ACMECORP*LOWES*20260308*1300*2*X*004010~
  ST*855*0001~
  BAK*00*AD*PO-2026-001*20260308~
  PO1*1*100*EA*10.00**VP*SKU-LOWES-001~
  CTT*1~
  SE*4*0001~
  GE*1*2~
  IEA*1*000000002~

  File 2: test_856_pass.edi → S3 key: lowes/acme/856/test_856_pass.edi
  ISA*00*          *00*          *ZZ*ACMECORP       *ZZ*LOWES          *260308*1400*^*00401*000000003*0*P*>~
  GS*SH*ACMECORP*LOWES*20260308*1400*3*X*004010~
  ST*856*0001~
  BSN*00*SH-2026-001*20260308*1400*0001~
  PRF*PO-2026-001****20260308~
  HL*1**S*1~
  HL*2*1*O*1~
  PRF*PO-2026-001~
  HL*3*2*I*0~
  LIN*1*VP*SKU-LOWES-001~
  SN1*1*100*EA~
  SE*10*0001~
  GE*1*3~
  IEA*1*000000003~

  File 3: test_810_pass.edi → S3 key: lowes/acme/810/test_810_pass.edi
  ISA*00*          *00*          *ZZ*ACMECORP       *ZZ*LOWES          *260308*1500*^*00401*000000004*0*P*>~
  GS*IN*ACMECORP*LOWES*20260308*1500*4*X*004010~
  ST*810*0001~
  BIG*20260308*INV-2026-001*20260308*PO-2026-001~
  N1*BT*LOWES COMPANIES INC*93*0601~
  N1*ST*ACMECORP FULFILLMENT*94*ACM001~
  IT1*1*100*EA*10.00**VP*SKU-LOWES-001~
  TDS*100000~
  SE*8*0001~
  GE*1*4~
  IEA*1*000000004~

────────────────────────────────
INPUTS
────────────────────────────────
  retailer_slug : lowes
  supplier_slug : acme
  po_number     : PO-2026-001

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Verify All 3 EDI Files in S3
  Check certportal-raw-edi for all 3 keys (855, 856, 810)

--- HITL CHECKPOINT 1 --- [AUTO]
Pause here. Ask the operator to confirm:
  [AUTO] [ ] test_855_pass.edi uploaded to lowes/acme/855/test_855_pass.edi
  [AUTO] [ ] test_856_pass.edi uploaded to lowes/acme/856/test_856_pass.edi
  [AUTO] [ ] test_810_pass.edi uploaded to lowes/acme/810/test_810_pass.edi
  [AUTO] [ ] All files match the EDI content shown above exactly
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 2 — Moses Validates 855 PO Acknowledgment
  python -m agents.moses --retailer lowes --supplier acme \
    --edi-key lowes/acme/855/test_855_pass.edi --tx 855 --channel gs1
  Assert: Exit 0, status = PASS
  SQL: SELECT status FROM test_occurrences WHERE supplier_slug='acme' AND transaction_type='855'
       ORDER BY validated_at DESC LIMIT 1;
  Assert: status = 'PASS'

STEP 3 — Moses Validates 856 ASN
  python -m agents.moses --retailer lowes --supplier acme \
    --edi-key lowes/acme/856/test_856_pass.edi --tx 856 --channel gs1
  Assert: Exit 0, status = PASS
  SQL: SELECT status FROM test_occurrences WHERE transaction_type='856' ORDER BY validated_at DESC LIMIT 1;
  Assert: status = 'PASS'

STEP 4 — Moses Validates 810 Invoice
  python -m agents.moses --retailer lowes --supplier acme \
    --edi-key lowes/acme/810/test_810_pass.edi --tx 810 --channel gs1
  Assert: Exit 0, status = PASS
  SQL: SELECT status FROM test_occurrences WHERE transaction_type='810' ORDER BY validated_at DESC LIMIT 1;
  Assert: status = 'PASS'

--- HITL CHECKPOINT 2 --- [AUTO]
Pause here. Ask the operator to verify:
  [AUTO] [ ] All 3 Moses runs exited 0 with PASS
  [AUTO] [ ] SQL: SELECT transaction_type, status FROM test_occurrences
           WHERE supplier_slug='acme' AND transaction_type IN ('855','856','810')
           ORDER BY validated_at;
      Expected: 3 rows, all PASS
  [AUTO] [ ] GET http://localhost:8002/scenarios as acme_supplier — 855, 856, 810 PASS rows visible
  [AUTO] [ ] If lifecycle_engine is wired:
        SQL: SELECT po_number, current_state FROM po_lifecycle WHERE po_number='PO-2026-001';
        Expected: current_state reflects the latest transaction (e.g., 'invoiced' after 810)
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] Moses validates 855, 856, 810 — all PASS
  [ ] test_occurrences has 3 new PASS rows (one per transaction type)
  [ ] S3 result files written for each transaction
  [ ] Scenarios page shows all 3 PASS results for acme
  [ ] If lifecycle_engine wired: po_lifecycle state advances after each transaction
```

---

## End-to-End (E2E) Flows

---

### E2E-01

**Full Order-to-Cash: 850 → 855 → 856 → 810 → Gate Progression → Supplier Certified**
**Perspectives:** All 3 (Retailer sets up, Supplier submits, Platform certifies)

---

> #### AgentBot Prompt — E2E-01

```
You are a certPortal testing agent executing scenario E2E-01.
This is a full end-to-end test spanning all 3 portals.
PO number for this run: PO-E2E-001

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual HTTP/CLI call and inspecting the response.
  - After each Moses run, verify via SQL that the test_occurrences row exists with correct PO number.
  - After each gate completion, verify via SQL that the gate state changed in hitl_gate_status.
  - Cross-portal verification at HITL gates: confirm state is consistent across all 3 portals' views.
  - The PO number PO-E2E-001 must appear in every transaction — verify it was NOT fabricated.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

PRE-RUN RESET — start clean:
  DELETE FROM test_occurrences WHERE supplier_slug='acme' AND result_json::text LIKE '%PO-E2E-001%';
  DELETE FROM lifecycle_events WHERE po_number='PO-E2E-001';
  DELETE FROM po_lifecycle WHERE po_number='PO-E2E-001';
  UPDATE hitl_gate_status SET gate_1='PENDING',gate_2='PENDING',gate_3='PENDING' WHERE supplier_id='acme';

────────────────────────────────
PREREQUISITES
────────────────────────────────
- All 3 portals running (8000, 8001, 8002)
- Moses importable, THESIS.md in S3 (lowes/acme/THESIS.md)
- S3 buckets accessible (certportal-raw-edi, certportal-workspaces)
- lifecycle_engine wired OR po_lifecycle managed manually via SQL

────────────────────────────────
PHASE 1 — RETAILER: Confirm EDI Spec is Published
────────────────────────────────

STEP 1 — Retailer checks spec setup
  POST http://localhost:8001/token/api
  form: username=lowes_retailer, password=certportal_retailer
  Save as RETAILER_TOKEN.
  GET http://localhost:8001/spec-setup  (with RETAILER_TOKEN)
  Assert: lowes spec version v2.0-test is present

--- HITL CHECKPOINT 1 (Retailer Phase) --- [HITL]
  [HITL] [ ] Confirm Lowe's EDI spec is visible in spec-setup (correct version, not stale)
  [AUTO] [ ] Confirm retailer_specs table has 1+ row for lowes
  [AUTO] [ ] Confirm THESIS.md is present in S3: certportal-raw-edi/lowes/acme/THESIS.md
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
PHASE 2 — SUPPLIER: Submit all 4 EDI transaction sets
────────────────────────────────

MANUAL SETUP (upload all 4 EDI files to certportal-raw-edi):
  850: lowes/acme/850/e2e_850.edi
       (Use test_850_pass.edi content, replace PO-2026-001 with PO-E2E-001 in BEG03)
  855: lowes/acme/855/e2e_855.edi  (BAK03 = PO-E2E-001)
  856: lowes/acme/856/e2e_856.edi  (PRF01 = PO-E2E-001)
  810: lowes/acme/810/e2e_810.edi  (BIG04 = PO-E2E-001)

STEP 2 — Moses validates 850 PO
  python -m agents.moses --retailer lowes --supplier acme
    --edi-key lowes/acme/850/e2e_850.edi --tx 850 --channel gs1
  Assert: PASS

STEP 3 — Moses validates 855 Ack
  python -m agents.moses --retailer lowes --supplier acme
    --edi-key lowes/acme/855/e2e_855.edi --tx 855 --channel gs1
  Assert: PASS

STEP 4 — Moses validates 856 ASN
  python -m agents.moses --retailer lowes --supplier acme
    --edi-key lowes/acme/856/e2e_856.edi --tx 856 --channel gs1
  Assert: PASS

STEP 5 — Moses validates 810 Invoice
  python -m agents.moses --retailer lowes --supplier acme
    --edi-key lowes/acme/810/e2e_810.edi --tx 810 --channel gs1
  Assert: PASS

--- HITL CHECKPOINT 2 (Supplier Phase) ---
  [AUTO] [ ] All 4 Moses runs returned PASS
  [AUTO] [ ] SQL: SELECT transaction_type, status FROM test_occurrences
           WHERE result_json::text LIKE '%PO-E2E-001%';
      Expected: 4 rows, all PASS (850, 855, 856, 810)
  [HITL] [ ] Open Chrissy portal — visually confirm all 4 transactions visible with PASS status
  [AUTO] [ ] If lifecycle_engine wired:
      SQL: SELECT current_state FROM po_lifecycle WHERE po_number='PO-E2E-001';
      Expected: 'invoiced' or terminal state after 810
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
PHASE 3 — PLATFORM: Gate Progression → Certify Supplier
────────────────────────────────

STEP 6 — Admin completes Gate 1 (Pam portal)
  POST http://localhost:8000/token/api  → admin token
  POST http://localhost:8000/suppliers/acme/gate/1/complete
  Assert: HTTP 200, new_state=COMPLETE
  NOTE: Meredith (retailer portal) has its own gate endpoint:
    POST http://localhost:8001/suppliers/acme/approve-gate/1   (with RETAILER_TOKEN)
    Either portal can be used for gate approval; they share the same DB row.

STEP 7 — Admin completes Gate 2
  POST http://localhost:8000/suppliers/acme/gate/2/complete
  Assert: HTTP 200, new_state=COMPLETE

STEP 8 — Admin completes Gate 3
  POST http://localhost:8000/suppliers/acme/gate/3/complete
  Assert: HTTP 200, new_state=COMPLETE

STEP 9 — Admin certifies supplier
  POST http://localhost:8000/suppliers/acme/gate/3/certify
  Assert: HTTP 200, {"status":"certified","supplier_id":"acme"}

--- HITL CHECKPOINT 3 (Platform Phase) ---
  [AUTO] [ ] SQL: SELECT gate_1,gate_2,gate_3 FROM hitl_gate_status WHERE supplier_id='acme';
      Expected: COMPLETE, COMPLETE, CERTIFIED
  [HITL] [ ] Open Pam portal — visually confirm acme shows CERTIFIED in suppliers list
  [HITL] [ ] Open Chrissy portal (http://localhost:8002/ or /certification) — confirm certification badge visible
  [HITL] [ ] Open Meredith portal — certified_count has increased by 1
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES (full E2E)
────────────────────────────────
  [ ] Retailer's EDI spec visible and current
  [ ] All 4 transaction sets (850/855/856/810) validated PASS for PO-E2E-001
  [ ] po_lifecycle tracks state through full order-to-cash (if wired)
  [ ] Gate 1 → 2 → 3 → CERTIFIED progression enforced in sequence
  [ ] Certification badge visible in Chrissy portal
  [ ] certified_count +1 in Meredith portal dashboard
  [ ] Monica memory has entries for each agent interaction
```

---

### E2E-02

**Failure Recovery Loop: EDI FAIL → Ryan Patch → Supplier Applies → Moses Re-Validates → PASS**
**Perspectives:** Supplier (submits, views errors, applies patch), Platform (monitors Monica)

---

> #### AgentBot Prompt — E2E-02

```
You are a certPortal testing agent executing scenario E2E-02.
This tests the full failure recovery loop: bad EDI → Ryan → patch apply → re-submit → PASS.
PO number: PO-E2E-002

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual call and inspecting the response.
  - After FAIL, verify via SQL that result_json contains the specific error codes.
  - After patch apply, verify via SQL that applied=TRUE — do not trust HTTP 200 alone.
  - After re-submit PASS, verify BOTH rows (FAIL + PASS) exist for PO-E2E-002 — audit trail.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- All portals running
- Moses wired to Ryan via S3 signal (or use DB seed for stub mode)
- If stub mode: Use direct DB inserts as shown in CHR-03

────────────────────────────────
STEPS
────────────────────────────────

STEP 1 — Supplier Token
  POST http://localhost:8002/token/api
  form: username=acme_supplier, password=certportal_supplier
  Save as SUPPLIER_TOKEN.

STEP 2 — Submit Malformed 850 (or seed FAIL)
  Option A (live): Upload test_850_fail.edi (from CHR-03) with PO-E2E-002 in BEG03
    python -m agents.moses --retailer lowes --supplier acme
      --edi-key lowes/acme/850/e2e_850_fail.edi --tx 850 --channel gs1
    Assert: Moses records FAIL, Ryan signal written to S3
  Option B (stub): Run INSERT from CHR-03 with po_number=PO-E2E-002

STEP 3 — Supplier Views Errors
  GET http://localhost:8002/errors
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: FAIL result for PO-E2E-002 visible with error codes

--- HITL CHECKPOINT 1 ---
  [AUTO] [ ] Errors page shows the FAIL for PO-E2E-002
  [HITL] [ ] Visually confirm: error messages are meaningful and actionable
      (e.g. "PO number exceeds 22 character maximum" — operator judges clarity)
  [AUTO] [ ] Ryan's patch suggestions appear alongside the errors
  [HITL] [ ] Decide: which patch to apply to fix BEG03? (operator judgment required)
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

STEP 4 — Supplier Applies the Patch
  SQL: SELECT id FROM patch_suggestions WHERE supplier_slug='acme' AND error_code='E001' LIMIT 1;
  Save as PATCH_ID.
  POST http://localhost:8002/patches/<PATCH_ID>/mark-applied
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: HTTP 200, applied=true

STEP 5 — Re-submit Corrected 850
  Upload corrected EDI file (BEG03 truncated to ≤22 chars, valid ISA13):
  File: e2e_850_fixed.edi → lowes/acme/850/e2e_850_fixed.edi
  BEG*00*SA*PO-E2E-002**20260308~  ← now ≤22 chars
  python -m agents.moses --retailer lowes --supplier acme
    --edi-key lowes/acme/850/e2e_850_fixed.edi --tx 850 --channel gs1
  Assert: PASS
  (Or in stub mode: INSERT a PASS row for PO-E2E-002)

STEP 6 — Errors Page No Longer Shows Active Errors
  GET http://localhost:8002/errors
  Header: Authorization: Bearer <SUPPLIER_TOKEN>
  Assert: PO-E2E-002 either shows PASS or is removed from error list

--- HITL CHECKPOINT 2 --- [AUTO]
  [AUTO] [ ] test_occurrences has both a FAIL and a PASS row for PO-E2E-002 (audit trail preserved)
  [AUTO] [ ] SQL: SELECT status FROM test_occurrences
           WHERE result_json::text LIKE '%PO-E2E-002%' ORDER BY validated_at;
      Expected: first row FAIL, second row PASS
  [AUTO] [ ] patch_suggestions shows applied=TRUE for the E001 patch
  [AUTO] [ ] Errors page no longer flags PO-E2E-002 as active error
  [AUTO] [ ] Admin check: Monica memory has entries for both FAIL and subsequent PASS
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES
────────────────────────────────
  [ ] Initial 850 records FAIL with specific error codes
  [ ] Ryan generates patch suggestions (via signal or seed)
  [ ] Supplier views actionable error messages and patch details
  [ ] Patch marked as applied in DB
  [ ] Corrected 850 re-validates to PASS
  [ ] Full audit trail: both FAIL and PASS rows preserved in test_occurrences
  [ ] Monica memory reflects the failure, patch, and recovery
```

---

### E2E-03

**New Supplier Onboarding from Scratch**
**Perspectives:** Platform creates user → Supplier activates → Retailer publishes spec → Supplier submits → Platform certifies

---

> #### AgentBot Prompt — E2E-03

```
You are a certPortal testing agent executing scenario E2E-03.
This simulates onboarding a brand-new supplier: bolt_supplier.
Full lifecycle: user creation → first login → spec available → 850 PASS → certified.

ANTI-HALLUCINATION RULES (apply to ALL steps):
  - Never report a PASS without executing the actual call and inspecting the response.
  - After user creation, verify via SQL that portal_users row exists with correct role/slugs.
  - After first login, decode JWT and verify all claims (sub, role, supplier_slug, retailer_slug).
  - Verify data isolation: bolt_supplier must NOT see acme data, and vice versa.
  - After certification, verify via SQL + all 3 portal views that CERTIFIED state is consistent.
  - If a step fails, report the EXACT error — do not guess or fabricate a plausible error.

────────────────────────────────
PREREQUISITES
────────────────────────────────
- All 3 portals running
- Admin has user-creation capability (POST /users endpoint or direct DB insert)
- lowes EDI spec already published (from MER-02 or seeded)

────────────────────────────────
PHASE 1 — PLATFORM: Create New Supplier User
────────────────────────────────

STEP 1 — Admin Creates New Supplier User
  POST http://localhost:8000/token/api
  form: username=pam_admin, password=certportal_admin  → ADMIN_TOKEN

  Option A — Use /register form endpoint (correct endpoint — form POST, not JSON API):
    POST http://localhost:8000/register
    Header: Authorization: Bearer <ADMIN_TOKEN>
    Content-Type: application/x-www-form-urlencoded
    Form data: username=bolt_supplier  password=BoltPass1!  role=supplier
               supplier_slug=bolt      retailer_slug=lowes
    Assert: HTTP 200, body contains {"status":"created","username":"bolt_supplier"}
    Note: The /register endpoint uses Form() params, not a JSON request body.
          Do NOT use Content-Type: application/json — it will be rejected.

  Option B (direct DB if /register not yet built):
    Compute bcrypt hash of "BoltPass1!" (rounds=12) and insert:
    INSERT INTO portal_users (username, hashed_password, role, supplier_slug, retailer_slug)
    VALUES ('bolt_supplier', '<bcrypt_hash>', 'supplier', 'bolt', 'lowes');

    INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
    VALUES ('bolt', 'PENDING', 'PENDING', 'PENDING', 'pam_admin');

--- HITL CHECKPOINT 1 (Platform) --- [AUTO]
  [AUTO] [ ] portal_users table has row for bolt_supplier with role=supplier
  [AUTO] [ ] hitl_gate_status has row for 'bolt' with all PENDING
  [AUTO] [ ] No test_occurrences rows for bolt yet
  [AUTO] [ ] GET http://localhost:8000/suppliers — new bolt supplier appears in list
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
PHASE 2 — SUPPLIER: First Login + Initial State
────────────────────────────────

STEP 2 — New Supplier First Login
  POST http://localhost:8002/token/api
  form: username=bolt_supplier, password=BoltPass1!
  Assert: HTTP 200 with valid JWT
  Decode JWT: sub=bolt_supplier, role=supplier, supplier_slug=bolt, retailer_slug=lowes

STEP 3 — Supplier Dashboard (empty state)
  GET http://localhost:8002/  (with bolt_supplier token)
  Assert: total_tests = 0, passed_tests = 0, progress_pct = 0
  Assert: all gates show PENDING

--- HITL CHECKPOINT 2 (Supplier) ---
  [HITL] [ ] Open Chrissy portal as bolt_supplier — visually confirm empty-state dashboard
  [AUTO] [ ] Dashboard shows 0 tests, all gates PENDING
  [AUTO] [ ] GET http://localhost:8002/scenarios — empty (no prior test_occurrences for bolt)
  [AUTO] [ ] Bolt supplier cannot see acme's scenarios (supplier_slug scoping enforced)
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
PHASE 3 — SUPPLIER: Submit First 850
────────────────────────────────

MANUAL SETUP: Upload bolt's test 850 to S3:
  Upload bolt/system/THESIS.md (any markdown content) to certportal-raw-edi
  Upload to certportal-raw-edi: lowes/bolt/850/bolt_850_pass.edi
  Content: same as test_850_pass.edi but GS06 receiver = BOLT, BEG03 = PO-BOLT-001

STEP 4 — Moses Validates Bolt's 850
  python -m agents.moses --retailer lowes --supplier bolt
    --edi-key lowes/bolt/850/bolt_850_pass.edi --tx 850 --channel gs1
  Assert: PASS

--- HITL CHECKPOINT 3 (Supplier) --- [AUTO]
  [AUTO] [ ] test_occurrences has PASS row for bolt/lowes/850
  [AUTO] [ ] GET http://localhost:8002/ as bolt_supplier — total_tests=1, passed_tests=1 (100%)
  [AUTO] [ ] Acme cannot see bolt's test results (supplier_slug scoping enforced)
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
PHASE 4 — PLATFORM: Advance Gates → Certify
────────────────────────────────

STEP 5 — Advance Bolt Through Gates (Pam or Meredith portal)
  Option A — Admin via Pam:
    POST http://localhost:8000/suppliers/bolt/gate/1/complete  → Assert 200
    POST http://localhost:8000/suppliers/bolt/gate/2/complete  → Assert 200
    POST http://localhost:8000/suppliers/bolt/gate/3/complete  → Assert 200
    POST http://localhost:8000/suppliers/bolt/gate/3/certify   → Assert 200 certified
  Option B — Retailer via Meredith (correct endpoint path — uses approve-gate):
    POST http://localhost:8001/suppliers/bolt/approve-gate/1   (with RETAILER_TOKEN) → Assert 200
    POST http://localhost:8001/suppliers/bolt/approve-gate/2   → Assert 200
    POST http://localhost:8001/suppliers/bolt/approve-gate/3   → Assert 200
    Then certify via Pam: POST http://localhost:8000/suppliers/bolt/gate/3/certify
  Note: Meredith gate endpoint is /approve-gate/{gate}, NOT /gate/{gate}/complete

--- HITL CHECKPOINT 4 (Platform) ---
  [AUTO] [ ] hitl_gate_status: gate_1=COMPLETE, gate_2=COMPLETE, gate_3=CERTIFIED for bolt
  [HITL] [ ] Open Pam portal — visually confirm bolt shows CERTIFIED in suppliers list
  [AUTO] [ ] GET http://localhost:8001/ as lowes_retailer — certified_count has increased
  [HITL] [ ] Open Chrissy portal (http://localhost:8002/ or /certification) as bolt_supplier
      Confirm certification badge visible on dashboard
  [AUTO] [ ] If lifecycle_engine wired — SQL audit:
      SELECT po.*, le.event_type, le.new_state
      FROM po_lifecycle po
      LEFT JOIN lifecycle_events le ON po.po_number = le.po_number
      WHERE po.partner_id = 'lowes' AND po.po_number = 'PO-BOLT-001';
Operator types CONTINUE or FAIL <reason>.
─────────────────────────

────────────────────────────────
EXPECTED OUTCOMES (full E2E-03)
────────────────────────────────
  [ ] New supplier user created with correct role/scope
  [ ] First login works, JWT correctly scoped
  [ ] Empty dashboard on first login (0 tests, all PENDING)
  [ ] 850 validates PASS, dashboard updates to 1/1 (100%)
  [ ] Gate 1→2→3→CERTIFIED progression succeeds in sequence
  [ ] CERTIFIED status visible across all 3 portals
  [ ] Data isolation: bolt cannot see acme data; acme cannot see bolt data
```

---

## Quick Reference — SQL Verification Queries

```sql
-- Check all test_occurrences for a supplier
SELECT transaction_type, status, validated_at FROM test_occurrences
WHERE supplier_slug = 'acme' ORDER BY validated_at DESC LIMIT 20;

-- Check gate progression
SELECT supplier_id, gate_1, gate_2, gate_3, last_updated_by FROM hitl_gate_status;

-- Check HITL queue (pending only)
SELECT queue_id, agent, summary, status, queued_at FROM hitl_queue
WHERE status = 'PENDING_APPROVAL';

-- Check Monica memory (last 10 entries)
SELECT agent, direction, LEFT(message,80) AS msg, retailer_slug, supplier_slug
FROM monica_memory ORDER BY timestamp DESC LIMIT 10;

-- Check lifecycle state (if lifecycle_engine wired)
SELECT po_number, current_state, is_terminal, ordered_qty, shipped_qty
FROM po_lifecycle WHERE partner_id = 'lowes' ORDER BY created_at DESC LIMIT 10;

-- Check lifecycle audit trail
SELECT po_number, event_type, prior_state, new_state, transaction_set, processed_at
FROM lifecycle_events WHERE po_number = 'PO-2026-001' ORDER BY processed_at;

-- Check revoked tokens after logout
SELECT jti, expires_at, revoked_at FROM revoked_tokens ORDER BY revoked_at DESC LIMIT 5;

-- Reset acme gates for re-testing
UPDATE hitl_gate_status
SET gate_1='PENDING', gate_2='PENDING', gate_3='PENDING', last_updated_by='test_reset'
WHERE supplier_id = 'acme';
```

---

## Invariant Compliance Checklist (run after all scenarios)

After completing all scenarios, verify the following architectural invariants held throughout testing:

```
INV-01 S3-only inter-agent:
  [ ] Grep portals/ for "from agents." → should return 0 results
  [ ] Grep portals/ for "import agents." → should return 0 results
  [ ] All agent triggers verified via S3 signal files, never direct calls

INV-02 Violations route through Monica:
  [ ] All FAIL test_occurrences triggered a ryan signal in S3 (not a direct ryan call)
  [ ] Monica memory table has entries for each agent interaction

INV-03 Gate ordering enforced:
  [ ] PAM-03 confirmed 2x 409 GateOrderViolation on out-of-order gate attempts
  [ ] Gate 1 always completed before Gate 2; Gate 2 before Gate 3

INV-05 Append-only log:
  [ ] SQL: SELECT COUNT(*) FROM lifecycle_events WHERE id IN
          (SELECT id FROM lifecycle_events ORDER BY id DESC LIMIT 100)
       — verify no UPDATEs or DELETEs were issued against this table

NC-03 PO number is primary key everywhere:
  [ ] Every test_occurrences row has a po_number in result_json
  [ ] Every lifecycle_events row has a po_number
  [ ] S3 signal files include po_number field

NC-05 strict_mode:
  [ ] lifecycle_engine/config.yaml has strict_mode: false for local dev
  [ ] Do NOT run strict_mode: true tests against production data
```

---

*End of real-life-test-scenarios.md — certPortal Sprint 1–6 | 2026-03-10*
