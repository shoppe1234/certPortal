"""chrissy_flow.py — Supplier portal (port 8002) E2E steps.

Steps:
  chrissy::login         GET /login → fill form → POST /token → assert /
  chrissy::scenarios     GET /scenarios
  chrissy::errors        GET /errors
  chrissy::patches       GET /patches (list renders via HTMX swap — needs networkidle)
  chrissy::certification GET /certification
  chrissy::logout        POST /logout → assert /login
"""
from __future__ import annotations

from playwrightcli.flows.base_flow import BaseFlow

PORTAL = "chrissy"

# Step names in run order — used by --dry-run
CHRISSY_STEPS = [
    "login",
    "scenarios",
    "errors",
    "patches",
    "certification",
    "logout",
]


class ChrissyFlow(BaseFlow):
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
        await self.verify("login")

        await r.run_step(f"{pfx}scenarios",     self._scenarios,     page=p, relogin_fn=self.relogin)
        await self.capture("scenarios")
        await self.verify("scenarios")
        await r.run_step(f"{pfx}errors",        self._errors,        page=p, relogin_fn=self.relogin)
        await self.capture("errors")
        await self.verify("errors")
        await r.run_step(f"{pfx}patches",       self._patches,       page=p, relogin_fn=self.relogin)
        await self.capture("patches")
        await self.verify("patches")
        await r.run_step(f"{pfx}certification", self._certification, page=p, relogin_fn=self.relogin)
        await self.capture("certification")
        await self.verify("certification")
        await r.run_step(f"{pfx}logout",        self.logout,         max_retries=2, page=p)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _scenarios(self) -> None:
        await self.goto("/scenarios")
        await self.assert_page_ok()
        await self.wait_htmx()
        # Table is empty when no test_occurrences exist for this supplier — that's OK
        await self.page.wait_for_selector(
            "table, .empty-state, main, h1, h2",
            timeout=10_000,
        )

    async def _errors(self) -> None:
        await self.goto("/errors")
        await self.assert_page_ok()
        await self.wait_htmx()
        await self.page.wait_for_selector(
            "main, h1, h2, body",
            timeout=10_000,
        )

    async def _patches(self) -> None:
        await self.goto("/patches")
        await self.assert_page_ok()
        # Patch list renders via HTMX swap after page load — wait for networkidle first
        await self.wait_htmx()
        # Patch list or empty state (no patches for acme_supplier yet is valid)
        await self.page.wait_for_selector(
            "table, .empty-state, main, h1, h2",
            timeout=10_000,
        )

    async def _certification(self) -> None:
        await self.goto("/certification")
        await self.assert_page_ok()
        await self.wait_htmx()
        await self.page.wait_for_selector(
            "main, h1, h2, body",
            timeout=10_000,
        )
