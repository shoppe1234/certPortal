"""base_flow.py — Shared Playwright helpers for all three portal flows.

Provides: login(), logout(), goto(), wait_htmx(), detect_page_error(),
          assert_page_ok(), relogin() (used as runner correction callback).
"""
from __future__ import annotations

from playwrightcli.config import TIMEOUTS


class BaseFlow:
    """Base class for PamFlow, MeredithFlow, ChrissyFlow."""

    def __init__(self, page, config: dict, runner) -> None:
        self.page = page
        self.config = config
        self.runner = runner
        self.base_url: str = config["url"].rstrip("/")
        self.username: str = config["username"]
        self.password: str = config["password"]
        self._logged_in: bool = False

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
