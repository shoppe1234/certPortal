"""testing/integration/test_e2e_03.py
E2E-03: New Supplier Onboarding from Scratch

Scenario:
  1. Pam admin registers a new supplier user 'bolt_supplier' via form POST /register
     (CORRECTION: /register is form-based, not JSON API — verified from portals/pam.py)
  2. New bolt_supplier user can log in to Chrissy portal
  3. Pam seeds gate status for bolt supplier
  4. Full gate progression: 1 → 2 → 3 → CERTIFIED
  5. bolt_supplier sees CERTIFIED in Chrissy portal

Verified corrections applied (from plan endpoint review):
  - POST /register is form-based (Form() params), not JSON
  - Fields: username, password, confirm_password, role, retailer_slug, supplier_slug
  - Error: 302 back to /register?error=...
  - Success: 302 to /register?msg=User+%27bolt_supplier%27+registered+successfully

Prerequisites:
  psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/clean_e2e.sql
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import browser_login, hitl

pytestmark = [pytest.mark.live_portals, pytest.mark.live_db, pytest.mark.p1]

PAM_URL = "http://localhost:8000"
MER_URL = "http://localhost:8001"
CHR_URL = "http://localhost:8002"

NEW_SUPPLIER_USER = "bolt_supplier"
NEW_SUPPLIER_PASS = "BoltNewPass2026!"
RETAILER = "lowes"
SUPPLIER = "bolt"


class TestE2E03:
    """E2E-03: New supplier onboarding from scratch."""

    @pytest.fixture(autouse=True)
    def clean_bolt_data(self, db):
        """Remove bolt supplier data before and after test."""
        self._clean(db)
        yield
        self._clean(db)

    def _clean(self, db):
        cur = db.cursor()
        cur.execute("DELETE FROM hitl_gate_status WHERE supplier_id='bolt'")
        cur.execute("DELETE FROM portal_users WHERE username=%s", (NEW_SUPPLIER_USER,))
        db.commit()

    def _admin_auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # ── Registration ──────────────────────────────────────────────────────────

    def test_register_page_accessible(self, pam, admin_token):
        """GET /register → 200 HTML form (admin-protected)."""
        r = pam.get("/register", headers=self._admin_auth(admin_token))
        assert r.status_code == 200
        assert "Register" in r.text

    def test_register_requires_auth(self, pam):
        """GET /register without auth → redirect."""
        r = pam.get("/register")
        assert r.status_code in (302, 401)

    def test_register_new_supplier_form_post(self, pam, admin_token, db):
        """POST /register with form data → new user in portal_users."""
        r = pam.post(
            "/register",
            data={
                "username": NEW_SUPPLIER_USER,
                "password": NEW_SUPPLIER_PASS,
                "confirm_password": NEW_SUPPLIER_PASS,
                "role": "supplier",
                "retailer_slug": RETAILER,
                "supplier_slug": SUPPLIER,
            },
            cookies={"access_token": admin_token},
        )
        # Should redirect to /register?msg=...registered+successfully
        assert r.status_code == 302
        loc = r.headers.get("location", "")
        assert "registered" in loc or "msg=" in loc

        # Verify user in DB
        cur = db.cursor()
        cur.execute(
            "SELECT role, retailer_slug, supplier_slug FROM portal_users WHERE username=%s",
            (NEW_SUPPLIER_USER,),
        )
        row = cur.fetchone()
        assert row is not None, f"User {NEW_SUPPLIER_USER} not found in portal_users"
        assert row[0] == "supplier"
        assert row[1] == RETAILER
        assert row[2] == SUPPLIER

    def test_register_duplicate_username_rejected(self, pam, admin_token, db):
        """Registering same username twice → redirect with error."""
        # Register once
        pam.post(
            "/register",
            data={
                "username": NEW_SUPPLIER_USER,
                "password": NEW_SUPPLIER_PASS,
                "confirm_password": NEW_SUPPLIER_PASS,
                "role": "supplier",
                "retailer_slug": RETAILER,
                "supplier_slug": SUPPLIER,
            },
            cookies={"access_token": admin_token},
        )
        # Register again — should fail
        r = pam.post(
            "/register",
            data={
                "username": NEW_SUPPLIER_USER,
                "password": NEW_SUPPLIER_PASS,
                "confirm_password": NEW_SUPPLIER_PASS,
                "role": "supplier",
                "retailer_slug": RETAILER,
                "supplier_slug": SUPPLIER,
            },
            cookies={"access_token": admin_token},
        )
        assert r.status_code == 302
        loc = r.headers.get("location", "")
        assert "error=" in loc or "taken" in loc.lower()

    def test_register_invalid_role_rejected(self, pam, admin_token):
        """Invalid role value → redirect with error."""
        r = pam.post(
            "/register",
            data={
                "username": "baduser_e2e",
                "password": NEW_SUPPLIER_PASS,
                "confirm_password": NEW_SUPPLIER_PASS,
                "role": "superadmin",  # invalid
                "retailer_slug": RETAILER,
                "supplier_slug": SUPPLIER,
            },
            cookies={"access_token": admin_token},
        )
        assert r.status_code == 302
        loc = r.headers.get("location", "")
        assert "error=" in loc

    # ── New user login ────────────────────────────────────────────────────────

    def test_new_supplier_can_login(self, chrissy, pam, admin_token):
        """Registered bolt_supplier can log in to Chrissy portal."""
        # Register first
        pam.post(
            "/register",
            data={
                "username": NEW_SUPPLIER_USER,
                "password": NEW_SUPPLIER_PASS,
                "confirm_password": NEW_SUPPLIER_PASS,
                "role": "supplier",
                "retailer_slug": RETAILER,
                "supplier_slug": SUPPLIER,
            },
            cookies={"access_token": admin_token},
        )

        # Login via Chrissy /token/api
        r = chrissy.post(
            "/token/api",
            data={"username": NEW_SUPPLIER_USER, "password": NEW_SUPPLIER_PASS},
        )
        assert r.status_code == 200
        assert "access_token" in r.json()

    # ── Gate progression ──────────────────────────────────────────────────────

    def test_new_supplier_gate_progression(self, pam, mer, admin_token, retailer_token, db):
        """Full gate 1→2→3 progression for bolt supplier."""
        # Seed gate status for bolt
        cur = db.cursor()
        cur.execute(
            """
            INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
            VALUES ('bolt','PENDING','PENDING','PENDING','e2e_03_init')
            ON CONFLICT (supplier_id) DO UPDATE
                SET gate_1='PENDING',gate_2='PENDING',gate_3='PENDING',last_updated_by='e2e_03_init'
            """
        )
        db.commit()

        # Gate 1 via Meredith approve-gate
        r1 = mer.post(f"/suppliers/bolt/approve-gate/1", headers=self._admin_auth(admin_token))
        assert r1.status_code == 200

        # Gate 2
        r2 = mer.post(f"/suppliers/bolt/approve-gate/2", headers=self._admin_auth(admin_token))
        assert r2.status_code == 200

        # Gate 3
        r3 = mer.post(f"/suppliers/bolt/approve-gate/3", headers=self._admin_auth(admin_token))
        assert r3.status_code == 200

        # Certify
        r_cert = pam.post(f"/suppliers/bolt/gate/3/certify", headers=self._admin_auth(admin_token))
        assert r_cert.status_code == 200
        assert r_cert.json()["status"] == "certified"

        # DB: gate_3=CERTIFIED
        cur.execute("SELECT gate_3 FROM hitl_gate_status WHERE supplier_id='bolt'")
        assert cur.fetchone()[0] == "CERTIFIED"

    # ── Browser layer ─────────────────────────────────────────────────────────

    def test_register_form_browser(self, page: Page, admin_token):
        """Browser: fill and submit /register form."""
        page.goto(f"{PAM_URL}/login")
        page.fill("input[name='username']", "pam_admin")
        page.fill("input[name='password']", "certportal_admin")
        page.click("button[type='submit']")
        page.wait_for_url(f"{PAM_URL}/")

        page.goto(f"{PAM_URL}/register")
        page.fill("input[name='username']", NEW_SUPPLIER_USER)
        page.fill("input[name='password']", NEW_SUPPLIER_PASS)
        page.fill("input[name='confirm_password']", NEW_SUPPLIER_PASS)

        # Select role=supplier (form has a select or text input)
        # Portal register form uses <input name="role"> — fill directly
        role_input = page.locator("input[name='role'], select[name='role']")
        if role_input.count() > 0:
            role_input.fill("supplier") if role_input.evaluate("el => el.tagName") == "INPUT" else role_input.select_option("supplier")

        page.fill("input[name='retailer_slug']", RETAILER)
        page.fill("input[name='supplier_slug']", SUPPLIER)
        page.click("button[type='submit']")

        # Should redirect to /register with success message
        expect(page).to_have_url(f"{PAM_URL}/register")

    @pytest.mark.hitl
    def test_onboarding_complete_visual(self, chrissy_page: Page, pam, admin_token, db):
        """[HITL] Operator confirms new supplier is onboarded and certified."""
        # Quick setup: register bolt_supplier and certify
        pam.post(
            "/register",
            data={
                "username": NEW_SUPPLIER_USER,
                "password": NEW_SUPPLIER_PASS,
                "confirm_password": NEW_SUPPLIER_PASS,
                "role": "supplier",
                "retailer_slug": RETAILER,
                "supplier_slug": SUPPLIER,
            },
            cookies={"access_token": admin_token},
        )
        cur = db.cursor()
        cur.execute(
            """
            INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
            VALUES ('bolt','CERTIFIED','CERTIFIED','CERTIFIED','e2e_hitl')
            ON CONFLICT (supplier_id) DO UPDATE
                SET gate_1='CERTIFIED',gate_2='CERTIFIED',gate_3='CERTIFIED',last_updated_by='e2e_hitl'
            """
        )
        db.commit()

        browser_login(chrissy_page, CHR_URL, NEW_SUPPLIER_USER, NEW_SUPPLIER_PASS)
        chrissy_page.goto(f"{CHR_URL}/certification")
        hitl(
            "E2E-03 complete. Confirm in browser:\n"
            f"  • Chrissy portal shows CERTIFIED status for bolt_supplier\n"
            f"  • Pam /suppliers shows bolt with gate_3=CERTIFIED\n"
            f"  SQL: SELECT role, supplier_slug FROM portal_users WHERE username='bolt_supplier';\n"
            f"  → role=supplier, supplier_slug=bolt",
            page=chrissy_page,
        )
