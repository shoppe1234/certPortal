"""playwrightcli/fixtures/token_fetcher.py — DB lookup for password reset tokens.

Standalone module: no imports from certportal/ or any other main-codebase module.
Reads CERTPORTAL_DB_URL from .env and queries password_reset_tokens directly.

Used by pam_flow's password-reset step to retrieve the token that the portal
wrote to the DB (bypassing email delivery, which is not testable in E2E).
"""
from __future__ import annotations

import os
from pathlib import Path


def _load_db_url() -> str | None:
    env_val = os.environ.get("CERTPORTAL_DB_URL")
    if env_val:
        return env_val
    env_file = Path(".env")
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("CERTPORTAL_DB_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


class TokenFetcher:
    """Synchronous DB client for reading password_reset_tokens."""

    def __init__(self) -> None:
        self._db_url = _load_db_url()

    def get_latest_token(self, username: str) -> str | None:
        """Return the most recent unused, non-expired reset token for username.

        Returns None if psycopg2 is unavailable, DB is unreachable, or no token exists.
        """
        if self._db_url is None:
            return None
        try:
            import psycopg2  # noqa: PLC0415
        except ImportError:
            return None
        try:
            conn = psycopg2.connect(self._db_url)
            cur = conn.cursor()
            cur.execute(
                "SELECT token FROM password_reset_tokens "
                "WHERE username = %s AND used = FALSE AND expires_at > NOW() "
                "ORDER BY created_at DESC LIMIT 1",
                (username,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return row[0] if row else None
        except Exception:
            return None
