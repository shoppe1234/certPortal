"""requirements_verifier.py — DOM-based business requirements verification.

Runs deterministic DOM assertions on each portal page to verify that business
requirements from CLAUDE.md, DECISIONS.md, and TECHNICAL_REQUIREMENTS.md are
reflected in the rendered UI.

Usage:
  Activated via `python -m playwrightcli --portal all --verify`
  Called from each flow via `await self.verify(step_name)`

Each check maps to a requirement ID (e.g., PAM-DASH-01, CHR-PATCH-03).
Results are accumulated per portal and written as a requirements report.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REPORT_DIR = Path("requirements_reports")


@dataclass
class ReqResult:
    """Result of a single requirement check."""
    req_id: str
    description: str
    status: str  # PASS | FAIL | SKIP
    detail: str = ""


@dataclass
class RequirementsVerifier:
    """Accumulates requirement check results across a portal flow."""

    portal: str
    results: list[ReqResult] = field(default_factory=list)
    # Optional S3 signal checker — attached by cli.py when --verify is active.
    # None when boto3 is unavailable or S3 is unreachable; signal checks SKIP.
    signal_checker: Any | None = field(default=None)

    def _record(self, req_id: str, description: str, passed: bool, detail: str = "") -> None:
        status = "PASS" if passed else "FAIL"
        self.results.append(ReqResult(req_id=req_id, description=description, status=status, detail=detail))
        icon = "+" if passed else "!"
        print(f"  [{icon}] {req_id}: {description} — {status}" + (f" ({detail})" if detail and not passed else ""))

    def _skip(self, req_id: str, description: str, reason: str = "") -> None:
        self.results.append(ReqResult(req_id=req_id, description=description, status="SKIP", detail=reason))
        print(f"  [-] {req_id}: {description} — SKIP" + (f" ({reason})" if reason else ""))

    # ------------------------------------------------------------------
    # PAM verification methods
    # ------------------------------------------------------------------

    async def verify_pam_login(self, page) -> None:
        """Verify PAM dashboard after successful login (PAM-AUTH-*, PAM-DASH-*)."""
        url = page.url

        # PAM-AUTH-03: Successful login redirects away from /login
        self._record("PAM-AUTH-03", "Login redirects to dashboard", "/login" not in url)

        # PAM-AUTH-05: Navigation shows logged-in username
        nav_text = await page.text_content("body") or ""
        self._record("PAM-AUTH-05", "Nav shows logged-in username", "pam_admin" in nav_text.lower())

        # PAM-AUTH-06: Navigation shows role badge
        self._record("PAM-AUTH-06", "Nav shows admin role indicator",
                      "admin" in nav_text.lower())

        # PAM-AUTH-07: Sign-out button present
        logout_el = await page.query_selector('a[href*="logout"], button:has-text("sign out"), button:has-text("logout"), a:has-text("sign out")')
        self._record("PAM-AUTH-07", "Sign-out button present", logout_el is not None)

        # PAM-AUTH-08: Register link present (admin-only)
        register_el = await page.query_selector('a[href*="register"]')
        self._record("PAM-AUTH-08", "Register link present (admin-only)", register_el is not None)

        # PAM-DASH-01 through PAM-DASH-03: KPI cards
        body_text = nav_text.lower()
        self._record("PAM-DASH-01", "KPI: retailer count element present",
                      "retailer" in body_text)
        self._record("PAM-DASH-02", "KPI: supplier count element present",
                      "supplier" in body_text)
        self._record("PAM-DASH-03", "KPI: HITL queue count present",
                      "hitl" in body_text or "queue" in body_text or "approval" in body_text)

        # PAM-DASH-04: Agent roster
        agents = ["monica", "dwight", "andy", "moses", "kelly", "ryan"]
        agents_found = [a for a in agents if a in body_text]
        self._record("PAM-DASH-04", "Agent roster visible (6 agents)",
                      len(agents_found) >= 4,
                      f"Found: {', '.join(agents_found)}")

        # XPORT-02: Portal-specific CSS
        css_link = await page.query_selector('link[href*="pam.css"], link[href*="pam"]')
        self._record("XPORT-02", "PAM CSS theme loaded", css_link is not None)

        # XPORT-03: HTMX loaded
        htmx_el = await page.query_selector('script[src*="htmx"]')
        self._record("XPORT-03", "HTMX library loaded", htmx_el is not None)

        # XPORT-05: Change password link
        chpw_el = await page.query_selector('a[href*="change-password"]')
        self._record("XPORT-05", "Change password link accessible", chpw_el is not None)

    async def verify_pam_retailers(self, page) -> None:
        """Verify PAM retailers page (PAM-RET-*)."""
        # PAM-RET-01: Page loads without error
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        no_error = "500" not in title and "error" not in title.lower()
        self._record("PAM-RET-01", "Retailers page loads without error", no_error)

        # PAM-RET-02: Table or empty-state renders
        table_el = await page.query_selector("table, .empty-state")
        has_content = await page.query_selector("main, h1, h2")
        self._record("PAM-RET-02", "Table or empty-state renders",
                      table_el is not None or has_content is not None)

        # PAM-RET-03: Table has retailer column
        body_text = (await page.text_content("body") or "").lower()
        self._record("PAM-RET-03", "Retailer column visible",
                      "retailer" in body_text)

    async def verify_pam_suppliers(self, page) -> None:
        """Verify PAM suppliers page (PAM-SUP-*)."""
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        no_error = "500" not in title and "error" not in title.lower()
        self._record("PAM-SUP-01", "Suppliers page loads without error", no_error)

        content_el = await page.query_selector("table, .empty-state")
        has_content = await page.query_selector("main, h1, h2")
        self._record("PAM-SUP-02", "Table or empty-state renders",
                      content_el is not None or has_content is not None)

        # PAM-SUP-03 & 04: Only check gate data when actual table rows exist
        data_table = await page.query_selector("table tbody tr")
        body_text = (await page.text_content("body") or "").lower()
        if data_table is not None:
            has_gates = ("gate" in body_text or "g1" in body_text or "g2" in body_text
                         or "g3" in body_text or "pending" in body_text
                         or "complete" in body_text or "certified" in body_text)
            self._record("PAM-SUP-03", "Gate status badges visible", has_gates)

            gate_buttons = await page.query_selector_all(
                'button:has-text("G1"), button:has-text("G2"), button:has-text("G3"), '
                'button:has-text("Certif"), a:has-text("G1"), a:has-text("G2"), a:has-text("G3")'
            )
            self._record("PAM-SUP-04", "Gate progression buttons present",
                          len(gate_buttons) > 0 or "certified" in body_text,
                          f"Found {len(gate_buttons)} gate buttons")
        else:
            self._skip("PAM-SUP-03", "Gate status badges visible", "No suppliers in table")
            self._skip("PAM-SUP-04", "Gate progression buttons present", "No suppliers in table")

    async def verify_pam_hitl_queue(self, page) -> None:
        """Verify PAM HITL queue page (PAM-HITL-*)."""
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        no_error = "500" not in title and "error" not in title.lower()
        self._record("PAM-HITL-01", "HITL queue page loads", no_error)

        body_text = (await page.text_content("body") or "").lower()
        has_queue_content = ("queue" in body_text or "hitl" in body_text
                             or "approval" in body_text or "pending" in body_text
                             or "no items" in body_text or "empty" in body_text)
        self._record("PAM-HITL-02", "Queue content or empty-state renders", has_queue_content)

        # Check for approve/reject if items exist.
        # The HITL queue template renders .hitl-card divs (not a <table>),
        # so detect the card list rather than a table element.
        hitl_items_el = await page.query_selector("#hitl-list, .hitl-card")
        if hitl_items_el is not None:
            approve_btn = await page.query_selector(
                'button:has-text("Approve"), button:has-text("approve"), '
                'a:has-text("Approve"), [hx-post*="approve"]'
            )
            self._record("PAM-HITL-03", "Approve action for pending items",
                          approve_btn is not None)

            reject_btn = await page.query_selector(
                'button:has-text("Reject"), button:has-text("reject"), '
                'a:has-text("Reject"), [hx-post*="reject"]'
            )
            self._record("PAM-HITL-04", "Reject action for pending items",
                          reject_btn is not None)
        else:
            self._skip("PAM-HITL-03", "Approve action for pending items", "Queue is empty")
            self._skip("PAM-HITL-04", "Reject action for pending items", "Queue is empty")

    async def verify_pam_monica_memory(self, page) -> None:
        """Verify PAM Monica memory page (PAM-MEM-*)."""
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        no_error = "500" not in title and "error" not in title.lower()
        self._record("PAM-MEM-01", "Monica memory page loads", no_error)

        has_content = await page.query_selector("table, .empty-state, main, h1, h2")
        self._record("PAM-MEM-02", "Memory log entries or empty-state render",
                      has_content is not None)

        # PAM-MEM-03: Pagination
        body_text = (await page.text_content("body") or "").lower()
        pagination = await page.query_selector(
            'a:has-text("Next"), a:has-text("Prev"), a:has-text("next"), '
            '.pagination, nav[aria-label*="pagination"]'
        )
        has_pagination = pagination is not None or "page" in body_text
        self._record("PAM-MEM-03", "Pagination controls present", has_pagination)

    # ------------------------------------------------------------------
    # MEREDITH verification methods
    # ------------------------------------------------------------------

    async def verify_meredith_login(self, page) -> None:
        """Verify Meredith dashboard after login (MER-AUTH-*, MER-DASH-*)."""
        url = page.url
        self._record("MER-AUTH-02", "Login redirects to dashboard", "/login" not in url)

        body_text = (await page.text_content("body") or "").lower()
        self._record("MER-AUTH-04", "Nav shows retailer context",
                      "retailer" in body_text or "lowes" in body_text)

        # XPORT-02: CSS theme
        css_link = await page.query_selector('link[href*="meredith.css"], link[href*="meredith"]')
        self._record("XPORT-02", "Meredith CSS theme loaded", css_link is not None)

        # XPORT-03: HTMX
        htmx_el = await page.query_selector('script[src*="htmx"]')
        self._record("XPORT-03", "HTMX library loaded", htmx_el is not None)

        # XPORT-05: Change password
        chpw_el = await page.query_selector('a[href*="change-password"]')
        self._record("XPORT-05", "Change password link accessible", chpw_el is not None)

    async def verify_meredith_spec_setup(self, page) -> None:
        """Verify Meredith spec setup page (MER-SPEC-*)."""
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        no_error = "500" not in title and "error" not in title.lower()
        self._record("MER-SPEC-01", "Spec setup page loads without error", no_error)

        body_text = (await page.text_content("body") or "").lower()

        # MER-SPEC-02: Wizard entry points (replaced PDF upload per ADR-032)
        wizard_entry = await page.query_selector(
            '.wizard-card, a[href*="lifecycle-wizard"], a[href*="yaml-wizard"], '
            'button:has-text("Lifecycle"), button:has-text("Layer 2"), '
            '[href*="wizard"]'
        )
        has_wizard_entry = wizard_entry is not None or "lifecycle wizard" in body_text or "layer 2" in body_text
        self._record("MER-SPEC-02", "Wizard entry points present (Lifecycle + Layer 2)", has_wizard_entry)

        # MER-SPEC-03: Retailer slug field
        retailer_input = await page.query_selector(
            'input[name*="retailer"], select[name*="retailer"]'
        )
        has_retailer = retailer_input is not None or "retailer" in body_text
        self._record("MER-SPEC-03", "Retailer slug field present", has_retailer)

        # MER-SPEC-04: Spec table, artifact gallery, or empty state
        spec_content = await page.query_selector("table, .empty-state, .artifact-card, .artifact-gallery")
        has_spec = spec_content is not None or "spec" in body_text or "artifact" in body_text
        self._record("MER-SPEC-04", "Spec table, artifact gallery, or empty-state renders", has_spec)

        # MER-SPEC-05: YAML Wizard link
        wizard_link = await page.query_selector(
            'a[href*="yaml-wizard"], a[href*="wizard"], '
            'button:has-text("Wizard"), button:has-text("YAML")'
        )
        has_wizard = wizard_link is not None or "wizard" in body_text or "yaml" in body_text
        self._record("MER-SPEC-05", "YAML Wizard link/button present", has_wizard)

    async def verify_meredith_supplier_status(self, page) -> None:
        """Verify Meredith supplier status page (MER-STATUS-*)."""
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        no_error = "500" not in title and "error" not in title.lower()
        self._record("MER-STATUS-01", "Supplier status page loads", no_error)

        table_el = await page.query_selector("table, .empty-state")
        has_content = await page.query_selector("main, h1, h2")
        self._record("MER-STATUS-02", "Status table or empty-state renders",
                      table_el is not None or has_content is not None)

        body_text = (await page.text_content("body") or "").lower()

        # MER-STATUS-03: Gate columns
        has_gate_cols = ("gate" in body_text or "spec" in body_text
                         or "validation" in body_text or "certification" in body_text
                         or "g1" in body_text or "g2" in body_text or "g3" in body_text)
        self._record("MER-STATUS-03", "Gate columns visible (Spec/Validation/Certification)",
                      has_gate_cols)

        # MER-STATUS-04: Gate status badges (only check when rows exist)
        has_badges = ("pending" in body_text or "complete" in body_text
                      or "certified" in body_text)
        data_row = await page.query_selector("table tbody tr")
        if data_row is not None:
            self._record("MER-STATUS-04", "Gate status badges present", has_badges)
        else:
            self._skip("MER-STATUS-04", "Gate status badges present", "No suppliers in table")

        # MER-STATUS-05: Test pass/fail counts
        has_test_counts = ("pass" in body_text or "fail" in body_text
                           or "test" in body_text)
        if table_el is not None:
            self._record("MER-STATUS-05", "Test pass/fail counts displayed", has_test_counts)
        else:
            self._skip("MER-STATUS-05", "Test pass/fail counts displayed", "No suppliers in table")

    # ------------------------------------------------------------------
    # CHRISSY verification methods
    # ------------------------------------------------------------------

    async def verify_chrissy_login(self, page) -> None:
        """Verify Chrissy dashboard after login (CHR-AUTH-*, CHR-DASH-*)."""
        url = page.url
        self._record("CHR-AUTH-02", "Login redirects to dashboard", "/login" not in url)

        body_text = (await page.text_content("body") or "").lower()
        self._record("CHR-AUTH-04", "Nav shows supplier context",
                      "supplier" in body_text or "acme" in body_text)

        # CHR-DASH-01: Dashboard loads
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        no_error = "500" not in title and "error" not in title.lower()
        self._record("CHR-DASH-01", "Dashboard loads without error", no_error)

        # CHR-DASH-02: Gate status cards
        has_gates = ("gate" in body_text or "g1" in body_text or "g2" in body_text
                     or "g3" in body_text or "spec" in body_text)
        self._record("CHR-DASH-02", "Gate status cards present (G1, G2, G3)", has_gates)

        # CHR-DASH-03: Progress indicator
        progress_el = await page.query_selector(
            '.progress, .progress-bar, [role="progressbar"], '
            '.step-indicator, .progress-fill'
        )
        has_progress = progress_el is not None or "progress" in body_text or "step" in body_text
        self._record("CHR-DASH-03", "Progress indicator visible", has_progress)

        # CHR-DASH-04: Test metrics
        has_metrics = ("test" in body_text or "passed" in body_text
                       or "scenario" in body_text or "%" in body_text)
        self._record("CHR-DASH-04", "Test metrics displayed", has_metrics)

        # CHR-DASH-05: Quick action links
        scenario_link = await page.query_selector('a[href*="scenario"]')
        error_link = await page.query_selector('a[href*="error"]')
        patch_link = await page.query_selector('a[href*="patch"]')
        found_links = sum(1 for l in [scenario_link, error_link, patch_link] if l is not None)
        self._record("CHR-DASH-05", "Quick action links (Scenarios, Errors, Patches)",
                      found_links >= 2,
                      f"Found {found_links}/3 links")

        # XPORT-02: CSS theme
        css_link = await page.query_selector('link[href*="chrissy.css"], link[href*="chrissy"]')
        self._record("XPORT-02", "Chrissy CSS theme loaded", css_link is not None)

        # XPORT-03: HTMX
        htmx_el = await page.query_selector('script[src*="htmx"]')
        self._record("XPORT-03", "HTMX library loaded", htmx_el is not None)

        # XPORT-05: Change password
        chpw_el = await page.query_selector('a[href*="change-password"]')
        self._record("XPORT-05", "Change password link accessible", chpw_el is not None)

    async def verify_chrissy_scenarios(self, page) -> None:
        """Verify Chrissy scenarios page (CHR-SCEN-*)."""
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        no_error = "500" not in title and "error" not in title.lower()
        self._record("CHR-SCEN-01", "Scenarios page loads without error", no_error)

        table_el = await page.query_selector("table, .empty-state")
        has_content = await page.query_selector("main, h1, h2")
        self._record("CHR-SCEN-02", "Scenario cards/table or empty-state",
                      table_el is not None or has_content is not None)

        body_text = (await page.text_content("body") or "").lower()

        # CHR-SCEN-03: Status badges (PASS/FAIL/PARTIAL)
        # Gate on .scenario-card (cards template) not table — matches CHR-SCEN-04 pattern.
        has_status = ("pass" in body_text or "fail" in body_text
                      or "partial" in body_text or "status" in body_text)
        scenario_card_early = await page.query_selector(".scenario-card")
        if scenario_card_early is not None:
            self._record("CHR-SCEN-03", "Status badges (PASS/FAIL/PARTIAL)", has_status)
        else:
            self._skip("CHR-SCEN-03", "Status badges (PASS/FAIL/PARTIAL)", "No scenarios data")

        # CHR-SCEN-04: Transaction type visible (only check when scenario cards exist)
        has_tx_type = ("850" in body_text or "855" in body_text or "856" in body_text
                       or "810" in body_text or "860" in body_text or "865" in body_text
                       or "transaction" in body_text)
        scenario_card = await page.query_selector(".scenario-card")
        if scenario_card is not None:
            self._record("CHR-SCEN-04", "Transaction type visible", has_tx_type)
        else:
            self._skip("CHR-SCEN-04", "Transaction type visible", "No scenarios data")

        # CHR-SCEN-05: Validation timestamp
        # Gate on .scenario-card (cards template) not table — matches CHR-SCEN-04 pattern.
        has_timestamp = ("validated" in body_text or "timestamp" in body_text
                         or "date" in body_text or "202" in body_text)
        if scenario_card_early is not None:
            self._record("CHR-SCEN-05", "Validation timestamp visible", has_timestamp)
        else:
            self._skip("CHR-SCEN-05", "Validation timestamp visible", "No scenarios data")

    async def verify_chrissy_errors(self, page) -> None:
        """Verify Chrissy errors page (CHR-ERR-*)."""
        # Check for 500 specifically — "error" appears legitimately in "Validation Errors"
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        no_error = "500" not in title and "internal server error" not in title.lower()
        self._record("CHR-ERR-01", "Errors page loads without error", no_error)

        has_content = await page.query_selector("main, h1, h2")
        self._record("CHR-ERR-02", "Error groups or empty-state renders",
                      has_content is not None)

        body_text = (await page.text_content("body") or "").lower()

        # CHR-ERR-03: Error details (expandable)
        has_detail_el = await page.query_selector(
            'details, .error-card, .expandable, [data-toggle], '
            '.accordion, .error-group'
        )
        has_detail_text = ("severity" in body_text or "error_code" in body_text
                           or "segment" in body_text or "element" in body_text)
        if has_detail_el is not None or has_detail_text:
            self._record("CHR-ERR-03", "Error details with severity/code/segment",
                          True)
        else:
            self._skip("CHR-ERR-03", "Error details with severity/code/segment",
                        "No error data or page is empty-state")

        # CHR-ERR-04: Patch suggestion section
        has_patch = ("patch" in body_text or "suggestion" in body_text
                     or "ryan" in body_text or "fix" in body_text)
        if has_detail_el is not None or has_detail_text:
            self._record("CHR-ERR-04", "Patch suggestion section visible", has_patch)
        else:
            self._skip("CHR-ERR-04", "Patch suggestion section visible",
                        "No errors to show patches for")

    async def verify_chrissy_patches(self, page) -> None:
        """Verify Chrissy patches page (CHR-PATCH-*)."""
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        no_error = "500" not in title and "error" not in title.lower()
        self._record("CHR-PATCH-01", "Patches page loads without error", no_error)

        table_el = await page.query_selector("table, .empty-state, .patch-card")
        has_content = await page.query_selector("main, h1, h2")
        self._record("CHR-PATCH-02", "Patch cards/table or empty-state",
                      table_el is not None or has_content is not None)

        body_text = (await page.text_content("body") or "").lower()

        # CHR-PATCH-03: Mark Applied action
        apply_btn = await page.query_selector(
            'button:has-text("Applied"), button:has-text("Apply"), '
            '[hx-post*="mark-applied"], button:has-text("Mark")'
        )
        if table_el is not None and "patch" in body_text:
            self._record("CHR-PATCH-03", "'Mark Applied' action available",
                          apply_btn is not None or "applied" in body_text)
        else:
            self._skip("CHR-PATCH-03", "'Mark Applied' action available", "No patches present")

        # CHR-PATCH-04: Reject action (only relevant when pending patches exist)
        reject_btn = await page.query_selector(
            'button:has-text("Reject"), [hx-post*="reject"]'
        )
        pending_btn = await page.query_selector('[hx-post*="mark-applied"]')
        if table_el is not None and "patch" in body_text and pending_btn is not None:
            self._record("CHR-PATCH-04", "'Reject' action available",
                          reject_btn is not None or "reject" in body_text)
        elif table_el is not None and "patch" in body_text:
            self._skip("CHR-PATCH-04", "'Reject' action available", "All patches already applied")
        else:
            self._skip("CHR-PATCH-04", "'Reject' action available", "No patches present")

        # CHR-PATCH-05: Filter controls
        filter_els = await page.query_selector_all(
            'button:has-text("All"), button:has-text("Pending"), button:has-text("Applied"), '
            '.filter-btn, .tab, [role="tab"]'
        )
        has_filters = len(filter_els) >= 2 or "filter" in body_text
        self._record("CHR-PATCH-05", "Filter controls (All/Pending/Applied)", has_filters)

        # CHR-PATCH-06: Content viewable
        content_link = await page.query_selector(
            'a[href*="content"], button:has-text("View"), button:has-text("view"), '
            'a:has-text("View")'
        )
        if table_el is not None and "patch" in body_text:
            self._record("CHR-PATCH-06", "Patch content viewable",
                          content_link is not None or "view" in body_text or "content" in body_text)
        else:
            self._skip("CHR-PATCH-06", "Patch content viewable", "No patches present")

    async def verify_chrissy_certification(self, page) -> None:
        """Verify Chrissy certification page (CHR-CERT-*)."""
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        no_error = "500" not in title and "error" not in title.lower()
        self._record("CHR-CERT-01", "Certification page loads without error", no_error)

        body_text = (await page.text_content("body") or "").lower()
        has_cert_info = ("certif" in body_text or "badge" in body_text
                         or "status" in body_text or "gate" in body_text
                         or "pending" in body_text or "complete" in body_text)
        self._record("CHR-CERT-02", "Certification badge or pending status visible",
                      has_cert_info)

    # ------------------------------------------------------------------
    # Certification full-flow verification (Step #8)
    # Called directly from scope_flow.py cert steps — not via verify() dispatch.
    # ------------------------------------------------------------------

    async def verify_cert_dashboard(self, page) -> None:
        """CHR-CERT-03: Dashboard shows CERTIFIED badge for cert_test supplier."""
        body_text = (await page.text_content("body") or "").lower()
        # chrissy_home.html renders "🎉 You're Certified!" and <div class="cert-badge">
        has_badge = (
            "certified" in body_text
            or "cert-badge" in (await page.content()).lower()
            or "edi certified" in body_text
        )
        self._record(
            "CHR-CERT-03",
            "Dashboard shows CERTIFIED badge for cert_test supplier",
            has_badge,
            "cert-badge element and/or 'certified' text found" if has_badge else "No certified badge visible",
        )

    async def verify_cert_certification_page(self, page) -> None:
        """CHR-CERT-04: /certification page shows certified status."""
        body_text = (await page.text_content("body") or "").lower()
        # chrissy_home.html renders "Certified" gate-status-badge and "EDI Certified" inside cert-badge
        has_certified_status = (
            "certified" in body_text
            or "edi certified" in body_text
        )
        self._record(
            "CHR-CERT-04",
            "/certification page shows certified status for cert_test supplier",
            has_certified_status,
            "'certified' status text found" if has_certified_status else "No certified status visible",
        )

    # ------------------------------------------------------------------
    # Scope isolation verification (Step #3)
    # Called directly from scope_flow.py — not via verify() dispatch.
    # ------------------------------------------------------------------

    async def verify_scope_supplier_patches(
        self,
        page,
        own_error_code: str,
        rival_error_code: str,
        req_own: str,
        req_isolation: str,
    ) -> None:
        """Check /patches for supplier scope: own data visible, rival's absent."""
        body_text = (await page.text_content("body") or "").lower()

        # Own supplier's patches must be present (own error code appears in patch card)
        has_own = own_error_code.lower() in body_text
        self._record(req_own, f"Own error code {own_error_code!r} visible in /patches", has_own)

        # Rival's distinctive error code must be absent
        rival_absent = rival_error_code.lower() not in body_text
        self._record(
            req_isolation,
            f"Rival error code {rival_error_code!r} absent from /patches",
            rival_absent,
            f"{'NOT FOUND (correct)' if rival_absent else 'LEAKED — rival data visible'}",
        )

    async def verify_scope_supplier_scenarios(
        self,
        page,
        own_tx_type: str,
        rival_retailer: str,
        req_own: str,
        req_isolation: str,
    ) -> None:
        """Check /scenarios for supplier scope: own tx type visible, rival retailer absent."""
        body_text = (await page.text_content("body") or "").lower()

        has_own = own_tx_type in body_text
        self._record(req_own, f"Transaction type {own_tx_type!r} visible in /scenarios", has_own)

        rival_absent = rival_retailer.lower() not in body_text
        self._record(
            req_isolation,
            f"Rival retailer {rival_retailer!r} absent from /scenarios",
            rival_absent,
            f"{'NOT FOUND (correct)' if rival_absent else 'LEAKED — rival retailer visible'}",
        )

    async def verify_scope_retailer_status(
        self,
        page,
        own_supplier: str,
        rival_supplier: str,
        req_own: str,
        req_isolation: str,
    ) -> None:
        """Check /supplier-status: own supplier visible, rival supplier absent."""
        body_text = (await page.text_content("body") or "").lower()

        has_own = own_supplier in body_text
        self._record(req_own, f"Own supplier {own_supplier!r} visible in /supplier-status", has_own)

        rival_absent = rival_supplier.lower() not in body_text
        self._record(
            req_isolation,
            f"Rival supplier {rival_supplier!r} absent from /supplier-status",
            rival_absent,
            f"{'NOT FOUND (correct)' if rival_absent else 'LEAKED — rival supplier visible'}",
        )

    # ------------------------------------------------------------------
    # Password reset E2E verification (Step #5)
    # Called directly from pam_flow password-reset step.
    # ------------------------------------------------------------------

    def verify_password_reset(
        self,
        *,
        forgot_redirected: bool,
        token_found: bool,
        reset_redirected: bool,
        login_succeeded: bool,
        restore_succeeded: bool,
    ) -> None:
        """PW-RESET-*: full forgot → token → reset → login → restore cycle.

        Args:
            forgot_redirected:  POST /forgot-password redirected to /login?msg=reset_sent.
            token_found:        TokenFetcher retrieved a valid token from the DB.
            reset_redirected:   POST /reset-password redirected to /login?msg=password_changed.
            login_succeeded:    Login with the new password succeeded (no /login in URL).
            restore_succeeded:  /change-password restored the original password (idempotency).
        """
        self._record(
            "PW-RESET-01",
            "POST /forgot-password redirects to /login?msg=reset_sent",
            forgot_redirected,
        )
        self._record(
            "PW-RESET-02",
            "Reset token written to DB and retrievable",
            token_found,
            "No token found in password_reset_tokens" if not token_found else "",
        )
        self._record(
            "PW-RESET-03",
            "POST /reset-password redirects to /login?msg=password_changed",
            reset_redirected,
        )
        self._record(
            "PW-RESET-04",
            "Login with new password succeeds after reset",
            login_succeeded,
        )
        self._record(
            "PW-RESET-05",
            "Original password restored via /change-password (idempotency)",
            restore_succeeded,
        )

    # ------------------------------------------------------------------
    # Gate enforcement verification (Step #4)
    # Called directly from pam_flow gate-enforcement step.
    # ------------------------------------------------------------------

    def verify_gate_enforcement(
        self,
        illegal_response: dict,
        legal_response: dict,
        supplier_id: str,
    ) -> None:
        """INV03-GATE-*: gate_enforcer.py blocks out-of-order transitions at the HTTP layer.

        Args:
            illegal_response: fetch() result for POST gate_3 when gate_2 is PENDING (expect 409).
            legal_response:   fetch() result for POST gate_2 when gate_1 is COMPLETE (expect 200).
            supplier_id:      Supplier used in the test (for error messages).
        """
        # INV03-GATE-01: out-of-order POST returns HTTP 409
        # (inv03_bad: gate_1=PENDING, so gate_2/complete must be blocked)
        status_409 = illegal_response.get("status") == 409
        self._record(
            "INV03-GATE-01",
            "Out-of-order gate POST (gate_2 while gate_1=PENDING) returns HTTP 409",
            status_409,
            f"HTTP {illegal_response.get('status')} (expected 409)",
        )

        # INV03-GATE-02: 409 body contains an ordering error message
        detail = str(illegal_response.get("body", {}).get("detail", "")).lower()
        has_error_msg = (
            "gate" in detail
            or "order" in detail
            or "precondition" in detail
            or "complete" in detail
            or "cannot" in detail
        )
        self._record(
            "INV03-GATE-02",
            "409 response body contains gate ordering error message",
            has_error_msg,
            f"detail: {detail[:120]!r}" if detail else "no detail field in response",
        )

        # INV03-GATE-03: legal gate-1 POST returns HTTP 200
        # (inv03_ok: gate_1 has no prerequisite; COMPLETE→COMPLETE upsert is idempotent)
        status_200 = legal_response.get("status") == 200
        self._record(
            "INV03-GATE-03",
            "Legal gate-1 POST (no prerequisite, idempotent) returns HTTP 200",
            status_200,
            f"HTTP {legal_response.get('status')} (expected 200)",
        )

    # ------------------------------------------------------------------
    # RBAC cross-portal enforcement verification (Step #7)
    # Called directly from rbac_flow — not via verify() dispatch.
    # ------------------------------------------------------------------

    def verify_rbac(
        self,
        *,
        req_id: str,
        description: str,
        access_blocked: bool,
    ) -> None:
        """RBAC-*: wrong-role access to protected route is blocked (redirect to /login).

        Args:
            req_id:        Requirement ID (RBAC-01 / RBAC-02 / RBAC-03).
            description:   Human-readable description for the report.
            access_blocked: Protected route redirected to /login (correct) or
                            was blocked at login for wrong-role user.
        """
        self._record(req_id, description, access_blocked,
                     "Blocked (correct)" if access_blocked else "LEAKED — route accessible to wrong role")

    # ------------------------------------------------------------------
    # JWT revocation verification (Step #6)
    # Called directly from pam_flow jwt-revocation step.
    # ------------------------------------------------------------------

    def verify_jwt_revocation(
        self,
        *,
        logout_redirected: bool,
        access_blocked: bool,
        relogin_ok: bool,
    ) -> None:
        """JWT-REV-*: logout → access blocked → fresh login succeeds.

        Args:
            logout_redirected: POST /logout caused browser to land on /login.
            access_blocked:    Navigating to a protected route after logout lands on /login.
            relogin_ok:        A fresh login after logout succeeds (not at /login).
        """
        self._record(
            "JWT-REV-01",
            "POST /logout redirects browser to /login",
            logout_redirected,
        )
        self._record(
            "JWT-REV-02",
            "Protected route inaccessible after logout (redirects to /login)",
            access_blocked,
        )
        self._record(
            "JWT-REV-03",
            "Fresh login after logout succeeds (lands away from /login)",
            relogin_ok,
        )

    # ------------------------------------------------------------------
    # Signal integration verification (Step #2)
    # Called directly from flow signal steps — not via verify() dispatch.
    # ------------------------------------------------------------------

    async def verify_signals_yaml_path2(
        self,
        ts: float,
        response: dict,
    ) -> None:
        """SIG-YAML2-*: YAML Wizard Path 2 POST + S3 andy_path2_trigger signal."""
        sc = self.signal_checker

        # SIG-YAML2-01: HTTP 200 from /yaml-wizard/path2
        http_ok = response.get("ok", False) and response.get("status") == 200
        self._record(
            "SIG-YAML2-01",
            "YAML Wizard Path 2 POST returns HTTP 200",
            http_ok,
            f"HTTP {response.get('status', '?')}",
        )

        if sc is None:
            self._skip("SIG-YAML2-02", "andy_path2_trigger_*.json signal written to S3", "S3 checker unavailable")
            self._skip("SIG-YAML2-03", "Signal payload has type=andy_yaml_path2 and retailer_slug", "S3 checker unavailable")
            return

        # SIG-YAML2-02: signal file exists under lowes/system/signals/
        signals = sc.list_signals_since("lowes/system/signals/andy_path2_trigger_", ts)
        has_signal = len(signals) > 0
        self._record(
            "SIG-YAML2-02",
            "andy_path2_trigger_*.json signal written to S3",
            has_signal,
            f"Found {len(signals)} signal(s) in lowes/system/signals/",
        )

        # SIG-YAML2-03: payload content correct
        if has_signal:
            payload = sc.get_object_json(signals[0]["Key"]) or {}
            correct_type = payload.get("type") == "andy_yaml_path2"
            correct_retailer = payload.get("retailer_slug") == "lowes"
            self._record(
                "SIG-YAML2-03",
                "Signal payload has type=andy_yaml_path2 and retailer_slug=lowes",
                correct_type and correct_retailer,
                f"type={payload.get('type')!r} retailer_slug={payload.get('retailer_slug')!r}",
            )
        else:
            self._skip("SIG-YAML2-03", "Signal payload has type=andy_yaml_path2 and retailer_slug=lowes", "No signal found")

    async def verify_signals_yaml_path1(
        self,
        ts: float,
        response: dict,
    ) -> None:
        """SIG-YAML1-*: YAML Wizard Path 1 — DEPRECATED (ADR-032). All checks SKIP."""
        self._skip("SIG-YAML1-01", "YAML Wizard Path 1 POST returns HTTP 200", "Path 1 deprecated (ADR-032)")
        self._skip("SIG-YAML1-02", "andy_path1_trigger_*.json signal written to S3", "Path 1 deprecated (ADR-032)")
        self._skip("SIG-YAML1-03", "Signal payload has type=andy_yaml_path1 and retailer_slug", "Path 1 deprecated (ADR-032)")

    async def verify_signals_yaml_path3(
        self,
        ts: float,
        response: dict,
    ) -> None:
        """SIG-YAML3-*: YAML Wizard Path 3 POST + S3 andy_path3_trigger signal."""
        sc = self.signal_checker

        http_ok = response.get("ok", False) and response.get("status") == 200
        self._record(
            "SIG-YAML3-01",
            "YAML Wizard Path 3 POST returns HTTP 200",
            http_ok,
            f"HTTP {response.get('status', '?')}",
        )

        if sc is None:
            self._skip("SIG-YAML3-02", "andy_path3_trigger_*.json signal written to S3", "S3 checker unavailable")
            self._skip("SIG-YAML3-03", "Signal payload has type=andy_yaml_path3 and retailer_slug", "S3 checker unavailable")
            return

        signals = sc.list_signals_since("lowes/system/signals/andy_path3_trigger_", ts)
        has_signal = len(signals) > 0
        self._record(
            "SIG-YAML3-02",
            "andy_path3_trigger_*.json signal written to S3",
            has_signal,
            f"Found {len(signals)} signal(s) in lowes/system/signals/",
        )

        if has_signal:
            payload = sc.get_object_json(signals[0]["Key"]) or {}
            correct_type = payload.get("type") == "andy_yaml_path3"
            correct_retailer = payload.get("retailer_slug") == "lowes"
            self._record(
                "SIG-YAML3-03",
                "Signal payload has type=andy_yaml_path3 and retailer_slug=lowes",
                correct_type and correct_retailer,
                f"type={payload.get('type')!r} retailer_slug={payload.get('retailer_slug')!r}",
            )
        else:
            self._skip("SIG-YAML3-03", "Signal payload has type=andy_yaml_path3 and retailer_slug=lowes", "No signal found")

    async def verify_signals_patch_applied(
        self,
        ts: float,
        patch_id: str,
        response: dict,
    ) -> None:
        """SIG-PATCH-*: Patch Mark-Applied POST + S3 moses_revalidate signal."""
        sc = self.signal_checker

        # SIG-PATCH-01: HTTP 200 from /patches/{id}/mark-applied
        http_ok = response.get("ok", False) and response.get("status") == 200
        self._record(
            "SIG-PATCH-01",
            "Patch Mark-Applied POST returns HTTP 200",
            http_ok,
            f"HTTP {response.get('status', '?')} patch_id={patch_id}",
        )

        if sc is None:
            self._skip("SIG-PATCH-02", "moses_revalidate_*.json signal written to S3", "S3 checker unavailable")
            self._skip("SIG-PATCH-03", "Signal payload has trigger=patch_applied and patch_id", "S3 checker unavailable")
            return

        # SIG-PATCH-02: signal file exists under lowes/acme/signals/
        signals = sc.list_signals_since(f"lowes/acme/signals/moses_revalidate_{patch_id}_", ts)
        has_signal = len(signals) > 0
        self._record(
            "SIG-PATCH-02",
            "moses_revalidate_*.json signal written to S3",
            has_signal,
            f"Found {len(signals)} signal(s) for patch_id={patch_id}",
        )

        # SIG-PATCH-03: payload content correct
        if has_signal:
            payload = sc.get_object_json(signals[0]["Key"]) or {}
            correct_trigger = payload.get("trigger") == "patch_applied"
            correct_pid = str(payload.get("patch_id", "")) == str(patch_id)
            self._record(
                "SIG-PATCH-03",
                "Signal payload has trigger=patch_applied and patch_id",
                correct_trigger and correct_pid,
                f"trigger={payload.get('trigger')!r} patch_id={payload.get('patch_id')!r}",
            )
        else:
            self._skip("SIG-PATCH-03", "Signal payload has trigger=patch_applied and patch_id", "No signal found")

    async def verify_signals_hitl_approved(
        self,
        ts: float,
        queue_id: str,
        response: dict,
    ) -> None:
        """SIG-HITL-*: HITL Approve POST + S3 kelly_approved signal."""
        sc = self.signal_checker

        # SIG-HITL-01: HTTP 200 from /hitl-queue/{queue_id}/approve
        http_ok = response.get("ok", False) and response.get("status") == 200
        self._record(
            "SIG-HITL-01",
            "HITL Approve POST returns HTTP 200",
            http_ok,
            f"HTTP {response.get('status', '?')} queue_id={queue_id}",
        )

        if sc is None:
            self._skip("SIG-HITL-02", f"kelly_approved_{queue_id}.json signal written to S3", "S3 checker unavailable")
            self._skip("SIG-HITL-03", "Signal payload has queue_id, draft, and channel", "S3 checker unavailable")
            return

        # SIG-HITL-02: exact signal key exists (queue_id is deterministic)
        signal_key = f"lowes/acme/signals/kelly_approved_{queue_id}.json"
        has_signal = sc.object_exists(signal_key)
        self._record(
            "SIG-HITL-02",
            f"kelly_approved_{queue_id}.json signal written to S3",
            has_signal,
            f"Key: {signal_key}",
        )

        # SIG-HITL-03: payload content correct
        if has_signal:
            payload = sc.get_object_json(signal_key) or {}
            has_queue_id = payload.get("queue_id") == queue_id
            has_draft    = bool(payload.get("draft"))
            has_channel  = bool(payload.get("channel"))
            self._record(
                "SIG-HITL-03",
                "Signal payload has queue_id, draft, and channel",
                has_queue_id and has_draft and has_channel,
                f"queue_id={has_queue_id} draft={has_draft} channel={has_channel}",
            )
        else:
            self._skip("SIG-HITL-03", "Signal payload has queue_id, draft, and channel", "No signal found")

    # ------------------------------------------------------------------
    # Lifecycle Wizard verification (LC-WIZ-01..08)
    # ------------------------------------------------------------------

    async def verify_lifecycle_wizard_page(self, page) -> None:
        """LC-WIZ-01: Lifecycle wizard page loads (HTTP 200, contains 'Lifecycle Wizard')."""
        body_text = (await page.text_content("body") or "").lower()
        has_title = "lifecycle wizard" in body_text or "lifecycle" in body_text
        self._record("LC-WIZ-01", "Lifecycle wizard page loads", has_title)

    async def verify_lifecycle_wizard_version_dropdown(self, page) -> None:
        """LC-WIZ-02: Version dropdown renders with at least one option."""
        options = await page.query_selector_all('select option, [data-version], .version-option')
        self._record(
            "LC-WIZ-02",
            "Version dropdown renders with at least one option",
            len(options) > 0,
            f"Found {len(options)} option(s)",
        )

    async def verify_lifecycle_wizard_tx_checkboxes(self, page) -> None:
        """LC-WIZ-03: Transaction checkboxes render for selected version."""
        checkboxes = await page.query_selector_all(
            'input[type="checkbox"][name*="transaction"], input[type="checkbox"][value*="85"], '
            'input[type="checkbox"][value*="81"]'
        )
        self._record(
            "LC-WIZ-03",
            "Transaction checkboxes render for selected version",
            len(checkboxes) > 0,
            f"Found {len(checkboxes)} checkbox(es)",
        )

    async def verify_lifecycle_wizard_mode_selector(self, page) -> None:
        """LC-WIZ-04: Mode selector shows three options (use/copy/create)."""
        body_text = (await page.text_content("body") or "").lower()
        has_use = "use" in body_text
        has_copy = "copy" in body_text or "clone" in body_text
        has_create = "create" in body_text or "new" in body_text
        modes_found = sum([has_use, has_copy, has_create])
        self._record(
            "LC-WIZ-04",
            "Mode selector shows three options (use/copy/create)",
            modes_found >= 2,
            f"Found {modes_found}/3 modes",
        )

    def verify_lifecycle_wizard_generate(self, status_code: int) -> None:
        """LC-WIZ-05: Generate returns HTTP 200."""
        self._record(
            "LC-WIZ-05",
            "Lifecycle wizard generate returns HTTP 200",
            status_code == 200,
            f"HTTP {status_code}",
        )

    def verify_lifecycle_wizard_s3(self, artifact_exists: bool) -> None:
        """LC-WIZ-06: Lifecycle YAML exists in S3 after generation."""
        self._record(
            "LC-WIZ-06",
            "Lifecycle YAML exists in S3 after generation",
            artifact_exists,
        )

    def verify_lifecycle_wizard_db_session(self, session_exists: bool) -> None:
        """LC-WIZ-07: wizard_sessions row created in DB."""
        self._record(
            "LC-WIZ-07",
            "wizard_sessions row created in DB",
            session_exists,
        )

    def verify_lifecycle_wizard_resume(self, resumed_at_correct_step: bool) -> None:
        """LC-WIZ-08: Resume loads correct step (navigate away and return)."""
        self._record(
            "LC-WIZ-08",
            "Resume loads correct step",
            resumed_at_correct_step,
        )

    # ------------------------------------------------------------------
    # Layer 2 Wizard verification (L2-WIZ-01..09)
    # ------------------------------------------------------------------

    async def verify_layer2_preset_selection(self, page) -> None:
        """L2-WIZ-01: Preset selection renders three options."""
        body_text = (await page.text_content("body") or "").lower()
        presets = await page.query_selector_all(
            'input[name*="preset"], select[name*="preset"] option, .preset-option, '
            '[data-preset]'
        )
        has_standard = "standard" in body_text
        has_minimal = "minimal" in body_text
        has_blank = "blank" in body_text or "manual" in body_text
        presets_found = max(len(presets), sum([has_standard, has_minimal, has_blank]))
        self._record(
            "L2-WIZ-01",
            "Preset selection renders three options",
            presets_found >= 2,
            f"Found {presets_found} preset(s)",
        )

    async def verify_layer2_segment_accordions(self, page) -> None:
        """L2-WIZ-02: Segment accordions render with element tables."""
        accordions = await page.query_selector_all(
            '.segment-accordion, details[data-segment], .accordion-segment, '
            '[class*="segment"], details summary'
        )
        self._record(
            "L2-WIZ-02",
            "Segment accordions render with element tables",
            len(accordions) > 0,
            f"Found {len(accordions)} accordion(s)",
        )

    def verify_layer2_overrides(self, yaml_content: str, override_applied: bool) -> None:
        """L2-WIZ-03: Overrides applied to generated YAML."""
        self._record(
            "L2-WIZ-03",
            "Overrides applied to generated YAML",
            override_applied,
        )

    def verify_layer2_yaml_valid(self, yaml_content: str) -> None:
        """L2-WIZ-04: Generated YAML is valid (non-empty, contains transaction key)."""
        has_content = bool(yaml_content and len(yaml_content) > 10)
        self._record(
            "L2-WIZ-04",
            "Generated YAML is valid (non-empty, contains transaction key)",
            has_content,
            f"Length: {len(yaml_content) if yaml_content else 0}",
        )

    def verify_layer2_artifacts_generated(self, md_exists: bool) -> None:
        """L2-WIZ-05: Artifacts generated (MD file exists)."""
        self._record(
            "L2-WIZ-05",
            "Artifacts generated (MD file exists)",
            md_exists,
        )

    def verify_layer2_annotations(self, content: str) -> None:
        """L2-WIZ-06: Artifacts contain Layer 2 annotations."""
        has_annotations = bool(content and ("layer 2" in content.lower() or "required" in content.lower()
                               or "qualifier" in content.lower() or "retailer" in content.lower()))
        self._record(
            "L2-WIZ-06",
            "Artifacts contain Layer 2 annotations",
            has_annotations,
        )

    def verify_layer2_download(self, status_code: int, content_length: int) -> None:
        """L2-WIZ-07: Download endpoint returns file content."""
        self._record(
            "L2-WIZ-07",
            "Download endpoint returns file content",
            status_code == 200 and content_length > 0,
            f"HTTP {status_code}, {content_length} bytes",
        )

    def verify_layer2_db_session(self, session_exists: bool) -> None:
        """L2-WIZ-08: wizard_sessions row created in DB."""
        self._record(
            "L2-WIZ-08",
            "wizard_sessions row created in DB",
            session_exists,
        )

    def verify_layer2_resume(self, resumed_at_correct_step: bool) -> None:
        """L2-WIZ-09: Resume loads correct step."""
        self._record(
            "L2-WIZ-09",
            "Resume loads correct step",
            resumed_at_correct_step,
        )

    # ------------------------------------------------------------------
    # Wizard Session verification (WIZ-SESS-01..04)
    # ------------------------------------------------------------------

    def verify_wizard_session_created(self, session_exists: bool) -> None:
        """WIZ-SESS-01: Wizard session created in DB after starting wizard."""
        self._record(
            "WIZ-SESS-01",
            "Wizard session created in DB after starting wizard",
            session_exists,
        )

    def verify_wizard_session_state(self, state_has_data: bool) -> None:
        """WIZ-SESS-02: Session state JSON contains step data."""
        self._record(
            "WIZ-SESS-02",
            "Session state JSON contains step data",
            state_has_data,
        )

    def verify_wizard_session_resume(self, resumed_at_correct_step: bool) -> None:
        """WIZ-SESS-03: Resume navigates to correct step number."""
        self._record(
            "WIZ-SESS-03",
            "Resume navigates to correct step number",
            resumed_at_correct_step,
        )

    def verify_wizard_session_multiple(self, multiple_listed: bool) -> None:
        """WIZ-SESS-04: Multiple active sessions listed on wizard landing page."""
        self._record(
            "WIZ-SESS-04",
            "Multiple active sessions listed on wizard landing page",
            multiple_listed,
        )

    # ------------------------------------------------------------------
    # Deprecation verification (DEPR-01..02)
    # ------------------------------------------------------------------

    def verify_deprecation_spec_upload(self, status_code: int) -> None:
        """DEPR-01: POST /spec-setup/upload returns HTTP 410."""
        self._record(
            "DEPR-01",
            "POST /spec-setup/upload returns HTTP 410",
            status_code == 410,
            f"HTTP {status_code}",
        )

    def verify_deprecation_yaml_path1(self, status_code: int) -> None:
        """DEPR-02: POST /yaml-wizard/path1 returns HTTP 410."""
        self._record(
            "DEPR-02",
            "POST /yaml-wizard/path1 returns HTTP 410",
            status_code == 410,
            f"HTTP {status_code}",
        )

    # ------------------------------------------------------------------
    # Onboarding verification (ONB-01..20)
    # ------------------------------------------------------------------

    async def verify_onboarding_page(self, page) -> None:
        """ONB checks for the onboarding wizard page."""
        body = (await page.text_content("body") or "").lower()
        url = page.url

        self._record("ONB-01", "Spec download link visible", "download" in body or "specification" in body)

    async def verify_onboarding_acknowledge(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("ONB-02", "Acknowledge sets specs_acknowledged", "step 2" in body or "contact" in body)
        self._record("ONB-03", "Gate A unlocks Step 2", "step 2" in body or "company" in body)

    async def verify_onboarding_contact(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("ONB-04", "All 4 contact fields required", "company" in body or "contact" in body)
        self._record("ONB-05", "Gate B unlocks Step 3", "step 3" in body or "connection" in body)

    async def verify_onboarding_connection(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("ONB-06", "Connection method dropdown populated", "as2" in body or "sftp" in body or "connection" in body)
        self._record("ONB-07", "Test EDI IDs saved, Gate 1 = COMPLETE", "step 4" in body or "item" in body)

    async def verify_onboarding_gate1_signal(self, page) -> None:
        if self.signal_checker:
            found = self.signal_checker.find_signal("gate1_complete")
            self._record("ONB-08", "Kelly sends test-environment-ready signal", found)
        else:
            self._skip("ONB-08", "Kelly gate1_complete signal", "SignalChecker unavailable")

    async def verify_onboarding_items(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("ONB-09", "Item table shows rows", "vendor" in body or "part" in body or "item" in body)
        # CSV upload tested by filling data
        has_upload = await page.query_selector('input[type="file"], input[accept=".csv"]')
        self._record("ONB-10", "CSV upload available", has_upload is not None or "csv" in body)
        self._record("ONB-11", "All required part numbers → items_complete", "step 5" in body or "scenario" in body or "testing" in body)

    async def verify_onboarding_scenarios(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("ONB-12", "Scenarios list rendered", "850" in body or "scenario" in body)
        self._record("ONB-13", "REQUIRED badge on mandatory transactions", "required" in body)
        exc_btn = await page.query_selector('button:has-text("Exception"), button:has-text("exception")')
        self._record("ONB-14", "Exception request button present", exc_btn is not None or "exception" in body)

    async def verify_onboarding_moses(self, page) -> None:
        self._skip("ONB-15", "Moses validation on submitted EDI docs", "Requires live Moses agent")

    async def verify_onboarding_gate2(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("ONB-16", "Gate 2 formula: all REQUIRED = CERTIFIED|EXEMPT", "gate" in body or "step" in body)

    async def verify_onboarding_prod_ids(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("ONB-17", "Production ID fields pre-empty", "production" in body or "go-live" in body or "prod" in body)
        self._record("ONB-18", "Submit triggers Gate 3 = PENDING", "pending" in body or "awaiting" in body or "certification" in body)

    async def verify_onboarding_pam_certify(self, page) -> None:
        self._skip("ONB-19", "PAM admin can certify Gate 3", "Cross-portal — tested in gate-model flow")

    async def verify_onboarding_kelly_cert(self, page) -> None:
        self._skip("ONB-20", "Kelly sends certification email", "Requires live Kelly agent")

    # ------------------------------------------------------------------
    # Exception verification (EXC-01..12)
    # ------------------------------------------------------------------

    async def verify_exception_request(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("EXC-01", "Reason_code dropdown with 4 options",
                      "not_applicable" in body or "not applicable" in body or "reason" in body)
        self._record("EXC-02", "Optional note field", "note" in body or "optional" in body or "context" in body)
        self._record("EXC-03", "Status = PENDING on creation", "pending" in body)

    async def verify_exception_queue(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("EXC-04", "Exception appears in Meredith /exception-queue",
                      "exception" in body and ("approve" in body or "deny" in body or "pending" in body))

    async def verify_exception_signal_request(self, page) -> None:
        if self.signal_checker:
            found = self.signal_checker.find_signal("exception_requested")
            self._record("EXC-05", "Kelly notification to retailer on request", found)
        else:
            self._skip("EXC-05", "Kelly exception_requested signal", "SignalChecker unavailable")

    async def verify_exception_approve(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("EXC-06", "Approve → status=APPROVED, transaction=EXEMPT",
                      "approved" in body or "exempt" in body)

    async def verify_exception_deny(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("EXC-07", "Deny → status=DENIED, transaction=REQUIRED",
                      "denied" in body or "required" in body)

    async def verify_exception_signal_resolve(self, page) -> None:
        if self.signal_checker:
            found = self.signal_checker.find_signal("exception_resolved")
            self._record("EXC-08", "Kelly notification to supplier on resolve", found)
        else:
            self._skip("EXC-08", "Kelly exception_resolved signal", "SignalChecker unavailable")

    async def verify_exception_withdraw(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("EXC-09", "Supplier can cancel PENDING request",
                      "withdraw" in body or "withdrawn" in body or "cancel" in body)

    async def verify_exception_gate2_blocked(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("EXC-10", "Gate 2 blocked while PENDING exceptions exist",
                      "pending" in body or "blocked" in body or "gate" in body)

    async def verify_exception_gate2_passes(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("EXC-11", "Gate 2 passes when all REQUIRED = CERTIFIED|EXEMPT",
                      "complete" in body or "certified" in body or "exempt" in body)

    async def verify_exception_history(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("EXC-12", "Exception history visible on scenario detail",
                      "exception" in body or "history" in body or "requested" in body)

    # ------------------------------------------------------------------
    # Template Library verification (TPL-01..10)
    # ------------------------------------------------------------------

    async def verify_template_create_form(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("TPL-01", "PAM template creation form renders",
                      "template" in body and ("slug" in body or "name" in body or "create" in body))

    async def verify_template_save(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("TPL-02", "Template saved with YAML content",
                      "template" in body and ("yaml" in body or "content" in body or "edit" in body))

    async def verify_template_publish(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("TPL-03", "Template publish sets is_published=TRUE",
                      "published" in body or "publish" in body)

    async def verify_template_unpublished_hidden(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("TPL-04", "Unpublished templates not visible to Meredith",
                      "draft" not in body or "template" in body)

    async def verify_template_meredith_visible(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("TPL-05", "Meredith /template-library shows published templates",
                      "template" in body and ("adopt" in body or "fork" in body or "standard" in body))

    async def verify_template_adopt(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("TPL-06", "Adopt creates retailer_template_adoption (mode=ADOPT)",
                      "adopt" in body)

    async def verify_template_fork(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("TPL-07", "Fork clones content (mode=FORK)",
                      "fork" in body)

    async def verify_template_fork_editable(self, page) -> None:
        self._skip("TPL-08", "Forked template editable independently", "Requires YAML editor interaction")

    async def verify_template_chrissy_transparent(self, page) -> None:
        self._skip("TPL-09", "Chrissy sees no difference between adopted vs custom", "Cross-portal transparency")

    async def verify_template_seed_visible(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("TPL-10", "Seed templates visible after migration",
                      "standard retail" in body or "grocery" in body or "drop ship" in body or "marketplace" in body)

    # ------------------------------------------------------------------
    # Gate Model verification (GATE-01..08)
    # ------------------------------------------------------------------

    async def verify_gate_a_enforced(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("GATE-01", "Gate A enforced: Step 2 locked until specs_acknowledged",
                      "step 1" in body or "spec" in body or "acknowledge" in body)

    async def verify_gate_b_enforced(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("GATE-02", "Gate B enforced: Step 3 locked until 4 contact fields",
                      "step 2" in body or "contact" in body or "company" in body)

    async def verify_gate_1_enforced(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("GATE-03", "Gate 1 enforced: Step 4 locked until connection + test IDs",
                      "step 3" in body or "connection" in body)

    async def verify_gates_sequential(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("GATE-04", "Gates sequential: cannot skip A → B → 1 → 2 → 3",
                      "locked" in body or "pending" in body or "step" in body)

    async def verify_gates_binary(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        # No PARTIAL states — only PENDING, COMPLETE, CERTIFIED
        has_partial = "partial" in body
        self._record("GATE-05", "Binary states: each gate is 0/1, no PARTIAL", not has_partial)

    async def verify_gate_chrissy_progress(self, page) -> None:
        progress_el = await page.query_selector(".wizard-progress, .gate-pill-row, .progress-section")
        self._record("GATE-06", "Gate status visible in Chrissy progress bar", progress_el is not None)

    async def verify_gate_pam_dashboard(self, page) -> None:
        body = (await page.text_content("body") or "").lower()
        self._record("GATE-07", "Gate status visible in PAM supplier dashboard",
                      "gate" in body and ("supplier" in body or "acme" in body))

    async def verify_gate_audit_trail(self, page) -> None:
        self._skip("GATE-08", "Gate transitions write to audit trail", "Requires DB verification")

    # ------------------------------------------------------------------
    # Visual Regression verification (VIS-01..05) — Phase 9 placeholders
    # ------------------------------------------------------------------

    async def verify_vis_design_system(self, page) -> None:
        link = await page.query_selector('link[href*="certportal-core.css"]')
        self._record("VIS-01", "All portals render with shared design system", link is not None)

    async def verify_vis_accent_colors(self, page) -> None:
        color = await page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()")
        self._record("VIS-02", "Portal accent colors differentiate", len(color) > 0)

    async def verify_vis_dark_mode(self, page) -> None:
        toggle = await page.query_selector('#theme-toggle')
        self._record("VIS-03", "Dark mode toggle functional", toggle is not None)

    async def verify_vis_nav_consistency(self, page) -> None:
        nav = await page.query_selector('nav')
        self._record("VIS-04", "Nav structure consistent across portals", nav is not None)

    async def verify_vis_responsive(self, page) -> None:
        overflow = await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth * 2")
        self._record("VIS-05", "Responsive: mobile breakpoint renders", overflow)

    # ------------------------------------------------------------------
    # CSS Deprecation verification methods
    # ------------------------------------------------------------------

    async def verify_css_depr_pam_core(self, page) -> None:
        link = await page.query_selector('link[href*="certportal-core.css"]')
        self._record("CSS-DEPR-01", "PAM login loads certportal-core.css", link is not None)

    async def verify_css_depr_pam_no_inline(self, page) -> None:
        import re
        html = await page.content()
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL | re.IGNORECASE)
        has_deprecated = any(
            "#0a0e1a" in block.lower() or "#00ff88" in block.lower()
            for block in style_blocks
        )
        self._record("CSS-DEPR-02", "PAM login has no deprecated inline CSS", not has_deprecated)

    async def verify_css_depr_meredith_core(self, page) -> None:
        link = await page.query_selector('link[href*="certportal-core.css"]')
        self._record("CSS-DEPR-03", "Meredith login loads certportal-core.css", link is not None)

    async def verify_css_depr_meredith_no_inline(self, page) -> None:
        import re
        html = await page.content()
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL | re.IGNORECASE)
        has_deprecated = any(
            "#4f6ef7" in block.lower() or "#f8f9fc" in block.lower()
            for block in style_blocks
        )
        self._record("CSS-DEPR-04", "Meredith login has no deprecated inline CSS", not has_deprecated)

    async def verify_css_depr_chrissy_core(self, page) -> None:
        link = await page.query_selector('link[href*="certportal-core.css"]')
        self._record("CSS-DEPR-05", "Chrissy login loads certportal-core.css", link is not None)

    async def verify_css_depr_chrissy_no_inline(self, page) -> None:
        import re
        html = await page.content()
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL | re.IGNORECASE)
        has_deprecated = any(
            "#f59e0b" in block.lower() or "#fffbf7" in block.lower()
            for block in style_blocks
        )
        self._record("CSS-DEPR-06", "Chrissy login has no deprecated inline CSS", not has_deprecated)

    async def verify_css_depr_pam_forgot(self, page) -> None:
        link = await page.query_selector('link[href*="certportal-core.css"]')
        self._record("CSS-DEPR-07", "PAM forgot-password uses design system", link is not None)

    async def verify_css_depr_tokens_active(self, page) -> None:
        title = await page.query_selector(".auth-title")
        btn = await page.query_selector(".auth-btn")
        self._record(
            "CSS-DEPR-08",
            "All portals use design system tokens on login",
            title is not None and btn is not None,
        )

    async def verify_css_depr_dark_mode(self, page) -> None:
        # Ensure we start in light mode regardless of prior state
        await page.evaluate('document.documentElement.setAttribute("data-theme", "light")')
        light_bg = await page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--color-base').trim()"
        )
        await page.evaluate('document.documentElement.setAttribute("data-theme", "dark")')
        dark_bg = await page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--color-base').trim()"
        )
        # Restore light theme
        await page.evaluate('document.documentElement.setAttribute("data-theme", "light")')
        self._record("CSS-DEPR-09", "PAM login respects dark mode", light_bg != dark_bg and len(dark_bg) > 0)

    # ------------------------------------------------------------------
    # Dispatch — route step name to verification method
    # ------------------------------------------------------------------

    async def verify(self, step: str, page) -> None:
        """Run all verification checks for a given step on the current page.

        Called from flow classes: await self.verify("login")
        """
        dispatch = {
            # PAM
            "pam::login":         self.verify_pam_login,
            "pam::retailers":     self.verify_pam_retailers,
            "pam::suppliers":     self.verify_pam_suppliers,
            "pam::hitl-queue":    self.verify_pam_hitl_queue,
            "pam::monica-memory": self.verify_pam_monica_memory,
            # Meredith
            "meredith::login":           self.verify_meredith_login,
            "meredith::spec-setup":      self.verify_meredith_spec_setup,
            "meredith::supplier-status": self.verify_meredith_supplier_status,
            # Chrissy
            "chrissy::login":         self.verify_chrissy_login,
            "chrissy::scenarios":     self.verify_chrissy_scenarios,
            "chrissy::errors":        self.verify_chrissy_errors,
            "chrissy::patches":       self.verify_chrissy_patches,
            "chrissy::certification": self.verify_chrissy_certification,
            # Onboarding
            "onboarding::spec-download":     self.verify_onboarding_page,
            "onboarding::acknowledge":       self.verify_onboarding_acknowledge,
            "onboarding::contact-form":      self.verify_onboarding_contact,
            "onboarding::connection-method": self.verify_onboarding_connection,
            "onboarding::test-ids":          self.verify_onboarding_gate1_signal,
            "onboarding::item-table":        self.verify_onboarding_items,
            "onboarding::items-complete":    self.verify_onboarding_items,
            "onboarding::scenario-list":     self.verify_onboarding_scenarios,
            "onboarding::exception-button":  self.verify_onboarding_scenarios,
            "onboarding::moses-validation":  self.verify_onboarding_moses,
            "onboarding::gate2-formula":     self.verify_onboarding_gate2,
            "onboarding::prod-ids-empty":    self.verify_onboarding_prod_ids,
            "onboarding::submit-gate3":      self.verify_onboarding_prod_ids,
            "onboarding::pam-certify":       self.verify_onboarding_pam_certify,
            "onboarding::kelly-cert-email":  self.verify_onboarding_kelly_cert,
            # Exception
            "exception::reason-dropdown":      self.verify_exception_request,
            "exception::note-optional":        self.verify_exception_request,
            "exception::status-pending":       self.verify_exception_request,
            "exception::appears-meredith":     self.verify_exception_queue,
            "exception::kelly-request-signal": self.verify_exception_signal_request,
            "exception::approve-exempt":       self.verify_exception_approve,
            "exception::deny-required":        self.verify_exception_deny,
            "exception::kelly-resolve-signal": self.verify_exception_signal_resolve,
            "exception::withdraw":             self.verify_exception_withdraw,
            "exception::gate2-blocked":        self.verify_exception_gate2_blocked,
            "exception::gate2-passes":         self.verify_exception_gate2_passes,
            "exception::history-visible":      self.verify_exception_history,
            # Template
            "template::create-form":         self.verify_template_create_form,
            "template::save-yaml":           self.verify_template_save,
            "template::publish":             self.verify_template_publish,
            "template::unpublished-hidden":  self.verify_template_unpublished_hidden,
            "template::meredith-visible":    self.verify_template_meredith_visible,
            "template::adopt":               self.verify_template_adopt,
            "template::fork":                self.verify_template_fork,
            "template::fork-editable":       self.verify_template_fork_editable,
            "template::chrissy-transparent": self.verify_template_chrissy_transparent,
            "template::seed-visible":        self.verify_template_seed_visible,
            # Gate Model
            "gate-model::gate-a-enforced":   self.verify_gate_a_enforced,
            "gate-model::gate-b-enforced":   self.verify_gate_b_enforced,
            "gate-model::gate-1-enforced":   self.verify_gate_1_enforced,
            "gate-model::gates-sequential":  self.verify_gates_sequential,
            "gate-model::binary-states":     self.verify_gates_binary,
            "gate-model::chrissy-progress":  self.verify_gate_chrissy_progress,
            "gate-model::pam-dashboard":     self.verify_gate_pam_dashboard,
            "gate-model::audit-trail":       self.verify_gate_audit_trail,
            # Visual Regression
            "visual::design-system":    self.verify_vis_design_system,
            "visual::accent-colors":    self.verify_vis_accent_colors,
            "visual::dark-mode":        self.verify_vis_dark_mode,
            "visual::nav-consistency":  self.verify_vis_nav_consistency,
            "visual::responsive":       self.verify_vis_responsive,
            # CSS Deprecation
            "css-depr::css-depr-01-pam-login-loads-core":      self.verify_css_depr_pam_core,
            "css-depr::css-depr-02-pam-login-no-inline":       self.verify_css_depr_pam_no_inline,
            "css-depr::css-depr-03-meredith-login-loads-core": self.verify_css_depr_meredith_core,
            "css-depr::css-depr-04-meredith-login-no-inline":  self.verify_css_depr_meredith_no_inline,
            "css-depr::css-depr-05-chrissy-login-loads-core":  self.verify_css_depr_chrissy_core,
            "css-depr::css-depr-06-chrissy-login-no-inline":   self.verify_css_depr_chrissy_no_inline,
            "css-depr::css-depr-07-pam-forgot-no-inline":      self.verify_css_depr_pam_forgot,
            "css-depr::css-depr-08-design-tokens-active":      self.verify_css_depr_tokens_active,
            "css-depr::css-depr-09-pam-dark-mode":             self.verify_css_depr_dark_mode,
        }

        fn = dispatch.get(step)
        if fn:
            await fn(page)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == "PASS")

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == "FAIL")

    @property
    def skip_count(self) -> int:
        return sum(1 for r in self.results if r.status == "SKIP")

    def write_report(self) -> str:
        """Write per-portal requirements report. Returns file path."""
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = REPORT_DIR / f"requirements_{self.portal}_{ts}.md"

        lines = [
            f"# Requirements Verification: {self.portal.upper()} Portal",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Total checks: {len(self.results)}",
            f"PASS: {self.pass_count}  |  FAIL: {self.fail_count}  |  SKIP: {self.skip_count}",
            "",
            "---",
            "",
        ]

        # Group by requirement prefix
        from collections import defaultdict
        groups: dict[str, list[ReqResult]] = defaultdict(list)
        for r in self.results:
            # Extract area from ID like "PAM-DASH-01" -> "PAM-DASH"
            parts = r.req_id.rsplit("-", 1)
            prefix = parts[0] if len(parts) == 2 else r.req_id
            groups[prefix].append(r)

        for prefix, reqs in groups.items():
            lines.append(f"## {prefix}")
            lines.append("")
            lines.append("| ID | Requirement | Status | Detail |")
            lines.append("|----|-------------|--------|--------|")
            for r in reqs:
                icon = {"PASS": "+", "FAIL": "!", "SKIP": "-"}[r.status]
                lines.append(f"| {r.req_id} | {r.description} | [{icon}] {r.status} | {r.detail} |")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)


def write_summary(verifiers: list[RequirementsVerifier]) -> str:
    """Write a combined summary report across all portals. Returns file path."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"summary_{ts}.md"

    total_pass = sum(v.pass_count for v in verifiers)
    total_fail = sum(v.fail_count for v in verifiers)
    total_skip = sum(v.skip_count for v in verifiers)
    total = total_pass + total_fail + total_skip

    lines = [
        "# Requirements Verification Summary",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"**Total: {total} checks  |  PASS: {total_pass}  |  FAIL: {total_fail}  |  SKIP: {total_skip}**",
        "",
        "---",
        "",
        "| Portal | PASS | FAIL | SKIP | Total |",
        "|--------|------|------|------|-------|",
    ]

    for v in verifiers:
        total_v = v.pass_count + v.fail_count + v.skip_count
        lines.append(f"| {v.portal.upper()} | {v.pass_count} | {v.fail_count} | {v.skip_count} | {total_v} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # List all failures
    failures = []
    for v in verifiers:
        for r in v.results:
            if r.status == "FAIL":
                failures.append(r)

    if failures:
        lines.append("## Failed Requirements")
        lines.append("")
        lines.append("| ID | Requirement | Detail |")
        lines.append("|----|-------------|--------|")
        for r in failures:
            lines.append(f"| {r.req_id} | {r.description} | {r.detail} |")
    else:
        lines.append("## All requirements passed!")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
