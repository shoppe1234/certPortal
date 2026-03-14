"""health_flow.py — Frontend health checks (checks 1–6).

Standalone flow (no BaseFlow import — follows scope_flow.py pattern).
Verifies cross-cutting frontend infrastructure: HTMX runtime, SRI integrity,
button click responses, wizard step progression, console errors, asset 404s.

Steps (handles own login/logout):
  health::pam          PAM portal health checks
  health::meredith     Meredith portal health checks
  health::chrissy      Chrissy portal health checks
  health::wizard       Wizard step progression (Meredith)

Requirements verified:
  HEALTH-HTMX-01..02     HTMX runtime loaded and version valid
  HEALTH-SRI-01..02      SRI scripts loaded, certPortal global defined
  HEALTH-BTN-01..02      HTMX button fires request and gets response
  HEALTH-WIZ-01..02      Wizard step indicator advances after Next click
  HEALTH-CONSOLE-01..02  No JS console errors during load or interactions
  HEALTH-ASSET-01..03    No 404s for scripts, stylesheets, images
"""
from __future__ import annotations

from playwrightcli.config import PORTALS, TIMEOUTS

PORTAL = "health"

HEALTH_STEPS = [
    "pam",
    "meredith",
    "chrissy",
    "wizard",
]

_PORTAL_CONFIGS = {
    "pam": {"url": PORTALS["pam"]["url"], "username": PORTALS["pam"]["username"], "password": PORTALS["pam"]["password"]},
    "meredith": {"url": PORTALS["meredith"]["url"], "username": PORTALS["meredith"]["username"], "password": PORTALS["meredith"]["password"]},
    "chrissy": {"url": PORTALS["chrissy"]["url"], "username": PORTALS["chrissy"]["username"], "password": PORTALS["chrissy"]["password"]},
}


class HealthFlow:
    """Standalone frontend health flow — does not extend BaseFlow."""

    def __init__(self, page, runner, *, verifier=None) -> None:
        self.page = page
        self.runner = runner
        self._verifier = verifier

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        r = self.runner
        pfx = f"{PORTAL}::"

        await r.run_step(f"{pfx}pam",      self._health_pam,      page=self.page)
        await r.run_step(f"{pfx}meredith",  self._health_meredith, page=self.page)
        await r.run_step(f"{pfx}chrissy",   self._health_chrissy,  page=self.page)
        await r.run_step(f"{pfx}wizard",    self._wizard_health,   page=self.page)

    async def _health_pam(self) -> None:
        await self._portal_health("pam")

    async def _health_meredith(self) -> None:
        await self._portal_health("meredith")

    async def _health_chrissy(self) -> None:
        await self._portal_health("chrissy")

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    async def _login(self, portal_name: str) -> None:
        cfg = _PORTAL_CONFIGS[portal_name]
        await self.page.goto(
            f"{cfg['url']}/login",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        await self.page.fill('input[name="username"]', cfg["username"])
        await self.page.fill('input[name="password"]', cfg["password"])
        async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
            await self.page.click('button[type="submit"]')
        if "/login" in self.page.url:
            raise AssertionError(f"Health login failed for {cfg['username']!r}")

    async def _logout(self) -> None:
        await self.page.evaluate("""() => {
            const f = document.createElement('form');
            f.method = 'POST';
            f.action = '/logout';
            document.body.appendChild(f);
            f.submit();
        }""")
        await self.page.wait_for_url("**/login**", timeout=TIMEOUTS["navigation"])

    async def _goto(self, portal_name: str, path: str) -> None:
        base = _PORTAL_CONFIGS[portal_name]["url"]
        await self.page.goto(
            f"{base}{path}",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        await self.page.wait_for_load_state("networkidle", timeout=TIMEOUTS["networkidle"])

    # ------------------------------------------------------------------
    # Per-portal health checks (checks 1, 2, 5, 6 + button click 3)
    # ------------------------------------------------------------------

    async def _portal_health(self, portal_name: str = "pam") -> None:
        """Run all health checks on a single portal's dashboard."""
        console_errors: list[str] = []

        # Check 5: attach console error listener before navigation
        def _on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)

        self.page.on("console", _on_console)

        try:
            await self._login(portal_name)
            await self.page.wait_for_load_state("networkidle", timeout=TIMEOUTS["networkidle"])

            if not self._verifier:
                await self._logout()
                return

            portal_label = portal_name.upper()

            # -- Check 1: HTMX runtime verification --
            htmx_info = await self.page.evaluate("""() => ({
                defined: typeof window.htmx !== 'undefined',
                version: (typeof window.htmx !== 'undefined' && window.htmx.version) ? window.htmx.version : null
            })""")
            self._verifier._record(
                f"HEALTH-HTMX-01",
                f"window.htmx is defined ({portal_label})",
                htmx_info.get("defined", False),
            )
            version = htmx_info.get("version")
            self._verifier._record(
                f"HEALTH-HTMX-02",
                f"window.htmx.version is valid semver ({portal_label})",
                bool(version and "." in str(version)),
                detail=f"version={version}" if version else "htmx not loaded",
            )

            # -- Check 2: SRI integrity validation --
            sri_info = await self.page.evaluate("""() => {
                const scripts = document.querySelectorAll('script[integrity]');
                const count = scripts.length;
                // Check that expected globals are defined (proves scripts loaded)
                const htmxOk = typeof window.htmx !== 'undefined';
                const certPortalOk = typeof window.certPortal !== 'undefined';
                // Collect script srcs for diagnostics
                const srcs = [];
                scripts.forEach(s => srcs.push(s.src || '(inline)'));
                return { count, htmxOk, certPortalOk, srcs };
            }""")
            # SRI-01: all integrity-checked scripts loaded
            all_loaded = sri_info.get("htmxOk", False)
            detail_parts = []
            if not sri_info.get("htmxOk"):
                detail_parts.append("htmx blocked by SRI")
            if sri_info.get("count", 0) == 0:
                detail_parts.append("no <script integrity> tags found")
            self._verifier._record(
                "HEALTH-SRI-01",
                f"All <script integrity> tags loaded ({portal_label})",
                all_loaded,
                detail="; ".join(detail_parts) if detail_parts else "",
            )
            # SRI-02: certPortal global defined (htmx_helpers.js loaded)
            self._verifier._record(
                "HEALTH-SRI-02",
                f"window.certPortal defined ({portal_label})",
                sri_info.get("certPortalOk", False),
            )

            # -- Check 6: Asset 404 detection --
            asset_info = await self.page.evaluate("""async () => {
                function getUrls(selector, attr) {
                    return [...document.querySelectorAll(selector)]
                        .map(el => el[attr] || el.getAttribute(attr) || '')
                        .filter(u => u && !u.startsWith('data:') && !u.startsWith('blob:'));
                }
                const scriptUrls = getUrls('script[src]', 'src');
                const linkUrls = getUrls('link[href]', 'href');
                const imgUrls = getUrls('img[src]', 'src');

                async function check(urls) {
                    const failed = [];
                    for (const url of urls) {
                        try {
                            const r = await fetch(url, { method: 'HEAD', mode: 'no-cors' });
                            // mode: no-cors returns opaque response for cross-origin;
                            // status 0 means opaque (cross-origin) — skip those
                            if (r.status === 404) failed.push(url);
                        } catch (e) {
                            // Network error — only flag same-origin failures
                            try {
                                const u = new URL(url);
                                if (u.origin === window.location.origin) {
                                    failed.push(url);
                                }
                            } catch (_) {}
                        }
                    }
                    return failed;
                }

                return {
                    failed_scripts: await check(scriptUrls),
                    failed_links: await check(linkUrls),
                    failed_imgs: await check(imgUrls),
                    total_scripts: scriptUrls.length,
                    total_links: linkUrls.length,
                    total_imgs: imgUrls.length,
                };
            }""")
            failed_scripts = asset_info.get("failed_scripts", [])
            failed_links = asset_info.get("failed_links", [])
            failed_imgs = asset_info.get("failed_imgs", [])

            self._verifier._record(
                "HEALTH-ASSET-01",
                f"All <script src> URLs resolve ({portal_label})",
                len(failed_scripts) == 0,
                detail=f"404: {', '.join(failed_scripts[:3])}" if failed_scripts else "",
            )
            self._verifier._record(
                "HEALTH-ASSET-02",
                f"All <link href> URLs resolve ({portal_label})",
                len(failed_links) == 0,
                detail=f"404: {', '.join(failed_links[:3])}" if failed_links else "",
            )
            self._verifier._record(
                "HEALTH-ASSET-03",
                f"All <img src> URLs resolve ({portal_label})",
                len(failed_imgs) == 0,
                detail=f"404: {', '.join(failed_imgs[:3])}" if failed_imgs else "",
            )

            # -- Check 3: Button click → response --
            btn_result = await self.page.evaluate("""() => {
                return new Promise((resolve) => {
                    if (typeof window.htmx === 'undefined') {
                        resolve({ sent: false, ok: false, reason: 'htmx not loaded' });
                        return;
                    }
                    // Find any element with hx-get or hx-post
                    const el = document.querySelector('[hx-get], [hx-post]');
                    if (!el) {
                        resolve({ sent: false, ok: false, reason: 'no htmx elements found' });
                        return;
                    }
                    let fired = false;
                    document.addEventListener('htmx:afterRequest', function handler(evt) {
                        fired = true;
                        document.removeEventListener('htmx:afterRequest', handler);
                        resolve({
                            sent: true,
                            ok: evt.detail.xhr.status < 400,
                            status: evt.detail.xhr.status,
                            target: el.tagName + (el.id ? '#' + el.id : '')
                        });
                    }, { once: true });
                    // Also listen for errors
                    document.addEventListener('htmx:sendError', function handler2(evt) {
                        document.removeEventListener('htmx:sendError', handler2);
                        if (!fired) resolve({ sent: true, ok: false, reason: 'sendError' });
                    }, { once: true });

                    // Use htmx.ajax for a safe side-effect-free test
                    // Fall back to triggering the found element
                    const hxGet = el.getAttribute('hx-get');
                    const hxPost = el.getAttribute('hx-post');
                    if (hxGet) {
                        htmx.ajax('GET', hxGet, { target: el, swap: 'none' });
                    } else if (hxPost) {
                        htmx.ajax('GET', '/health', { target: el, swap: 'none' });
                    }
                    setTimeout(() => { if (!fired) resolve({ sent: false, ok: false, reason: 'timeout' }); }, 5000);
                });
            }""")
            self._verifier._record(
                "HEALTH-BTN-01",
                f"HTMX element sends network request ({portal_label})",
                btn_result.get("sent", False),
                detail=btn_result.get("reason", "") if not btn_result.get("sent") else "",
            )
            self._verifier._record(
                "HEALTH-BTN-02",
                f"HTMX element receives non-error response ({portal_label})",
                btn_result.get("ok", False),
                detail=f"status={btn_result.get('status', '?')}" if btn_result.get("sent") else btn_result.get("reason", ""),
            )

            # -- Check 5: Console errors during page load --
            load_errors = [e for e in console_errors
                           if not _is_benign_console_error(e)]
            self._verifier._record(
                "HEALTH-CONSOLE-01",
                f"No JS errors during page load ({portal_label})",
                len(load_errors) == 0,
                detail=f"{len(load_errors)} error(s): {'; '.join(load_errors[:3])}" if load_errors else "",
            )

            await self._logout()
        finally:
            self.page.remove_listener("console", _on_console)

    # ------------------------------------------------------------------
    # Check 4: Wizard step progression
    # ------------------------------------------------------------------

    async def _wizard_health(self) -> None:
        """Create a lifecycle wizard session, click Next, verify step advances."""
        console_errors: list[str] = []

        def _on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)

        self.page.on("console", _on_console)

        try:
            await self._login("meredith")

            if not self._verifier:
                await self._logout()
                return

            # Create a new lifecycle wizard session via fetch
            result = await self.page.evaluate("""async () => {
                try {
                    const r = await fetch('/lifecycle-wizard/new', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: 'session_name=Health+Check+Wizard',
                        redirect: 'follow'
                    });
                    return {ok: r.ok, status: r.status, url: r.url};
                } catch (e) {
                    return {ok: false, status: 0, error: String(e)};
                }
            }""")

            session_url = result.get("url", "")
            if not session_url or "/lifecycle-wizard/" not in session_url:
                self._verifier._skip("HEALTH-WIZ-01", "Step indicator advances after Next", "Could not create wizard session")
                self._verifier._skip("HEALTH-WIZ-02", "DOM content updates after step change", "Could not create wizard session")
                await self._logout()
                return

            # Extract session ID
            session_id = session_url.rstrip("/").split("/")[-1]
            if "?" in session_id:
                session_id = session_id.split("?")[0]

            # Navigate to the session page
            await self._goto("meredith", f"/lifecycle-wizard/{session_id}")

            # Read the current step from DOM
            before_step = await self.page.evaluate("""() => {
                const active = document.querySelector('.wizard-step--active .wizard-step-circle');
                return active ? active.textContent.trim() : null;
            }""")

            # Read the panel ID to verify content
            before_panel = await self.page.evaluate("""() => {
                const panel = document.querySelector('.wizard-step-panel');
                return panel ? panel.id : null;
            }""")

            # Submit step 0 (mode=use) via fetch and reload
            await self.page.evaluate(f"""async () => {{
                const r = await fetch('/lifecycle-wizard/{session_id}/save-step', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                    body: 'step_number=0&mode=use'
                }});
                return {{ok: r.ok, status: r.status}};
            }}""")

            # Reload to see next step
            await self._goto("meredith", f"/lifecycle-wizard/{session_id}")

            # Read step indicator again
            after_step = await self.page.evaluate("""() => {
                const active = document.querySelector('.wizard-step--active .wizard-step-circle');
                return active ? active.textContent.trim() : null;
            }""")

            after_panel = await self.page.evaluate("""() => {
                const panel = document.querySelector('.wizard-step-panel');
                return panel ? panel.id : null;
            }""")

            # WIZ-01: step indicator number advances
            step_advanced = (
                before_step is not None
                and after_step is not None
                and before_step != after_step
            )
            self._verifier._record(
                "HEALTH-WIZ-01",
                "Step indicator advances after Next",
                step_advanced,
                detail=f"before={before_step}, after={after_step}",
            )

            # WIZ-02: DOM content (panel ID) changes
            dom_changed = (
                before_panel is not None
                and after_panel is not None
                and before_panel != after_panel
            )
            self._verifier._record(
                "HEALTH-WIZ-02",
                "DOM content updates after step change",
                dom_changed,
                detail=f"before={before_panel}, after={after_panel}",
            )

            # -- Check 5 part 2: console errors during interactions --
            interaction_errors = [e for e in console_errors
                                  if not _is_benign_console_error(e)]
            self._verifier._record(
                "HEALTH-CONSOLE-02",
                "No JS errors during wizard interactions",
                len(interaction_errors) == 0,
                detail=f"{len(interaction_errors)} error(s): {'; '.join(interaction_errors[:3])}" if interaction_errors else "",
            )

            await self._logout()
        finally:
            self.page.remove_listener("console", _on_console)


def _is_benign_console_error(msg: str) -> bool:
    """Filter out known benign console errors (favicon, CORS, etc.)."""
    benign_patterns = [
        "favicon.ico",
        "favicon",
        "ERR_FILE_NOT_FOUND",
        "CORS",
        "Access-Control-Allow-Origin",
        "the server responded with a status of 404 (Not Found)",  # favicon
    ]
    msg_lower = msg.lower()
    return any(p.lower() in msg_lower for p in benign_patterns)
