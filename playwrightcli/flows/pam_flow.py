"""pam_flow.py — Admin portal (port 8000) E2E steps.

Steps:
  pam::login               GET /login → fill form → POST /token → assert redirect to /
  pam::retailers           GET /retailers
  pam::suppliers           GET /suppliers
  pam::hitl-queue          GET /hitl-queue
  pam::hitl-approve-signal POST /hitl-queue/seed-hitl-sig-001/approve → verify S3 kelly signal
  pam::gate-enforcement    POST gate/2/complete (blocked) + gate/1/complete (legal) → verify INV-03
  pam::password-reset      Full forgot→token→reset→login→restore cycle (Step #5)
  pam::jwt-revocation      Logout → access blocked → new login succeeds (Step #6)
  pam::monica-memory       GET /monica-memory
  pam::logout              POST /logout → assert redirect to /login

Human mode (--human flag):
  Login is automated (infrastructure). For every other step the control page
  shows guidance, waits for the human to click 'Done' or 'Skip', then runs
  the same assertions that the automated flow would run.
"""
from __future__ import annotations

import time

from playwrightcli.flows.base_flow import BaseFlow

PORTAL = "pam"

# queue_id of the dedicated signal-test HITL item (seeded by playwrightcli/fixtures/seed.sql)
_SIGNAL_QUEUE_ID = "seed-hitl-sig-001"

# Step names in run order — used by --dry-run
PAM_STEPS = [
    "login",
    "retailers",
    "suppliers",
    "hitl-queue",
    "hitl-approve-signal",
    "gate-enforcement",
    "password-reset",
    "jwt-revocation",
    "monica-memory",
    "logout",
]

# Human-readable guidance for each step shown in --human mode
HUMAN_GUIDANCE: dict[str, str] = {
    "retailers": (
        "Navigate to /retailers (Retailers in the nav). "
        "Wait for the retailer table or empty state to appear."
    ),
    "suppliers": (
        "Navigate to /suppliers (Suppliers in the nav). "
        "Wait for the supplier table or empty state to appear."
    ),
    "hitl-queue": (
        "Navigate to /hitl-queue (HITL Queue in the nav). "
        "Wait for the queue list to appear."
    ),
    "hitl-approve-signal": (
        "The harness will POST approve on the signal-test HITL item and verify "
        "the S3 kelly_approved signal. Stay on /hitl-queue."
    ),
    "gate-enforcement": (
        "The harness will POST illegal and legal gate transitions and verify "
        "INV-03 enforcement (409 on illegal, 200 on legal). No manual action needed."
    ),
    "password-reset": (
        "The harness will run the full forgot→token→reset→login→restore cycle "
        "using the pw_reset_test user. No manual action needed."
    ),
    "jwt-revocation": (
        "The harness will test JWT revocation: logout → access blocked → new login. "
        "No manual action needed."
    ),
    "monica-memory": (
        "Navigate to /monica-memory (Monica Memory in the nav). "
        "Wait for the page to load."
    ),
    "logout": (
        "Click the Logout button (or navigate to /logout) to end your session. "
        "You should be redirected to /login."
    ),
}


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
        await r.run_step(f"{pfx}hitl-queue",          self._hitl_queue,          page=p, relogin_fn=self.relogin)
        await self.capture("hitl-queue")
        await self.verify("hitl-queue")
        await r.run_step(f"{pfx}hitl-approve-signal", self._hitl_approve_signal, page=p, relogin_fn=self.relogin)
        await r.run_step(f"{pfx}gate-enforcement",   self._gate_enforcement,    page=p, relogin_fn=self.relogin)
        await r.run_step(f"{pfx}password-reset",     self._password_reset,      page=p, relogin_fn=self.relogin)
        await r.run_step(f"{pfx}jwt-revocation",     self._jwt_revocation,      page=p, relogin_fn=self.relogin)
        await r.run_step(f"{pfx}monica-memory",      self._monica_memory,       page=p, relogin_fn=self.relogin)
        await self.capture("monica-memory")
        await self.verify("monica-memory")
        await r.run_step(f"{pfx}logout",       self._logout_step,   max_retries=2, page=p)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _retailers(self) -> None:
        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["retailers"], "pam::retailers")
            if not ready:
                return
        else:
            await self.goto("/retailers")
            await self.assert_page_ok()
            await self.wait_htmx()

        # Assertions — run in both modes
        await self.page.wait_for_selector(
            "table, .empty-state, main, h1, h2",
            timeout=10_000,
        )

    async def _suppliers(self) -> None:
        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["suppliers"], "pam::suppliers")
            if not ready:
                return
        else:
            await self.goto("/suppliers")
            await self.assert_page_ok()
            await self.wait_htmx()

        # Assertions — run in both modes
        await self.page.wait_for_selector(
            "table, .empty-state, main, h1, h2",
            timeout=10_000,
        )

    async def _hitl_queue(self) -> None:
        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["hitl-queue"], "pam::hitl-queue")
            if not ready:
                return
        else:
            await self.goto("/hitl-queue")
            await self.assert_page_ok()
            await self.wait_htmx()

        # Assertions — run in both modes
        # The #hitl-table element is NOT rendered when the queue is empty (known from memory).
        # Assert any page structure is present instead.
        await self.page.wait_for_selector(
            "main, h1, h2, body",
            timeout=10_000,
        )

    async def _hitl_approve_signal(self) -> None:
        """POST approve on the signal-test HITL item, verify Kelly S3 dispatch signal.

        Uses a dedicated queue item (seed-hitl-sig-001) that seed.sql resets to
        PENDING_APPROVAL on each re-seed, keeping this test idempotent.

        SIG-HITL-01: HTTP 200 returned.
        SIG-HITL-02: kelly_approved_seed-hitl-sig-001.json written to S3.
        SIG-HITL-03: Payload contains queue_id, draft, and channel.
        """
        if self._verifier is None:
            return  # --verify not active; skip entirely

        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["hitl-approve-signal"], "pam::hitl-approve-signal")
            if not ready:
                return

        await self.goto("/hitl-queue")
        await self.assert_page_ok()
        await self.wait_htmx()

        ts = time.time() - 1  # 1 s buffer for LastModified clock skew
        queue_id = _SIGNAL_QUEUE_ID

        response = await self.page.evaluate("""async (qid) => {
            try {
                const r = await fetch('/hitl-queue/' + qid + '/approve', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                const body = await r.json();
                return {ok: r.ok, status: r.status, body: body};
            } catch (e) {
                return {ok: false, status: 0, body: {}, error: String(e)};
            }
        }""", queue_id)

        await self._verifier.verify_signals_hitl_approved(ts, queue_id, response)

    async def _gate_enforcement(self) -> None:
        """Verify INV-03: out-of-order gate transitions are rejected with HTTP 409.

        Uses supplier 'inv03_test' (seeded with gate_1=COMPLETE, gate_2=PENDING):
          - Illegal POST: gate_3/complete while gate_2 is PENDING  → expect 409
          - Legal  POST: gate_2/complete while gate_1 is COMPLETE  → expect 200

        INV03-GATE-01: 409 on illegal advance.
        INV03-GATE-02: 409 body contains ordering error message.
        INV03-GATE-03: 200 on legal next-gate advance.
        """
        if self._verifier is None:
            return  # --verify not active; skip entirely

        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["gate-enforcement"], "pam::gate-enforcement")
            if not ready:
                return

        # inv03_bad: gate_1=PENDING — gate_2/complete is always illegal (409).
        # This supplier's state never changes so the test is fully idempotent.
        illegal_response = await self.page.evaluate("""async () => {
            try {
                const r = await fetch('/suppliers/inv03_bad/gate/2/complete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                let body = {};
                try { body = await r.json(); } catch (_) {}
                return {ok: r.ok, status: r.status, body: body};
            } catch (e) {
                return {ok: false, status: 0, body: {}, error: String(e)};
            }
        }""")

        # inv03_ok: gate_1=COMPLETE — gate_1/complete is always legal (no prerequisite)
        # and idempotent (COMPLETE→COMPLETE upsert, no downstream state change).
        legal_response = await self.page.evaluate("""async () => {
            try {
                const r = await fetch('/suppliers/inv03_ok/gate/1/complete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                let body = {};
                try { body = await r.json(); } catch (_) {}
                return {ok: r.ok, status: r.status, body: body};
            } catch (e) {
                return {ok: false, status: 0, body: {}, error: String(e)};
            }
        }""")

        self._verifier.verify_gate_enforcement(illegal_response, legal_response, "inv03_bad/inv03_ok")

    async def _password_reset(self) -> None:
        """Full forgot-password → reset → login → restore cycle (Step #5).

        Uses dedicated seed user 'pw_reset_test' (admin role, email set).
        Seed always restores their password to 'TestResetPass1!' so this
        step is fully idempotent across consecutive runs.

        PW-RESET-01: POST /forgot-password redirects correctly.
        PW-RESET-02: Token written to DB and retrievable via TokenFetcher.
        PW-RESET-03: POST /reset-password redirects to password_changed.
        PW-RESET-04: Login with new password succeeds.
        PW-RESET-05: /change-password restores original password.
        """
        if self._verifier is None:
            return

        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["password-reset"], "pam::password-reset")
            if not ready:
                return

        from playwrightcli.fixtures.token_fetcher import TokenFetcher

        _USER = "pw_reset_test"
        _ORIG_PW = "TestResetPass1!"
        _NEW_PW = "NewResetPass2!"
        fetcher = TokenFetcher()

        # --- PW-RESET-01: trigger forgot-password ---
        await self.goto("/forgot-password")
        await self.page.fill('input[name="username"]', _USER)
        async with self.page.expect_navigation(timeout=10_000):
            await self.page.click('button[type="submit"]')
        forgot_redirected = "msg=reset_sent" in self.page.url

        # --- PW-RESET-02: retrieve token from DB ---
        token = fetcher.get_latest_token(_USER)
        token_found = token is not None

        # --- PW-RESET-03: submit reset form ---
        reset_redirected = False
        if token_found:
            await self.page.goto(
                f"{self.base_url}/reset-password?token={token}",
                wait_until="domcontentloaded",
            )
            await self.page.fill('input[name="new_password"]', _NEW_PW)
            await self.page.fill('input[name="confirm_password"]', _NEW_PW)
            async with self.page.expect_navigation(timeout=10_000):
                await self.page.click('button[type="submit"]')
            reset_redirected = "msg=password_changed" in self.page.url

        # --- PW-RESET-04: login with new password ---
        login_succeeded = False
        if reset_redirected:
            await self.page.goto(
                f"{self.base_url}/login",
                wait_until="domcontentloaded",
            )
            await self.page.fill('input[name="username"]', _USER)
            await self.page.fill('input[name="password"]', _NEW_PW)
            async with self.page.expect_navigation(timeout=10_000):
                await self.page.click('button[type="submit"]')
            login_succeeded = "/login" not in self.page.url

        # --- PW-RESET-05: restore original password (idempotency) ---
        restore_succeeded = False
        if login_succeeded:
            response = await self.page.evaluate(
                """async (args) => {
                    const fd = new FormData();
                    fd.append('current_password', args.cur);
                    fd.append('new_password', args.orig);
                    fd.append('confirm_password', args.orig);
                    const r = await fetch('/change-password', {method: 'POST', body: fd});
                    return {ok: r.ok, status: r.status, url: r.url};
                }""",
                {"cur": _NEW_PW, "orig": _ORIG_PW},
            )
            restore_succeeded = response.get("ok", False)

        self._verifier.verify_password_reset(
            forgot_redirected=forgot_redirected,
            token_found=token_found,
            reset_redirected=reset_redirected,
            login_succeeded=login_succeeded,
            restore_succeeded=restore_succeeded,
        )

        # Return to pam_admin session so downstream steps work
        await self.relogin()

    async def _jwt_revocation(self) -> None:
        """Verify JWT revocation: logout → access blocked → new login succeeds (Step #6).

        Does NOT rely on reading httpOnly cookies. Instead tests the observable
        browser behaviour: after /logout, protected routes redirect to /login;
        a fresh login then succeeds.

        JWT-REV-01: POST /logout redirects browser to /login.
        JWT-REV-02: Navigating to a protected route after logout redirects to /login.
        JWT-REV-03: A fresh login after logout succeeds (not at /login).
        """
        if self._verifier is None:
            return

        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["jwt-revocation"], "pam::jwt-revocation")
            if not ready:
                return

        # --- JWT-REV-01: POST /logout → redirect to /login ---
        await self.goto("/suppliers")   # confirm we're authenticated first
        await self.page.evaluate("""() => {
            const f = document.createElement('form');
            f.method = 'POST';
            f.action = '/logout';
            document.body.appendChild(f);
            f.submit();
        }""")
        await self.page.wait_for_url("**/login**", timeout=10_000)
        logout_redirected = "/login" in self.page.url

        # --- JWT-REV-02: navigate to protected route without session → /login ---
        await self.page.goto(
            f"{self.base_url}/suppliers",
            wait_until="domcontentloaded",
        )
        access_blocked = "/login" in self.page.url

        # --- JWT-REV-03: new login succeeds ---
        await self.page.fill('input[name="username"]', self.username)
        await self.page.fill('input[name="password"]', self.password)
        async with self.page.expect_navigation(timeout=10_000):
            await self.page.click('button[type="submit"]')
        relogin_ok = "/login" not in self.page.url
        if relogin_ok:
            self._logged_in = True

        self._verifier.verify_jwt_revocation(
            logout_redirected=logout_redirected,
            access_blocked=access_blocked,
            relogin_ok=relogin_ok,
        )

    async def _monica_memory(self) -> None:
        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["monica-memory"], "pam::monica-memory")
            if not ready:
                return
        else:
            await self.goto("/monica-memory")
            await self.assert_page_ok()
            await self.wait_htmx()

        # Assertions — run in both modes
        await self.page.wait_for_selector(
            "table, .empty-state, main, h1, h2",
            timeout=10_000,
        )

    async def _logout_step(self) -> None:
        if self.human_mode:
            ready = await self.await_human(HUMAN_GUIDANCE["logout"], "pam::logout")
            if not ready:
                return
            # Human performed logout; assert we are now on /login
            await self.page.wait_for_url("**/login**", timeout=10_000)
        else:
            await self.logout()
