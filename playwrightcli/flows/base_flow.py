"""base_flow.py — Shared Playwright helpers for all three portal flows.

Provides: login(), logout(), goto(), wait_htmx(), detect_page_error(),
          assert_page_ok(), relogin() (used as runner correction callback),
          capture() (pushes screenshot to observer queue),
          await_human() (human-in-the-loop step prompt).
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from playwrightcli.config import TIMEOUTS

if TYPE_CHECKING:
    from playwrightcli.observer import ObserverFrame
    from playwrightcli.requirements_verifier import RequirementsVerifier


class BaseFlow:
    """Base class for PamFlow, MeredithFlow, ChrissyFlow."""

    def __init__(
        self,
        page,
        config: dict,
        runner,
        *,
        observer_queue: asyncio.Queue | None = None,
        verifier: RequirementsVerifier | None = None,
        human_mode: bool = False,
    ) -> None:
        self.page = page
        self.config = config
        self.runner = runner
        self.base_url: str = config["url"].rstrip("/")
        self.username: str = config["username"]
        self.password: str = config["password"]
        self._logged_in: bool = False
        self._observer_queue = observer_queue
        self._verifier = verifier
        self._portal: str = config.get("role", "unknown")
        self.human_mode: bool = human_mode

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def login(self) -> None:
        """Navigate to /login, fill credentials, assert redirect to /."""
        await self.page.goto(
            f"{self.base_url}/login",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        await self.page.fill('input[name="username"]', self.username)
        await self.page.fill('input[name="password"]', self.password)

        async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
            await self.page.click('button[type="submit"]')

        url = self.page.url
        if "error=" in url:
            raise AssertionError(
                f"Login failed — credentials rejected. URL: {url}. "
                f"Check config.py username/password for {self.config.get('role', '?')}"
            )
        if "/login" in url:
            raise AssertionError(f"Login did not redirect away from /login. URL: {url}")

        self._logged_in = True

    async def logout(self) -> None:
        """POST /logout via JS form submission; assert redirect to /login."""
        # Submit a dynamically created form — works regardless of template structure.
        await self.page.evaluate(
            """() => {
                const f = document.createElement('form');
                f.method = 'POST';
                f.action = '/logout';
                document.body.appendChild(f);
                f.submit();
            }"""
        )
        await self.page.wait_for_url(
            f"**/login**",
            timeout=TIMEOUTS["navigation"],
        )
        self._logged_in = False

    async def relogin(self) -> None:
        """Re-authenticate — used as a StepRunner correction callback for session expiry."""
        self._logged_in = False
        await self.login()

    # ------------------------------------------------------------------
    # Human-in-the-loop prompt
    # ------------------------------------------------------------------

    async def await_human(self, guidance: str, step_name: str = "") -> bool:
        """Pause for human action via the localhost control page.

        Calls human_control.get_server() (lazy import — only active in
        --human mode), updates the displayed step, and waits for the user
        to click "Done, advance" or "Skip" in their browser.

        Returns True to advance, False to skip.
        """
        from playwrightcli.human_control import get_server
        srv = get_server()
        srv.set_step(
            step_name=step_name,
            guidance=guidance,
            portal=self._portal,
            portal_url=self.base_url,
        )
        print(f"  [human] {step_name} — act in browser, then click 'Done' at http://localhost:{srv.port}")
        return await srv.wait_for_advance()

    # ------------------------------------------------------------------
    # Observer — real-time screenshot capture
    # ------------------------------------------------------------------

    async def capture(self, step: str) -> None:
        """Take a full-page screenshot and push to the observer queue.

        No-op if observer mode is not active (queue is None).
        Called by each flow after navigating + waiting for HTMX to settle.
        """
        if self._observer_queue is None:
            return

        from playwrightcli.observer import ObserverFrame

        png_bytes = await self.page.screenshot(full_page=True)

        # Map role -> portal name for consistent naming
        portal_name_map = {"admin": "pam", "retailer": "meredith", "supplier": "chrissy"}
        portal = portal_name_map.get(self._portal, self._portal)

        frame = ObserverFrame(
            portal=portal,
            step=step,
            png_bytes=png_bytes,
            url=self.page.url,
        )
        await self._observer_queue.put(frame)

    # ------------------------------------------------------------------
    # Requirements verification
    # ------------------------------------------------------------------

    async def verify(self, step: str) -> None:
        """Run business requirement checks on the current page.

        No-op if --verify mode is not active (verifier is None).
        Called by each flow after navigating + waiting for HTMX to settle.
        """
        if self._verifier is None:
            return

        # Map role -> portal name for consistent step keys
        portal_name_map = {"admin": "pam", "retailer": "meredith", "supplier": "chrissy"}
        portal = portal_name_map.get(self._portal, self._portal)
        await self._verifier.verify(f"{portal}::{step}", self.page)

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    async def goto(self, path: str) -> None:
        """Navigate to a portal path and wait for DOM content."""
        await self.page.goto(
            f"{self.base_url}{path}",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )

    async def wait_htmx(self) -> None:
        """Wait for HTMX async swaps to settle (networkidle)."""
        await self.page.wait_for_load_state(
            "networkidle",
            timeout=TIMEOUTS["networkidle"],
        )

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    async def assert_page_ok(self) -> None:
        """Fail if we hit /login (session expired) or a 5xx error page."""
        url = self.page.url
        if "/login" in url and self._logged_in:
            raise AssertionError(
                f"Redirected to /login mid-flow — session expired. URL: {url}"
            )
        # Detect 5xx by page title (FastAPI renders "Internal Server Error")
        try:
            title = await self.page.title()
            if "500" in title or "internal server error" in title.lower():
                raise AssertionError(f"Portal returned a 500 error page (title: {title!r})")
        except Exception as exc:
            if "AssertionError" in type(exc).__name__:
                raise
            # page.title() can fail on blank pages; not fatal

    def detect_page_error(self) -> str | None:
        """Return error description if URL contains error indicators, else None."""
        url = self.page.url
        if "error=" in url:
            return f"URL contains error param: {url}"
        return None
