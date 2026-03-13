"""scope_flow.py — Multi-tenant scope isolation + certification full-flow (Steps #3 and #8).

Verifies INV-06: data is scoped to {retailer_slug}/{supplier_slug}/ at the
portal level. Logs in as four different users across two tenants and asserts
that each user sees only their own tenant's data.

Also verifies Step #8 (certification full flow): cert_supplier (supplier_slug='cert_test',
gate_3=CERTIFIED) should see the CERTIFIED badge on both the dashboard and /certification.

Tenants under test (scope steps):
  Tenant A (lowes):   lowes_retailer / acme_supplier
  Tenant B (target):  target_retailer / rival_supplier

Steps (each handles its own login/logout):
  scope::supplier-a-patches    acme sees 850-BEG-01, NOT 855-AK1-01
  scope::supplier-a-scenarios  acme sees tx-type 850, NOT retailer 'target'
  scope::supplier-b-patches    rival sees 855-AK1-01, NOT 850-BEG-01
  scope::supplier-b-scenarios  rival sees tx-type 855, NOT retailer 'lowes'
  scope::retailer-a-status     lowes sees 'acme', NOT 'rival'
  scope::retailer-b-status     target sees 'rival', NOT 'acme'
  scope::cert-dashboard        cert_supplier sees CERTIFIED badge on /
  scope::cert-certification    cert_supplier sees certified status on /certification

Requirements verified:
  SCOPE-SUP-01 / SCOPE-SUP-02  acme supplier isolation (/patches + /scenarios)
  SCOPE-SUP-03 / SCOPE-SUP-04  rival supplier isolation (/patches + /scenarios)
  SCOPE-RET-01 / SCOPE-RET-02  lowes retailer isolation (/supplier-status)
  SCOPE-RET-03 / SCOPE-RET-04  target retailer isolation (/supplier-status)
  CHR-CERT-03                  Dashboard shows CERTIFIED badge for cert_test supplier
  CHR-CERT-04                  /certification page shows certified status
"""
from __future__ import annotations

from playwrightcli.config import PORTALS, TIMEOUTS

PORTAL = "scope"

SCOPE_STEPS = [
    "supplier-a-patches",
    "supplier-a-scenarios",
    "supplier-b-patches",
    "supplier-b-scenarios",
    "retailer-a-status",
    "retailer-b-status",
    "cert-dashboard",
    "cert-certification",
]

# Tenant A
_CHRISSY_URL  = PORTALS["chrissy"]["url"]
_MEREDITH_URL = PORTALS["meredith"]["url"]

_USERS = {
    "acme_supplier":   {"password": "certportal_supplier",  "url": _CHRISSY_URL},
    "rival_supplier":  {"password": "certportal_rival",     "url": _CHRISSY_URL},
    "lowes_retailer":  {"password": "certportal_retailer",  "url": _MEREDITH_URL},
    "target_retailer": {"password": "certportal_target",    "url": _MEREDITH_URL},
    "cert_supplier":   {"password": "certportal_cert",      "url": _CHRISSY_URL},
}


class ScopeFlow:
    """Standalone scope isolation flow — does not extend BaseFlow."""

    def __init__(self, page, runner, *, verifier=None) -> None:
        self.page = page
        self.runner = runner
        self._verifier = verifier

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        r = self.runner

        await r.run_step("scope::supplier-a-patches",   self._supplier_a_patches,   page=self.page)
        await r.run_step("scope::supplier-a-scenarios", self._supplier_a_scenarios, page=self.page)
        await r.run_step("scope::supplier-b-patches",   self._supplier_b_patches,   page=self.page)
        await r.run_step("scope::supplier-b-scenarios", self._supplier_b_scenarios, page=self.page)
        await r.run_step("scope::retailer-a-status",    self._retailer_a_status,    page=self.page)
        await r.run_step("scope::retailer-b-status",    self._retailer_b_status,    page=self.page)
        await r.run_step("scope::cert-dashboard",       self._cert_dashboard,       page=self.page)
        await r.run_step("scope::cert-certification",   self._cert_certification,   page=self.page)

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
            raise AssertionError(f"Scope login failed for {username!r} — check seed users")

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
    # Step implementations
    # ------------------------------------------------------------------

    async def _supplier_a_patches(self) -> None:
        """acme_supplier /patches: 850-BEG-01 visible, 855-AK1-01 absent."""
        await self._login("acme_supplier")
        await self._goto("acme_supplier", "/patches")
        if self._verifier:
            await self._verifier.verify_scope_supplier_patches(
                self.page,
                own_error_code="850-BEG-01",
                rival_error_code="855-AK1-01",
                req_own="SCOPE-SUP-01",
                req_isolation="SCOPE-SUP-02",
            )
        await self._logout()

    async def _supplier_a_scenarios(self) -> None:
        """acme_supplier /scenarios: tx-type 850 visible, rival retailer 'target' absent."""
        await self._login("acme_supplier")
        await self._goto("acme_supplier", "/scenarios")
        if self._verifier:
            await self._verifier.verify_scope_supplier_scenarios(
                self.page,
                own_tx_type="850",
                rival_retailer="target",
                req_own="SCOPE-SUP-03",
                req_isolation="SCOPE-SUP-04",
            )
        await self._logout()

    async def _supplier_b_patches(self) -> None:
        """rival_supplier /patches: 855-AK1-01 visible, 850-BEG-01 absent."""
        await self._login("rival_supplier")
        await self._goto("rival_supplier", "/patches")
        if self._verifier:
            await self._verifier.verify_scope_supplier_patches(
                self.page,
                own_error_code="855-AK1-01",
                rival_error_code="850-BEG-01",
                req_own="SCOPE-SUP-05",
                req_isolation="SCOPE-SUP-06",
            )
        await self._logout()

    async def _supplier_b_scenarios(self) -> None:
        """rival_supplier /scenarios: tx-type 855 visible, rival retailer 'lowes' absent."""
        await self._login("rival_supplier")
        await self._goto("rival_supplier", "/scenarios")
        if self._verifier:
            await self._verifier.verify_scope_supplier_scenarios(
                self.page,
                own_tx_type="855",
                rival_retailer="lowes",
                req_own="SCOPE-SUP-07",
                req_isolation="SCOPE-SUP-08",
            )
        await self._logout()

    async def _retailer_a_status(self) -> None:
        """lowes_retailer /supplier-status: 'acme' visible, 'rival' absent."""
        await self._login("lowes_retailer")
        await self._goto("lowes_retailer", "/supplier-status")
        if self._verifier:
            await self._verifier.verify_scope_retailer_status(
                self.page,
                own_supplier="acme",
                rival_supplier="rival",
                req_own="SCOPE-RET-01",
                req_isolation="SCOPE-RET-02",
            )
        await self._logout()

    async def _retailer_b_status(self) -> None:
        """target_retailer /supplier-status: 'rival' visible, 'acme' absent."""
        await self._login("target_retailer")
        await self._goto("target_retailer", "/supplier-status")
        if self._verifier:
            await self._verifier.verify_scope_retailer_status(
                self.page,
                own_supplier="rival",
                rival_supplier="acme",
                req_own="SCOPE-RET-03",
                req_isolation="SCOPE-RET-04",
            )
        await self._logout()

    async def _cert_dashboard(self) -> None:
        """cert_supplier /: CERTIFIED badge visible on dashboard (CHR-CERT-03).

        Requires seed: cert_supplier (supplier_slug='cert_test'), hitl_gate_status
        gate_3='CERTIFIED' for cert_test.
        """
        await self._login("cert_supplier")
        await self._goto("cert_supplier", "/")
        if self._verifier:
            await self._verifier.verify_cert_dashboard(self.page)
        await self._logout()

    async def _cert_certification(self) -> None:
        """cert_supplier /certification: certified status visible (CHR-CERT-04)."""
        await self._login("cert_supplier")
        await self._goto("cert_supplier", "/certification")
        if self._verifier:
            await self._verifier.verify_cert_certification_page(self.page)
        await self._logout()
