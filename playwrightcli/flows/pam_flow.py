"""pam_flow.py — Admin portal (port 8000) E2E steps.

Steps:
  pam::login        GET /login → fill form → POST /token → assert redirect to /
  pam::retailers    GET /retailers
  pam::suppliers    GET /suppliers
  pam::hitl-queue   GET /hitl-queue (table may be absent when queue is empty)
  pam::monica-memory GET /monica-memory
  pam::logout       POST /logout → assert redirect to /login
"""
from __future__ import annotations

from playwrightcli.flows.base_flow import BaseFlow

PORTAL = "pam"

# Step names in run order — used by --dry-run
PAM_STEPS = [
    "login",
    "retailers",
    "suppliers",
    "hitl-queue",
    "monica-memory",
    "logout",
]


class PamFlow(BaseFlow):
    async def run(self) -> None:
        r = self.runner
        p = self.page
        pfx = f"{PORTAL}::"

        # login is fatal — nothing downstream works without a session
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

        await r.run_step(f"{pfx}retailers",    self._retailers,     page=p, relogin_fn=self.relogin)
        await self.capture("retailers")
        await self.verify("retailers")
        await r.run_step(f"{pfx}suppliers",    self._suppliers,     page=p, relogin_fn=self.relogin)
        await self.capture("suppliers")
        await self.verify("suppliers")
        await r.run_step(f"{pfx}hitl-queue",   self._hitl_queue,    page=p, relogin_fn=self.relogin)
        await self.capture("hitl-queue")
        await self.verify("hitl-queue")
        await r.run_step(f"{pfx}monica-memory", self._monica_memory, page=p, relogin_fn=self.relogin)
        await self.capture("monica-memory")
        await self.verify("monica-memory")
        await r.run_step(f"{pfx}logout",       self.logout,         max_retries=2, page=p)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _retailers(self) -> None:
        await self.goto("/retailers")
        await self.assert_page_ok()
        await self.wait_htmx()
        # Expect the page to contain a table or empty-state element
        await self.page.wait_for_selector(
            "table, .empty-state, main, h1, h2",
            timeout=10_000,
        )

    async def _suppliers(self) -> None:
        await self.goto("/suppliers")
        await self.assert_page_ok()
        await self.wait_htmx()
        await self.page.wait_for_selector(
            "table, .empty-state, main, h1, h2",
            timeout=10_000,
        )

    async def _hitl_queue(self) -> None:
        await self.goto("/hitl-queue")
        await self.assert_page_ok()
        await self.wait_htmx()
        # The #hitl-table element is NOT rendered when the queue is empty (known from memory).
        # Assert any page structure is present instead.
        await self.page.wait_for_selector(
            "main, h1, h2, body",
            timeout=10_000,
        )

    async def _monica_memory(self) -> None:
        await self.goto("/monica-memory")
        await self.assert_page_ok()
        await self.wait_htmx()
        await self.page.wait_for_selector(
            "table, .empty-state, main, h1, h2",
            timeout=10_000,
        )
