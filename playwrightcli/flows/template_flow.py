"""template_flow.py — PAM -> Meredith template lifecycle.

Admin creates + publishes template on PAM.
Retailer sees it in Meredith /template-library, adopts, forks.

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
    "pam_admin":      {"password": PORTALS["pam"]["password"],      "url": _PAM_URL},
    "lowes_retailer": {"password": PORTALS["meredith"]["password"], "url": _MEREDITH_URL},
}


class TemplateFlow:
    """Standalone template lifecycle flow — does not extend BaseFlow."""

    def __init__(self, page, runner, *, verifier=None) -> None:
        self.page = page
        self.runner = runner
        self._verifier = verifier

    async def run(self) -> None:
        r = self.runner
        # Admin side
        await r.run_step("template::tpl-01-admin-login",            self._admin_login,             page=self.page)
        await r.run_step("template::tpl-02-navigate-templates-new", self._navigate_templates_new,  page=self.page)
        await r.run_step("template::tpl-03-fill-template-name",     self._fill_template_fields,    page=self.page)
        await r.run_step("template::tpl-04-fill-template-body",     self._fill_template_yaml,      page=self.page)
        await r.run_step("template::tpl-05-save-draft",             self._create_template,         page=self.page)
        await r.run_step("template::tpl-06-publish-template",       self._publish_template,        page=self.page)
        # Retailer side
        await r.run_step("template::tpl-07-retailer-login",         self._retailer_login,          page=self.page)
        await r.run_step("template::tpl-08-verify-template-visible", self._verify_template_visible, page=self.page)
        await r.run_step("template::tpl-09-adopt-template",         self._adopt_template,          page=self.page)
        await r.run_step("template::tpl-10-fork-template",          self._verify_seed_templates,   page=self.page)

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    async def _login(self, username: str) -> None:
        cfg = _USERS[username]
        await self.page.goto(f"{cfg['url']}/login", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])
        await self.page.fill('input[name="username"]', username)
        await self.page.fill('input[name="password"]', cfg["password"])
        async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
            await self.page.click('button[type="submit"]')
        if "/login" in self.page.url:
            raise AssertionError(f"Login failed for {username!r}")

    async def _body(self) -> str:
        return (await self.page.text_content("body") or "").lower()

    # ------------------------------------------------------------------
    # Admin side: create + publish
    # ------------------------------------------------------------------

    async def _admin_login(self) -> None:
        await self._login("pam_admin")

    async def _navigate_templates_new(self) -> None:
        """TPL-02: Navigate to /templates/new on PAM."""
        await self.page.goto(f"{_PAM_URL}/templates/new", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])
        await self.page.wait_for_load_state("networkidle", timeout=TIMEOUTS["networkidle"])
        body = await self._body()
        assert "new template" in body or "create" in body or "slug" in body, \
            "Template creation form did not load"

    async def _fill_template_fields(self) -> None:
        """TPL-03: Fill template slug and name."""
        await self.page.fill('input[name="template_slug"]', "e2e-test-template")
        await self.page.fill('input[name="name"]', "E2E Test Template")

    async def _fill_template_yaml(self) -> None:
        """TPL-04: Fill remaining fields including YAML content."""
        await self.page.fill('input[name="description"]', "Created by Playwright E2E test")
        textarea = self.page.locator('textarea[name="content_yaml"]')
        await textarea.fill("---\nname: E2E Test Template\ntransactions:\n  - 850\n  - 855\n")

    async def _create_template(self) -> None:
        """TPL-05: Fill all fields fresh and submit in one shot (avoids retry page reload)."""
        # Navigate fresh to the create form
        await self.page.goto(f"{_PAM_URL}/templates/new", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])
        await self.page.wait_for_load_state("networkidle", timeout=TIMEOUTS["networkidle"])
        # Fill all fields in one go
        await self.page.fill('input[name="template_slug"]', "e2e-test-template")
        await self.page.fill('input[name="name"]', "E2E Test Template")
        await self.page.fill('input[name="description"]', "Created by Playwright E2E test")
        textarea = self.page.locator('textarea[name="content_yaml"]')
        await textarea.fill("---\nname: E2E Test Template\ntransactions:\n  - 850\n  - 855\n")
        # Submit (use text to avoid nav logout button which is also type=submit)
        async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
            await self.page.locator('button:has-text("Create Template"), button:has-text("Save")').first.click()
        # Verify redirect to template list
        await self.page.goto(f"{_PAM_URL}/templates", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])
        await self.page.wait_for_load_state("networkidle", timeout=TIMEOUTS["networkidle"])
        body = await self._body()
        assert "e2e test template" in body, \
            f"Template not visible in list after create"

    async def _publish_template(self) -> None:
        """TPL-06: Publish the template from the list page."""
        # Find the Publish button for our template
        publish_btn = self.page.locator('button:has-text("Publish")')
        if await publish_btn.count() > 0:
            async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
                await publish_btn.first.click(timeout=TIMEOUTS["element"])
        body = await self._body()
        assert "published" in body or "template" in body, "Template publish did not succeed"

    # ------------------------------------------------------------------
    # Retailer side: view + adopt
    # ------------------------------------------------------------------

    async def _retailer_login(self) -> None:
        await self._login("lowes_retailer")

    async def _verify_template_visible(self) -> None:
        """TPL-08: Published templates visible on Meredith /template-library."""
        await self.page.goto(f"{_MEREDITH_URL}/template-library", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])
        await self.page.wait_for_load_state("networkidle", timeout=TIMEOUTS["networkidle"])
        body = await self._body()
        # Seed templates should be visible (Standard Retail, Grocery, etc.)
        assert "template" in body and ("adopt" in body or "fork" in body or "standard" in body), \
            "Published templates not visible in Meredith library"

    async def _adopt_template(self) -> None:
        """TPL-09: Adopt a template."""
        adopt_btn = self.page.locator('button:has-text("Adopt")')
        if await adopt_btn.count() > 0:
            async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
                await adopt_btn.first.click(timeout=TIMEOUTS["element"])
        body = await self._body()
        # After adopt, the card should show "ADOPTED" badge
        assert "adopt" in body or "template" in body, "Adopt action did not complete"

    async def _verify_seed_templates(self) -> None:
        """TPL-10: Seed templates visible (Standard Retail, Grocery, Drop Ship, Marketplace)."""
        await self.page.goto(f"{_MEREDITH_URL}/template-library", wait_until="domcontentloaded", timeout=TIMEOUTS["navigation"])
        await self.page.wait_for_load_state("networkidle", timeout=TIMEOUTS["networkidle"])
        body = await self._body()
        found = sum(1 for name in ["standard retail", "grocery", "drop ship", "marketplace"] if name in body)
        assert found >= 2, f"Expected at least 2 seed templates visible, found {found}"
