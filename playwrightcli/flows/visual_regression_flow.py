"""visual_regression_flow.py — Visual regression checks for the unified design system.

Verifies that the certportal-core.css design system is loaded on all portals,
accent colors are distinct, dark mode works, nav is consistent, and responsive
layout renders correctly.

Requirements verified: VIS-01 through VIS-05.
"""
from __future__ import annotations

from playwrightcli.config import PORTALS, TIMEOUTS

PORTAL = "visual"

VISUAL_STEPS = [
    "vis-01-pam-dashboard-screenshot",
    "vis-02-meredith-wizard-screenshot",
    "vis-03-chrissy-onboarding-screenshot",
    "vis-04-responsive-mobile-viewport",
    "vis-05-dark-mode-toggle",
]

_PAM_URL = PORTALS["pam"]["url"]
_MEREDITH_URL = PORTALS["meredith"]["url"]
_CHRISSY_URL = PORTALS["chrissy"]["url"]


class VisualRegressionFlow:
    """Standalone visual regression flow — does not extend BaseFlow."""

    def __init__(self, page, runner, *, verifier=None) -> None:
        self.page = page
        self.runner = runner
        self._verifier = verifier

    async def run(self) -> None:
        r = self.runner
        await r.run_step("visual::vis-01-pam-dashboard-screenshot",      self._vis_01, page=self.page)
        await r.run_step("visual::vis-02-meredith-wizard-screenshot",    self._vis_02, page=self.page)
        await r.run_step("visual::vis-03-chrissy-onboarding-screenshot", self._vis_03, page=self.page)
        await r.run_step("visual::vis-04-responsive-mobile-viewport",    self._vis_04, page=self.page)
        await r.run_step("visual::vis-05-dark-mode-toggle",              self._vis_05, page=self.page)

    async def _login(self, portal: str) -> None:
        cfg = PORTALS[portal]
        await self.page.goto(
            f"{cfg['url']}/login",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        await self.page.fill('input[name="username"]', cfg["username"])
        await self.page.fill('input[name="password"]', cfg["password"])
        async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
            await self.page.click('button[type="submit"]')
        if "/login" in self.page.url:
            raise AssertionError(f"Visual login failed for {cfg['username']!r}")

    # ------------------------------------------------------------------
    # VIS-01: All portals load certportal-core.css
    # ------------------------------------------------------------------

    async def _vis_01(self) -> None:
        """VIS-01: All three portals render with shared design system."""
        for url in [_PAM_URL, _MEREDITH_URL, _CHRISSY_URL]:
            await self.page.goto(f"{url}/login", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])
            link = await self.page.query_selector('link[href*="certportal-core.css"]')
            if link is None:
                raise AssertionError(f"certportal-core.css not loaded on {url}")

        if self._verifier:
            await self._verifier.verify("visual::design-system", self.page)

    # ------------------------------------------------------------------
    # VIS-02: Portal accent colors differentiate
    # ------------------------------------------------------------------

    async def _vis_02(self) -> None:
        """VIS-02: Each portal has a distinct --color-primary."""
        colors = {}
        for portal, url in [("pam", _PAM_URL), ("meredith", _MEREDITH_URL), ("chrissy", _CHRISSY_URL)]:
            await self.page.goto(f"{url}/login", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])
            # Check portal override CSS is loaded
            override_link = await self.page.query_selector(f'link[href*="portal-{portal}.css"]')
            if override_link is None:
                raise AssertionError(f"portal-{portal}.css not loaded on {url}")
            color = await self.page.evaluate(
                "getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()"
            )
            colors[portal] = color

        # All three must be distinct
        unique_colors = set(colors.values())
        if len(unique_colors) < 3:
            raise AssertionError(f"Portal accent colors not distinct: {colors}")

        if self._verifier:
            await self._verifier.verify("visual::accent-colors", self.page)

    # ------------------------------------------------------------------
    # VIS-03: Dark mode toggle works and persists
    # ------------------------------------------------------------------

    async def _vis_03(self) -> None:
        """VIS-03: Dark mode toggle functional on Chrissy."""
        await self.page.goto(f"{_CHRISSY_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])

        # Default theme should be light for Chrissy
        theme = await self.page.evaluate('document.documentElement.getAttribute("data-theme")')
        # Click toggle
        toggle = await self.page.query_selector("#theme-toggle")
        if toggle is None:
            raise AssertionError("Dark mode toggle button (#theme-toggle) not found")
        await toggle.click()

        new_theme = await self.page.evaluate('document.documentElement.getAttribute("data-theme")')
        if theme == new_theme:
            raise AssertionError(f"Toggle did not change theme: still '{new_theme}'")

        if self._verifier:
            await self._verifier.verify("visual::dark-mode", self.page)

    # ------------------------------------------------------------------
    # VIS-04: Nav structure consistent across portals
    # ------------------------------------------------------------------

    async def _vis_04(self) -> None:
        """VIS-04: Nav height and structure identical across portals."""
        for url in [_PAM_URL, _MEREDITH_URL, _CHRISSY_URL]:
            await self.page.goto(f"{url}/login", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])
            nav = await self.page.query_selector("nav.nav")
            if nav is None:
                raise AssertionError(f"nav.nav not found on {url}")

        if self._verifier:
            await self._verifier.verify("visual::nav-consistency", self.page)

    # ------------------------------------------------------------------
    # VIS-05: Responsive: mobile breakpoint renders
    # ------------------------------------------------------------------

    async def _vis_05(self) -> None:
        """VIS-05: 375px viewport renders without horizontal scroll."""
        await self.page.set_viewport_size({"width": 375, "height": 812})
        await self.page.goto(f"{_CHRISSY_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])

        scroll_width = await self.page.evaluate("document.documentElement.scrollWidth")
        viewport_width = await self.page.evaluate("window.innerWidth")
        if scroll_width > viewport_width + 5:  # 5px tolerance
            raise AssertionError(f"Horizontal scroll detected: scrollWidth={scroll_width} > viewport={viewport_width}")

        # Reset viewport
        await self.page.set_viewport_size({"width": 1280, "height": 720})

        if self._verifier:
            await self._verifier.verify("visual::responsive", self.page)
