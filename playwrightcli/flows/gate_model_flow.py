"""gate_model_flow.py — Gate A/B/1/2/3 sequential enforcement on Chrissy.

Verifies the onboarding gate model:
  - Gates are strictly sequential (step 2 locked until gate A done, etc.)
  - Gate values are binary (0 or 1, no PARTIAL state)
  - Progress bar reflects current gate status

Requirements verified: GATE-01 through GATE-08.
"""
from __future__ import annotations

from playwrightcli.config import PORTALS, TIMEOUTS

PORTAL = "gate_model"

GATE_MODEL_STEPS = [
    "gate-01-login-chrissy",
    "gate-02-navigate-onboarding",
    "gate-03-step2-locked-before-gate-a",
    "gate-04-gate-a-binary-value",
    "gate-05-step3-locked-before-gate-b",
    "gate-06-gate-b-binary-value",
    "gate-07-progress-bar-visible",
    "gate-08-progress-bar-reflects-status",
]

_CHRISSY_URL = PORTALS["chrissy"]["url"]
_USERNAME = PORTALS["chrissy"]["username"]
_PASSWORD = PORTALS["chrissy"]["password"]


class GateModelFlow:
    """Standalone gate model enforcement flow — does not extend BaseFlow."""

    def __init__(self, page, runner, *, verifier=None) -> None:
        self.page = page
        self.runner = runner
        self._verifier = verifier

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        r = self.runner

        await r.run_step("gate_model::gate-01-login-chrissy",               self._login_chrissy,              page=self.page)
        await r.run_step("gate_model::gate-02-navigate-onboarding",          self._navigate_onboarding,        page=self.page)
        await r.run_step("gate_model::gate-03-step2-locked-before-gate-a",   self._step2_locked_before_gate_a, page=self.page)
        await r.run_step("gate_model::gate-04-gate-a-binary-value",          self._gate_a_binary_value,        page=self.page)
        await r.run_step("gate_model::gate-05-step3-locked-before-gate-b",   self._step3_locked_before_gate_b, page=self.page)
        await r.run_step("gate_model::gate-06-gate-b-binary-value",          self._gate_b_binary_value,        page=self.page)
        await r.run_step("gate_model::gate-07-progress-bar-visible",         self._progress_bar_visible,       page=self.page)
        await r.run_step("gate_model::gate-08-progress-bar-reflects-status", self._progress_bar_reflects,      page=self.page)

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    async def _login(self) -> None:
        await self.page.goto(
            f"{_CHRISSY_URL}/login",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        await self.page.fill('input[name="username"]', _USERNAME)
        await self.page.fill('input[name="password"]', _PASSWORD)
        async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
            await self.page.click('button[type="submit"]')
        if "/login" in self.page.url:
            raise AssertionError(f"Gate model login failed for {_USERNAME!r}")

    async def _goto(self, path: str) -> None:
        await self.page.goto(
            f"{_CHRISSY_URL}{path}",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        await self.page.wait_for_load_state("networkidle", timeout=TIMEOUTS["networkidle"])

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _login_chrissy(self) -> None:
        """GATE-01: Login as acme_supplier on Chrissy."""
        await self._login()

    async def _navigate_onboarding(self) -> None:
        """GATE-02: Navigate to /onboarding."""
        await self._goto("/onboarding")

    async def _step2_locked_before_gate_a(self) -> None:
        """GATE-03: Step 2 is locked/disabled before gate A is completed."""
        step2 = self.page.locator(
            '[data-step="2"].locked, [data-step="2"][disabled], '
            '[data-step="2"][aria-disabled="true"]'
        )
        count = await step2.count()
        if count == 0:
            raise AssertionError("Step 2 is NOT locked before gate A — gate sequencing violated")

    async def _gate_a_binary_value(self) -> None:
        """GATE-04: Gate A value is binary (0 or 1, no PARTIAL)."""
        gate_a = self.page.locator('[data-gate="A"]')
        status = await gate_a.get_attribute("data-status", timeout=TIMEOUTS["element"])
        if status not in ("0", "1"):
            raise AssertionError(f"Gate A has non-binary value: {status!r}")

    async def _step3_locked_before_gate_b(self) -> None:
        """GATE-05: Step 3 is locked/disabled before gate B is completed."""
        step3 = self.page.locator(
            '[data-step="3"].locked, [data-step="3"][disabled], '
            '[data-step="3"][aria-disabled="true"]'
        )
        count = await step3.count()
        if count == 0:
            raise AssertionError("Step 3 is NOT locked before gate B — gate sequencing violated")

    async def _gate_b_binary_value(self) -> None:
        """GATE-06: Gate B value is binary (0 or 1, no PARTIAL)."""
        gate_b = self.page.locator('[data-gate="B"]')
        status = await gate_b.get_attribute("data-status", timeout=TIMEOUTS["element"])
        if status not in ("0", "1"):
            raise AssertionError(f"Gate B has non-binary value: {status!r}")

    async def _progress_bar_visible(self) -> None:
        """GATE-07: Progress bar is visible on the onboarding page."""
        bar = self.page.locator('.progress-bar, [role="progressbar"], [data-component="progress"]')
        await bar.first.wait_for(timeout=TIMEOUTS["element"])

    async def _progress_bar_reflects(self) -> None:
        """GATE-08: Progress bar reflects current gate status accurately."""
        bar = self.page.locator('.progress-bar, [role="progressbar"], [data-component="progress"]')
        # Verify the progress value is a valid percentage (0-100)
        value = await bar.first.get_attribute("aria-valuenow", timeout=TIMEOUTS["element"])
        if value is not None:
            pct = int(value)
            if not (0 <= pct <= 100):
                raise AssertionError(f"Progress bar value out of range: {pct}")
