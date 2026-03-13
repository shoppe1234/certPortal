"""server.py — Localhost HTTP control server for human-in-the-loop runs.

Architecture:
  - ControlServer owns all mutable state (current step, threading primitives).
  - _Handler is a stateless BaseHTTPRequestHandler; it reaches back to
    ControlServer via self.server._ctrl (attached at start() time).
  - The HTTPServer runs in a daemon thread so it never blocks shutdown.
  - wait_for_advance() bridges back to asyncio via asyncio.to_thread(),
    keeping the Playwright event loop alive while the human acts.

Thread safety:
  - _lock guards all mutable fields written by set_step() and signal_advance().
  - _event is cleared inside set_step() (under the lock) before returning,
    so no race window exists between set_step() and wait_for_advance().
"""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from playwrightcli.human_control._page import render_page


class _Handler(BaseHTTPRequestHandler):
    """HTTP request handler.  self.server is the HTTPServer instance;
    self.server._ctrl is the ControlServer."""

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # suppress default access log noise

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._serve_page()
        elif self.path == "/status":
            self._serve_status()
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_page(self) -> None:
        ctrl: ControlServer = self.server._ctrl  # type: ignore[attr-defined]
        with ctrl._lock:
            html = render_page(
                step=ctrl.current_step,
                guidance=ctrl.current_guidance,
                portal=ctrl.current_portal,
                port=ctrl.port,
                portal_url=ctrl.portal_url,
                step_id=ctrl.step_id,
            )
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_status(self) -> None:
        ctrl: ControlServer = self.server._ctrl  # type: ignore[attr-defined]
        with ctrl._lock:
            data = {
                "step": ctrl.current_step,
                "guidance": ctrl.current_guidance,
                "portal": ctrl.current_portal,
                "step_id": ctrl.step_id,
                "waiting": not ctrl._event.is_set(),
            }
        self._send_json(data)

    # ------------------------------------------------------------------
    # POST
    # ------------------------------------------------------------------

    def do_POST(self) -> None:
        ctrl: ControlServer = self.server._ctrl  # type: ignore[attr-defined]
        if self.path == "/advance":
            ctrl.signal_advance(skip=False)
            self._send_json({"action": "advance", "step": ctrl.current_step})
        elif self.path == "/skip":
            ctrl.signal_advance(skip=True)
            self._send_json({"action": "skip", "step": ctrl.current_step})
        else:
            self.send_response(404)
            self.end_headers()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _send_json(self, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ControlServer:
    """Singleton HTTP server that holds human-in-the-loop step state.

    Lifecycle (managed by human_control/__init__.py):
        server = ControlServer(port=9999)
        server.start()                          # spawns daemon thread
        ...
        server.set_step(name, guidance, portal, portal_url)
        advanced = await server.wait_for_advance()  # True=advance, False=skip
        ...
        server.stop()                           # shuts down socket
    """

    def __init__(self, port: int = 9999) -> None:
        self.port = port

        # Protected by _lock
        self.current_step: str = ""
        self.current_guidance: str = "Waiting for run to start…"
        self.current_portal: str = ""
        self.portal_url: str = ""
        self.step_id: int = 0       # monotonic counter; JS compares to detect changes
        self._result: str = ""      # "advance" | "skip"

        self._lock = threading.Lock()
        self._event = threading.Event()

        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Bind the socket and start the daemon thread."""
        self._httpd = HTTPServer(("127.0.0.1", self.port), _Handler)
        self._httpd._ctrl = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            daemon=True,
            name="human-control-server",
        )
        self._thread.start()

    def stop(self) -> None:
        """Shutdown the server and release the socket."""
        if self._httpd is not None:
            self._httpd.shutdown()   # blocks until serve_forever() returns
            self._httpd.server_close()
            self._httpd = None
        self._thread = None

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def set_step(
        self,
        step_name: str,
        guidance: str,
        portal: str = "",
        portal_url: str = "",
    ) -> None:
        """Update the displayed step and reset the advance signal.

        The event is cleared here (under the lock) so there is no race
        window between this call and wait_for_advance().
        """
        with self._lock:
            self.current_step = step_name
            self.current_guidance = guidance
            self.current_portal = portal
            self.portal_url = portal_url
            self.step_id += 1
            self._result = ""
            self._event.clear()

    def signal_advance(self, skip: bool = False) -> None:
        """Called by the HTTP handler when the user clicks advance or skip."""
        with self._lock:
            self._result = "skip" if skip else "advance"
            self._event.set()

    # ------------------------------------------------------------------
    # Async wait
    # ------------------------------------------------------------------

    async def wait_for_advance(self) -> bool:
        """Async-safe wait.  Returns True=advance, False=skip.

        Uses asyncio.to_thread() (Python 3.9+) to block in a thread pool
        without stalling the Playwright event loop.
        """
        await asyncio.to_thread(self._event.wait)
        with self._lock:
            return self._result != "skip"
