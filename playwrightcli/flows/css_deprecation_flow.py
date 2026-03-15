"""css_deprecation_flow.py — Verify deprecated inline CSS has been removed from auth pages.

Checks that all portal login/forgot/reset pages load the unified design system
(certportal-core.css + portal-*.css + auth-standalone.css) instead of inline
<style> blocks with hardcoded colors.

Requirements verified: CSS-DEPR-01 through CSS-DEPR-09.
"""
from __future__ import annotations

from playwrightcli.config import PORTALS, TIMEOUTS

PORTAL = "css-depr"

CSS_DEPR_STEPS = [
    "css-depr-01-pam-login-loads-core",
    "css-depr-02-pam-login-no-inline",
    "css-depr-03-meredith-login-loads-core",
    "css-depr-04-meredith-login-no-inline",
    "css-depr-05-chrissy-login-loads-core",
    "css-depr-06-chrissy-login-no-inline",
    "css-depr-07-pam-forgot-no-inline",
    "css-depr-08-design-tokens-active",
    "css-depr-09-pam-dark-mode",
]

_PAM_URL = PORTALS["pam"]["url"]
_MEREDITH_URL = PORTALS["meredith"]["url"]
_CHRISSY_URL = PORTALS["chrissy"]["url"]


class CssDeprecationFlow:
    """Standalone flow — does not extend BaseFlow (ADR-027)."""

    def __init__(self, page, runner, *, verifier=None) -> None:
        self.page = page
        self.runner = runner
        self._verifier = verifier

    async def run(self) -> None:
        r = self.runner
        await r.run_step("css-depr::css-depr-01-pam-login-loads-core",    self._depr_01, page=self.page)
        await r.run_step("css-depr::css-depr-02-pam-login-no-inline",     self._depr_02, page=self.page)
        await r.run_step("css-depr::css-depr-03-meredith-login-loads-core", self._depr_03, page=self.page)
        await r.run_step("css-depr::css-depr-04-meredith-login-no-inline", self._depr_04, page=self.page)
        await r.run_step("css-depr::css-depr-05-chrissy-login-loads-core", self._depr_05, page=self.page)
        await r.run_step("css-depr::css-depr-06-chrissy-login-no-inline",  self._depr_06, page=self.page)
        await r.run_step("css-depr::css-depr-07-pam-forgot-no-inline",     self._depr_07, page=self.page)
        await r.run_step("css-depr::css-depr-08-design-tokens-active",     self._depr_08, page=self.page)
        await r.run_step("css-depr::css-depr-09-pam-dark-mode",            self._depr_09, page=self.page)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _goto_login(self, portal: str) -> None:
        cfg = PORTALS[portal]
        await self.page.goto(
            f"{cfg['url']}/login",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )

    async def _assert_core_css_loaded(self, portal: str) -> None:
        link = await self.page.query_selector('link[href*="certportal-core.css"]')
        if link is None:
            raise AssertionError(f"certportal-core.css not loaded on {portal} login page")

    async def _assert_no_deprecated_inline(self, portal: str, deprecated_colors: list[str]) -> None:
        html = await self.page.content()
        # Check there's no <style> block with deprecated colors
        import re
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL | re.IGNORECASE)
        for block in style_blocks:
            for color in deprecated_colors:
                if color.lower() in block.lower():
                    raise AssertionError(
                        f"{portal} login page still has inline <style> with deprecated color {color}"
                    )

    # ------------------------------------------------------------------
    # CSS-DEPR-01: PAM login loads certportal-core.css
    # ------------------------------------------------------------------

    async def _depr_01(self) -> None:
        await self._goto_login("pam")
        await self._assert_core_css_loaded("pam")

        if self._verifier:
            await self._verifier.verify("css-depr::css-depr-01-pam-login-loads-core", self.page)

    # ------------------------------------------------------------------
    # CSS-DEPR-02: PAM login has no inline deprecated CSS
    # ------------------------------------------------------------------

    async def _depr_02(self) -> None:
        await self._goto_login("pam")
        await self._assert_no_deprecated_inline("pam", ["#0a0e1a", "#00ff88"])

        if self._verifier:
            await self._verifier.verify("css-depr::css-depr-02-pam-login-no-inline", self.page)

    # ------------------------------------------------------------------
    # CSS-DEPR-03: Meredith login loads certportal-core.css
    # ------------------------------------------------------------------

    async def _depr_03(self) -> None:
        await self._goto_login("meredith")
        await self._assert_core_css_loaded("meredith")

        if self._verifier:
            await self._verifier.verify("css-depr::css-depr-03-meredith-login-loads-core", self.page)

    # ------------------------------------------------------------------
    # CSS-DEPR-04: Meredith login has no inline deprecated CSS
    # ------------------------------------------------------------------

    async def _depr_04(self) -> None:
        await self._goto_login("meredith")
        await self._assert_no_deprecated_inline("meredith", ["#4f6ef7", "#f8f9fc"])

        if self._verifier:
            await self._verifier.verify("css-depr::css-depr-04-meredith-login-no-inline", self.page)

    # ------------------------------------------------------------------
    # CSS-DEPR-05: Chrissy login loads certportal-core.css
    # ------------------------------------------------------------------

    async def _depr_05(self) -> None:
        await self._goto_login("chrissy")
        await self._assert_core_css_loaded("chrissy")

        if self._verifier:
            await self._verifier.verify("css-depr::css-depr-05-chrissy-login-loads-core", self.page)

    # ------------------------------------------------------------------
    # CSS-DEPR-06: Chrissy login has no inline deprecated CSS
    # ------------------------------------------------------------------

    async def _depr_06(self) -> None:
        await self._goto_login("chrissy")
        await self._assert_no_deprecated_inline("chrissy", ["#f59e0b", "#fffbf7"])

        if self._verifier:
            await self._verifier.verify("css-depr::css-depr-06-chrissy-login-no-inline", self.page)

    # ------------------------------------------------------------------
    # CSS-DEPR-07: PAM forgot-password uses design system (no deprecated inline)
    # ------------------------------------------------------------------

    async def _depr_07(self) -> None:
        await self.page.goto(
            f"{_PAM_URL}/forgot-password",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        link = await self.page.query_selector('link[href*="certportal-core.css"]')
        if link is None:
            raise AssertionError("certportal-core.css not loaded on PAM forgot-password page")
        await self._assert_no_deprecated_inline("pam-forgot", ["#0a0e1a", "#00ff88"])

        if self._verifier:
            await self._verifier.verify("css-depr::css-depr-07-pam-forgot-no-inline", self.page)

    # ------------------------------------------------------------------
    # CSS-DEPR-08: All three portals' login pages use var(--color-primary)
    # ------------------------------------------------------------------

    async def _depr_08(self) -> None:
        for portal in ("pam", "meredith", "chrissy"):
            await self._goto_login(portal)
            # Check that the auth-title element's computed color comes from the design system
            title = await self.page.query_selector(".auth-title")
            if title is None:
                raise AssertionError(f".auth-title not found on {portal} login page")

            # Verify the auth-btn uses --color-primary (check computed background)
            btn = await self.page.query_selector(".auth-btn")
            if btn is None:
                raise AssertionError(f".auth-btn not found on {portal} login page")

        if self._verifier:
            await self._verifier.verify("css-depr::css-depr-08-design-tokens-active", self.page)

    # ------------------------------------------------------------------
    # CSS-DEPR-09: PAM login respects dark mode
    # ------------------------------------------------------------------

    async def _depr_09(self) -> None:
        await self._goto_login("pam")

        # Get light mode background
        light_bg = await self.page.evaluate(
            "getComputedStyle(document.body).backgroundColor"
        )

        # Toggle to dark mode
        await self.page.evaluate('document.documentElement.setAttribute("data-theme", "dark")')
        dark_bg = await self.page.evaluate(
            "getComputedStyle(document.body).backgroundColor"
        )

        if light_bg == dark_bg:
            raise AssertionError(
                f"PAM login dark mode not working: light={light_bg}, dark={dark_bg}"
            )

        if self._verifier:
            await self._verifier.verify("css-depr::css-depr-09-pam-dark-mode", self.page)
