# cliRequirements — Business Requirements Verification Harness

## What This Is

A deterministic, DOM-based verification harness that runs alongside the existing
Playwright E2E flows. While the design observer (`--observe`) evaluates CSS and
visual quality, the requirements verifier (`--verify`) checks that each portal page
**actually exhibits the business functionality** specified in `CLAUDE.md`,
`DECISIONS.md`, `TECHNICAL_REQUIREMENTS.md`, and `README.md`.

Activated via: `python -m playwrightcli --portal all --verify`

---

## Architecture

```
Playwright Flow (existing)
  |
  pam::login -> verify("login") -> DOM assertions on rendered page
  pam::retailers -> verify("retailers") -> check table columns, data rows
  pam::suppliers -> verify("suppliers") -> check gate badges, action buttons
  ...
  |
  RequirementsVerifier accumulates PASS / FAIL / SKIP per requirement
  |
  Writes: requirements_reports/requirements_{portal}_{timestamp}.md
```

**Key property:** Verifications are synchronous DOM checks on the live Playwright
page — no API calls, no screenshots. Each check maps to a specific business
requirement with a unique ID (e.g., `PAM-DASH-01`, `MER-YAML-03`).

---

## Requirements Checklist

### PAM (Admin Portal — Port 8000)

#### Authentication (PAM-AUTH-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| PAM-AUTH-01 | Login form renders with username + password fields | ADR-014 | `input[name="username"]` and `input[name="password"]` exist |
| PAM-AUTH-02 | Login form has submit button | ADR-014 | `button[type="submit"]` exists |
| PAM-AUTH-03 | Successful login redirects to dashboard (not /login) | ADR-014 | URL does not contain `/login` after auth |
| PAM-AUTH-04 | "Forgot password?" link present on login page | ADR-023 | `a[href*="forgot-password"]` exists |
| PAM-AUTH-05 | Navigation shows logged-in username | ADR-014 | Nav contains `pam_admin` text |
| PAM-AUTH-06 | Navigation shows role badge (admin) | ADR-014 | Nav contains role indicator |
| PAM-AUTH-07 | Sign-out button present in navigation | ADR-014 | Logout link/button exists |
| PAM-AUTH-08 | Register link present (admin-only feature) | ADR-016 | `/register` link in nav |

#### Dashboard (PAM-DASH-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| PAM-DASH-01 | KPI cards display retailer count | CLAUDE.md portals | Element with retailer count exists |
| PAM-DASH-02 | KPI cards display supplier count | CLAUDE.md portals | Element with supplier count exists |
| PAM-DASH-03 | KPI cards display HITL queue pending count | CLAUDE.md portals | HITL count element exists |
| PAM-DASH-04 | Agent roster visible (Monica, Dwight, Andy, Moses, Kelly, Ryan) | README.md | Agent names present in page content |

#### Retailers Management (PAM-RET-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| PAM-RET-01 | Retailers page loads without error | CLAUDE.md | No 500/error state |
| PAM-RET-02 | Table or empty-state renders | CLAUDE.md | `table` or `.empty-state` exists |
| PAM-RET-03 | Table has retailer_slug column | portals/pam.py | `th` with "retailer" text |

#### Suppliers & Gate Management (PAM-SUP-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| PAM-SUP-01 | Suppliers page loads without error | CLAUDE.md | No 500/error state |
| PAM-SUP-02 | Table or empty-state renders | CLAUDE.md | `table` or `.empty-state` exists |
| PAM-SUP-03 | Gate status badges visible (G1, G2, G3) | INV-03, ADR gate enforcement | Gate badge elements exist |
| PAM-SUP-04 | Gate progression buttons present | gate_enforcer.py | Action buttons for gate transitions |
| PAM-SUP-05 | Gate ordering enforced (1 -> 2 -> 3) | INV-03 | No "skip gate" buttons |

#### HITL Queue (PAM-HITL-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| PAM-HITL-01 | HITL queue page loads | ADR-022 | No 500/error state |
| PAM-HITL-02 | Queue table or empty-state renders | ADR-022 | `table` or empty indicator |
| PAM-HITL-03 | Approve action available for pending items | ADR-020 | Approve button/link exists if items present |
| PAM-HITL-04 | Reject action available for pending items | ADR-020 | Reject button/link exists if items present |

#### Monica Memory (PAM-MEM-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| PAM-MEM-01 | Monica memory page loads | INV-05 | No 500/error state |
| PAM-MEM-02 | Memory log entries or empty-state render | INV-05 | Content area exists |
| PAM-MEM-03 | Pagination controls present | portals/pam.py | Pagination links visible |

---

### MEREDITH (Retailer Portal — Port 8001)

#### Authentication (MER-AUTH-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| MER-AUTH-01 | Login form renders with username + password fields | ADR-014 | Input fields exist |
| MER-AUTH-02 | Successful login redirects to dashboard | ADR-014 | URL not `/login` |
| MER-AUTH-03 | "Forgot password?" link present | ADR-023 | Link exists |
| MER-AUTH-04 | Navigation shows retailer context | ADR-014 | Nav shows username/role |

#### Spec Setup — Dwight Integration (MER-SPEC-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| MER-SPEC-01 | Spec setup page loads without error | CLAUDE.md | No 500/error state |
| MER-SPEC-02 | Upload form present (Trading Partner Guide PDF) | ADR-018 | Upload form/button exists |
| MER-SPEC-03 | Retailer slug field present | ADR-018 | Input for retailer identification |
| MER-SPEC-04 | Spec table or empty-state renders | ADR-018 | Table or placeholder content |
| MER-SPEC-05 | YAML Wizard link/button present | portals/meredith.py | Link to `/yaml-wizard` or equivalent |

#### YAML Wizard — Andy 3-Path Ingestion (MER-YAML-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| MER-YAML-01 | YAML wizard page accessible | ADR-018 | Page loads without error |
| MER-YAML-02 | Path 1 (PDF Extract) tab/section visible | TECHNICAL_REQUIREMENTS 9.1 | Tab or section for PDF extraction |
| MER-YAML-03 | Path 2 (Upload YAML) tab/section visible | TECHNICAL_REQUIREMENTS 9.1 | Tab or section for YAML upload |
| MER-YAML-04 | Path 3 (Step-by-Step Wizard) tab/section visible | TECHNICAL_REQUIREMENTS 9.1 | Tab or section for wizard form |
| MER-YAML-05 | Transaction bundle selector present | portals/meredith.py | Dropdown/select for bundles |

#### Supplier Status Board (MER-STATUS-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| MER-STATUS-01 | Supplier status page loads | CLAUDE.md | No 500/error state |
| MER-STATUS-02 | Status table or empty-state renders | CLAUDE.md | Table or placeholder |
| MER-STATUS-03 | Gate columns visible (G1 Spec, G2 Validation, G3 Certification) | INV-03 | Gate header columns |
| MER-STATUS-04 | Gate status badges present (PENDING/COMPLETE/CERTIFIED) | gate_enforcer.py | Badge elements with status text |
| MER-STATUS-05 | Test pass/fail counts displayed | portals/meredith.py | Count elements in table rows |

---

### CHRISSY (Supplier Portal — Port 8002)

#### Authentication (CHR-AUTH-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| CHR-AUTH-01 | Login form renders with username + password fields | ADR-014 | Input fields exist |
| CHR-AUTH-02 | Successful login redirects to dashboard | ADR-014 | URL not `/login` |
| CHR-AUTH-03 | "Forgot password?" link present | ADR-023 | Link exists |
| CHR-AUTH-04 | Navigation shows supplier context | ADR-014 | Nav shows username/role |

#### Dashboard — Lifecycle & Progress (CHR-DASH-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| CHR-DASH-01 | Dashboard loads without error | CLAUDE.md | No 500/error state |
| CHR-DASH-02 | Gate status cards present (Gate 1, Gate 2, Gate 3) | INV-03 | Three gate card elements |
| CHR-DASH-03 | Progress indicator visible | portals/chrissy.py | Progress bar or step indicator |
| CHR-DASH-04 | Test metrics displayed (total, passed, percentage) | portals/chrissy.py | Metric elements exist |
| CHR-DASH-05 | Quick action links present (Scenarios, Errors, Patches) | portals/chrissy.py | Navigation links to key pages |

#### Test Scenarios — Lifecycle Visibility (CHR-SCEN-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| CHR-SCEN-01 | Scenarios page loads without error | CLAUDE.md | No 500/error state |
| CHR-SCEN-02 | Scenario cards/table renders or empty-state | portals/chrissy.py | Content area exists |
| CHR-SCEN-03 | Status badges present (PASS/FAIL/PARTIAL) | portals/chrissy.py | Status badge elements |
| CHR-SCEN-04 | Transaction type visible per scenario | TECHNICAL_REQUIREMENTS | Transaction type column/label |
| CHR-SCEN-05 | Validation timestamp visible | portals/chrissy.py | Timestamp element |

#### Validation Errors — Error Detail + Patches (CHR-ERR-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| CHR-ERR-01 | Errors page loads without error | CLAUDE.md | No 500/error state |
| CHR-ERR-02 | Error groups or empty-state renders | portals/chrissy.py | Content area exists |
| CHR-ERR-03 | Error details expandable (severity, code, segment) | portals/chrissy.py | Expandable card/accordion elements |
| CHR-ERR-04 | Patch suggestion section visible (if patches exist) | ADR-019 | Patch section or "no patches" indicator |

#### Patches — Ryan's Suggestions (CHR-PATCH-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| CHR-PATCH-01 | Patches page loads without error | ADR-019 | No 500/error state |
| CHR-PATCH-02 | Patch cards/table renders or empty-state | ADR-019 | Content area exists |
| CHR-PATCH-03 | "Mark Applied" action available for pending patches | ADR-019 | Apply button/link exists |
| CHR-PATCH-04 | "Reject" action available for pending patches | ADR-019 | Reject button/link exists |
| CHR-PATCH-05 | Filter controls present (All/Pending/Applied) | portals/chrissy.py | Filter buttons or tabs |
| CHR-PATCH-06 | Patch content viewable | ADR-019 | Content link/button exists |

#### Certification Status (CHR-CERT-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| CHR-CERT-01 | Certification page loads without error | CLAUDE.md | No 500/error state |
| CHR-CERT-02 | Certification badge or pending status visible | portals/chrissy.py | Badge or status element |

---

### CROSS-PORTAL (XPORT-*)

| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| XPORT-01 | All portals respond to /health with 200 | All portals | Pre-flight HTTP check |
| XPORT-02 | Portal-specific CSS theme loads | CLAUDE.md | Stylesheet link in `<head>` |
| XPORT-03 | HTMX library loaded | ADR-007 | `<script>` tag for htmx |
| XPORT-04 | No console JavaScript errors on page load | General | `page.on("pageerror")` listener |
| XPORT-05 | Change password link accessible | ADR-016 | `/change-password` link in nav |

---

## Possible and Future Enhancements

### 1. YAML Wizard Interactive Verification
**Current gap:** The harness navigates to `/yaml-wizard` and checks that the 3-path
tabs exist, but cannot verify that **submitting** a YAML file through Path 2 triggers
schema validation (Andy agent + `schema_validators/validate_file()`).

**Future:** Upload a test YAML fixture through the wizard form, verify the S3 signal
(`andy_path2_trigger_{ts}.json`) is written, and check that the validation result
appears in the UI. Requires a test YAML file in `playwrightcli/fixtures/`.

### 2. Patch Apply → Moses Revalidation Signal Verification
**Current gap:** The harness checks that "Mark Applied" buttons exist on `/patches`,
but cannot verify that clicking the button writes the S3 revalidation signal
(`moses_revalidate_{patch_id}_{ts}.json`).

**Future:** Click "Mark Applied" on a test patch, then query S3 (or check the response)
to confirm the signal was written with correct `trigger="patch_applied"` payload.

### 3. HITL Approve → Kelly Dispatch Signal Verification
**Current gap:** Checks that approve/reject buttons exist on `/hitl-queue`, but cannot
verify the full loop: approve → S3 signal → Kelly dispatch.

**Future:** Approve a test HITL item, verify the S3 signal
(`kelly_approved_{queue_id}.json`) exists, optionally trigger Kelly's
`--dispatch-approved` and verify the message was sent.

### 4. Lifecycle State Progression End-to-End
**Current gap:** Chrissy's `/scenarios` page shows test results, but the harness cannot
verify the full lifecycle: 850 → 855 → 856 → 810 state progression as reflected in
the supplier's gate advancement.

**Future:** Seed the database with a known PO lifecycle (via SQL fixtures or Moses CLI),
then verify that Chrissy's dashboard shows the correct gate states and that the
scenarios page reflects the expected PASS/FAIL status per transaction type.

### 5. Gate Enforcement UI Verification
**Current gap:** The harness checks that gate badges exist, but cannot test that
attempting to skip a gate (e.g., advancing G3 before G2) shows an error.

**Future:** Use an admin session in PAM to attempt out-of-order gate progression via
HTMX POST, verify that the 409 Conflict response is handled gracefully in the UI
with an appropriate error message.

### 6. Password Reset Flow End-to-End
**Current gap:** Checks that "Forgot password?" link exists on login pages, but cannot
verify the full flow: forgot → email → reset token → new password → login.

**Future:** Navigate the forgot-password form, intercept or mock the SMTP call,
extract the reset token, complete the reset flow, and verify login with new credentials.
Requires SMTP mock or test mailbox integration.

### 7. Refresh Token Rotation Verification
**Current gap:** Authentication checks verify login works, but cannot test that an
expired access token is silently refreshed via the refresh token cookie.

**Future:** Login, manually expire the access token cookie (set a past expiry), make a
navigation request, and verify that `/token/refresh` is called and a new access token
is issued without redirecting to `/login`.

### 8. Multi-Tenant Scope Verification
**Current gap:** Each portal is tested with a single user. Cannot verify that a retailer
user cannot see another retailer's data, or that a supplier user is scoped correctly.

**Future:** Create two test users with different `retailer_slug` / `supplier_slug` scopes.
Login as each and verify that data is properly scoped — User A cannot see User B's
suppliers, patches, or scenarios.

### 9. Agent Roster Status Verification (PAM)
**Current gap:** Checks that agent names appear on the PAM dashboard, but cannot verify
that agent status indicators reflect real state (e.g., Monica last ran at X, Kelly
has N pending dispatches).

**Future:** Seed the database with known agent activity, verify that PAM's agent roster
shows correct last-run timestamps and status indicators.

### 10. HTMX Polling Verification
**Current gap:** Checks that HTMX is loaded, but cannot verify that polling endpoints
(`hx-trigger="every 30s"`) are actually firing and updating content.

**Future:** Wait 30+ seconds on a page with HTMX polling, intercept the XHR request,
and verify that the partial HTML response updates the target element. Use
`page.route()` to mock the polling response with known data and verify DOM update.

### 11. Database Fixture Seeding
**Current gap:** Verification results depend on database state. Empty tables produce
empty-state UI, which passes checks but doesn't verify data rendering.

**Future:** Create a `playwrightcli/fixtures/seed.sql` that inserts known test data
(retailers, suppliers, gate statuses, test occurrences, patches, HITL items, Monica
memory entries). Run before `--verify` to ensure all pages have data to render.
This transforms empty-state checks into data-rendering checks.

### 12. Accessibility Requirements (WCAG AA)
**Current gap:** The design observer checks contrast ratios visually. The requirements
harness could check programmatic accessibility.

**Future:** Use `page.accessibility.snapshot()` to verify: ARIA landmarks exist,
form inputs have labels, buttons have accessible names, heading hierarchy is correct
(h1 → h2 → h3, no skips), focus indicators are visible.

### 13. Cross-Portal Navigation Consistency
**Current gap:** Each portal is tested independently. Cannot verify that shared
patterns (nav bar structure, logout flow, change-password flow) are consistent.

**Future:** After verifying all portals, compare their navigation structures:
same number of nav items, same footer layout, same logout behavior. Flag
inconsistencies as WARN.

### 14. Error Page Verification
**Current gap:** The harness verifies happy paths. Cannot verify that error states
(401, 403, 404, 500) render appropriately.

**Future:** Navigate to non-existent routes (`/nonexistent`), attempt unauthorized
access (logout then hit protected route), and verify that error pages render with
correct status codes and user-friendly messages (not raw stack traces).

---

## Output

| Artifact | Path | When Created |
|----------|------|-------------|
| Requirements report | `requirements_reports/requirements_{portal}_{timestamp}.md` | Every `--verify` run |
| Combined summary | `requirements_reports/summary_{timestamp}.md` | Every `--verify` run |
| Screenshots (if combined with --observe) | `screenshots/{portal}/{step}.png` | When `--observe` also active |

---

## Usage

```bash
# Verify all portals — headed browser, DOM assertions only
python -m playwrightcli --portal all --verify

# Verify single portal, headless
python -m playwrightcli --portal chrissy --headless --verify

# Combine with design observer (both verifications in one run)
python -m playwrightcli --portal all --observe --verify

# Dry-run: show which requirements will be checked
python -m playwrightcli --portal all --verify --dry-run

# Standard E2E run (no verification, original behavior)
python -m playwrightcli --portal all
```

---

## Requirement ID Convention

```
{PORTAL}-{AREA}-{NUMBER}
```

| Prefix | Portal |
|--------|--------|
| PAM | Admin portal (Pam) |
| MER | Retailer portal (Meredith) |
| CHR | Supplier portal (Chrissy) |
| XPORT | Cross-portal shared requirements |

| Area | Domain |
|------|--------|
| AUTH | Authentication & account management |
| DASH | Dashboard / home page |
| RET | Retailers management |
| SUP | Suppliers & gate management |
| HITL | HITL queue |
| MEM | Monica memory log |
| SPEC | Spec setup |
| YAML | YAML wizard |
| STATUS | Supplier status board |
| SCEN | Test scenarios |
| ERR | Validation errors |
| PATCH | Patches / Ryan's suggestions |
| CERT | Certification status |

---

## Requirements Memory System

The verifier maintains a **separate, persistent memory** from the step-correction
memory (`memory_manager.py`). This enables trend analysis across iterative runs.

### Files

| File | Purpose | Format |
|------|---------|--------|
| `playwrightcli/requirements_feedback.md` | Append-only log of every `--verify` run | Human-readable markdown |
| `playwrightcli/requirements_history.jsonl` | Structured run data for programmatic analysis | JSON Lines (one record per run) |
| `playwrightcli/requirements_memory.md` | Consolidated trend analysis | Auto-generated markdown |

### How It Works

```
Run 1: --verify
  → results recorded to requirements_feedback.md + requirements_history.jsonl
  → requirements_memory.md generated with baseline

Run 2: --verify (after code changes)
  → new results appended
  → memory.md rewritten with trend analysis:
      Regressions:  PAM-SUP-03 was PASS, now FAIL
      Recoveries:   CHR-PATCH-03 was FAIL, now PASS
      Stable:       42 requirements consistently passing

Run N: --verify
  → full timeline visible (last 10 runs)
  → ALERT printed for 3+ consecutive failures
  → flapping requirements flagged
```

### Trend Categories

| Category | Meaning |
|----------|---------|
| **Stable PASS** | Requirement passed on every recorded run |
| **Persistent FAIL** | Requirement failed on every recorded run — needs attention |
| **Regression** | Was PASS, now FAIL — something broke |
| **Recovery** | Was FAIL, now PASS — fix confirmed working |
| **Flapping** | Changed status 3+ times — unstable, likely environmental |

### Consolidation

Requirements memory is auto-consolidated after each `--verify` run. It can also
be triggered manually:

```bash
python -m playwrightcli --consolidate
# consolidates BOTH step corrections AND requirements trends
```

### Dry-Run with History

```bash
python -m playwrightcli --portal all --verify --dry-run
```

Shows planned verification checks with historical context:
```
Requirements history: 5 previous run(s) recorded

=== PAM ===
  pam::login
    -> verify: PAM-AUTH-03..08, PAM-DASH-01..04, XPORT-02,03,05
  pam::suppliers
    -> verify: PAM-SUP-01..04
       PAM-SUP-03: FAIL (3 consecutive)
```
