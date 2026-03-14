# certPortal — Claude Code Instructions

## Project State

Sprints 1–6 are complete. playwrightcli Steps #1–8 and #10 are complete.
Wizard Refactoring (Phases A–P) is complete: two-wizard architecture replacing PDF upload,
23 new requirement checks (LC-WIZ, L2-WIZ, WIZ-SESS, DEPR), 3 SIG-YAML1 checks marked SKIP.
See `DECISIONS.md` (ADR-001 through ADR-036) for the authoritative record of every
architectural decision made during Sprints 1–6, playwrightcli hardening, and the wizard refactoring.
See `TODO.md` for Step #9 (deferred), wizard-deferred items, and root-level engineering to-dos.

## Architecture Invariants — NEVER VIOLATE
- INV-01: Agents never import each other. S3 is the only inter-agent channel.
- INV-02: All violations route through Monica via PAM-STATUS.json on S3.
- INV-03: Gate ordering enforced by gate_enforcer.py.
- INV-04: No LangChain. Explicit OpenAI calls only.
- INV-05: MONICA-MEMORY.md is append-only. Never open with "w".
- INV-06: S3 paths scoped to {retailer_slug}/{supplier_slug}/.
- INV-07: Portals never import from agents/.

## Constraints
- NC-01: edi_framework/ is READ-ONLY at runtime. Never write to it.
- NC-02: No hardcoded transaction logic in .py files. YAML is the brain.
- NC-03: PO number is the primary key in every table, log, and S3 path.
- NC-04: pyedi_core/ must work standalone without lifecycle_engine/ installed.
- NC-05: strict_mode=false dev, strict_mode=true production.

## Full Technical Specification
Read TECHNICAL_REQUIREMENTS.md for the original Sprint 1 design spec (TRD v2.0)
covering lifecycle_engine/, schema_validators/, Postgres schema, and Moses integration.

## Key Modules

### lifecycle_engine/ (Sprint 1 — complete)
Order-to-cash state machine. Tracks every PO through its lifecycle.
- `engine.py` — LifecycleEngine: 8-step process_event() sequence
- `state_store.py` — Postgres persistence (psycopg2, no ORM, explicit transactions)
- `validators.py` — 5 pure business-rule validators (transition, qty chain, N1, terminal, PO continuity)
- `loader.py` — Loads order_to_cash.yaml at startup, caches in memory
- `interface.py` — Public API: on_document_processed() — the ONLY file pipeline.py imports
- `s3_writer.py` — Writes violations to S3 for Monica (INV-02)
- `exceptions.py` — LifecycleError hierarchy (8 exception classes)
- `config.yaml` — Profile-based strict_mode toggle
- `migrations/001_lifecycle_tables.sql` — po_lifecycle, lifecycle_events, lifecycle_violations

### schema_validators/ (Sprint 1 — complete)
Pykwalify-based YAML validation. Dual role:
1. Dev/CI gate — validates all edi_framework/ YAMLs
2. Andy Path 2 runtime gate — validates uploaded YAMLs before storage

### edi_framework/ (Sprint 1 — complete, read-only at runtime)
- `transactions/` — 6 transaction YAMLs (850, 855, 856, 860, 865, 810)
- `mappings/` — 6 turnaround mapping files
- `lifecycle/order_to_cash.yaml` — State machine definition (717 lines)
- `meta/` — 3 pykwalify meta-schemas
- `lowes_master.yaml` — Transaction registry
- `partner_registry.yaml` — White-label partner registry (Layer 0)
- `templates/layer2_presets.yaml` — Competitive advantage presets

### certportal/generators/ (Wizard Refactoring)
Deterministic spec generation pipeline. Synchronous in-portal Python (no agent signals).
- `x12_source.py` — Dual pyx12/Stedi X12 definition loader. NO HARDCODING.
- `version_registry.py` — Dynamic X12 version enumeration (4010, 4030, 5010)
- `template_loader.py` — Reads partner_registry, presets, lifecycles, transactions
- `lifecycle_builder.py` — Use/copy/create lifecycle modes with pykwalify validation
- `layer2_builder.py` — Preset + override merge with meta-schema validation
- `spec_builder.py` — Merges Layer 1 + Layer 2 → unified spec → MD/HTML/PDF artifacts
- `render_markdown.py` — Companion guide with Layer 2 annotations
- `render_html.py` — Branded HTML (Meredith theme)
- `render_pdf.py` — weasyprint/fpdf2 PDF generation
- `artifact_writer.py` — S3 + DB artifact persistence

### certportal/core/ (Sprints 1–6)
- `auth.py` — JWT HS256 (access + refresh tokens), bcrypt, DB-backed auth with _DEV_USERS fallback, JWT revocation (jti), password reset tokens, revoked token cleanup
- `workspace.py` — S3AgentWorkspace (OVH S3-compatible)
- `gate_enforcer.py` — Gate ordering enforcement (INV-03)
- `email_utils.py` — SMTP helper for password reset emails (INV-07 compliant)
- `config.py` — Pydantic settings
- `database.py` — asyncpg connection pool
- `models.py` — Pydantic models (ValidationResult, ValidationError)
- `monica_logger.py` — Async logging to Monica

### Portals (Sprints 1–6)
All three portals: FastAPI + Jinja2 + HTMX, JWT-protected with role scoping.
- `portals/pam.py` — Admin portal (port 8000): HITL queue, /register (admin-only), dashboard
- `portals/meredith.py` — Retailer portal (port 8001): spec setup, Lifecycle Wizard, Layer 2 YAML Wizard, artifact gallery, workspace signals
- `portals/chrissy.py` — Supplier portal (port 8002): patch apply/reject/content viewer

Auth on all portals: /login, /token, /token/refresh, /logout, /change-password, /forgot-password, /reset-password

### Agents
- `agents/moses.py` — EDI validation (deterministic). Lifecycle hook via _extract_po_from_edi() regex (ADR-012)
- `agents/monica.py` — Orchestrator. Escalation → HITL queue DB write (ADR-022, psycopg2 sync)
- `agents/kelly.py` — Communications. Real dispatch: SMTP, Google Chat, Teams (ADR-020). Gemini Flash-Lite memory (ADR-024)
- `agents/andy.py` — YAML mapper (3 ingestion paths; Path 1 deprecated per ADR-032, returns 410)
- `agents/dwight.py` — PDF spec analyst (GPT-4o; disconnected from Meredith per ADR-032, deferred to TODO)
- `agents/ryan.py` — Patch generator (GPT-4o-mini)

## Database
- CERTPORTAL_DB_URL = Postgres
- **psycopg2** for lifecycle_engine/ and agents (synchronous context)
- **asyncpg** for portals and certportal/core/auth.py (async FastAPI context)
- No SQLAlchemy. No ORM.
- All writes in explicit transactions with BEGIN/COMMIT/ROLLBACK.
- lifecycle_events table: INSERT ONLY. Never UPDATE or DELETE.

### Migrations (apply in order)
1. `migrations/001_app_tables.sql` — gate_status, hitl_queue, test_occurrences, etc.
2. `lifecycle_engine/migrations/001_lifecycle_tables.sql` — po_lifecycle, lifecycle_events, lifecycle_violations
3. `migrations/002_users_table.sql` — portal_users (bcrypt, roles, scoping)
4. `migrations/003_patch_reject.sql` — patch_suggestions.rejected column
5. `migrations/004_revoked_tokens.sql` — revoked_tokens (JWT revocation)
6. `migrations/005_password_reset.sql` — password_reset_tokens + portal_users.email column
7. `migrations/007_wizard_sessions.sql` — wizard_sessions (JSONB state, multi-session)
8. `migrations/008_retailer_specs_v2.sql` — retailer_specs v2 (x12_version, artifacts)

## S3 Workspace
- Use existing S3AgentWorkspace abstraction from certportal.core
- Do NOT use raw boto3 directly
- All paths scoped to {retailer_slug}/{supplier_slug}/

## Testing
9 test suites (A–I) orchestrated by `testing/certportal_jules_test.py`:
- Suite A: Portal auth (JWT, bcrypt, refresh, revocation, password reset)
- Suite B: Agent unit tests (Andy, Ryan)
- Suite C: Gate enforcer (INV-03)
- Suite D: S3 workspace scope
- Suite E: HITL flow
- Suite F: End-to-end lifecycle engine (requires live Postgres)
- Suite G: Moses lifecycle hook
- Suite H: Sprint 4 integration (signals, patches, dispatch, escalation)
- Suite I: Kelly Gemini memory consolidation

Run: `python -m testing.certportal_jules_test`

## playwrightcli E2E Harness (Steps #1–8, #10 + Wizard Flows complete)
Self-correcting Playwright CLI with requirements verification.

### Steps completed
- **Step #1** — `playwrightcli/fixtures/seed.sql`: idempotent test data for all 9 previously-skipped checks
- **Step #2** — Signal integration: YAML Wizard Path 2 → S3, Patch Apply → S3, HITL Approve → S3
- **Step #3** — Multi-tenant scope isolation: suppliers/retailers cannot see each other's data (INV-06)
- **Step #4** — Gate enforcement UI: out-of-order advance returns 409, legal advance returns 200 (INV-03)
- **Step #5** — Password reset E2E: forgot → DB token → reset → login → restore (fully idempotent)
- **Step #6** — JWT revocation E2E: logout → protected route blocked → new login succeeds (JWT-REV-01..03)
- **Step #7** — RBAC cross-portal: supplier→PAM blocked, retailer→Chrissy blocked, supplier→Meredith blocked (RBAC-01..03)
- **Step #8** — Certification full flow: cert_supplier (gate_3=CERTIFIED) sees badge on dashboard + /certification (CHR-CERT-03..04)
- **Step #10** — Andy Path 3 signals + Path 1 deprecated: SIG-YAML3-01..03 active; SIG-YAML1-01..03 SKIP (ADR-032)
- **Wizard Flows** — Lifecycle wizard E2E (LC-WIZ-01..08), Layer 2 wizard E2E (L2-WIZ-01..09), wizard session persistence (WIZ-SESS-01..04), deprecation checks (DEPR-01..02)

### Key files
- `playwrightcli/fixtures/seed.sql`            — idempotent test data (apply before first run)
- `playwrightcli/fixtures/signal_checker.py`   — standalone S3 signal scanner (no main codebase imports)
- `playwrightcli/fixtures/artifact_checker.py` — standalone S3 artifact checker (no main codebase imports)
- `playwrightcli/fixtures/token_fetcher.py`    — standalone DB reader for password_reset_tokens
- `playwrightcli/flows/scope_flow.py`          — scope isolation + cert full flow (standalone, no BaseFlow)
- `playwrightcli/flows/rbac_flow.py`           — RBAC cross-portal enforcement (standalone, no BaseFlow)
- `playwrightcli/flows/lifecycle_wizard_flow.py` — lifecycle wizard E2E (standalone, no BaseFlow)
- `playwrightcli/flows/layer2_wizard_flow.py`  — Layer 2 YAML wizard E2E (standalone, no BaseFlow)
- `playwrightcli/flows/wizard_session_flow.py` — multi-session persistence E2E (standalone, no BaseFlow)
- `playwrightcli/requirements_verifier.py`     — all verify_* methods; accumulates PASS/FAIL/SKIP

### Isolation constraint (ADR-027)
playwrightcli/ must NEVER import from certportal/, portals/, agents/, or lifecycle_engine/.
All fixtures use only stdlib + psycopg2 + boto3 (third-party only).

### Run
```bash
# Apply seed once (or after resetting DB)
psql "$CERTPORTAL_DB_URL" -f playwrightcli/fixtures/seed.sql

# Full run — headed, with requirements verification
python -m playwrightcli --portal all --verify

# Headless, idempotent
python -m playwrightcli --portal all --verify --headless

# Dry-run: show steps and req IDs without opening browser
python -m playwrightcli --portal all --verify --dry-run
```

## Key File Locations
- edi_framework/lifecycle/order_to_cash.yaml   — state machine definition
- edi_framework/lowes_master.yaml              — transaction registry
- edi_framework/partner_registry.yaml          — white-label partner registry (Layer 0)
- edi_framework/templates/layer2_presets.yaml  — competitive advantage presets
- pyedi_core/config/config.yaml               — parser runtime config (partner_id: lowes)
- lifecycle_engine/config.yaml                — engine config (strict_mode profiles)
- certportal/core/auth.py                     — JWT + bcrypt + revocation + password reset
- certportal/core/email_utils.py              — SMTP helper for reset emails
- certportal/generators/spec_builder.py       — Layer 1 + Layer 2 merge → artifacts
- certportal/generators/x12_source.py         — dynamic X12 definition loader (pyx12 + Stedi)
- playwrightcli/fixtures/seed.sql             — E2E test data seed (apply before harness)
- instructions/wizard_refactoring_prompt.md   — approved wizard refactoring spec (Phases A–P)
