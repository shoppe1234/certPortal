# certPortal — TODO

Sprints 1–6 complete. playwrightcli Steps #1–8, #10 complete.
Wizard Refactoring (Phases A–P) complete: two-wizard architecture, 23 new requirement checks.
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

### ~~Step #10 — Andy Path 1 & Path 3 Signals~~ ✓ COMPLETE (Path 1 now deprecated)
Added `meredith::yaml-wizard-path3-signal` step to `meredith_flow.py`.
Path 1 deprecated per ADR-032 (returns 410 Gone). SIG-YAML1-01..03 marked SKIP.
Path 3 active: SIG-YAML3-01..03 (3 checks). Deprecation checks: DEPR-01..02 (2 checks).

### ~~Step #11 — Wizard E2E Flows~~ ✓ COMPLETE (Wizard Refactoring Phase P)
Three new standalone flows added:
- `lifecycle_wizard_flow.py` — Lifecycle wizard end-to-end (LC-WIZ-01..08, 8 checks)
- `layer2_wizard_flow.py` — Layer 2 YAML wizard end-to-end (L2-WIZ-01..09, 9 checks)
- `wizard_session_flow.py` — Multi-session persistence (WIZ-SESS-01..04, 4 checks)
New fixture: `artifact_checker.py` (standalone S3 artifact checker, ADR-027 compliant).

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
- Blocks PRs that break any requirement checks

**Database Migration Tooling** (`scripts/migrate.py`)
- A single script that applies all 8 migration files in order
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

### Deferred — Wizard Refactoring

**Dwight Re-incorporation**
- Reconnect PDF analysis as optional/admin fallback for spec creation
- Dwight agent stays in codebase, just disconnected from Meredith wizard flow
- Files: `agents/dwight.py`, `portals/meredith.py`

**Andy Path 1 (PDF → YAML)**
- Re-enable when Dwight is re-incorporated
- Path 1 signal handler currently returns 410 Gone
- Files: `agents/andy.py`, `portals/meredith.py`

**lab_850 Seed Integration**
- Re-enable as optional pre-fill source for Layer 2 wizard
- lab_850 generates wizard_payload JSON that can seed Layer 2 presets
- Files: `lab_850/seed_generator.py`, `certportal/generators/layer2_builder.py`

**THESIS.md Artifact Format**
- Re-enable when Dwight is re-incorporated
- May become one of the artifact formats alongside MD/HTML/PDF

**Admin Template Upload Portal (PAM)**
- Add PAM route for admins to upload pre-formatted Layer 2 templates
- Templates become available to all retailers in the Layer 2 wizard
- Competitive advantage: curated templates as a service offering
- Files: `portals/pam.py`, `edi_framework/templates/`

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

**Dwight E2E Test** *(blocked — Dwight disconnected from Meredith per ADR-032)*
- `agents/dwight.py` is built but has no Playwright-layer test
- `POST /spec-setup/upload` now returns 410 Gone — Dwight trigger removed
- Deferred until Dwight re-incorporation (see "Deferred — Wizard Refactoring" below)
- When re-enabled: add test fixture PDF, POST via reconnected route, verify THESIS.md in S3

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

PAM            40 checks  (auth, dashboard, retailers, suppliers, HITL, gate enforcement, password reset, JWT revocation, memory)
MEREDITH       24 checks  (auth, spec setup, supplier status, YAML wizard signals path 2/3; SIG-YAML1 SKIP — Path 1 deprecated ADR-032)
CHRISSY        30 checks  (auth, dashboard, scenarios, errors, patches, patch signal, certification)
SCOPE          14 checks  (supplier A/B isolation, retailer A/B isolation, cert full flow)
RBAC            3 checks  (supplier→PAM, retailer→Chrissy, supplier→Meredith)
LIFECYCLE-WIZ   8 checks  (LC-WIZ-01..08: page load, version dropdown, tx checkboxes, modes, generate, S3, DB session, resume)
LAYER2-WIZ      9 checks  (L2-WIZ-01..09: presets, segments, overrides, YAML, artifacts, annotations, download, DB, resume)
WIZARD-SESSION  4 checks  (WIZ-SESS-01..04: session create, state JSON, resume step, multiple sessions)
DEPRECATION     2 checks  (DEPR-01..02: /spec-setup/upload 410, /yaml-wizard/path1 410)
────────────────────────
TOTAL         134 checks
```

(Note: SIG-YAML1 S3 checks are SKIP — Path 1 deprecated. SIG-YAML3 S3 checks degrade to SKIP when S3 unavailable.)
