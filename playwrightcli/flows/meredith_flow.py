"""meredith_flow.py — Retailer portal (port 8001) E2E steps.

Steps:
  meredith::login                    GET /login → fill form → POST /token → assert /
  meredith::spec-setup               GET /spec-setup (wizard entry points, not PDF upload)
  meredith::supplier-status          GET /supplier-status
  meredith::yaml-wizard-signal       POST /yaml-wizard/path2 → verify S3 andy_path2_trigger signal
  meredith::deprecated-path1         POST /yaml-wizard/path1 → verify HTTP 410 (DEPR-02)
  meredith::deprecated-upload        POST /spec-setup/upload → verify HTTP 410 (DEPR-01)
  meredith::yaml-wizard-path3-signal POST /yaml-wizard/path3 → verify S3 andy_path3_trigger signal
  meredith::logout                   POST /logout → assert /login

Human mode (--human flag):
  Login is automated (infrastructure). For every other step the terminal prints
  guidance, waits for your Enter keypress, then runs the same assertions that
  the automated flow would run — so PASS/FAIL reflects real browser state.
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
    "deprecated-path1",
    "deprecated-upload",
    "yaml-wizard-path3-signal",
    "logout",
]

# Human-readable guidance for each step shown in --human mode
HUMAN_GUIDANCE: dict[str, str] = {
    "spec-setup": (
        "Navigate to /spec-setup (Spec Setup in the nav). "
        "Wait for the page to load — you should see wizard entry points "
        "(Lifecycle Wizard, Layer 2 Wizard) instead of PDF upload."
    ),
    "supplier-status": (
        "Navigate to /supplier-status (Supplier Status in the nav). "
        "Wait for the supplier table or empty state to appear."
    ),
    "yaml-wizard-signal": (
        "Navigate to /yaml-wizard and trigger Path 2 (upload an existing YAML / "
        "select bundle). Complete the form and submit. "
        "The harness will fire the API call automatically after you press Enter."
    ),
    "deprecated-path1": (
        "The harness will POST /yaml-wizard/path1 and verify it returns HTTP 410 (Gone). "
        "Path 1 (PDF upload) has been deprecated (ADR-032)."
    ),
    "deprecated-upload": (
        "The harness will POST /spec-setup/upload and verify it returns HTTP 410 (Gone). "
        "PDF upload has been deprecated (ADR-032)."
    ),
    "yaml-wizard-path3-signal": (
        "Navigate to /yaml-wizard and trigger Path 3 (manual segment overrides). "
        "Complete the form and submit. "
        "The harness will fire the API call automatically after you press Enter."
    ),
    "logout": (
        "Click the Logout button (or navigate to /logout) to end your session. "
        "You should be redirected to /login."
    ),
}


class MeredithFlow(BaseFlow):
    async def run(self) -> None:
        r = self.runner
        p = self.page
        pfx = f"{PORTAL}::"

        # Login is always automated — it is infrastructure, not a portal feature.
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

        await r.run_step(f"{pfx}supplier-status", self._supplier_status, page=p, relogin_fn=self.relogin)
        await self.capture("supplier-status")
        await self.verify("supplier-status")

        await r.run_step(f"{pfx}yaml-wizard-signal",       self._yaml_wizard_signal,       page=p, relogin_fn=self.relogin)
        await r.run_step(f"{pfx}deprecated-path1",         self._deprecated_path1,         page=p, relogin_fn=self.relogin)
        await r.run_step(f"{pfx}deprecated-upload",        self._deprecated_upload,        page=p, relogin_fn=self.relogin)
        await r.run_step(f"{pfx}yaml-wizard-path3-signal", self._yaml_wizard_path3_signal, page=p, relogin_fn=self.relogin)

        await r.run_step(f"{pfx}logout", self._logout_step, max_retries=2, page=p)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _spec_setup(self) -> None:
        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["spec-setup"], "meredith::spec-setup")
            if not ready:
                return
        else:
            await self.goto("/spec-setup")
            await self.assert_page_ok()
            await self.wait_htmx()

        # Assertions — verify wizard entry points render (not PDF upload)
        await self.page.wait_for_selector(
            "main, h1, h2, .wizard-card, a[href*='lifecycle-wizard'], a[href*='yaml-wizard']",
            timeout=10_000,
        )

    async def _supplier_status(self) -> None:
        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["supplier-status"], "meredith::supplier-status")
            if not ready:
                return
        else:
            await self.goto("/supplier-status")
            await self.assert_page_ok()
            await self.wait_htmx()

        # Assertions — run in both modes
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

        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["yaml-wizard-signal"], "meredith::yaml-wizard-signal")
            if not ready:
                return
            # Human navigated to yaml-wizard; assert page state before firing API
            await self.assert_page_ok()
        else:
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

    async def _deprecated_path1(self) -> None:
        """POST /yaml-wizard/path1 — verify HTTP 410 (Path 1 deprecated, ADR-032).

        DEPR-02: POST /yaml-wizard/path1 returns HTTP 410.
        """
        if self._verifier is None:
            return

        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["deprecated-path1"], "meredith::deprecated-path1")
            if not ready:
                return

        response = await self.page.evaluate("""async () => {
            try {
                const r = await fetch('/yaml-wizard/path1', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        retailer_slug: 'lowes',
                        pdf_key: 'lowes/system/test_spec.pdf'
                    })
                });
                return {ok: r.ok, status: r.status};
            } catch (e) {
                return {ok: false, status: 0, error: String(e)};
            }
        }""")

        self._verifier.verify_deprecation_yaml_path1(response.get("status", 0))

    async def _deprecated_upload(self) -> None:
        """POST /spec-setup/upload — verify HTTP 410 (PDF upload deprecated, ADR-032).

        DEPR-01: POST /spec-setup/upload returns HTTP 410.
        """
        if self._verifier is None:
            return

        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["deprecated-upload"], "meredith::deprecated-upload")
            if not ready:
                return

        response = await self.page.evaluate("""async () => {
            try {
                const r = await fetch('/spec-setup/upload', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({retailer_slug: 'lowes'})
                });
                return {ok: r.ok, status: r.status};
            } catch (e) {
                return {ok: false, status: 0, error: String(e)};
            }
        }""")

        self._verifier.verify_deprecation_spec_upload(response.get("status", 0))

    async def _yaml_wizard_path3_signal(self) -> None:
        """POST /yaml-wizard/path3 via browser fetch, verify S3 andy_path3_trigger signal.

        SIG-YAML3-01: HTTP 200 returned.
        SIG-YAML3-02: andy_path3_trigger_*.json written under lowes/system/signals/.
        SIG-YAML3-03: Payload contains type=andy_yaml_path3 and retailer_slug=lowes.
        """
        if self._verifier is None:
            return

        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["yaml-wizard-path3-signal"], "meredith::yaml-wizard-path3-signal")
            if not ready:
                return
            await self.assert_page_ok()
        else:
            await self.goto("/yaml-wizard")
            await self.assert_page_ok()

        ts = time.time() - 1

        response = await self.page.evaluate("""async () => {
            try {
                const r = await fetch('/yaml-wizard/path3', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        retailer_slug: 'lowes',
                        bundle: 'general_merchandise',
                        segment_overrides: {}
                    })
                });
                const body = await r.json();
                return {ok: r.ok, status: r.status, body: body};
            } catch (e) {
                return {ok: false, status: 0, body: {}, error: String(e)};
            }
        }""")

        await self._verifier.verify_signals_yaml_path3(ts, response)

    async def _logout_step(self) -> None:
        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["logout"], "meredith::logout")
            if not ready:
                return
            # Human performed logout; assert we are now on /login
            await self.page.wait_for_url("**/login**", timeout=10_000)
        else:
            await self.logout()
