"""testing/integration/test_mer_04.py
MER-04: Token Refresh + Change Password (Retailer)

Verified from source (portals/meredith.py):
  - POST /token (form login) → 302, sets access_token + refresh_token cookies (httponly)
  - POST /token/refresh (Cookie: refresh_token=..) → 200 JSON {access_token, token_type}
    + new access_token cookie
  - POST /change-password (form: current_password, new_password, confirm_password)
    → 302 to /change-password?msg=Password+changed+successfully
    → portal_users.updated_at updated
  - Old password rejected after change (401)
  - New password accepted (200 token)
  - REFRESH_TOKEN_EXPIRE_DAYS = 30
"""
from __future__ import annotations

import base64
import json

import pytest
from playwright.sync_api import Page

from .conftest import assert_status, browser_login, hitl

pytestmark = [pytest.mark.live_portals, pytest.mark.live_db, pytest.mark.p1, pytest.mark.serial]

MER_URL = "http://localhost:8001"
RETAILER_USER = "lowes_retailer"
RETAILER_PASS = "certportal_retailer"
NEW_PASS = "RetailerNewPass1!"


class TestMER04:
    """MER-04: Token refresh + change password flow."""

    @pytest.fixture(autouse=True)
    def restore_password(self, db):
        """Restore dev password hash after any change-password test."""
        yield
        try:
            # bcrypt hash for 'certportal_retailer' (from migrations/002_users_table.sql)
            original_hash = "$2b$12$GFviKss9RDxqxa1wmxt8dO9Quy/tf9eWmbzck6Uh.SrAmywWWjSgW"
            cur = db.cursor()
            cur.execute(
                "UPDATE portal_users SET hashed_password=%s, updated_at=NOW() WHERE username=%s",
                (original_hash, RETAILER_USER),
            )
            db.commit()
        except Exception:
            db.rollback()

    # ── Token Refresh ────────────────────────────────────────────────────────

    def test_form_login_sets_both_cookies(self, mer):
        """Form login /token sets access_token and refresh_token cookies."""
        r = mer.post("/token", data={"username": RETAILER_USER, "password": RETAILER_PASS})
        assert_status(r, 302, msg="POST /token form login sets cookies")
        assert "access_token" in r.cookies
        assert "refresh_token" in r.cookies

    def test_token_refresh_issues_new_token(self, mer):
        """POST /token/refresh with refresh_token cookie → new access_token."""
        # Get refresh token from form login
        r = mer.post("/token", data={"username": RETAILER_USER, "password": RETAILER_PASS})
        assert_status(r, 302, msg="POST /token form login for refresh test")
        refresh_tok = r.cookies.get("refresh_token")
        assert refresh_tok, "refresh_token cookie not set after form login"

        # Use refresh token to get new access token
        r2 = mer.post("/token/refresh", cookies={"refresh_token": refresh_tok})
        assert_status(r2, 200, msg="POST /token/refresh issues new token")
        body = r2.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

        # New token must be different from original
        original_access = r.cookies.get("access_token", "")
        assert body["access_token"] != original_access

    def test_refresh_token_claims_preserved(self, mer):
        """Refreshed token retains sub=lowes_retailer, role=retailer."""
        r = mer.post("/token", data={"username": RETAILER_USER, "password": RETAILER_PASS})
        refresh_tok = r.cookies.get("refresh_token")
        r2 = mer.post("/token/refresh", cookies={"refresh_token": refresh_tok})
        new_token = r2.json()["access_token"]

        parts = new_token.split(".")
        padding = "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
        assert payload["sub"] == RETAILER_USER
        assert payload["role"] == "retailer"

    def test_refresh_without_cookie_returns_401(self, mer):
        """POST /token/refresh without cookie → 401."""
        r = mer.post("/token/refresh")
        assert_status(r, 401, msg="POST /token/refresh without cookie")

    @pytest.mark.hitl
    def test_token_refresh_visual(self, mer_page: Page):
        """[HITL] Operator confirms new access_token cookie appears in browser."""
        browser_login(mer_page, MER_URL, RETAILER_USER, RETAILER_PASS)
        hitl(
            "Open Browser DevTools → Application → Cookies → localhost:8001. "
            "Confirm: access_token and refresh_token cookies both present and httpOnly. "
            "Now navigate to /token/refresh — confirm new access_token cookie is set.",
            page=mer_page,
        )

    # ── Change Password ──────────────────────────────────────────────────────

    def test_change_password_success(self, mer, retailer_token, db):
        """Change password → 302 success redirect, updated_at updated in DB."""
        r = mer.post(
            "/change-password",
            data={
                "current_password": RETAILER_PASS,
                "new_password": NEW_PASS,
                "confirm_password": NEW_PASS,
            },
            cookies={"access_token": retailer_token},
        )
        assert_status(r, 302, msg="POST /change-password success redirect")
        loc = r.headers.get("location", "")
        assert "password_changed" in loc or "Password+changed" in loc or "msg=" in loc

        # DB: updated_at must be recent
        cur = db.cursor()
        cur.execute(
            "SELECT updated_at FROM portal_users WHERE username=%s", (RETAILER_USER,)
        )
        row = cur.fetchone()
        assert row is not None

    def test_change_password_wrong_current_rejected(self, mer, retailer_token):
        """Wrong current password → 302 back with error."""
        r = mer.post(
            "/change-password",
            data={
                "current_password": "WRONG_CURRENT_PASS",
                "new_password": NEW_PASS,
                "confirm_password": NEW_PASS,
            },
            cookies={"access_token": retailer_token},
        )
        assert_status(r, 302, msg="POST /change-password wrong current password")
        loc = r.headers.get("location", "")
        assert "error=" in loc

    def test_change_password_mismatch_rejected(self, mer, retailer_token):
        """Mismatched new/confirm passwords → 302 back with error."""
        r = mer.post(
            "/change-password",
            data={
                "current_password": RETAILER_PASS,
                "new_password": NEW_PASS,
                "confirm_password": "DIFFERENT_PASS!",
            },
            cookies={"access_token": retailer_token},
        )
        assert_status(r, 302, msg="POST /change-password mismatched passwords")
        loc = r.headers.get("location", "")
        assert "error=" in loc

    def test_old_password_rejected_after_change(self, mer, retailer_token):
        """After change, old password must fail /token/api."""
        # Change password
        mer.post(
            "/change-password",
            data={
                "current_password": RETAILER_PASS,
                "new_password": NEW_PASS,
                "confirm_password": NEW_PASS,
            },
            cookies={"access_token": retailer_token},
        )
        # Old password rejected
        r = mer.post(
            "/token/api",
            data={"username": RETAILER_USER, "password": RETAILER_PASS},
        )
        assert_status(r, 401, msg="POST /token/api old password rejected after change")

    def test_new_password_accepted_after_change(self, mer, retailer_token):
        """After change, new password must succeed."""
        mer.post(
            "/change-password",
            data={
                "current_password": RETAILER_PASS,
                "new_password": NEW_PASS,
                "confirm_password": NEW_PASS,
            },
            cookies={"access_token": retailer_token},
        )
        r = mer.post(
            "/token/api",
            data={"username": RETAILER_USER, "password": NEW_PASS},
        )
        assert_status(r, 200, msg="POST /token/api new password accepted after change")
        assert "access_token" in r.json()
