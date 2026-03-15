"""template_flow.py — PAM → Meredith template lifecycle.

Verifies the full template lifecycle:
  1. Admin creates and publishes a template on PAM
  2. Retailer sees published template in library on Meredith
  3. Retailer adopts template, forks template

Requirements verified: TPL-01 through TPL-10.
"""
from __future__ import annotations

from playwrightcli.config import PORTALS, TIMEOUTS

PORTAL = "template"

TEMPLATE_STEPS = [
    "tpl-01-admin-login",
    "tpl-02-navigate-templates-new",
    "tpl-03-fill-template-name",
    "tpl-04-fill-template-body",
    "tpl-05-save-draft",
    "tpl-06-publish-template",
    "tpl-07-retailer-login",
    "tpl-08-verify-template-visible",
    "tpl-09-adopt-template",
    "tpl-10-fork-template",
]

_PAM_URL = PORTALS["pam"]["url"]
_MEREDITH_URL = PORTALS["meredith"]["url"]

_USERS = {
    "pam_admin":       {"password": PORTALS["pam"]["password"],      "url": _PAM_URL},
    "lowes_retailer":  {"password": PORTALS["meredith"]["password"], "url": _MEREDITH_URL},
}


class TemplateFlow:
    """Standalone template lifecycle flow — does not extend BaseFlow."""

    def __init__(self, page, runner, *, verifier=None) -> None:
        self.page = page
        self.runner = runner
        self._verifier = verifier

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        r = self.runner

        # Admin side: create + publish
        await r.run_step("template::tpl-01-admin-login",          self._admin_login,            page=self.page)
        await r.run_step("template::tpl-02-navigate-templates-new", self._navigate_templates_new, page=self.page)
        await r.run_step("template::tpl-03-fill-template-name",   self._fill_template_name,     page=self.page)
        await r.run_step("template::tpl-04-fill-template-body",   self._fill_template_body,     page=self.page)
        await r.run_step("template::tpl-05-save-draft",           self._save_draft,             page=self.page)
        await r.run_step("template::tpl-06-publish-template",     self._publish_template,       page=self.page)

        # Retailer side: view + adopt + fork
        await r.run_step("template::tpl-07-retailer-login",       self._retailer_login,         page=self.page)
        await r.run_step("template::tpl-08-verify-template-visible", self._verify_template_visible, page=self.page)
        await r.run_step("template::tpl-09-adopt-template",       self._adopt_template,         page=self.page)
        await r.run_step("template::tpl-10-fork-template",        self._fork_template,          page=self.page)

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
            raise AssertionError(f"Template login failed for {username!r}")

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
    # Step implementations — admin side
    # ------------------------------------------------------------------

    async def _admin_login(self) -> None:
        """TPL-01: Login as pam_admin on PAM."""
        await self._login("pam_admin")

    async def _navigate_templates_new(self) -> None:
        """TPL-02: Navigate to /templates/new."""
        await self._goto("pam_admin", "/templates/new")

    async def _fill_template_name(self) -> None:
        """TPL-03: Fill template name."""
        await self.page.fill(
            'input[name="template_name"]',
            "E2E Test Template",
        )

    async def _fill_template_body(self) -> None:
        """TPL-04: Fill template body/content."""
        await self.page.fill(
            'textarea[name="template_body"], [data-field="template_body"]',
            "Automated E2E test template body content.",
        )

    async def _save_draft(self) -> None:
        """TPL-05: Save template as draft."""
        save_btn = self.page.locator('button:has-text("Save Draft"), button[data-action="save-draft"]')
        await save_btn.first.click(timeout=TIMEOUTS["element"])
        await self.page.wait_for_selector(
            '.alert-success, [data-status="draft"]',
            timeout=TIMEOUTS["element"],
        )

    async def _publish_template(self) -> None:
        """TPL-06: Publish the template."""
        publish_btn = self.page.locator('button:has-text("Publish"), button[data-action="publish"]')
        await publish_btn.first.click(timeout=TIMEOUTS["element"])
        await self.page.wait_for_selector(
            '.alert-success, [data-status="published"]',
            timeout=TIMEOUTS["element"],
        )
        await self._logout()

    # ------------------------------------------------------------------
    # Step implementations — retailer side
    # ------------------------------------------------------------------

    async def _retailer_login(self) -> None:
        """TPL-07: Login as lowes_retailer on Meredith."""
        await self._login("lowes_retailer")

    async def _verify_template_visible(self) -> None:
        """TPL-08: Verify published template is visible in /template-library."""
        await self._goto("lowes_retailer", "/template-library")
        row = self.page.locator('text="E2E Test Template"')
        await row.first.wait_for(timeout=TIMEOUTS["element"])

    async def _adopt_template(self) -> None:
        """TPL-09: Adopt the published template."""
        adopt_btn = self.page.locator('button:has-text("Adopt"), button[data-action="adopt"]')
        await adopt_btn.first.click(timeout=TIMEOUTS["element"])
        await self.page.wait_for_selector(
            '.alert-success, [data-status="adopted"]',
            timeout=TIMEOUTS["element"],
        )

    async def _fork_template(self) -> None:
        """TPL-10: Fork the adopted template."""
        fork_btn = self.page.locator('button:has-text("Fork"), button[data-action="fork"]')
        await fork_btn.first.click(timeout=TIMEOUTS["element"])
        await self.page.wait_for_selector(
            '.alert-success, [data-status="forked"]',
            timeout=TIMEOUTS["element"],
        )
        await self._logout()
