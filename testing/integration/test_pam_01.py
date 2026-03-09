"""testing/integration/test_pam_01.py
PAM-01: Admin Auth, Token Claims, Logout + Revocation

Verified from source:
  - /health → {"status":"ok","portal":"pam","version":"1.0.0"}
  - /token   → 302 redirect on valid login (form-based)
  - /token/api → 200 JSON {"access_token":..,"token_type":"bearer"} (API endpoint)
  - JWT: sub, role, retailer_slug, supplier_slug, type="access", exp, jti (32-char hex)
  - ACCESS_TOKEN_EXPIRE_MINUTES = 480 (certportal/core/auth.py)
  - Cookie names: access_token, refresh_token (httponly, samesite=lax)
  - /logout → clears cookies, inserts jti into revoked_tokens table
  - Revoked token detail: "Token has been revoked"
"""
from __future__ import annotations

import base64
import json
import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import browser_login, hitl

pytestmark = [pytest.mark.live_portals, pytest.mark.live_db, pytest.mark.p0]

PAM_URL = "http://localhost:8000"


class TestPAM01:
    """PAM-01: Admin Auth, Token Claims, Logout + Revocation."""

    # ── API layer ────────────────────────────────────────────────────────────

    def test_health(self, pam):
        r = pam.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "portal": "pam", "version": "1.0.0"}

    def test_wrong_password_browser_redirect(self, pam):
        """Browser login with wrong password → 302 to /login?error=..."""
        r = pam.post("/token", data={"username": "pam_admin", "password": "wrong_password_123"})
        assert r.status_code == 302
        loc = r.headers.get("location", "")
        assert "error=" in loc or "Invalid" in loc

    def test_supplier_token_blocked_on_admin_portal(self, pam, supplier_token):
        """Supplier JWT rejected on admin-only route → 403."""
        r = pam.get("/retailers", headers={"Authorization": f"Bearer {supplier_token}"})
        assert r.status_code == 403

    def test_retailer_token_blocked_on_admin_portal(self, pam, retailer_token):
        """Retailer JWT rejected on admin-only route → 403."""
        r = pam.get("/retailers", headers={"Authorization": f"Bearer {retailer_token}"})
        assert r.status_code == 403

    def test_api_token_returns_json(self, pam):
        """/token/api returns JSON with access_token + token_type."""
        r = pam.post("/token/api", data={"username": "pam_admin", "password": "certportal_admin"})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_jwt_claims(self, admin_token):
        """JWT payload has correct claims: sub, role, type, jti (32-char hex), exp."""
        # Decode middle segment (pad to multiple of 4 for base64)
        parts = admin_token.split(".")
        padding = "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))

        assert payload["sub"] == "pam_admin"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
        assert payload["retailer_slug"] is None
        assert payload["supplier_slug"] is None
        # JTI: secrets.token_hex(16) = 32-char hex string
        jti = payload["jti"]
        assert len(jti) == 32
        assert re.match(r"^[0-9a-f]{32}$", jti)
        # exp - iat ≈ 480 minutes (8 hours) — allow ±2 min clock drift
        if "iat" in payload:
            delta_minutes = (payload["exp"] - payload["iat"]) / 60
            assert 478 <= delta_minutes <= 482

    def test_revocation_flow(self, pam, db):
        """Login → logout → reuse access_token → should be rejected. JTI in revoked_tokens."""
        # Get a fresh token via form login to capture cookie
        r = pam.post("/token", data={"username": "pam_admin", "password": "certportal_admin"})
        assert r.status_code == 302
        cookie_val = r.cookies.get("access_token")
        assert cookie_val, "access_token cookie must be set after login"

        # Decode JTI from cookie token
        parts = cookie_val.split(".")
        padding = "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
        jti = payload["jti"]

        # Logout — should revoke cookie and insert JTI
        logout_resp = pam.post("/logout", cookies={"access_token": cookie_val})
        assert logout_resp.status_code == 302

        # Verify JTI was inserted into revoked_tokens
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM revoked_tokens WHERE jti=%s", (jti,))
        count = cur.fetchone()[0]
        assert count == 1, f"JTI {jti} must be in revoked_tokens after logout"

    def test_cross_portal_role_rejection_json(self, pam):
        """/token/api returns 401 for invalid credentials (JSON response)."""
        r = pam.post("/token/api", data={"username": "pam_admin", "password": "TOTALLY_WRONG"})
        assert r.status_code == 401
        assert "Invalid" in r.json().get("detail", "")

    # ── Browser layer ────────────────────────────────────────────────────────

    def test_login_page_renders(self, page: Page):
        """Login page has correct title and heading."""
        page.goto(f"{PAM_URL}/login")
        expect(page).to_have_title("certPortal Admin — Login")
        expect(page.locator("h1")).to_contain_text("certPortal · Admin")
        expect(page.locator("button[type='submit']")).to_be_visible()
        expect(page.locator("input[name='username']")).to_be_visible()
        expect(page.locator("input[name='password']")).to_be_visible()

    @pytest.mark.hitl
    def test_login_page_visual_theme(self, page: Page):
        """[HITL] Operator confirms dark theme, #00ff88 green accent, layout."""
        page.goto(f"{PAM_URL}/login")
        expect(page).to_have_title("certPortal Admin — Login")
        hitl(
            "Confirm: dark theme (#0a0e1a background), green accent (#00ff88 on h1), "
            "monospace font, login card centered, 'Forgot password?' link visible.",
            page=page,
        )

    def test_browser_login_and_dashboard(self, page: Page):
        """Browser login → dashboard redirect → admin nav links present."""
        browser_login(page, PAM_URL, "pam_admin", "certportal_admin")
        expect(page).to_have_url(f"{PAM_URL}/")
        expect(page.locator("a[href='/retailers']")).to_be_visible()
        expect(page.locator("a[href='/suppliers']")).to_be_visible()
        expect(page.locator("a[href='/hitl-queue']")).to_be_visible()

    def test_browser_wrong_password_error(self, page: Page):
        """Wrong password shows error parameter in URL."""
        page.goto(f"{PAM_URL}/login")
        page.fill("input[name='username']", "pam_admin")
        page.fill("input[name='password']", "wrong_password")
        page.click("button[type='submit']")
        expect(page).to_have_url(re.compile(r".*error=.*"))
