"""testing/integration/test_pam_04.py
PAM-04: Monica Memory Pagination + Forgot-Password Reset Flow

Verified from source (portals/pam.py):
  - GET  /monica-memory → 200 HTML, paginated; query params: page, limit
  - GET  /forgot-password → 200 HTML form
  - POST /forgot-password → 302 to /login?msg=reset_sent (no user enumeration)
  - DB: password_reset_tokens.token, username, expires_at, used=FALSE
  - GET  /reset-password?token=<tok> → 200 HTML (valid), 302 to /forgot-password?error (invalid)
  - POST /reset-password → updates portal_users.hashed_password, portal_users.updated_at
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import browser_login, hitl

pytestmark = [pytest.mark.live_portals, pytest.mark.live_db, pytest.mark.p1]

PAM_URL = "http://localhost:8000"


class TestPAM04:
    """PAM-04: Monica memory log + forgot-password flow."""

    @pytest.fixture(autouse=True)
    def seed_monica_memory(self, db):
        """Ensure ≥5 monica_memory rows exist for pagination tests."""
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM monica_memory")
        count = cur.fetchone()[0]
        if count < 5:
            cur.execute(
                """
                INSERT INTO monica_memory (timestamp, agent, direction, message, retailer_slug, supplier_slug)
                VALUES
                  (now()-interval '5 min','moses','Q','Validating 850 for acme/lowes','lowes','acme'),
                  (now()-interval '4 min','moses','A','PASS: 850 PO-TEST-850 valid','lowes','acme'),
                  (now()-interval '3 min','ryan','Q','Generating patch for BEG03','lowes','acme'),
                  (now()-interval '2 min','ryan','A','Patch generated: truncate ISA13','lowes','acme'),
                  (now()-interval '1 min','monica','A','Escalated to HITL queue','lowes','acme')
                """
            )
            db.commit()

    # ── Monica Memory ────────────────────────────────────────────────────────

    def test_monica_memory_accessible(self, pam, admin_token):
        """GET /monica-memory returns 200 for admin."""
        r = pam.get("/monica-memory", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_monica_memory_requires_auth(self, pam):
        """GET /monica-memory without token → redirect."""
        r = pam.get("/monica-memory")
        assert r.status_code in (302, 401)

    def test_monica_memory_pagination(self, pam, admin_token):
        """Pagination parameters (page, limit) are accepted and reflected in response."""
        r = pam.get(
            "/monica-memory?page=1&limit=2",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        # Pagination metadata should be present in rendered HTML
        assert "page" in r.text or "total" in r.text

    @pytest.mark.hitl
    def test_monica_memory_visual(self, pam_page: Page):
        """[HITL] Operator confirms memory log entries display correctly."""
        browser_login(pam_page, PAM_URL, "pam_admin", "certportal_admin")
        pam_page.goto(f"{PAM_URL}/monica-memory")
        hitl(
            "Verify: Monica memory log shows at least 5 entries from agents "
            "(moses, ryan, monica). Entries are in reverse chronological order. "
            "Pagination controls visible.",
            page=pam_page,
        )

    # ── Forgot Password ──────────────────────────────────────────────────────

    def test_forgot_password_page_renders(self, pam):
        """GET /forgot-password returns 200 HTML form."""
        r = pam.get("/forgot-password")
        assert r.status_code == 200
        assert "Forgot Password" in r.text or "forgot" in r.text.lower()

    def test_forgot_password_unknown_user_no_enumeration(self, pam):
        """Unknown username → same redirect as valid username (no enumeration)."""
        r = pam.post("/forgot-password", data={"username": "nonexistent_user_xyz"})
        assert r.status_code == 302
        loc = r.headers.get("location", "")
        assert "reset_sent" in loc

    def test_forgot_password_valid_user_redirects(self, pam):
        """Valid username → 302 to /login?msg=reset_sent."""
        r = pam.post("/forgot-password", data={"username": "pam_admin"})
        assert r.status_code == 302
        loc = r.headers.get("location", "")
        assert "reset_sent" in loc

    def test_password_reset_token_written_to_db(self, pam, db):
        """After forgot-password submit, token exists in password_reset_tokens."""
        pam.post("/forgot-password", data={"username": "pam_admin"})
        cur = db.cursor()
        cur.execute(
            """
            SELECT token, expires_at, used FROM password_reset_tokens
            WHERE username='pam_admin' ORDER BY expires_at DESC LIMIT 1
            """
        )
        row = cur.fetchone()
        assert row is not None, "password_reset_tokens must have a row for pam_admin"
        token, expires_at, used = row
        assert token and len(token) > 10
        assert not used

    def test_invalid_reset_token_redirects_back(self, pam):
        """GET /reset-password with bad token → redirect to /forgot-password?error=..."""
        r = pam.get("/reset-password?token=invalid-token-xyz")
        assert r.status_code == 302
        loc = r.headers.get("location", "")
        assert "error=" in loc or "forgot-password" in loc

    def test_valid_reset_token_shows_form(self, pam, db):
        """GET /reset-password with valid token → 200 HTML form."""
        pam.post("/forgot-password", data={"username": "pam_admin"})
        cur = db.cursor()
        cur.execute(
            """
            SELECT token FROM password_reset_tokens
            WHERE username='pam_admin' AND used=FALSE ORDER BY expires_at DESC LIMIT 1
            """
        )
        row = cur.fetchone()
        if row is None:
            pytest.skip("No unused reset token found — ensure pam_admin has email configured")
        token = row[0]

        r = pam.get(f"/reset-password?token={token}")
        assert r.status_code == 200
        assert "new_password" in r.text.lower() or "password" in r.text.lower()

    @pytest.mark.hitl
    def test_password_reset_email_arrived(self, pam):
        """[HITL] Operator verifies reset email delivered to inbox."""
        pam.post("/forgot-password", data={"username": "pam_admin"})
        hitl(
            "Check the pam_admin email inbox. Confirm: a password reset email arrived with "
            "a reset link URL. The link should contain a token parameter. "
            "Do NOT click the link — just confirm delivery.",
        )
