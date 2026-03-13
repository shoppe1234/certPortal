"""meredith_flow.py — Retailer portal (port 8001) E2E steps.

Steps:
  meredith::login              GET /login → fill form → POST /token → assert /
  meredith::spec-setup         GET /spec-setup
  meredith::supplier-status    GET /supplier-status
  meredith::yaml-wizard-signal POST /yaml-wizard/path2 → verify S3 andy_path2_trigger signal
  meredith::logout             POST /logout → assert /login
"""
from __future__ import annotations

import time

from playwrightcli.flows.base_flow import BaseFlow

PORTAL = "meredith"

# Step names in run order — used by --dry-run
MEREDITH_STEPS = [
    "login",
    "spec-setup",
    "supplier-status",
    "yaml-wizard-signal",
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
        await self.verify("login")

        await r.run_step(f"{pfx}spec-setup",      self._spec_setup,      page=p, relogin_fn=self.relogin)
        await self.capture("spec-setup")
        await self.verify("spec-setup")
        await r.run_step(f"{pfx}supplier-status",    self._supplier_status,    page=p, relogin_fn=self.relogin)
        await self.capture("supplier-status")
        await self.verify("supplier-status")
        await r.run_step(f"{pfx}yaml-wizard-signal", self._yaml_wizard_signal, page=p, relogin_fn=self.relogin)
        await r.run_step(f"{pfx}logout",             self.logout,              max_retries=2, page=p)

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

    async def _yaml_wizard_signal(self) -> None:
        """POST /yaml-wizard/path2 via browser fetch, verify S3 andy_path2_trigger signal.

        SIG-YAML2-01: HTTP 200 returned.
        SIG-YAML2-02: andy_path2_trigger_*.json written under lowes/system/signals/.
        SIG-YAML2-03: Payload contains type=andy_yaml_path2 and retailer_slug=lowes.
        """
        if self._verifier is None:
            return  # --verify not active; skip entirely

        await self.goto("/yaml-wizard")
        await self.assert_page_ok()

        ts = time.time() - 1  # 1 s buffer for LastModified clock skew

        response = await self.page.evaluate("""async () => {
            try {
                const r = await fetch('/yaml-wizard/path2', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        retailer_slug: 'lowes',
                        bundle: 'general_merchandise',
                        yaml_key: 'lowes/system/test_upload_fixture.yaml'
                    })
                });
                const body = await r.json();
                return {ok: r.ok, status: r.status, body: body};
            } catch (e) {
                return {ok: false, status: 0, body: {}, error: String(e)};
            }
        }""")

        await self._verifier.verify_signals_yaml_path2(ts, response)
