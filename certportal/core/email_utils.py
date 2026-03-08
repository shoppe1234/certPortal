"""certportal/core/email_utils.py — SMTP helper for portal-initiated emails (ADR-023).

INV-07: portals cannot import from agents/. This module replicates the
smtplib/STARTTLS pattern from agents/kelly._dispatch_email() so that portals
can send password-reset emails without creating an agents/ import.

Fail-safe: if SMTP_HOST is not set, logs a warning to stderr and returns False.
Never raises — callers must be resilient to email failures.
"""
from __future__ import annotations

import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_reset_email(to_addr: str, reset_link: str, portal_name: str) -> bool:
    """Send a password-reset email via SMTP/STARTTLS.

    Args:
        to_addr:     Recipient email address (from portal_users.email).
        reset_link:  Full https://... URL with the reset token in the query string.
        portal_name: Human-readable portal label used in the subject line (e.g. "Admin").

    Returns:
        True on successful send, False on configuration error or SMTP failure.

    Environment variables (from .env.template, ADR-020 / ADR-023):
        SMTP_HOST     — required; if absent, logs warning and returns False.
        SMTP_PORT     — default 587.
        SMTP_USER     — optional; skips login() if empty.
        SMTP_PASSWORD — used with SMTP_USER.
        SMTP_FROM     — sender address, default certportal@example.com.
    """
    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("SMTP_FROM", "certportal@example.com")

    if not host:
        print(
            f"[email_utils] SMTP_HOST not configured — reset email not sent to {to_addr}",
            file=sys.stderr,
        )
        return False

    body_text = (
        f"You requested a password reset for the certPortal {portal_name} portal.\n\n"
        f"Click the link below within 60 minutes to set a new password:\n"
        f"{reset_link}\n\n"
        f"If you did not request this reset, ignore this email — your password is unchanged."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[certPortal] Password Reset — {portal_name}"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(body_text, "plain"))

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            if user:
                server.login(user, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        return True
    except Exception as exc:
        print(
            f"[email_utils] SMTP error sending to {to_addr}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return False
