"""meredith_flow.py — Retailer portal (port 8001) E2E steps.

Steps:
  meredith::login           GET /login → fill form → POST /token → assert /
  meredith::spec-setup      GET /spec-setup
  meredith::supplier-status GET /supplier-status
  meredith::logout          POST /logout → assert /login
"""
from __future__ import annotations

from playwrightcli.flows.base_flow import BaseFlow

PORTAL = "meredith"

# Step names in run order — used by --dry-run
MEREDITH_STEPS = [
    "login",
    "spec-setup",
    "supplier-status",
    "logout",
]


class MeredithFlow(BaseFlow):
    async def run(self) -> None:
        r = self.runner
        p = self.page
        pfx = f"{PORTAL}::"

        ok = await r.run_step(
            f"{pfx}login",
            self.login,
            max_retries=2,
            fatal=True,
            page=p,
        )
        if not ok:
            return
        await self.capture("login")

        await r.run_step(f"{pfx}spec-setup",      self._spec_setup,      page=p, relogin_fn=self.relogin)
        await self.capture("spec-setup")
        await r.run_step(f"{pfx}supplier-status",  self._supplier_status, page=p, relogin_fn=self.relogin)
        await self.capture("supplier-status")
        await r.run_step(f"{pfx}logout",           self.logout,           max_retries=2, page=p)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _spec_setup(self) -> None:
        await self.goto("/spec-setup")
        await self.assert_page_ok()
        await self.wait_htmx()
        # Spec table or empty-state (no specs uploaded yet is valid)
        await self.page.wait_for_selector(
            "table, .empty-state, main, h1, h2",
            timeout=10_000,
        )

    async def _supplier_status(self) -> None:
        await self.goto("/supplier-status")
        await self.assert_page_ok()
        await self.wait_htmx()
        await self.page.wait_for_selector(
            "table, .empty-state, main, h1, h2",
            timeout=10_000,
        )
