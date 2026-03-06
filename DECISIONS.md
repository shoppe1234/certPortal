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

## Out-of-scope items (not built per Section 10)

- React frontend
- Google ADK / Gemini Flash-Lite (Sprint 2 stubs added to kelly.py)
- AS2 / SFTP ingest
- Stripe billing
- White-label subdomain routing
- PagerDuty (`if settings.pagerduty_key` guard pattern noted but not implemented)
- Full PyEDI-Core integration (stubbed)
- Production PostgreSQL schema migrations (schema SQL in database.py as comments only)
