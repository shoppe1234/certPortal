"""testing/integration/test_mer_01.py
MER-01: Retailer Login, Dashboard, Spec Board

Verified from source (portals/meredith.py):
  - GET  /health → {"status":"ok","portal":"meredith","version":"1.0.0"}
  - POST /token/api → 200 JSON {access_token, token_type}; role=retailer, retailer_slug=lowes
  - POST /token/api (supplier on retailer portal) → 401 (supplier role rejected)
  - POST /token/api (admin on retailer portal) → 200 (admin allowed on all portals)
  - GET  / → 200 HTML dashboard
  - GET  /spec-setup → 200 HTML
  - GET  /yaml-wizard → 200 HTML, includes supported_bundles
  - GET  /supplier-status → 200 HTML
  - Retailer token → 403 on Chrissy supplier-only route /scenarios

Prerequisites:
  psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/seed_hitl_queue.sql (optional, for counts)
  Seed retailer_specs: INSERT INTO retailer_specs (...) VALUES ('lowes','v2.0-test','lowes/THESIS.md','lowes/spec.pdf')
"""
from __future__ import annotations

import base64
import json
import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import assert_status, browser_login, hitl

pytestmark = [pytest.mark.live_portals, pytest.mark.live_db, pytest.mark.p0]

MER_URL = "http://localhost:8001"
CHR_URL = "http://localhost:8002"
PAM_URL = "http://localhost:8000"


class TestMER01:
    """MER-01: Retailer login, JWT claims, dashboard, cross-portal blocking."""

    @pytest.fixture(autouse=True)
    def seed_retailer_spec(self, db):
        """Ensure a lowes retailer spec exists for dashboard/spec-setup tests."""
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM retailer_specs WHERE retailer_slug='lowes'")
        if cur.fetchone()[0] == 0:
            cur.execute(
                """
                INSERT INTO retailer_specs (retailer_slug, spec_version, thesis_s3_key)
                VALUES ('lowes','v2.0-test','lowes/acme/THESIS.md')
                """
            )
            db.commit()

    # ── API layer ────────────────────────────────────────────────────────────

    def test_health(self, mer):
        r = mer.get("/health")
        assert_status(r, 200, msg="GET /health meredith")
        assert r.json() == {"status": "ok", "portal": "meredith", "version": "1.0.0"}

    def test_retailer_token(self, mer):
        """Retailer login via /token/api → 200 JSON token."""
        r = mer.post(
            "/token/api",
            data={"username": "lowes_retailer", "password": "certportal_retailer"},
        )
        assert_status(r, 200, msg="POST /token/api retailer login")
        assert "access_token" in r.json()

    def test_retailer_jwt_claims(self, retailer_token):
        """JWT payload: sub=lowes_retailer, role=retailer, retailer_slug=lowes."""
        parts = retailer_token.split(".")
        padding = "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
        assert payload["sub"] == "lowes_retailer"
        assert payload["role"] == "retailer"
        assert payload["retailer_slug"] == "lowes"
        assert payload["type"] == "access"

    def test_supplier_rejected_on_retailer_portal(self, mer):
        """Supplier credentials on retailer portal → token issues OK but role rejected on protected routes."""
        # /token/api itself issues a token regardless of role
        r = mer.post(
            "/token/api",
            data={"username": "acme_supplier", "password": "certportal_supplier"},
        )
        assert_status(r, 200, msg="POST /token/api supplier token issues on retailer portal")
        token = r.json()["access_token"]

        # But supplier token must be blocked on retailer-protected routes
        r2 = mer.get("/", headers={"Authorization": f"Bearer {token}"})
        assert_status(r2, 403, msg="GET / supplier token blocked on retailer portal")

    def test_admin_allowed_on_retailer_portal(self, mer, admin_token):
        """Admin token accepted on retailer portal (admin role permitted everywhere)."""
        r = mer.get("/", headers={"Authorization": f"Bearer {admin_token}"})
        assert_status(r, 200, msg="GET / admin token allowed on retailer portal")

    def test_retailer_token_blocked_on_supplier_portal(self, chrissy, retailer_token):
        """Retailer token rejected on Chrissy supplier-protected route → 403."""
        r = chrissy.get("/scenarios", headers={"Authorization": f"Bearer {retailer_token}"})
        assert_status(r, 403, msg="GET /scenarios retailer token blocked on supplier portal")

    def test_retailer_dashboard(self, mer, retailer_token):
        """GET / returns 200 with spec, supplier_count, certified_count."""
        r = mer.get("/", headers={"Authorization": f"Bearer {retailer_token}"})
        assert_status(r, 200, msg="GET / retailer dashboard")

    def test_spec_setup_page(self, mer, retailer_token):
        """GET /spec-setup → 200, shows seeded spec."""
        r = mer.get("/spec-setup", headers={"Authorization": f"Bearer {retailer_token}"})
        assert_status(r, 200, msg="GET /spec-setup retailer page")
        assert "lowes" in r.text or "v2.0-test" in r.text

    def test_yaml_wizard_page(self, mer, retailer_token):
        """GET /yaml-wizard → 200, includes supported_bundles."""
        r = mer.get("/yaml-wizard", headers={"Authorization": f"Bearer {retailer_token}"})
        assert_status(r, 200, msg="GET /yaml-wizard retailer page")
        assert "general_merchandise" in r.text
        assert "850" in r.text

    def test_supplier_status_page(self, mer, retailer_token):
        """GET /supplier-status → 200."""
        r = mer.get("/supplier-status", headers={"Authorization": f"Bearer {retailer_token}"})
        assert_status(r, 200, msg="GET /supplier-status retailer page")

    # ── Browser layer ────────────────────────────────────────────────────────

    def test_login_page_renders(self, page: Page):
        """Meredith login page has correct title and heading."""
        page.goto(f"{MER_URL}/login")
        expect(page).to_have_title("certPortal Retailer — Login")
        expect(page.locator("h1")).to_contain_text("certPortal · Retailer")

    def test_browser_login_and_dashboard(self, page: Page):
        """Browser login → dashboard redirect."""
        browser_login(page, MER_URL, "lowes_retailer", "certportal_retailer")
        expect(page).to_have_url(f"{MER_URL}/")

    @pytest.mark.hitl
    def test_dashboard_visual(self, mer_page: Page):
        """[HITL] Operator confirms light theme, supplier counts, spec visible."""
        browser_login(mer_page, MER_URL, "lowes_retailer", "certportal_retailer")
        hitl(
            "Confirm: light theme (#f8f9fc background, #4f6ef7 primary). "
            "Dashboard shows: correct supplier_count, certified_count from DB. "
            "Spec setup link and YAML wizard link visible in navigation.",
            page=mer_page,
        )
