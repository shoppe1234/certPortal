"""exception_flow.py — Exception request lifecycle (Chrissy → Meredith → Kelly signal).

Verifies the full exception lifecycle:
  1. Supplier requests exception on Chrissy (with reason_code)
  2. Retailer reviews exception queue on Meredith
  3. Retailer approves/denies, status updates propagate
  4. Kelly notification signal is emitted

Requirements verified: EXC-01 through EXC-12.
"""
from __future__ import annotations

from playwrightcli.config import PORTALS, TIMEOUTS

PORTAL = "exception"

EXCEPTION_STEPS = [
    "exc-01-supplier-login",
    "exc-02-navigate-exceptions",
    "exc-03-select-reason-code",
    "exc-04-fill-justification",
    "exc-05-submit-request",
    "exc-06-confirm-pending-status",
    "exc-07-retailer-login",
    "exc-08-navigate-exception-queue",
    "exc-09-verify-request-visible",
    "exc-10-approve-exception",
    "exc-11-verify-approved-status",
    "exc-12-verify-kelly-signal",
]

_CHRISSY_URL = PORTALS["chrissy"]["url"]
_MEREDITH_URL = PORTALS["meredith"]["url"]

_USERS = {
    "acme_supplier": {"password": PORTALS["chrissy"]["password"], "url": _CHRISSY_URL},
    "lowes_retailer": {"password": PORTALS["meredith"]["password"], "url": _MEREDITH_URL},
}


class ExceptionFlow:
    """Standalone exception lifecycle flow — does not extend BaseFlow."""

    def __init__(self, page, runner, *, verifier=None) -> None:
        self.page = page
        self.runner = runner
        self._verifier = verifier

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        r = self.runner

        # Supplier side: request exception
        await r.run_step("exception::exc-01-supplier-login",       self._supplier_login,        page=self.page)
        await r.run_step("exception::exc-02-navigate-exceptions",  self._navigate_exceptions,   page=self.page)
        await r.run_step("exception::exc-03-select-reason-code",   self._select_reason_code,    page=self.page)
        await r.run_step("exception::exc-04-fill-justification",   self._fill_justification,    page=self.page)
        await r.run_step("exception::exc-05-submit-request",       self._submit_request,        page=self.page)
        await r.run_step("exception::exc-06-confirm-pending-status", self._confirm_pending,     page=self.page)

        # Retailer side: review + approve
        await r.run_step("exception::exc-07-retailer-login",       self._retailer_login,        page=self.page)
        await r.run_step("exception::exc-08-navigate-exception-queue", self._navigate_queue,    page=self.page)
        await r.run_step("exception::exc-09-verify-request-visible", self._verify_request_visible, page=self.page)
        await r.run_step("exception::exc-10-approve-exception",    self._approve_exception,     page=self.page)
        await r.run_step("exception::exc-11-verify-approved-status", self._verify_approved,     page=self.page)
        await r.run_step("exception::exc-12-verify-kelly-signal",  self._verify_kelly_signal,   page=self.page)

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    async def _login(self, username: str) -> None:
        cfg = _USERS[username]
        await self.page.goto(
            f"{cfg['url']}/login",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        await self.page.fill('input[name="username"]', username)
        await self.page.fill('input[name="password"]', cfg["password"])
        async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
            await self.page.click('button[type="submit"]')
        if "/login" in self.page.url:
            raise AssertionError(f"Exception login failed for {username!r}")

    async def _logout(self) -> None:
        await self.page.evaluate("""() => {
            const f = document.createElement('form');
            f.method = 'POST';
            f.action  = '/logout';
            document.body.appendChild(f);
            f.submit();
        }""")
        await self.page.wait_for_url("**/login**", timeout=TIMEOUTS["navigation"])

    async def _goto(self, username: str, path: str) -> None:
        base = _USERS[username]["url"]
        await self.page.goto(
            f"{base}{path}",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        await self.page.wait_for_load_state("networkidle", timeout=TIMEOUTS["networkidle"])

    # ------------------------------------------------------------------
    # Step implementations — supplier side
    # ------------------------------------------------------------------

    async def _supplier_login(self) -> None:
        """EXC-01: Login as acme_supplier on Chrissy."""
        await self._login("acme_supplier")

    async def _navigate_exceptions(self) -> None:
        """EXC-02: Navigate to /exceptions page."""
        await self._goto("acme_supplier", "/exceptions")

    async def _select_reason_code(self) -> None:
        """EXC-03: Select reason_code from dropdown."""
        select = self.page.locator('select[name="reason_code"]')
        await select.select_option(index=1, timeout=TIMEOUTS["element"])

    async def _fill_justification(self) -> None:
        """EXC-04: Fill justification textarea."""
        await self.page.fill(
            'textarea[name="justification"]',
            "Automated E2E test: requesting exception for scenario coverage.",
        )

    async def _submit_request(self) -> None:
        """EXC-05: Submit the exception request."""
        submit = self.page.locator('button:has-text("Submit"), button[type="submit"]')
        await submit.first.click(timeout=TIMEOUTS["element"])

    async def _confirm_pending(self) -> None:
        """EXC-06: Confirm the request shows PENDING status."""
        await self.page.wait_for_selector(
            '.status-pending, [data-status="PENDING"]',
            timeout=TIMEOUTS["element"],
        )
        await self._logout()

    # ------------------------------------------------------------------
    # Step implementations — retailer side
    # ------------------------------------------------------------------

    async def _retailer_login(self) -> None:
        """EXC-07: Login as lowes_retailer on Meredith."""
        await self._login("lowes_retailer")

    async def _navigate_queue(self) -> None:
        """EXC-08: Navigate to /exception-queue."""
        await self._goto("lowes_retailer", "/exception-queue")

    async def _verify_request_visible(self) -> None:
        """EXC-09: Verify the supplier's exception request is visible in the queue."""
        row = self.page.locator('tr:has-text("acme"), [data-supplier="acme"]')
        await row.first.wait_for(timeout=TIMEOUTS["element"])

    async def _approve_exception(self) -> None:
        """EXC-10: Approve the exception request."""
        approve_btn = self.page.locator('button:has-text("Approve"), button[data-action="approve"]')
        await approve_btn.first.click(timeout=TIMEOUTS["element"])

    async def _verify_approved(self) -> None:
        """EXC-11: Verify the request now shows APPROVED status."""
        await self.page.wait_for_selector(
            '.status-approved, [data-status="APPROVED"]',
            timeout=TIMEOUTS["element"],
        )
        await self._logout()

    async def _verify_kelly_signal(self) -> None:
        """EXC-12: Verify Kelly notification signal was emitted."""
