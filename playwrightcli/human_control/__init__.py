"""human_control — localhost control page for human-in-the-loop Playwright runs.

Replaces stdin input() with a browser UI on http://localhost:9999.
The page shows the current step guidance and two buttons:
  "Done, advance"  — POST /advance → harness proceeds
  "Skip this step" — POST /skip    → harness skips assertions for this step

Public API
----------
start_server(port=9999) -> ControlServer
    Start the HTTP server (idempotent — safe to call multiple times).

stop_server() -> None
    Shutdown the server and release the socket.

get_server() -> ControlServer
    Return the running singleton (or create one if not yet started).

Integration points (see base_flow.await_human and cli.main):
    # cli.py — wrap the run:
        ctrl = start_server()
        try:
            asyncio.run(_run_portal(...))
        finally:
            stop_server()

    # base_flow.await_human — per step:
        from playwrightcli.human_control import get_server
        srv = get_server()
        srv.set_step(step_name, guidance, portal, portal_url)
        return await srv.wait_for_advance()

Isolation: this module uses only Python stdlib + playwrightcli.human_control
internals. No imports from certportal/, portals/, or agents/.
"""
from __future__ import annotations

from playwrightcli.human_control.server import ControlServer

CONTROL_PORT: int = 9999

_server: ControlServer | None = None


def get_server() -> ControlServer:
    """Return the singleton ControlServer, creating it if needed.

    Does NOT start the HTTP server — call start_server() for that.
    """
    global _server
    if _server is None:
        _server = ControlServer(port=CONTROL_PORT)
    return _server


def start_server(port: int = CONTROL_PORT) -> ControlServer:
    """Start the HTTP server on *port* (idempotent).

    Returns the running ControlServer instance.
    Raises OSError if the port is already in use by another process.
    """
    global _server
    if _server is not None:
        return _server  # already running — idempotent
    _server = ControlServer(port=port)
    _server.start()
    return _server


def stop_server() -> None:
    """Shutdown the HTTP server and release the socket."""
    global _server
    if _server is not None:
        _server.stop()
        _server = None
