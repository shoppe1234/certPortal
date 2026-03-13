"""rbac_flow.py — RBAC cross-portal enforcement verification (Step #7).

Verifies that role guards block access across portals. Actual role rules:
  PAM      (8000): admin only
  Meredith (8001): admin or retailer
  Chrissy  (8002): admin or supplier

Steps log in to a portal with wrong-role credentials and assert that
the target protected route redirects to /login (or stays at /login on login).

No new seed data needed — existing users cover all cases:
  acme_supplier  (role=supplier, password=certportal_supplier)
  lowes_retailer (role=retailer, password=certportal_retailer)

Requirements verified:
  RBAC-01  Supplier JWT rejected on PAM admin route (/suppliers)
  RBAC-02  Retailer JWT rejected on Chrissy supplier route (/patches)
  RBAC-03  Supplier JWT rejected on Meredith retailer route (/supplier-status)
"""
from __future__ import annotations

from playwrightcli.config import PORTALS, TIMEOUTS

PORTAL = "rbac"

RBAC_STEPS = [
    "supplier-rejects-admin-route",
    "retailer-rejects-supplier-route",
    "supplier-rejects-retailer-route",
]

_PAM_URL      = PORTALS["pam"]["url"]
_MEREDITH_URL = PORTALS["meredith"]["url"]
_CHRISSY_URL  = PORTALS["chrissy"]["url"]


class RbacFlow:
    """Standalone RBAC flow — does not extend BaseFlow."""

    def __init__(self, page, runner, *, verifier=None) -> None:
        self.page = page
        self.runner = runner
        self._verifier = verifier

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        r = self.runner
        await r.run_step("rbac::supplier-rejects-admin-route",    self._supplier_rejects_admin,    page=self.page)
        await r.run_step("rbac::retailer-rejects-supplier-route", self._retailer_rejects_supplier, page=self.page)
        await r.run_step("rbac::supplier-rejects-retailer-route", self._supplier_rejects_retailer, page=self.page)

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    async def _login(self, portal_url: str, username: str, password: str) -> bool:
        """Navigate to portal_url/login and submit credentials.

        Returns True if login redirected away from /login (session established),
        False if still at /login (credentials or role rejected at login time).
        """
        await self.page.goto(
            f"{portal_url}/login",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        await self.page.fill('input[name="username"]', username)
        await self.page.fill('input[name="password"]', password)
        async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
            await self.page.click('button[type="submit"]')
        return "/login" not in self.page.url

    async def _logout_current(self) -> None:
        """POST /logout on the currently active portal page."""
        await self.page.evaluate("""() => {
            const f = document.createElement('form');
            f.method = 'POST';
            f.action = '/logout';
            document.body.appendChild(f);
            f.submit();
        }""")
        await self.page.wait_for_url("**/login**", timeout=TIMEOUTS["navigation"])

    async def _try_access(self, portal_url: str, path: str) -> bool:
        """Navigate to portal_url + path. Returns True if redirected to /login."""
        await self.page.goto(
            f"{portal_url}{path}",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        return "/login" in self.page.url

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _supplier_rejects_admin(self) -> None:
        """acme_supplier logs into PAM; /suppliers (admin-only) must redirect to /login.

        Login to PAM with supplier role — PAM may reject at login or at /suppliers.
        Either way, /suppliers must not be accessible.

        RBAC-01: Supplier JWT rejected on PAM admin route (/suppliers).
        """
        # Try to log in to PAM with supplier credentials
        login_ok = await self._login(_PAM_URL, "acme_supplier", "certportal_supplier")
        if login_ok:
            # Session established — check that /suppliers redirects to /login
            blocked = await self._try_access(_PAM_URL, "/suppliers")
            if not blocked:
                await self._logout_current()
        else:
            # PAM rejected login entirely for supplier role — route is blocked at auth
            blocked = True

        if self._verifier:
            self._verifier.verify_rbac(
                req_id="RBAC-01",
                description="Supplier JWT rejected on PAM admin route (/suppliers)",
                access_blocked=blocked,
            )

    async def _retailer_rejects_supplier(self) -> None:
        """lowes_retailer logs into Chrissy; /patches (supplier role required) must block.

        Chrissy requires admin or supplier. Retailer is neither → blocked.

        RBAC-02: Retailer JWT rejected on Chrissy supplier route (/patches).
        """
        login_ok = await self._login(_CHRISSY_URL, "lowes_retailer", "certportal_retailer")
        if login_ok:
            blocked = await self._try_access(_CHRISSY_URL, "/patches")
            if not blocked:
                await self._logout_current()
        else:
            blocked = True

        if self._verifier:
            self._verifier.verify_rbac(
                req_id="RBAC-02",
                description="Retailer JWT rejected on Chrissy supplier route (/patches)",
                access_blocked=blocked,
            )

    async def _supplier_rejects_retailer(self) -> None:
        """acme_supplier logs into Meredith; /supplier-status (retailer role) must block.

        Meredith requires admin or retailer. Supplier is neither → blocked.

        RBAC-03: Supplier JWT rejected on Meredith retailer route (/supplier-status).
        """
        login_ok = await self._login(_MEREDITH_URL, "acme_supplier", "certportal_supplier")
        if login_ok:
            blocked = await self._try_access(_MEREDITH_URL, "/supplier-status")
            if not blocked:
                await self._logout_current()
        else:
            blocked = True

        if self._verifier:
            self._verifier.verify_rbac(
                req_id="RBAC-03",
                description="Supplier JWT rejected on Meredith retailer route (/supplier-status)",
                access_blocked=blocked,
            )
