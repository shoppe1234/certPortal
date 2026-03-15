# cliRequirements — Business Requirements Verification Harness

## What This Is

A deterministic, DOM-based verification harness that runs alongside the existing
Playwright E2E flows. While the design observer (`--observe`) evaluates CSS and
visual quality, the requirements verifier (`--verify`) checks that each portal page
**actually exhibits the business functionality** specified in `CLAUDE.md`,
`DECISIONS.md`, `TECHNICAL_REQUIREMENTS.md`, and `README.md`.

Activated via: `python -m playwrightcli --portal all --verify`

**Current state (Steps #1–8, #10 + Portal Refactoring complete):** 189 checks across 14 flows, 0 failures.
Portal Refactoring added 5 new flows: onboarding (ONB-01..20), exception (EXC-01..12),
template (TPL-01..10), gate-model (GATE-01..08), visual regression (VIS-01..05).

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

#### HITL Signal Integration (SIG-HITL-*) — Step #2
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| SIG-HITL-01 | POST /hitl-queue/{id}/approve returns HTTP 200 | ADR-020 | fetch() status == 200 |
| SIG-HITL-02 | kelly_approved_{id}.json written to S3 after approve | ADR-020 | SignalChecker.object_exists() |
| SIG-HITL-03 | Signal payload contains queue_id, draft, and channel | ADR-020 | JSON key check via S3 fetch |

#### Gate Enforcement (INV03-GATE-*) — Step #4
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| INV03-GATE-01 | Out-of-order gate POST (gate_2 while gate_1=PENDING) returns HTTP 409 | INV-03, gate_enforcer.py | fetch() status == 409 |
| INV03-GATE-02 | 409 response body contains gate ordering error message | INV-03 | "gate"/"cannot"/"complete" in detail field |
| INV03-GATE-03 | Legal gate-1 POST (no prerequisite, idempotent) returns HTTP 200 | INV-03 | fetch() status == 200 |

#### Password Reset E2E (PW-RESET-*) — Step #5
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| PW-RESET-01 | POST /forgot-password redirects to /login?msg=reset_sent | ADR-023 | URL contains msg=reset_sent |
| PW-RESET-02 | Reset token written to password_reset_tokens and retrievable | ADR-023 | TokenFetcher.get_latest_token() returns non-None |
| PW-RESET-03 | POST /reset-password redirects to /login?msg=password_changed | ADR-023 | URL contains msg=password_changed |
| PW-RESET-04 | Login with new password succeeds after reset | ADR-023 | URL does not contain /login after submit |
| PW-RESET-05 | Original password restored via /change-password (idempotency) | ADR-016 | fetch() ok == True |

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

#### YAML Wizard Signal Integration (SIG-YAML2-*) — Step #2
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| SIG-YAML2-01 | POST /yaml-wizard/path2 returns HTTP 200 | ADR-018 | fetch() status == 200 |
| SIG-YAML2-02 | andy_path2_trigger_*.json written to S3 | ADR-018 | SignalChecker.list_signals_since() finds key |
| SIG-YAML2-03 | Signal payload has type=andy_yaml_path2 and retailer_slug | ADR-018 | JSON key/value check via S3 fetch |

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

#### Patches — Patch Apply Signal (SIG-PATCH-*) — Step #2
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| SIG-PATCH-01 | POST /patches/{id}/mark-applied returns HTTP 200 | ADR-019 | fetch() status == 200 |
| SIG-PATCH-02 | moses_revalidate_{id}_{ts}.json written to S3 | ADR-019 | SignalChecker.list_signals_since() finds key |
| SIG-PATCH-03 | Signal payload has trigger=patch_applied and patch_id | ADR-019 | JSON key/value check via S3 fetch |

#### Certification Status (CHR-CERT-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| CHR-CERT-01 | Certification page loads without error | CLAUDE.md | No 500/error state |
| CHR-CERT-02 | Certification badge or pending status visible | portals/chrissy.py | Badge or status element |

---

### SCOPE — Multi-Tenant Isolation (INV-06) — Step #3

Verifies that supplier and retailer data is correctly scoped. Four users across two
tenants (lowes/acme, target/rival) log in and confirm they can see their own data
and cannot see the other tenant's data.

#### Supplier Isolation (SCOPE-SUP-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| SCOPE-SUP-01 | acme_supplier sees own error code (850-BEG-01) on /patches | INV-06 | "850-beg-01" in body text |
| SCOPE-SUP-02 | acme_supplier cannot see rival error code (855-AK1-01) | INV-06 | "855-ak1-01" absent from body text |
| SCOPE-SUP-03 | acme_supplier sees own transaction type (850) on /scenarios | INV-06 | "850" in body text |
| SCOPE-SUP-04 | acme_supplier cannot see rival retailer "target" on /scenarios | INV-06 | "target" absent from body text |
| SCOPE-SUP-05 | rival_supplier sees own error code (855-AK1-01) on /patches | INV-06 | "855-ak1-01" in body text |
| SCOPE-SUP-06 | rival_supplier cannot see acme error code (850-BEG-01) | INV-06 | "850-beg-01" absent from body text |
| SCOPE-SUP-07 | rival_supplier sees own transaction type (855) on /scenarios | INV-06 | "855" in body text |
| SCOPE-SUP-08 | rival_supplier cannot see acme retailer "lowes" on /scenarios | INV-06 | "lowes" absent from body text |

#### Retailer Isolation (SCOPE-RET-*)
| ID | Requirement | Source | Verification |
|----|-------------|--------|--------------|
| SCOPE-RET-01 | lowes_retailer sees "acme" on /supplier-status | INV-06 | "acme" in body text |
| SCOPE-RET-02 | lowes_retailer cannot see "rival" on /supplier-status | INV-06 | "rival" absent from body text |
| SCOPE-RET-03 | target_retailer sees "rival" on /supplier-status | INV-06 | "rival" in body text |
| SCOPE-RET-04 | target_retailer cannot see "acme" on /supplier-status | INV-06 | "acme" absent from body text |

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

## Completed Enhancements (Steps #1–5)

The following items from the original "Future Enhancements" list are now **implemented**:

| # | Enhancement | Implemented as | Step |
|---|-------------|----------------|------|
| 11 | Database Fixture Seeding | `playwrightcli/fixtures/seed.sql` — idempotent, covers all 9 previously-skipped checks | Step #1 |
| 2 | Patch Apply → Moses Signal | `chrissy::patch-apply-signal` + SIG-PATCH-01..03 + `signal_checker.py` | Step #2 |
| 3 | HITL Approve → Kelly Signal | `pam::hitl-approve-signal` + SIG-HITL-01..03 + `signal_checker.py` | Step #2 |
| 1 | YAML Wizard Path 2 Signal | `meredith::yaml-wizard-signal` + SIG-YAML2-01..03 | Step #2 |
| 8 | Multi-Tenant Scope Verification | `scope_flow.py` + SCOPE-SUP-01..08 + SCOPE-RET-01..04 | Step #3 |
| 5 | Gate Enforcement UI Verification | `pam::gate-enforcement` + INV03-GATE-01..03 | Step #4 |
| 6 | Password Reset Flow E2E | `pam::password-reset` + PW-RESET-01..05 + `token_fetcher.py` | Step #5 |

---

## Completed Enhancements (Steps #6–8, #10)

| Step | Focus | Req IDs | Flow / Step Key |
|------|-------|---------|-----------------|
| #6 | **JWT revocation E2E** — logout → protected route blocked → new login succeeds | JWT-REV-01..03 | `pam::jwt-revocation` |
| #7 | **RBAC cross-portal** — supplier→PAM 403, retailer→Chrissy 403, supplier→Meredith 403 | RBAC-01..03 | `rbac_flow.py` (new standalone flow) |
| #8 | **Certification full flow** — gate_3=CERTIFIED reflected in Chrissy dashboard + /certification | CHR-CERT-03..04 | `scope::cert-dashboard`, `scope::cert-certification` |
| #10 | **Andy path 1 & 3 signals** — complete signal coverage for all 3 ingestion paths | SIG-YAML1-01..03, SIG-YAML3-01..03 | `meredith::yaml-wizard-path1-signal`, `meredith::yaml-wizard-path3-signal` |

### JWT-REV Requirements
| ID | Requirement | Verification |
|----|-------------|--------------|
| JWT-REV-01 | POST /logout redirects browser to /login | URL is /login after form submit |
| JWT-REV-02 | Protected route inaccessible after logout | Navigation to /suppliers lands at /login |
| JWT-REV-03 | Fresh login after logout succeeds | New credentials accepted, URL off /login |

### RBAC Requirements
| ID | Requirement | Verification |
|----|-------------|--------------|
| RBAC-01 | Supplier JWT rejected on PAM admin route (/suppliers) | PAM redirects supplier to /login |
| RBAC-02 | Retailer JWT rejected on Chrissy supplier route (/patches) | Chrissy redirects retailer to /login |
| RBAC-03 | Supplier JWT rejected on Meredith retailer route (/supplier-status) | Meredith redirects supplier to /login |

### CHR-CERT-03..04 Requirements (Step #8)
| ID | Requirement | Verification |
|----|-------------|--------------|
| CHR-CERT-03 | Dashboard shows CERTIFIED badge for cert_test supplier | `.cert-badge` element and "EDI Certified" text visible |
| CHR-CERT-04 | /certification page shows certified status | "certified" text visible |

### SIG-YAML1 / SIG-YAML3 Requirements (Step #10)
| ID | Requirement | Verification |
|----|-------------|--------------|
| SIG-YAML1-01 | YAML Wizard Path 1 POST returns HTTP 200 | response.status == 200 |
| SIG-YAML1-02 | andy_path1_trigger_*.json written to S3 | S3 object exists after timestamp |
| SIG-YAML1-03 | Signal payload has type=andy_yaml_path1 and retailer_slug=lowes | payload fields validated |
| SIG-YAML3-01 | YAML Wizard Path 3 POST returns HTTP 200 | response.status == 200 |
| SIG-YAML3-02 | andy_path3_trigger_*.json written to S3 | S3 object exists after timestamp |
| SIG-YAML3-03 | Signal payload has type=andy_yaml_path3 and retailer_slug=lowes | payload fields validated |

## Deferred Enhancement (Step #9)

| Step | Focus | Req IDs | Why Deferred |
|------|-------|---------|--------------|
| #9 | **Monica escalation pipeline** — FAIL occurrence → HITL queue write | MON-ESC-01..03 | Requires Monica running as a live background process — not feasible in automated harness without orchestration |

---

## Remaining Future Enhancements (not yet scheduled)

### Refresh Token Rotation Verification
**Gap:** Auth checks verify login, but not that expired access tokens are silently refreshed.
**Future:** Manually expire access token cookie, navigate, verify `/token/refresh` fires.

### Agent Roster Status Verification (PAM)
**Gap:** Agent names on dashboard are verified but not their live status indicators.
**Future:** Seed known agent activity, verify PAM roster shows correct last-run timestamps.

### HTMX Polling Verification
**Gap:** HTMX library load is verified but polling endpoints are not exercised.
**Future:** Use `page.route()` to intercept polling XHR and verify DOM updates.

### Accessibility Requirements (WCAG AA)
**Gap:** Design observer checks visuals; programmatic accessibility not checked.
**Future:** `page.accessibility.snapshot()` — ARIA landmarks, form labels, heading hierarchy.

### Cross-Portal Navigation Consistency
**Gap:** Portals tested independently; shared nav/logout patterns not compared.
**Future:** Compare nav structure, footer layout, and logout behavior across all three portals.

### Error Page Verification
**Gap:** Happy paths only; 401/403/404/500 error rendering not checked.
**Future:** Navigate to non-existent routes and unauthorized pages; verify error pages render
correctly with user-friendly messages, not raw stack traces.

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

| Prefix | Portal / Domain |
|--------|--------|
| PAM | Admin portal (Pam) |
| MER | Retailer portal (Meredith) |
| CHR | Supplier portal (Chrissy) |
| SCOPE | Multi-tenant scope isolation (all portals) |
| XPORT | Cross-portal shared requirements |
| SIG | S3 signal integration (Step #2) |
| INV03 | Gate enforcement invariant (Step #4) |
| PW | Password reset flow (Step #5) |
| JWT | JWT revocation (Step #6) |
| RBAC | Role-based access control (Step #7) |
| MON | Monica escalation pipeline (Step #9, deferred) |

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
| GATE | Gate enforcement checks |
| RESET | Password reset flow |
| SUP/RET | Scope isolation checks (within SCOPE prefix) |

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
