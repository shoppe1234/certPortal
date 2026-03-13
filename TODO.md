# certPortal — TODO

Sprints 1–6 complete. playwrightcli Steps #1–8, #10 complete (112 checks, 35 steps, all PASS).
Items below are the next logical layer of work, grouped by category.

---

## playwrightcli — Next Steps (Step #6+)

These extend the E2E harness. Each follows the same pattern:
add a step to a flow, add a `verify_*` method to `requirements_verifier.py`,
add seed data if needed, and register in `cli.py`.

### ~~Step #6 — JWT Revocation E2E~~ ✓ COMPLETE
Added `pam::jwt-revocation` step to `pam_flow.py`. Tests: logout → /suppliers blocked → fresh login succeeds.
Requirements: JWT-REV-01..03 (3 checks).

### ~~Step #7 — RBAC Cross-Portal Enforcement~~ ✓ COMPLETE
New `rbac_flow.py` standalone flow. Actual role rules: PAM=admin only, Meredith=admin|retailer, Chrissy=admin|supplier.
Steps: supplier→PAM /suppliers blocked, retailer→Chrissy /patches blocked, supplier→Meredith /supplier-status blocked.
Requirements: RBAC-01..03 (3 checks).

### ~~Step #8 — Certification Full Flow (Chrissy)~~ ✓ COMPLETE
Added `cert_supplier` (supplier_slug=cert_test, gate_3=CERTIFIED) to seed.sql. Added `scope::cert-dashboard` and
`scope::cert-certification` steps to scope_flow.py. Verifies CERTIFIED badge on dashboard and /certification.
Requirements: CHR-CERT-03..04 (2 checks).

### Step #9 — Monica Escalation Pipeline E2E (DEFERRED)
**Goal:** prove that a supplier FAIL scenario (EDI validation error) triggers Monica to write
a HITL queue item — end-to-end from test_occurrences row to PAM queue entry.

Requires Monica to be running as a background process or triggered inline — not feasible
in the current automated headless harness. Defer until Docker Compose orchestration is in place.

New requirements:
```
MON-ESC-01  FAIL occurrence triggers Monica escalation signal write to S3
MON-ESC-02  Monica reads signal and writes PENDING_APPROVAL item to hitl_queue
MON-ESC-03  New HITL item visible in PAM /hitl-queue for the correct supplier
```

### ~~Step #10 — Andy Path 1 & Path 3 Signals~~ ✓ COMPLETE
Added `meredith::yaml-wizard-path1-signal` and `meredith::yaml-wizard-path3-signal` steps to `meredith_flow.py`.
POST /yaml-wizard/path1 and /path3, verify respective S3 andy_pathN_trigger_*.json signals.
Requirements: SIG-YAML1-01..03, SIG-YAML3-01..03 (6 checks).

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

## Documentation & QA

**Master Task List** (`instructions/master_task_list_discussion.md`)
- A per-persona (Admin · Retailer · Supplier) task list covering every portal function,
  login steps, limitations, and sequence numbers for Playwright storyboarding
- Will serve as: internal QA checklist · user manual foundation · screenshot narration script
- Status: **DEFERRED — 8 open questions must be answered first**
- Discussion captured in: `instructions/master_task_list_discussion.md`
- Key decisions needed before writing:
  1. Audience sophistication (EDI-literate vs. plain-language)
  2. Sequence numbering scheme (flat vs. hierarchical)
  3. Error path depth (happy path only vs. full QA coverage)
  4. Account bootstrap flow (admin pre-creates accounts vs. assumed pre-existing)
  5. Limitation tagging (design constraints vs. TODO items separated or combined)
  6. Playwright narration voice (first-person / third-person / imperative)
  7. Screenshot checkpoint granularity (every step vs. milestones only)
  8. Deferred feature treatment (`[FUTURE]` tags vs. excluded entirely)

---

## Quick Reference — Current Harness State

```
python -m playwrightcli --portal all --verify --headless

PAM      40 checks  (auth, dashboard, retailers, suppliers, HITL, gate enforcement, password reset, JWT revocation, memory)
MEREDITH 24 checks  (auth, spec setup, supplier status, YAML wizard signals path 2/1/3)
CHRISSY  30 checks  (auth, dashboard, scenarios, errors, patches, patch signal, certification)
SCOPE    14 checks  (supplier A/B isolation, retailer A/B isolation, cert full flow)
RBAC      3 checks  (supplier→PAM, retailer→Chrissy, supplier→Meredith)
──────────────────
TOTAL   111 checks  0 FAIL  0 SKIP
```

(Note: 112 requirement checks total — SIG-YAML1/YAML3 S3 checks are SKIP when S3 unavailable; HTTP checks always run.)
