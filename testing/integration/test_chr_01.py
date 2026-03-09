"""testing/integration/test_chr_01.py
CHR-01: Supplier Login, Dashboard, Gate Status Display

Verified from source (portals/chrissy.py):
  - GET  /health → {"status":"ok","portal":"chrissy","version":"1.0.0"}
  - POST /token/api → 200, role=supplier, supplier_slug=acme, retailer_slug=lowes
  - Retailer token blocked on supplier portal → 403
  - Admin token allowed on supplier portal → 200
  - GET  / → 200 HTML dashboard with gate status + test counts
  - GET  /scenarios → 200, scoped to supplier_slug from JWT
  - GET  /certification → 200 HTML

Prerequisites:
  psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/seed_test_occurrences.sql
  INSERT INTO hitl_gate_status ...  (see seed in conftest or test fixture below)
"""
from __future__ import annotations

import base64
import json

import pytest
from playwright.sync_api import Page, expect

from .conftest import assert_status, browser_login, hitl

pytestmark = [pytest.mark.live_portals, pytest.mark.live_db, pytest.mark.p0]

CHR_URL = "http://localhost:8002"
PAM_URL = "http://localhost:8000"
MER_URL = "http://localhost:8001"


class TestCHR01:
    """CHR-01: Supplier login, dashboard, cross-portal blocking."""

    @pytest.fixture(autouse=True)
    def seed_supplier_data(self, db):
        """Ensure hitl_gate_status and test_occurrences rows exist for acme."""
        cur = db.cursor()
        cur.execute(
            """
            INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
            VALUES ('acme','COMPLETE','PENDING','PENDING','test_seed')
            ON CONFLICT (supplier_id) DO UPDATE
                SET gate_1='COMPLETE', gate_2='PENDING', gate_3='PENDING',
                    last_updated_by='test_seed'
            """
        )
        # Ensure at least 1 PASS and 1 FAIL row
        cur.execute("SELECT COUNT(*) FROM test_occurrences WHERE supplier_slug='acme'")
        if cur.fetchone()[0] < 2:
            cur.execute(
                """
                INSERT INTO test_occurrences
                    (supplier_slug, retailer_slug, transaction_type, channel, status, result_json)
                VALUES
                    ('acme','lowes','850','gs1','PASS','{"errors":[],"po_number":"PO-SEED-PASS"}'),
                    ('acme','lowes','850','gs1','FAIL','{"errors":[{"code":"E001"}],"po_number":"PO-SEED-FAIL"}')
                """
            )
        db.commit()

    def _auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # ── API layer ────────────────────────────────────────────────────────────

    def test_health(self, chrissy):
        r = chrissy.get("/health")
        assert_status(r, 200, msg="GET /health chrissy")
        assert r.json() == {"status": "ok", "portal": "chrissy", "version": "1.0.0"}

    def test_supplier_login(self, chrissy):
        """/token/api returns token for acme_supplier."""
        r = chrissy.post(
            "/token/api",
            data={"username": "acme_supplier", "password": "certportal_supplier"},
        )
        assert_status(r, 200, msg="POST /token/api supplier login")
        assert "access_token" in r.json()

    def test_supplier_jwt_claims(self, supplier_token):
        """JWT: role=supplier, supplier_slug=acme, retailer_slug=lowes."""
        parts = supplier_token.split(".")
        padding = "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
        assert payload["sub"] == "acme_supplier"
        assert payload["role"] == "supplier"
        assert payload["supplier_slug"] == "acme"
        assert payload["retailer_slug"] == "lowes"
        assert payload["type"] == "access"

    def test_retailer_token_blocked_on_supplier_portal(self, chrissy, retailer_token):
        """Retailer JWT → 403 on supplier-only route."""
        r = chrissy.get("/scenarios", headers=self._auth(retailer_token))
        assert_status(r, 403, msg="GET /scenarios retailer token blocked on supplier portal")

    def test_admin_token_allowed_on_supplier_portal(self, chrissy, admin_token):
        """Admin token → 200 on supplier portal (admin has universal access)."""
        r = chrissy.get("/", headers=self._auth(admin_token))
        assert_status(r, 200, msg="GET / admin token on supplier portal")

    def test_supplier_blocked_on_admin_portal(self, pam, supplier_token):
        """Supplier JWT → 403 on Pam admin-only route."""
        r = pam.get("/retailers", headers=self._auth(supplier_token))
        assert_status(r, 403, msg="GET /retailers supplier token blocked on admin portal")

    def test_dashboard_accessible(self, chrissy, supplier_token):
        """GET / with supplier token → 200 HTML."""
        r = chrissy.get("/", headers=self._auth(supplier_token))
        assert_status(r, 200, msg="GET / supplier dashboard")

    def test_scenarios_page_accessible(self, chrissy, supplier_token):
        """GET /scenarios with supplier token → 200 HTML."""
        r = chrissy.get("/scenarios", headers=self._auth(supplier_token))
        assert_status(r, 200, msg="GET /scenarios supplier")

    def test_certification_page_accessible(self, chrissy, supplier_token):
        """GET /certification with supplier token → 200 HTML."""
        r = chrissy.get("/certification", headers=self._auth(supplier_token))
        assert_status(r, 200, msg="GET /certification supplier")

    def test_errors_page_accessible(self, chrissy, supplier_token):
        """GET /errors with supplier token → 200 HTML."""
        r = chrissy.get("/errors", headers=self._auth(supplier_token))
        assert_status(r, 200, msg="GET /errors supplier")

    def test_patches_page_accessible(self, chrissy, supplier_token):
        """GET /patches with supplier token → 200 HTML."""
        r = chrissy.get("/patches", headers=self._auth(supplier_token))
        assert_status(r, 200, msg="GET /patches supplier")

    # ── Browser layer ────────────────────────────────────────────────────────

    def test_login_page_renders(self, page: Page):
        """Chrissy login page has correct title."""
        page.goto(f"{CHR_URL}/login")
        expect(page).to_have_title("certPortal Supplier — Login")
        expect(page.locator("h1")).to_contain_text("certPortal · Supplier")

    def test_browser_login_and_dashboard(self, page: Page):
        """Browser login → dashboard redirect."""
        browser_login(page, CHR_URL, "acme_supplier", "certportal_supplier")
        expect(page).to_have_url(f"{CHR_URL}/")

    @pytest.mark.hitl
    def test_dashboard_visual(self, chrissy_page: Page):
        """[HITL] Operator confirms warm theme, gate status, pass/fail counts."""
        browser_login(chrissy_page, CHR_URL, "acme_supplier", "certportal_supplier")
        hitl(
            "Confirm: warm theme (#fffbf7 background, #f59e0b amber primary). "
            "Dashboard shows: gate_1=COMPLETE, gate_2=PENDING, gate_3=PENDING. "
            "Progress bar shows correct pass percentage. "
            "Scenarios link and Errors link visible in navigation.",
            page=chrissy_page,
        )
