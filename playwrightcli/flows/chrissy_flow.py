"""chrissy_flow.py — Supplier portal (port 8002) E2E steps.

Steps:
  chrissy::login              GET /login → fill form → POST /token → assert /
  chrissy::scenarios          GET /scenarios
  chrissy::errors             GET /errors
  chrissy::patches            GET /patches (list renders via HTMX swap — needs networkidle)
  chrissy::patch-apply-signal POST /patches/{id}/mark-applied → verify S3 moses_revalidate signal
  chrissy::certification      GET /certification
  chrissy::logout             POST /logout → assert /login
"""
from __future__ import annotations

import os
import time

from playwrightcli.flows.base_flow import BaseFlow

PORTAL = "chrissy"

# Step names in run order — used by --dry-run
CHRISSY_STEPS = [
    "login",
    "scenarios",
    "errors",
    "patches",
    "patch-apply-signal",
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
        await r.run_step(f"{pfx}patches",            self._patches,            page=p, relogin_fn=self.relogin)
        await self.capture("patches")
        await self.verify("patches")
        await r.run_step(f"{pfx}patch-apply-signal", self._patch_apply_signal, page=p, relogin_fn=self.relogin)
        await r.run_step(f"{pfx}certification",      self._certification,      page=p, relogin_fn=self.relogin)
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

    async def _patch_apply_signal(self) -> None:
        """Navigate to /patches, POST mark-applied on a pending patch, verify Moses S3 signal.

        The seed-inserted signal-test patch (error_code=SIG-TEST-01, applied=FALSE) will
        be the most-recently-created pending patch (ORDER BY created_at DESC), so the
        page.evaluate script finds it first — leaving the DOM-check patch (850-BEG-01)
        untouched for re-runs.

        SIG-PATCH-01: HTTP 200 returned.
        SIG-PATCH-02: moses_revalidate_{id}_{ts}.json written under lowes/acme/signals/.
        SIG-PATCH-03: Payload contains trigger=patch_applied and patch_id.
        """
        if self._verifier is None:
            return  # --verify not active; skip entirely

        # Pre-step: reset SIG-TEST-01 patch to applied=FALSE for idempotent re-runs
        try:
            import psycopg2
            db_url = os.environ.get("CERTPORTAL_DB_URL", "")
            if not db_url:
                from playwrightcli.fixtures.signal_checker import _load_dotenv
                env = _load_dotenv()
                db_url = env.get("CERTPORTAL_DB_URL", "")
            if db_url:
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                cur.execute(
                    "UPDATE patch_suggestions SET applied = FALSE "
                    "WHERE error_code = 'SIG-TEST-01' AND applied = TRUE"
                )
                conn.commit()
                cur.close()
                conn.close()
        except Exception:
            pass  # Best-effort; if DB is unreachable the test will fail naturally

        await self.goto("/patches")
        await self.assert_page_ok()
        await self.wait_htmx()

        ts = time.time() - 1  # 1 s buffer for LastModified clock skew

        response = await self.page.evaluate("""async () => {
            // Find first pending mark-applied button — seed sorts SIG-TEST-01 first
            // (most-recently inserted, ORDER BY created_at DESC).
            const btn = document.querySelector('[hx-post*="/mark-applied"]');
            if (!btn) {
                return {ok: false, status: 0, body: {}, patch_id: null,
                        error: 'No pending patch button found on /patches'};
            }
            const url = btn.getAttribute('hx-post');
            // Extract patch_id from "/patches/{id}/mark-applied"
            const patch_id = url.split('/')[2];
            try {
                const r = await fetch(url, {method: 'POST'});
                const body = await r.json();
                return {ok: r.ok, status: r.status, body: body, patch_id: patch_id};
            } catch (e) {
                return {ok: false, status: 0, body: {}, patch_id: patch_id, error: String(e)};
            }
        }""")

        patch_id = str(response.get("patch_id") or "unknown")
        await self._verifier.verify_signals_patch_applied(ts, patch_id, response)

    async def _certification(self) -> None:
        await self.goto("/certification")
        await self.assert_page_ok()
        await self.wait_htmx()
        await self.page.wait_for_selector(
            "main, h1, h2, body",
            timeout=10_000,
        )
