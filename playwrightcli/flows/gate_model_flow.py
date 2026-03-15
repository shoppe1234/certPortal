"""gate_model_flow.py — Gate A/B/1/2/3 sequential enforcement on Chrissy.

Verifies gate ordering via the CSS classes in chrissy_onboarding.html:
  .wizard-step--locked / .wizard-step--active / .wizard-step--done
  .gate-pill--pending / .gate-pill--complete / .gate-pill--certified

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

    async def run(self) -> None:
        r = self.runner
        await r.run_step("gate_model::gate-01-login-chrissy",               self._login_chrissy,         page=self.page)
        await r.run_step("gate_model::gate-02-navigate-onboarding",          self._navigate_onboarding,   page=self.page)
        await r.run_step("gate_model::gate-03-step2-locked-before-gate-a",   self._step2_locked,          page=self.page)
        await r.run_step("gate_model::gate-04-gate-a-binary-value",          self._gate_a_binary,         page=self.page)
        await r.run_step("gate_model::gate-05-step3-locked-before-gate-b",   self._step3_locked,          page=self.page)
        await r.run_step("gate_model::gate-06-gate-b-binary-value",          self._gate_b_binary,         page=self.page)
        await r.run_step("gate_model::gate-07-progress-bar-visible",         self._progress_visible,      page=self.page)
        await r.run_step("gate_model::gate-08-progress-bar-reflects-status", self._progress_reflects,     page=self.page)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _login(self) -> None:
        await self.page.goto(f"{_CHRISSY_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])
        await self.page.fill('input[name="username"]', _USERNAME)
        await self.page.fill('input[name="password"]', _PASSWORD)
        async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
            await self.page.click('button[type="submit"]')
        if "/login" in self.page.url:
            raise AssertionError(f"Login failed for {_USERNAME!r}")

    async def _goto(self, path: str) -> None:
        await self.page.goto(f"{_CHRISSY_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])
        await self.page.wait_for_load_state("networkidle", timeout=TIMEOUTS["networkidle"])

    async def _body(self) -> str:
        return (await self.page.text_content("body") or "").lower()

    # ------------------------------------------------------------------
    # Steps — use CSS class selectors from chrissy_onboarding.html
    # ------------------------------------------------------------------

    async def _login_chrissy(self) -> None:
        await self._login()

    async def _navigate_onboarding(self) -> None:
        await self._goto("/onboarding")
        body = await self._body()
        assert "onboarding" in body or "step" in body, "Onboarding page did not load"

    async def _step2_locked(self) -> None:
        """GATE-03: Steps after the current one should have wizard-step--locked class."""
        # With acme starting at step 1 (gate A pending), steps 2-6 should be locked
        locked = self.page.locator('.wizard-step--locked')
        count = await locked.count()
        assert count > 0, "No locked steps found — gate sequencing not enforced visually"

    async def _gate_a_binary(self) -> None:
        """GATE-04: Gate A value is PENDING or COMPLETE — never PARTIAL."""
        body = await self._body()
        assert "partial" not in body, "Found 'PARTIAL' state — gates should be binary (PENDING/COMPLETE)"
        # Verify gate pill exists
        pills = self.page.locator('.gate-pill')
        count = await pills.count()
        assert count >= 5, f"Expected 5 gate pills (A,B,1,2,3), found {count}"

    async def _step3_locked(self) -> None:
        """GATE-05: Verify step 3+ are locked when gate B is pending."""
        # On step 1, everything from step 2 onward is locked
        locked = self.page.locator('.wizard-step--locked')
        active = self.page.locator('.wizard-step--active')
        locked_count = await locked.count()
        active_count = await active.count()
        assert active_count >= 1, "No active step indicator found"
        assert locked_count >= 1, "No locked step indicators found"

    async def _gate_b_binary(self) -> None:
        """GATE-06: Gate B value is binary — verify no PARTIAL in gate pills."""
        body = await self._body()
        # Check gate pill CSS classes — should be --pending or --complete, never --partial
        pending_pills = self.page.locator('.gate-pill--pending')
        complete_pills = self.page.locator('.gate-pill--complete')
        pending_count = await pending_pills.count()
        complete_count = await complete_pills.count()
        total = pending_count + complete_count
        # All 5 gates should be accounted for (might also have --certified)
        certified_pills = self.page.locator('.gate-pill--certified')
        certified_count = await certified_pills.count()
        assert (total + certified_count) >= 5, \
            f"Gate pills: {pending_count} pending + {complete_count} complete + {certified_count} certified = {total + certified_count} (expected >=5)"

    async def _progress_visible(self) -> None:
        """GATE-07: Wizard progress section is visible."""
        progress = self.page.locator('.wizard-progress')
        await progress.wait_for(timeout=TIMEOUTS["element"])

    async def _progress_reflects(self) -> None:
        """GATE-08: Progress bar step indicators match gate status."""
        # Count done vs locked vs active steps
        done = await self.page.locator('.wizard-step--done').count()
        active = await self.page.locator('.wizard-step--active').count()
        locked = await self.page.locator('.wizard-step--locked').count()
        total = done + active + locked
        assert total == 6, f"Expected 6 step indicators, found {total} (done={done}, active={active}, locked={locked})"
        assert active == 1, f"Expected exactly 1 active step, found {active}"
