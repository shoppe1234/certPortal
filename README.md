# certPortal

Cloud-native, multi-tenant EDI certification platform. Sprints 1–6 + Portal Refactoring complete. 189 Playwright E2E checks, 0 failures.

## Architecture

**6-agent deterministic Python pipeline** (agents named after *The Office* characters):

| Agent | Role | LLM |
|---|---|---|
| Monica | Orchestrator + HITL Keeper | GPT-4o-mini (HITL summaries) |
| Dwight | Spec Analyst (PDF → THESIS.md) | GPT-4o |
| Andy | YAML Mapper (3-path ingestion) | GPT-4o-mini (Path 1 only) |
| Moses | Payload Analyst (EDI validation + lifecycle hook) | None — fully deterministic |
| Kelly | Multi-Channel Communications (email/Teams/Google Chat) | GPT-4o-mini + Gemini Flash-Lite (thread memory) |
| Ryan | Patch Generator | GPT-4o-mini |

**3 portals** (FastAPI + Jinja2 + HTMX):

| Portal | Audience | Port | Theme |
|---|---|---|---|
| Pam | certPortal Admins | 8000 | Pink accent, defaults dark |
| Meredith | Retailer EDI Managers | 8001 | Blue accent |
| Chrissy | Supplier EDI Coordinators | 8002 | Amber accent, warm task-focused |

**Core modules:**

| Module | Purpose |
|---|---|
| `lifecycle_engine/` | Order-to-cash state machine — tracks every PO through 850→855→856→810 (psycopg2, no ORM) |
| `schema_validators/` | Pykwalify-based YAML validation — CI gate + Andy Path 2 runtime gate |
| `edi_framework/` | Read-only YAML specs: 6 transactions, 6 mappings, lifecycle state machine, meta-schemas |
| `pyedi_core/` | X12/CSV/fixed-length EDI parser with lifecycle hook |
| `certportal/core/` | Shared: auth (JWT + bcrypt), S3 workspace, gate enforcer, config, email utils |

## Setup

```bash
# 1. Create .env from template
cp .env.template .env
# Fill in: CERTPORTAL_DB_URL, OVH_S3_KEY, OVH_S3_SECRET, OPENAI_API_KEY,
#          CERTPORTAL_JWT_SECRET, and optionally SMTP_*, GEMINI_API_KEY

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install package (makes certportal.core importable)
pip install -e .

# 4. Run Postgres migrations (in order)
psql $CERTPORTAL_DB_URL -f migrations/001_app_tables.sql
psql $CERTPORTAL_DB_URL -f lifecycle_engine/migrations/001_lifecycle_tables.sql
psql $CERTPORTAL_DB_URL -f migrations/002_users_table.sql
psql $CERTPORTAL_DB_URL -f migrations/003_patch_reject.sql
psql $CERTPORTAL_DB_URL -f migrations/004_revoked_tokens.sql
psql $CERTPORTAL_DB_URL -f migrations/005_password_reset.sql
psql $CERTPORTAL_DB_URL -f migrations/007_wizard_sessions.sql
psql $CERTPORTAL_DB_URL -f migrations/008_retailer_specs_v2.sql
psql $CERTPORTAL_DB_URL -f migrations/009_exception_requests.sql
psql $CERTPORTAL_DB_URL -f migrations/010_template_library.sql
psql $CERTPORTAL_DB_URL -f migrations/011_expanded_gates.sql

# 5. Run portals (each in its own terminal or via Procfile)
uvicorn portals.pam:app --port 8000
uvicorn portals.meredith:app --port 8001
uvicorn portals.chrissy:app --port 8002
```

## Running agents (CLI)

```bash
# Dwight — process a retailer PDF spec
python -m agents.dwight --retailer elior --pdf-key tpg/elior-guide.pdf

# Moses — validate a supplier's EDI file
python -m agents.moses --retailer elior --supplier acme --edi-key raw/850.edi --tx 850 --channel gs1

# Monica — orchestrate one pipeline run
python -m agents.monica --retailer elior --supplier acme

# Kelly — generate a communication
python -m agents.kelly --retailer elior --supplier acme --channel email --thread-id t001 --trigger validation_fail

# Kelly — dispatch approved HITL messages
python -m agents.kelly --dispatch-approved

# Ryan — generate patches (reads ValidationResult from S3)
python -m agents.ryan --retailer elior --supplier acme --result-key results/850_20260305T120000.json
```

## Running tests

```bash
# Run all 9 suites (A–I)
python -m testing.certportal_jules_test
```

| Suite | Focus |
|---|---|
| A | Portal auth — JWT, bcrypt, refresh tokens, revocation, password reset |
| B | Agent unit tests — Andy YAML validation, Ryan thesis lookup |
| C | Gate enforcer (INV-03) |
| D | S3 workspace scope |
| E | HITL flow — Monica → Pam → Kelly |
| F | End-to-end lifecycle engine (requires live Postgres) |
| G | Moses lifecycle hook |
| H | Sprint 4 integration — signals, patches, dispatch, escalation |
| I | Kelly Gemini Flash-Lite memory consolidation |

## Playwright E2E CLI

```bash
# Apply test data seed (once, or after DB reset)
psql "$CERTPORTAL_DB_URL" -f playwrightcli/fixtures/seed.sql

# Full run — headed browser, requirements verification active
python -m playwrightcli --portal all --verify

# Headless, idempotent (safe to run repeatedly without re-seeding)
python -m playwrightcli --portal all --verify --headless

# Single portal
python -m playwrightcli --portal pam --verify --headless

# Dry-run: show planned steps + requirement IDs, no browser
python -m playwrightcli --portal all --verify --dry-run
```

**Current coverage (Steps #1–8, #10 + Portal Refactoring):** 189 checks across 14 flows, 0 failures.

| Flow | Steps | Checks | Focus |
|------|-------|--------|-------|
| PAM | 10 | 40 | Auth, Dashboard, Retailers, Suppliers, HITL, Gate enforcement, Password reset, JWT revocation, Memory |
| Meredith | 7 | 24 | Auth, Spec setup, Supplier status, YAML Wizard signals |
| Chrissy | 7 | 30 | Auth, Dashboard, Scenarios, Errors, Patches, Signals, Certification |
| Scope | 8 | 14 | Multi-tenant isolation (INV-06), Certification full flow |
| RBAC | 3 | 3 | Cross-portal role enforcement |
| Lifecycle-Wizard | 10 | 8 | Lifecycle wizard E2E |
| Layer2-Wizard | 10 | 9 | Layer 2 YAML wizard E2E |
| Wizard-Session | 5 | 4 | Multi-session persistence |
| Health | 4 | 33 | HTMX, SRI, buttons, console, assets |
| Onboarding | 20 | 20 | 6-step supplier onboarding wizard |
| Exception | 12 | 12 | Exception request → approve/deny → Kelly signal |
| Template | 10 | 10 | PAM create/publish → Meredith adopt/fork |
| Gate-Model | 8 | 8 | Gate A/B/1/2/3 enforcement, binary states |
| Visual | 5 | 5 | Design system, dark mode, responsive |

See `TODO.md` for Step #9 (Monica escalation, deferred) and remaining project to-dos.

## Database

PostgreSQL via `CERTPORTAL_DB_URL`. Two drivers:

| Driver | Used by | Context |
|---|---|---|
| `psycopg2` | `lifecycle_engine/`, `agents/monica.py` | Synchronous agent/library code |
| `asyncpg` | Portals, `certportal/core/auth.py` | Async FastAPI endpoints |

**Tables** (6 migrations):

| Table | Migration | Purpose |
|---|---|---|
| App tables (gate_status, hitl_queue, etc.) | 001_app_tables.sql | Core application state |
| po_lifecycle | lifecycle_engine/001 | One row per PO — current state + qty columns |
| lifecycle_events | lifecycle_engine/001 | Append-only audit trail of every state transition |
| lifecycle_violations | lifecycle_engine/001 | Every failed validation or illegal transition |
| portal_users | 002 | Bcrypt-hashed credentials, roles, retailer/supplier scoping |
| patch_suggestions.rejected | 003 | Added rejected column to patch suggestions |
| revoked_tokens | 004 | JWT revocation — jti-based, with expiry cleanup |
| password_reset_tokens | 005 | Single-use 60-minute email reset tokens |

## Architectural invariants

See `DECISIONS.md` for all Sprint 1–6 decisions (ADR-001 through ADR-025).

Key invariants (enforced in code):
- **INV-01**: Agents never import each other (S3 workspace is the only inter-agent channel)
- **INV-02**: All agent ambiguity routes through Monica via PAM-STATUS.json flags
- **INV-03**: Gate ordering enforced by `gate_enforcer.py` (raises `GateOrderViolation`)
- **INV-04**: No LangChain — explicit OpenAI client calls only
- **INV-05**: `MONICA-MEMORY.md` is append-only (never opened with `"w"`)
- **INV-06**: `S3AgentWorkspace` scopes all paths to `{retailer_slug}/{supplier_slug}/`
- **INV-07**: Portals never import from `agents/`

## Sprint history

| Sprint / Step | Key deliverables |
|---|---|
| Sprint 1 | lifecycle_engine/, schema_validators/, edi_framework/, pyedi_core hook, Moses integration |
| Sprint 2 | JWT HS256 auth across all portals, Suite B–F tests, coverage hardening |
| Sprint 3 | /register (admin), /change-password (all portals), bcrypt DB-backed auth |
| Sprint 4 | Refresh tokens, Meredith workspace signals, Chrissy patch apply/reject, Kelly real dispatch, Monica escalation |
| Sprint 5 | JWT revocation via revoked_tokens table, JTI claims |
| Sprint 6 | Email password reset, Kelly Gemini Flash-Lite memory, revoked token cleanup |
| CLI Step #1 | `playwrightcli/fixtures/seed.sql` — idempotent test data; unblocks 9 previously-skipped checks |
| CLI Step #2 | Signal integration tests — YAML Wizard Path 2, Patch Apply, HITL Approve → S3 (SIG-YAML2/PATCH/HITL) |
| CLI Step #3 | Multi-tenant scope isolation — INV-06 verified at the UI layer (SCOPE-SUP-01..08, SCOPE-RET-01..04); meredith.py scope leak fixed |
| CLI Step #4 | Gate enforcement UI — INV-03 verified at HTTP layer: 409 on out-of-order, 200 on legal (INV03-GATE-01..03) |
| CLI Step #5 | Password reset E2E — full forgot→token→reset→login→restore cycle, fully idempotent (PW-RESET-01..05) |
| CLI Step #6 | JWT revocation E2E — logout → access blocked → new login succeeds (JWT-REV-01..03); pam_flow |
| CLI Step #7 | RBAC cross-portal enforcement — supplier/retailer blocked on wrong-role routes (RBAC-01..03); new rbac_flow.py |
| CLI Step #8 | Certification full flow — gate_3=CERTIFIED badge verified in Chrissy dashboard + /certification (CHR-CERT-03..04); scope_flow |
| CLI Step #10 | Andy Path 1 & 3 signals — S3 signal coverage for all 3 YAML wizard ingestion paths (SIG-YAML1/YAML3-01..03); meredith_flow |
