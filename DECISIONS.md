# certPortal — Architectural Decision Record (Sprint 1)

Decisions made during Sprint 1 build that were not explicitly covered by the build prompt.
All choices favour the most conservative, explicit, auditable option.

---

## ADR-001: `yaml` dependency added to requirements.txt

**Context:** `agents/andy.py` and `agents/moses.py` require YAML parsing (`.yaml` map files).
**Decision:** Added `PyYAML==6.0.2` to `requirements.txt`. The build prompt listed no YAML
library explicitly, but `pdfplumber` and other libraries were listed. PyYAML is the de-facto
standard X12 YAML tooling dependency.
**Alternative considered:** `ruamel.yaml` (roundtrip-safe). Rejected — overkill for Sprint 1.

---

## ADR-002: `append_log` MONICA-MEMORY.md routing

**Context:** INV-05 requires append-only semantics for `MONICA-MEMORY.md`.
The spec says the file lives at `certportal-workspaces/admin/MONICA-MEMORY.md`.
`S3AgentWorkspace` is always initialised with a `retailer_slug` and optional `supplier_slug`.
**Decision:** `append_log()` detects the `MONICA-MEMORY.MD` key (case-insensitive) and routes
it to the global `admin/` prefix instead of the scoped tenant path. All other log files are
scoped normally.
**Why:** This avoids requiring a separate "admin workspace" class while keeping INV-05
(never `"w"`, always append via download→append→re-upload).

---

## ADR-003: PAM-STATUS.json key structure

**Context:** Multiple agents write to `PAM-STATUS.json` for a given supplier.
The spec says "never overwrites wholesale — always merges."
**Decision:** PAM-STATUS.json is stored at
`{retailer_slug}/{supplier_slug}/PAM-STATUS.json` (unscoped from the workspace prefix).
`write_pam_status()` reads the file, performs a top-level key merge (nested dicts are
recursively merged one level deep), then re-uploads. This matches the spec's "merge patch"
intent while remaining atomic enough for Sprint 1.
**Sprint 2:** Replace with a proper JSON Merge Patch (RFC 7396) implementation.

---

## ADR-004: Monica logger — async DB insert strategy

**Context:** `monica_logger.log()` is a synchronous function (called from agents that are
themselves synchronous). The DB insert is async (asyncpg).
**Decision:** Use `asyncio.ensure_future()` when a running event loop exists (FastAPI context),
and `asyncio.run()` when called from CLI/agent context (no running loop). Failures are caught
and printed — they must not crash agents (best-effort write).
**Risk:** `ensure_future()` in FastAPI may drop the task if the app shuts down mid-flight.
Acceptable for Sprint 1 (ops observability via S3 MONICA-MEMORY.md is the primary log).

---

## ADR-005: Kelly — INV-01 HITL queue duplication

**Context:** Kelly needs to queue drafts for Monica's HITL approval (same logic as
`monica.queue_for_approval()`). INV-01 forbids importing from `agents/monica.py`.
**Decision:** Kelly implements `_queue_for_monica_hitl()` internally — a private function
that replicates the queue-write logic (write to PAM-STATUS.json) without calling Monica.
Monica reads the queue on its next `run()` invocation.
**Note:** This is intentional duplication of ~20 lines to preserve INV-01.

---

## ADR-006: pyedi_core stub

**Context:** The build prompt says to stub `pyedi_core.validate()`. The library is not in
`requirements.txt` (it is a future/custom dependency).
**Decision:** In `agents/moses.py`, we attempt `import pyedi_core` and define an in-module
stub class `_PyEdiCoreStub` on `ImportError`. The stub always returns an empty error list
(i.e., all EDI is "valid" in Sprint 1). This makes Moses runnable without the real library.

---

## ADR-007: HTMX partial templates

**Context:** Portals reference HTMX partial templates (`_gate_status_row.html`, etc.) that
are not listed in the spec's `templates/` directory listing.
**Decision:** Created these as minimal fragment templates (no `{% extends %}`). They are
prefixed with `_` to signal they are partials, not full pages.

---

## ADR-008: Portal JWT authentication

**Context:** `python-jose[cryptography]` is in requirements.txt but the spec does not
specify JWT route protection for Sprint 1.
**Decision:** Sprint 1 portals run without JWT middleware. Routes return first-row DB data
(no user context). JWT auth skeleton is deferred to Sprint 2.
**Note in code:** `# Sprint 1: no auth — show first supplier found` comments mark where
JWT-based user lookup will be inserted.

---

## ADR-009: Gate enforcer SQL injection prevention

**Context:** `gate_enforcer.py:transition_gate()` builds a SQL statement with
`f"gate_{gate}"` (an integer) in the column name. This is technically dynamic SQL.
**Decision:** Gate number is validated against `(1, 2, 3)` before use and comes from
internal caller logic (not user input). Risk is low. Noted here for Sprint 2 audit.

---

## ADR-010: `download_retailer_map` method on S3AgentWorkspace

**Context:** Moses and Ryan need to download retailer-level files (THESIS.md, YAML maps)
that live at `{retailer_slug}/` without the `/{supplier_slug}/` suffix. The standard
`download()` method scopes to supplier level.
**Decision:** Added `download_retailer_map(key)` method that prefixes with only
`{retailer_slug}/`. Agents initialised with a supplier scope call this method for
retailer-level reads — this is intentional cross-scope access for reading shared retailer
resources, explicitly permitted by the data model.

---

## ADR-011: `prior_state` nullable in `lifecycle_events`

**Context:** The first document in a PO lifecycle (850 Purchase Order) has no predecessor
state — `prior_state` is conceptually NULL at that point.
**Decision:** Changed `prior_state TEXT NOT NULL` to `prior_state TEXT` (nullable) in
`001_lifecycle_tables.sql`. The engine passes `None` for the first event; Postgres stores NULL.
**Impact:** Test_02 in SuiteF verifies `events[0]['prior_state'] is None` explicitly.
**Sprint 2:** No change needed — NULL semantics are correct and self-documenting.

---

## ADR-012: Moses lifecycle hook via `_extract_po_from_edi()` regex

**Context:** Moses calls `pyedi_core.validate()` (segment validation), not `Pipeline.run()`.
The lifecycle hook in `pipeline.py` therefore does not fire for Moses-processed files.
**Decision:** Added direct `on_document_processed()` call in `agents/moses.py` (Step 13b).
Since Moses has only raw EDI content (no parsed payload), a helper `_extract_po_from_edi()`
uses X12 segment regexes to extract the PO number: BEG03 (850), BCH03 (860), BAK03 (855),
BCA03 (865), PRF01 (856), BIG04 (810). If the segment is absent the engine logs a non-fatal
`missing_po` violation (`strict_mode=False` in dev).
**Alternative considered:** Running `Pipeline.run()` inside Moses for the sole purpose of
getting a parsed payload. Rejected — circular coupling, doubles parse time, risk of manifest
side-effects.
**Sprint 2:** When Moses is upgraded to call `Pipeline.run()` directly, remove the regex
fallback and use the parsed payload dict from `pipeline.run(return_payload=True)`.

---

## ADR-013: Lifecycle hook fires only on non-dry-run writes

**Context:** `pipeline.py` has a `dry_run` mode that skips file writes. The lifecycle hook
was placed inside the `if not do_dry_run:` block after `driver.write()`.
**Decision:** Lifecycle events are only recorded for real document writes, not dry-run
executions. This prevents test/simulation runs from polluting the `po_lifecycle` audit trail
and avoids duplicate events when the same file is tested before production processing.
**Impact:** `Pipeline.run(dry_run=True)` will never advance lifecycle state. Document this
in operator runbooks.
**Sprint 2:** Consider adding a `lifecycle_dry_run` flag to `lifecycle_engine/config.yaml`
if staging environments need state-machine simulation without Postgres writes.

---

## ADR-014: JWT authentication across all three portals

**Context:** ADR-008 deferred JWT auth to Sprint 2. The dependency `python-jose[cryptography]`
was already in `requirements.txt`. Sprint 1 portals ran without auth — routes returned first-row
DB data with no user context, marked with `# Sprint 1: no auth` comments.

**Decision:** Implemented full JWT HS256 authentication in `certportal/core/auth.py` and wired
it into all three portals (Pam, Meredith, Chrissy). This supersedes ADR-008.

**Design choices:**
1. **Shared auth module** — all three portals import from `certportal.core.auth` (INV-07: portals
   never import from `agents/`, importing from `certportal.core` is explicitly permitted).
2. **Dual token acceptance** — `get_current_user()` accepts `Authorization: Bearer <token>` header
   (API/programmatic callers) OR `access_token` httponly cookie (browser sessions after `/token`).
   Bearer header takes priority when both are present.
3. **`require_role()` factory** — returns a FastAPI dependency; applied at the router level via
   `APIRouter(dependencies=[Depends(require_role(...))])` so all data routes in a portal are
   protected without per-route repetition.
4. **Role scoping** — Pam requires `admin`. Meredith requires `admin` or `retailer`. Chrissy
   requires `admin` or `supplier`. Admin users see cross-tenant data; scoped users see only their
   own `retailer_slug` / `supplier_slug`.
5. **Login flow** — each portal has `/login` (GET, inline HTML), `/token` (POST form → cookie +
   302 redirect), `/token/api` (POST → JSON, for tests), `/logout` (POST → clear cookie + 302).
6. **401/403 exception handlers** — browser requests (Accept: text/html) redirect to `/login`;
   API callers receive JSON error responses.
7. **Sprint 1 credentials** — `_DEV_USERS` dict with plaintext passwords (3 users: pam_admin,
   lowes_retailer, acme_supplier). Marked for Sprint 2 replacement with DB users + bcrypt.
8. **Token lifetime** — 480 minutes (8-hour working day). `ACCESS_TOKEN_EXPIRE_MINUTES` is a
   module-level constant used by all portals.

**Suite A coverage** — `testing/suites/suite_a.py` verifies: token round-trip, Bearer header
acceptance, cookie acceptance, Bearer-over-cookie priority, 401 on missing token, 401 on expired
token, require_role pass, require_role 403 fail, authenticate_user, _DEV_USERS structure.

**Sprint 2:** Replace `_DEV_USERS` with DB `users` table + `bcrypt.checkpw()`. Add `/register`
and `/change-password` endpoints. Refresh tokens out of scope for Sprint 1.

---

## ADR-015: DB-backed portal authentication (Sprint 2)

**Context:** ADR-014 implemented JWT with `_DEV_USERS` — a plaintext in-process dict of three
dev accounts. That approach is unsuitable for any shared or non-local environment.
ADR-014 explicitly flagged Sprint 2 replacement with DB + bcrypt.

**Decision:** `authenticate_user()` in `certportal/core/auth.py` is now an async function
that queries the `portal_users` Postgres table via asyncpg first, falling back to `_DEV_USERS`
bcrypt verification when the DB is unreachable.

**Design choices:**
1. **bcrypt library (not passlib)** — `bcrypt>=4.0` is used directly (`bcrypt.hashpw` /
   `bcrypt.checkpw`). `passlib[bcrypt]` has a known compatibility issue with Python ≥ 3.13
   (AttributeError on `__about__`). The `bcrypt` library has no such issue. Rounds=12.
2. **asyncpg for portal auth** — Portals are FastAPI async apps; asyncpg is already in
   `requirements.txt` and is async-native. (lifecycle_engine uses psycopg2 per CLAUDE.md for
   its synchronous library context — no conflict.)
3. **DB-first, _DEV_USERS fallback** — authenticate_user tries the DB:
   - DB unreachable (exception): warning logged → _DEV_USERS bcrypt fallback.
   - User found in DB with wrong password: returns None immediately (no _DEV_USERS backdoor).
   - User not found in DB: falls through to _DEV_USERS (supports dev users not yet seeded).
   - User found in DB with correct password: returns user record, no fallback needed.
4. **_DEV_USERS passwords are bcrypt-hashed** — Sprint 1 plaintext `password` key replaced
   with `hashed_password` (bcrypt, rounds=12). The dev passwords are unchanged; the storage
   format is now secure in both code and migrations.
5. **migrations/002_users_table.sql** — Creates `portal_users` table (id, username,
   hashed_password, role, retailer_slug, supplier_slug, is_active, created_at, updated_at).
   Seeds the 3 dev users ON CONFLICT DO NOTHING (idempotent re-runs).
6. **Portal /token endpoints** — All six `authenticate_user()` calls (2 per portal × 3
   portals) updated from `user = authenticate_user(...)` to `user = await authenticate_user(...)`.

**Suite A** — Updated to 11 tests (was 10):
- test_09: async call via `_run_async(authenticate_user(...))`, uses _DEV_USERS fallback.
- test_10: checks `hashed_password` key (not `password`) and verifies bcrypt format (`$2b$`).
- test_11 (new): mocks `asyncpg.connect` to test the DB code path; also verifies the
  "user not found in DB → _DEV_USERS fallback" sub-path.

**Sprint 3:** `/register` and `/change-password` endpoints using `hash_password()` helper
(already exported from auth.py). Refresh token support out of scope.

---

## Out-of-scope items (not built per Section 10)

- React frontend
- Google ADK / Gemini Flash-Lite (Sprint 2 stubs added to kelly.py)
- AS2 / SFTP ingest
- Stripe billing
- White-label subdomain routing
- PagerDuty (`if settings.pagerduty_key` guard pattern noted but not implemented)
- Full PyEDI-Core integration (stubbed)
- Production PostgreSQL schema migrations (schema SQL in database.py as comments only)
