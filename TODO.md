# certPortal — TODO

Sprints 1–6 complete. playwrightcli Steps #1–5 complete (97 checks, 27 steps, all PASS).
Items below are the next logical layer of work, grouped by category.

---

## playwrightcli — Next Steps (Step #6+)

These extend the E2E harness. Each follows the same pattern:
add a step to a flow, add a `verify_*` method to `requirements_verifier.py`,
add seed data if needed, and register in `cli.py`.

### Step #6 — JWT Revocation E2E
**Goal:** prove that a JWT is dead after logout — reusing the cookie returns 401 / redirect to /login.

- Log in as `pam_admin`, capture the `access_token` cookie value via `page.evaluate`
- POST `/logout` to revoke it
- Replay the captured token in a fetch to a protected route (e.g. `/suppliers`)
- Assert HTTP 401 or redirect to `/login` (not 200)

New requirements:
```
JWT-REV-01  Logout POSTs to /logout and redirects to /login
JWT-REV-02  Revoked token rejected on protected route (401 / redirect)
JWT-REV-03  New login after logout succeeds with fresh token
```

---

### Step #7 — RBAC Cross-Portal Enforcement
**Goal:** prove that role guards block access across portals (INV-07 adjacency test).

- `acme_supplier` (role=supplier) attempts GET `http://localhost:8000/suppliers` (PAM — admin only) → expect redirect to /login or 403
- `lowes_retailer` (role=retailer) attempts GET `http://localhost:8002/patches` (Chrissy — supplier only) → expect redirect or 403
- `pam_admin` (role=admin) attempts GET `http://localhost:8002/` (Chrissy — supplier only) → expect redirect or 403

New requirements:
```
RBAC-01  Supplier JWT rejected on PAM admin route
RBAC-02  Retailer JWT rejected on Chrissy supplier route
RBAC-03  Admin JWT rejected on Chrissy supplier route
```

No new seed needed — existing users cover all three cases.

---

### Step #8 — Certification Full Flow (Chrissy)
**Goal:** CHR-CERT-01/02 currently only check page load. Extend to verify gate_3=CERTIFIED is
reflected in the UI (badge, status text, download link if present).

- Seed a `cert_test` supplier with `gate_3='CERTIFIED'` (ON CONFLICT DO UPDATE to reset)
- Log in as `cert_supplier` (add seed user with `supplier_slug='cert_test'`)
- Navigate to `/` (dashboard) and `/certification`
- Assert certification badge and/or "Certified" text is visible

New requirements:
```
CHR-CERT-03  Dashboard shows gate_3=CERTIFIED badge for certified supplier
CHR-CERT-04  /certification page shows certification status and date
```

---

### Step #9 — Monica Escalation Pipeline E2E
**Goal:** prove that a supplier FAIL scenario (EDI validation error) triggers Monica to write
a HITL queue item — end-to-end from test_occurrences row to PAM queue entry.

- Seed a fresh FAIL `test_occurrence` with `status='FAIL'` for a dedicated supplier
- POST to Moses via the agent's HTTP interface (or trigger via a seeded signal) to simulate escalation
- Wait for Monica to process and write to `hitl_queue`
- Verify a new queue item appears in PAM `/hitl-queue` for that supplier

New requirements:
```
MON-ESC-01  FAIL occurrence triggers Monica escalation signal write to S3
MON-ESC-02  Monica reads signal and writes PENDING_APPROVAL item to hitl_queue
MON-ESC-03  New HITL item visible in PAM /hitl-queue for the correct supplier
```

Note: requires Monica to be running as a background process or triggered inline.

---

### Step #10 — Andy Path 1 & Path 3 Signals
**Goal:** the `meredith::yaml-wizard-signal` step covers Path 2 only. Complete the set.

- Path 1: POST `/yaml-wizard/path1` → verify `andy_path1_trigger_*.json` written to S3
- Path 3: POST `/yaml-wizard/path3` → verify `andy_path3_trigger_*.json` written to S3

New requirements:
```
SIG-YAML1-01..03  (mirrors SIG-YAML2-* for Path 1)
SIG-YAML3-01..03  (mirrors SIG-YAML2-* for Path 3)
```

---

## Root Project — Engineering To-Dos

Items that belong in the main codebase, not in the test harness.

### Infrastructure

**Docker Compose** (`docker-compose.yml`)
- Services: `postgres`, `pam` (port 8000), `meredith` (8001), `chrissy` (8002)
- One-command dev startup: `docker compose up`
- Replaces the three-terminal `uvicorn` + manual Postgres workflow
- Include a `seed` init container that applies all migrations + `playwrightcli/fixtures/seed.sql`

**CI/CD Pipeline** (`.github/workflows/portals.yml`)
- Currently only `edi_ci.yml` exists (validates edi_framework/ YAMLs)
- Add: install deps → run migrations → start portals → run Playwright harness (`--headless --verify`)
- Blocks PRs that break any of the 97 requirement checks

**Database Migration Tooling** (`scripts/migrate.py`)
- A single script that applies all 6 migration files in order
- Currently documented in CLAUDE.md but requires manual `psql` calls
- Idempotent (IF NOT EXISTS guards already in place)

---

### Deferred ADR Work

**ADR-003 — JSON Merge Patch for PAM-STATUS.json**
- Monica currently does top-level key merge on `PAM-STATUS.json`
- Upgrade to RFC 7396 JSON Merge Patch so partial updates don't overwrite unrelated keys
- File: `agents/monica.py`

**ADR-012 — Moses Pipeline.run() upgrade**
- Moses extracts PO numbers via `_extract_po_from_edi()` regex fallback
- Upgrade to call `pyedi_core.pipeline.Pipeline.run()` directly
- Removes fragile regex and uses the parser's native PO extraction
- File: `agents/moses.py`

**ADR-025 — pg_cron for revoked token cleanup**
- Currently an in-app asyncio loop runs `DELETE FROM revoked_tokens WHERE expires_at < NOW()`
- Replace with a `pg_cron` scheduled job so cleanup runs even when portals are down
- Migration: `migrations/006_pg_cron_cleanup.sql`

---

### Security & Production Readiness

**Rate Limiting on Auth Endpoints**
- `/token`, `/forgot-password`, `/register` have no rate limiting
- Add `slowapi` or a middleware that caps to N requests/minute per IP
- Prevents credential stuffing and token enumeration

**Admin Audit Log**
- Gate transitions (`/suppliers/{id}/gate/{n}/complete`) have `last_updated_by` in DB
- HITL approvals/rejections are logged but not surfaced in PAM
- Add `/audit-log` page to PAM showing: who, what action, which supplier, when
- DB: existing `hitl_queue.resolved_by` + new `gate_audit_log` table (or use lifecycle_events)

**Secret Management**
- `.env` pattern is correct for dev; production needs a secrets manager
- Document how to plug in AWS Secrets Manager / HashiCorp Vault for `CERTPORTAL_DB_URL`, `S3_*`, API keys

---

### Agent Completeness

**Dwight E2E Test**
- `agents/dwight.py` is built but has no Playwright-layer test
- Add a test fixture PDF (`playwrightcli/fixtures/test_spec.pdf`)
- POST it via Meredith `/spec-setup/upload` and verify Dwight writes a `thesis.md` to S3
- Currently Dwight is only unit-tested via Suite B

**Kelly Dispatch Verification**
- Kelly real dispatch (SMTP, Google Chat, Teams) is tested in Suite I (Gemini memory consolidation)
- No E2E proof that a specific HITL approval actually triggers Kelly to send a real message
- Add an SMTP test double (e.g. `mailhog` in Docker) so the Playwright step can verify email delivery
- Requirement: `KELLY-DISPATCH-01..03`

---

### UX / Product

**Nav-bar completions (all three portals)**
- `/register` link only appears on PAM; confirmed admin-only but not linked from dashboard
- `/change-password` exists but not in primary nav — referenced only from footer on some portals

**Account Deletion**
- No `/delete-account` or admin-initiated deactivation UI
- DB has `is_active BOOLEAN` column on `portal_users` — wiring exists, UI does not

**React Frontend** *(explicitly deferred — noted in DECISIONS.md as out-of-scope for Sprints 1–6)*
- Current: FastAPI + Jinja2 + HTMX
- Future: React SPA + FastAPI JSON API
- No action needed until a new sprint is scoped

---

## Quick Reference — Current Harness State

```
python -m playwrightcli --portal all --verify --headless

PAM      37 checks  (auth, dashboard, retailers, suppliers, HITL, gate enforcement, password reset, memory)
MEREDITH 18 checks  (auth, spec setup, supplier status, YAML wizard signal)
CHRISSY  30 checks  (auth, dashboard, scenarios, errors, patches, patch signal, certification)
SCOPE    12 checks  (supplier A/B isolation, retailer A/B isolation)
─────────────────
TOTAL    97 checks  0 FAIL  0 SKIP
```
