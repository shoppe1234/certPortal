# certPortal — Architectural Decision Record (Sprint 1–4)

Decisions made during Sprints 1–4 that were not explicitly covered by the build prompt.
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

## ADR-016: Sprint 3 /register and /change-password Endpoints

**Date:** 2026-03-07
**Status:** Accepted

### Context

ADR-015 introduced bcrypt-hashed passwords and the portal_users DB table seeded with dev
users, but provided no runtime mechanism to add new users or rotate passwords. Sprint 3 adds
self-service password management and admin-controlled user provisioning without requiring
direct DB access.

### Decision

**POST /register (Pam admin portal only)**
- Lives on the admin-protected router (require_role admin).
- GET: renders inline HTML form (dark Pam theme) with fields: username, password,
  confirm_password, role (dropdown: admin/retailer/supplier), retailer_slug (optional),
  supplier_slug (optional).
- POST: validates fields, hashes password via hash_password() (bcrypt rounds=12), INSERTs
  into portal_users. Catches asyncpg.UniqueViolationError for duplicate username.
- All validation failures redirect to /register?error=... (PRG pattern).
- Accessible at http://localhost:8000/register (admin portal port only).

**POST /change-password (all three portals)**
- Lives on the protected router of each portal (admin, retailer/admin, supplier/admin).
- GET: renders inline HTML form themed per portal (dark/light/warm).
  Displays currently signed-in username from the JWT sub claim.
- POST logic:
  1. Validate new passwords match.
  2. Validate len(new_password) >= 8.
  3. Verify current_password via authenticate_user() (DB-first + _DEV_USERS fallback).
  4. Hash new password: hash_password(new_password).
  5. UPDATE portal_users SET hashed_password = ..., updated_at = NOW() WHERE username = ...
  6. If UPDATE 0 (user is dev-only, not in DB): redirect with informational error.
  7. Success: redirect to /change-password?msg=Password+changed+successfully.

### Rationale

| Choice | Reason |
|---|---|
| PRG pattern (Post-Redirect-Get) | Prevents form re-submission on refresh |
| Inline HTML (not Jinja2 templates) | Consistent with existing login pages; no template file proliferation |
| authenticate_user() for current-pw verify | Re-uses existing DB+fallback path; correct semantics |
| UPDATE 0 check | Informs dev users (fallback only) that they cannot persist password changes |
| Admin-only /register | Prevents self-registration; admin controls who has portal access |

### Consequences

- portals/pam.py: imports asyncpg (for UniqueViolationError) and hash_password.
- portals/meredith.py, portals/chrissy.py: import Form, Annotated, asyncpg, hash_password.
- testing/suites/suite_a.py: 11 to 14 tests (test_12 hash_password round-trip, test_13
  /register endpoint, test_14 /change-password endpoint via TestClient + mocked DB).
- No new DB migrations required: endpoints write to portal_users from migrations/002.

### Not implemented (Sprint 3 scope boundary)

- Refresh tokens (deferred to Sprint 4)
- Email-based password reset (deferred)
- Account deletion / deactivation UI (admin can UPDATE portal_users SET is_active = FALSE directly)
- Nav-bar links to /register and /change-password (deferred; accessible via direct URL)

---

## ADR-017: Stateless JWT Refresh Tokens

**Date:** 2026-03-07
**Status:** Accepted

### Context

ADR-016 deferred refresh tokens to Sprint 4. Sprint 3 access tokens have an 8-hour
expiry (ACCESS_TOKEN_EXPIRE_MINUTES = 480). After expiry the user must re-authenticate.
Browser sessions should survive overnight without forcing a full re-login the following day.

### Decision

- Add `REFRESH_TOKEN_EXPIRE_DAYS = 30` to `certportal/core/auth.py`.
- `create_refresh_token(data)`: encodes a JWT with `type='refresh'` claim and 30-day expiry.
- `decode_refresh_token(token)`: calls `decode_token()` then asserts `type == 'refresh'`; raises HTTP 401 otherwise.
- `build_token_claims()` now tags every access token with `type='access'`.
- `get_current_user()` rejects tokens where `payload.get("type") == "refresh"`. Tokens without a `type` claim remain valid (backward compat with Sprint 1–3 tokens).
- Each portal `POST /token` handler sets two httponly cookies: `access_token` (8h) and `refresh_token` (30d).
- Each portal exposes `POST /token/refresh`: reads `refresh_token` cookie, calls `decode_refresh_token()`, issues a fresh access token, sets a new `access_token` cookie.
- **No DB revocation table** in Sprint 4. Revocation deferred to Sprint 5+ (requires a `revoked_tokens` table and a lookup on every request).

### Rationale

| Choice | Reason |
|---|---|
| Stateless JWT (no revocation DB) | Simple, zero-latency; acceptable for Sprint 4 scope |
| `type` claim separation | Prevents refresh tokens being used as access tokens |
| 30-day expiry | Standard SaaS convention; balances convenience vs. exposure window |
| Backward compat (no `type` → still valid) | Sprint 1–3 tokens remain valid without forced re-login |
| Per-portal /token/refresh endpoint | Identical implementation; avoids shared app-level coupling |

### Consequences

- `certportal/core/auth.py`: +35 lines (REFRESH_TOKEN_EXPIRE_DAYS, create_refresh_token, decode_refresh_token; modified build_token_claims, get_current_user).
- All three portals: each gains a `refresh_token` cookie on `/token` and a new `POST /token/refresh` endpoint.
- `testing/suites/suite_a.py`: 14 → 17 tests (test_15 round-trip, test_16 type-claim rejection, test_17 /token/refresh endpoint via TestClient).

---

## ADR-018: Meredith Workspace Signal Format

**Date:** 2026-03-07
**Status:** Accepted

### Context

`portals/meredith.py` had four `# TODO Sprint 2` stubs in the spec-setup and yaml-wizard
endpoints. These stubs needed to be replaced with real workspace signal writes so that the
Dwight (spec analysis) and Andy (YAML wizard) agents are triggered correctly.

### Decision

- Replace all four TODO stubs with `workspace.upload(key, json.dumps(payload))` calls using `S3AgentWorkspace`.
- Use `"system"` as the `supplier_slug` for all Meredith-triggered signals. At the time of trigger, Meredith operates at the retailer level (no supplier context); `"system"` is explicit and avoids None path issues.
- Signal key format: `signals/{agent}_{path}_trigger_{ts}.json` where `ts = int(time.time())`.
- Signal payloads always include `retailer_slug` so downstream agents can scope their own workspace.

| Endpoint | Signal Key | Agent |
|---|---|---|
| POST /spec-setup/upload | `signals/dwight_trigger_{ts}.json` | Dwight (spec analysis) |
| POST /yaml-wizard/path1 | `signals/andy_path1_trigger_{ts}.json` | Andy (PDF extraction) |
| POST /yaml-wizard/path2 | `signals/andy_path2_trigger_{ts}.json` | Andy (YAML upload validation) |
| POST /yaml-wizard/path3 | `signals/andy_path3_trigger_{ts}.json` | Andy (wizard form) |

### Rationale

- INV-01 compliant: portals write signals; agents poll S3 for triggers.
- INV-07 compliant: meredith.py never imports from `agents/`.
- `"system"` as supplier_slug is explicit. None would break S3 path scoping in `S3AgentWorkspace`.

### Consequences

- `portals/meredith.py` imports `json`, `time`, `S3AgentWorkspace`.
- `testing/suites/suite_h.py` Group 1: 3 tests verify upload key format and payload structure.

---

## ADR-019: Chrissy Patch Apply / Reject / Content Flow

**Date:** 2026-03-07
**Status:** Accepted

### Context

Sprint 3 delivered `GET /patches` (list) and `POST /patches/{id}/mark-applied` (set `applied=TRUE`).
Sprint 4 adds supplier-facing reject capability and a content viewer, plus wires the apply
action into Moses revalidation.

### Decision

**`POST /patches/{id}/mark-applied` (expanded):**
- Fetch the full `patch_suggestions` row (including `retailer_slug`, `supplier_slug`).
- Set `applied=TRUE` in the DB (existing behavior preserved).
- Write a Moses revalidation signal to S3: `signals/moses_revalidate_{patch_id}_{ts}.json` with `trigger="patch_applied"`, `patch_id`, `supplier_slug`, `retailer_slug`.

**`POST /patches/{id}/reject` (new):**
- Sets `rejected=TRUE` in `patch_suggestions` (new column via migration 003).
- No S3 signal: rejection is a terminal state, no downstream reprocessing needed.
- Returns `{"status": "rejected", "patch_id": id}`.

**`GET /patches/{id}/content` (new):**
- Fetches patch row, downloads `patch_s3_key` via `S3AgentWorkspace`.
- Returns inline `HTMLResponse` with `<pre>`-wrapped markdown content.
- Requires supplier or admin role.

**Migration 003 (`migrations/003_patch_reject.sql`):**
```sql
ALTER TABLE patch_suggestions
    ADD COLUMN IF NOT EXISTS rejected BOOLEAN NOT NULL DEFAULT FALSE;
```

### Rationale

- Moses revalidation signal on apply closes the loop: applied patches trigger re-validation so Moses can confirm the fix resolved the original violation.
- No signal on reject: rejected patches are abandoned; no processing needed downstream.
- Inline HTML for content: avoids template proliferation; supplier just needs to read the diff.

### Consequences

- `portals/chrissy.py`: imports `S3AgentWorkspace`, `time`; mark-applied expanded; two new endpoints added.
- `migrations/003_patch_reject.sql`: new migration file, applied before Sprint 4 tests run.
- `testing/suites/suite_h.py` Group 2: 3 tests cover apply signal, reject DB write, content endpoint.

---

## ADR-020: Kelly Real Channel Dispatch (SMTP / Google Chat / Teams)

**Date:** 2026-03-07
**Status:** Accepted

### Context

Kelly's `_dispatch_message()` was a Sprint 1 stub that only logged. Sprint 4 wires up
real delivery for the three supported channels plus a HITL approval signal from Pam.

### Decision

**Kelly dispatch helpers** (all fail-safe — missing config logs a warning and returns, never raises):

| Helper | Env Vars | Protocol |
|---|---|---|
| `_dispatch_email()` | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | `smtplib.SMTP` |
| `_dispatch_google_chat()` | `KELLY_GOOGLE_CHAT_OAUTH_TOKEN_{RETAILER}` | `requests.post` to Google Chat REST API, `Authorization: Bearer {token}` |
| `_dispatch_teams()` | `KELLY_TEAMS_WEBHOOK_{RETAILER}` | `requests.post` to Teams incoming webhook URL |

**`dispatch_approved()` public function:**
- Queries `hitl_queue WHERE status = 'APPROVED'`.
- Calls `_dispatch_message()` for each row.
- Exposed as `python -m agents.kelly --dispatch-approved` CLI flag.

**Pam HITL approve (INV-01 compliant):**
- `POST /hitl-queue/{queue_id}/approve` writes `signals/kelly_approved_{queue_id}.json` to S3 after the DB UPDATE.
- Kelly polls S3 for these signals and calls `dispatch_approved()`.
- Pam never calls `kelly.run()` directly (INV-07 compliant).

**`.env` additions:**
```
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=certportal@example.com
# KELLY_TEAMS_WEBHOOK_LOWES=
```

### Rationale

- Fail-safe dispatch: missing env var = log + return. No exception propagates. Agents must be resilient to partial configuration in dev.
- Per-retailer env var naming (`KELLY_GOOGLE_CHAT_OAUTH_TOKEN_{RETAILER.upper()}`) follows existing pattern in `.env.template`.
- S3 signal from Pam: INV-01 and INV-07 both require portals never call agents directly.

### Consequences

- `agents/kelly.py`: `_dispatch_message()` stub replaced; three private helpers added; `dispatch_approved()` public function added; `--dispatch-approved` CLI flag added.
- `portals/pam.py`: approve endpoint imports `S3AgentWorkspace`; writes signal after DB update.
- `.env` / `.env.template`: SMTP and Teams webhook keys added.
- `testing/suites/suite_h.py` Group 3 + 4: 6 tests covering Pam signal write, Kelly email/chat/missing-env.

---

## ADR-021: JWT Revocation via revoked_tokens Table

**Date:** 2026-03-07
**Status:** Accepted

### Context

ADR-017 explicitly deferred JWT revocation to Sprint 5+. Stateless refresh tokens mean that
a stolen or logged-out token remains valid until its `exp` claim lapses — up to 8 hours for
access tokens, 30 days for refresh tokens. Sprint 5 adds a DB-backed revocation mechanism so
that logout immediately invalidates tokens.

### Decision

**New table** (`migrations/004_revoked_tokens.sql`):
```sql
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti        TEXT PRIMARY KEY,
    revoked_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expires_at ON revoked_tokens (expires_at);
```

**JTI claim** — `secrets.token_hex(16)` added to every token (both access and refresh) at
creation time via `create_access_token()` and `create_refresh_token()`. Tokens without a
`jti` claim are still accepted (backward compat with Sprint 1–4 tokens).

**`get_current_user()` revocation check** — if `_revocation_pool` is set (non-None), a
`SELECT 1 FROM revoked_tokens WHERE jti=$1 AND expires_at > NOW()` lookup is performed before
returning the user dict. Result: HTTP 401 `"Token has been revoked"`.

**`set_revocation_pool(pool)` / `_revocation_pool`** — module-level variable in
`certportal/core/auth.py`. Each portal's lifespan calls `set_revocation_pool(pool)` after
creating the asyncpg pool and `set_revocation_pool(None)` on teardown. Tests that do not set
the pool skip the revocation check automatically (backward compat).

**`/logout` handler** — updated on all three portals to:
1. Accept `access_token: str | None = Cookie(default=None)` parameter.
2. Delete both `access_token` and `refresh_token` cookies (fixes Sprint 4 gap — only access_token was cleared).
3. Decode the token, extract `jti` + `exp`, INSERT into `revoked_tokens` with correct `expires_at`.
4. On any decode error (expired, malformed): swallow exception, clear cookies regardless.

**Cleanup** — no auto-cleanup in Sprint 5. Deferred to Sprint 6:
`DELETE FROM revoked_tokens WHERE expires_at < NOW()`.

### Rationale

| Choice | Reason |
|---|---|
| DB lookup on every request | Immediate revocation guarantee; asyncpg pool makes it non-blocking |
| `_revocation_pool = None` default | Tests continue to work without a live DB; no interface change |
| `expires_at` filter in lookup | Never matches rows that would have expired anyway; keeps table small |
| Soft backward compat (no `jti` → skip) | Sprint 1–4 access tokens remain valid without forced re-login |
| Only access_token decoded on logout | Refresh token is opaque to the logout handler (httponly cookie) |

### Consequences

- `certportal/core/auth.py`: +25 lines (`jti` in both token creators; `_revocation_pool`; `set_revocation_pool()`; revocation check in `get_current_user()`).
- `portals/pam.py`, `portals/meredith.py`, `portals/chrissy.py`: lifespan registers pool; `/logout` clears both cookies + inserts jti.
- `migrations/004_revoked_tokens.sql`: new file.
- `testing/suites/suite_a.py`: 17 → 20 tests (test_18 JTI in tokens; test_19 logout inserts jti; test_20 revoked token rejected).

---

## ADR-022: Monica Escalation → HITL Queue DB Write

**Date:** 2026-03-07
**Status:** Accepted

### Context

Sprint 4 Monica `_check_kelly_escalations()` detects `SENTIMENT_ESCALATION` markers in
GLOBAL-FEEDBACK.md and logs them, but does not take further action. The Kelly → Monica →
HITL → Pam → Kelly communication loop is incomplete: Pam cannot see or approve escalations.

### Decision

**New helper `_queue_escalation_for_hitl(supplier_slug, retailer_slug, thread_id)`** in
`agents/monica.py`:
- Uses psycopg2 (sync) to INSERT one `hitl_queue` row per escalation.
- `queue_id = f"escalation_{thread_id}_{int(time.time())}"` — unique per invocation.
- `ON CONFLICT (queue_id) DO NOTHING` — idempotent; safe on repeated Monica runs.
- `agent='KELLY'`, `channel='email'`, `status='PENDING_APPROVAL'`.
- Fail-safe: missing `CERTPORTAL_DB_URL` → log + return False; any psycopg2 error → log + return False.

**`run()` integration** — after `_check_kelly_escalations()` returns thread IDs, iterates and calls
`_queue_escalation_for_hitl()` for each. Inserts `"escalation_queued:{thread_id}"` into
`summary["actions_taken"]` when inserted = True.

**Downstream flow** (no new code required):
1. Pam reads from `hitl_queue` (existing Pam dashboard + HITL queue page).
2. Pam approves → existing Sprint 4 approve endpoint writes `signals/kelly_approved_{queue_id}.json`.
3. Kelly polls S3 and dispatches via `_dispatch_message()`.

### Rationale

| Choice | Reason |
|---|---|
| psycopg2 sync (not asyncpg) | Monica's `run()` is synchronous; matches Kelly's `dispatch_approved()` pattern |
| hitl_queue DB write (not S3 PAM-STATUS.json) | Pam dashboard reads from DB; S3 HITL path is not connected to the Pam UI |
| INV-01 preserved | Monica never imports Kelly; escalation queued to DB, Kelly reads S3 signal from Pam |
| Fail-safe (no exception propagation) | Monica must complete its run even if DB is unavailable |

### Consequences

- `agents/monica.py`: `_queue_escalation_for_hitl()` private helper; `run()` step 5 extended.
- `testing/suites/suite_h.py`: 12 → 14 tests (test_13 escalation queued; test_14 no escalation → no write).
- No new DB migrations: `hitl_queue` table already exists from `migrations/001_app_tables.sql`.

---

## ADR-023: Email-Based Password Reset

**Date:** 2026-03-07
**Status:** Accepted

### Context

Users who forget their portal password have no self-service recovery path. Admin-driven password
resets (Pam `/register` + manual communication) are the only option. Sprint 6 adds a standard
forgot-password email flow to all three portals.

### Decision

**New table** (`migrations/005_password_reset.sql`):
```sql
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token      TEXT PRIMARY KEY,
    username   TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used       BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**`portal_users` schema extension:** `ALTER TABLE portal_users ADD COLUMN IF NOT EXISTS email TEXT;`
(nullable — existing dev users have no email; email is set at user creation time going forward).

**Token:** `secrets.token_urlsafe(32)` — 43 URL-safe characters, 60-minute expiry, single-use.
Marked `used=TRUE` atomically in the same transaction as the password UPDATE.

**New functions in `certportal/core/auth.py`:**
- `create_password_reset_token(username, pool) -> str` — generates token, INSERTs row, returns token.
- `validate_password_reset_token(token, pool) -> str | None` — SELECT + UPDATE used=TRUE in-call;
  returns username on success or None if invalid/expired/used.

**New module `certportal/core/email_utils.py`** — INV-07-compliant standalone SMTP helper.
Portals cannot import from `agents/`; this module replicates Kelly's `smtplib/STARTTLS` pattern
without an agents/ dependency. Fail-safe: missing `SMTP_HOST` logs to stderr and returns False.

**New routes** (all three portals):
- `GET /forgot-password` — username form (inline HTML, themed per portal).
- `POST /forgot-password` — looks up user+email, generates token, emails reset link.
  Always redirects to `/login?msg=reset_sent` — never reveals whether username/email exists.
- `GET /reset-password?token=...` — peeks (SELECT only, does NOT mark used); shows form if valid.
- `POST /reset-password` — validates token (marks used), updates `hashed_password`, redirects.

**Login page** (each portal): "Forgot password?" link added below the Sign In button.

### Rationale

| Choice | Reason |
|---|---|
| `token_urlsafe(32)` (43 chars) | Cryptographically random, URL-safe, unpredictable without brute-force |
| 60-minute expiry | Long enough to be usable; short enough to limit exposure |
| `ON CONFLICT (token) DO NOTHING` | Handles the astronomically unlikely duplicate token without error |
| GET /reset-password does NOT mark used | Allows browser back-button / link preview without consuming the token |
| Always reset_sent redirect | Prevents username/email enumeration attacks |
| `certportal/core/email_utils.py` (not agents/) | INV-07: portals never import from agents/ |
| Nullable `email` column | Backward compat — existing dev users unaffected |

### Consequences

- `migrations/005_password_reset.sql`: new file (ADD COLUMN + CREATE TABLE + 2 indexes).
- `certportal/core/email_utils.py`: new file (~50 lines).
- `certportal/core/auth.py`: +25 lines (`create_password_reset_token`, `validate_password_reset_token`).
- `portals/pam.py`, `portals/meredith.py`, `portals/chrissy.py`: 4 new routes each; login page link.
- `testing/suites/suite_a.py`: 20 → 24 tests (test_21 through test_24).

---

## ADR-024: Kelly Gemini Flash-Lite Thread Memory Consolidation

**Date:** 2026-03-07
**Status:** Accepted

### Context

`agents/kelly.py` contains a stub `consolidate_memory_adk(thread_id)` added in Sprint 2 that
raises `NotImplementedError`. The intent (per docstring) is "always-on thread memory" using
Google ADK + Gemini Flash-Lite. Sprint 6 delivers the real implementation.

### Decision

**SDK:** `google-generativeai` (direct Gemini Python SDK). Model: `gemini-1.5-flash-8b`
(Flash-Lite tier — fast, low-cost, suitable for summarisation). Added to `requirements.txt`.
`google-adk` (Google's orchestration framework) is not used — a single summarisation call does
not warrant orchestration overhead.

**Signature extended:** `consolidate_memory_adk(thread_id: str, history: list[dict]) -> dict`
Thread history is already loaded by `run()` before the call; passing it avoids a redundant
S3 read inside the function.

**Return schema:**
```python
{
    "thread_id": str,
    "summary": str,               # 2-3 sentence narrative
    "sentiment_trend": str,       # "improving" | "stable" | "deteriorating" | "unknown"
    "key_exchanges": int,
    "consolidated_at": str | None # ISO-8601 UTC timestamp; None on failure
}
```

**Fail-safe:** Returns the empty-summary dict `{..., "summary": "", "consolidated_at": None}`
if `GEMINI_API_KEY` is absent or any API/parsing error occurs. Logs warning via `kelly_logger`.
Never raises — Kelly's `run()` must be resilient to partial configuration.

**All imports are lazy** (inside the function body) — avoids import-time failure when
`google-generativeai` is not installed (e.g. in CI environments where it's omitted).

**Wired into `run()`** after `_load_thread_history()` and before `classify_tone()`.
`memory["summary"]` is injected as additional context into `_draft_message()` prompt.

**Environment variable added:** `GEMINI_API_KEY=` in `.env.template`.

### Rationale

| Choice | Reason |
|---|---|
| `google-generativeai` not `google-adk` | Simpler, more stable; ADK framework overkill for single-call summarisation |
| `gemini-1.5-flash-8b` | Fast + cheap; Flash-Lite tier appropriate for thread summaries |
| Lazy imports | Allows Kelly to start without `google-generativeai` installed; no import error in dev |
| Pass `history` not `thread_id` | Avoids second S3 read; reuses history already loaded by `run()` |
| Fail-safe empty dict | Kelly must complete its pipeline even when Gemini is unavailable |

### Consequences

- `agents/kelly.py`: stub replaced (~45 lines); `run()` step 1.5 added (~4 lines).
- `requirements.txt`: `google-generativeai>=0.8` added.
- `.env.template`: `GEMINI_API_KEY=` added.
- `testing/suites/suite_i.py`: new suite — 2 tests (success path + fallback path).
- `testing/certportal_jules_test.py`: Suite I registered.

---

## ADR-025: Revoked Tokens Expiry Background Cleanup

**Date:** 2026-03-07
**Status:** Accepted

### Context

ADR-021 explicitly deferred cleanup of expired rows from `revoked_tokens` to Sprint 6.
Without cleanup, the table grows unboundedly. Since `expires_at` is indexed and the revocation
check already filters `expires_at > NOW()`, expired rows never cause incorrect behaviour — they
are dead weight only. Sprint 6 adds an automatic hourly cleanup.

### Decision

**New function `cleanup_expired_revoked_tokens() -> int`** in `certportal/core/auth.py`:
```python
DELETE FROM revoked_tokens WHERE expires_at < NOW()
```
Returns the number of rows deleted. No-op and returns 0 when `_revocation_pool` is None
(backward compat — tests do not set the pool).

**Portal lifespan background task** (all three portals) — `asyncio.create_task(_cleanup_loop())`:
1. Runs one immediate pass on startup (clears any rows that expired while portal was down).
2. Then sleeps 3600 seconds and repeats indefinitely.
3. Task is cancelled on portal shutdown (in the `finally` block of the lifespan).

No external scheduler, no new dependencies. The uvicorn asyncio event loop hosts the task.

### Rationale

| Choice | Reason |
|---|---|
| `asyncio.create_task` in lifespan | Zero new dependencies; fits existing FastAPI/uvicorn async model |
| 1-hour interval | JTIs live 8h (access) to 30d (refresh); hourly is precise enough |
| Immediate first pass | Clears stale rows from any portal downtime without waiting 1 hour |
| `task.cancel()` on shutdown | Clean shutdown; avoids spurious errors on SIGTERM |
| No separate cleanup service | Sprint 6 scope; a dedicated pg_cron rule can replace this in a future sprint |

### Consequences

- `certportal/core/auth.py`: `cleanup_expired_revoked_tokens()` added (~8 lines).
- `portals/pam.py`, `portals/meredith.py`, `portals/chrissy.py`: lifespan updated with cleanup task; `import asyncio` added.
- `testing/suites/suite_a.py`: test_25 added (cleanup function behaviour).
