"""testing/integration/test_pam_03.py
PAM-03: Supplier Gate Progression + Violation Guard

Verified from source (portals/pam.py, certportal/core/gate_enforcer.py):
  - POST /suppliers/{supplier_id}/gate/{gate}/complete
    → 200: {"status":"ok","supplier_id":..,"gate":..,"new_state":"COMPLETE"}
    → 409: GateOrderViolation (skip gate)
    → 400: {"detail":"gate must be 1, 2, or 3"}
  - POST /suppliers/{supplier_id}/gate/3/certify
    → 200: {"status":"certified","supplier_id":..}
  - DB: hitl_gate_status.gate_1/2/3, last_updated_by

Prerequisites:
  psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/reset_gates.sql
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import assert_status, browser_login, hitl

pytestmark = [pytest.mark.live_portals, pytest.mark.live_db, pytest.mark.p0, pytest.mark.serial]

PAM_URL = "http://localhost:8000"
SUPPLIER = "acme"


class TestPAM03:
    """PAM-03: Supplier gate progression + enforcement."""

    @pytest.fixture(autouse=True)
    def reset_gates(self, db):
        """Reset acme gates to PENDING before each test that uses gates."""
        try:
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO hitl_gate_status (supplier_id, gate_1, gate_2, gate_3, last_updated_by)
                VALUES (%s,'PENDING','PENDING','PENDING','test_reset')
                ON CONFLICT (supplier_id) DO UPDATE
                    SET gate_1='PENDING', gate_2='PENDING', gate_3='PENDING',
                        last_updated=NOW(), last_updated_by='test_reset'
                """,
                (SUPPLIER,),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    def _gate_url(self, gate: int) -> str:
        return f"/suppliers/{SUPPLIER}/gate/{gate}/complete"

    def _auth(self, admin_token: str) -> dict:
        return {"Authorization": f"Bearer {admin_token}"}

    # ── Negative tests ───────────────────────────────────────────────────────

    def test_skip_gate_1_to_2_violation(self, pam, admin_token):
        """Attempt gate 2 before gate 1 → 409 GateOrderViolation."""
        r = pam.post(self._gate_url(2), headers=self._auth(admin_token))
        assert_status(r, 409, msg="POST /suppliers/{id}/gate/2/complete skip gate 1 violation")

    def test_skip_gate_1_to_3_violation(self, pam, admin_token):
        """Attempt gate 3 before gate 1 → 409 GateOrderViolation."""
        r = pam.post(self._gate_url(3), headers=self._auth(admin_token))
        assert_status(r, 409, msg="POST /suppliers/{id}/gate/3/complete skip gate 1 violation")

    def test_invalid_gate_number(self, pam, admin_token):
        """Gate number 4 → 400 Bad Request."""
        r = pam.post(f"/suppliers/{SUPPLIER}/gate/4/complete", headers=self._auth(admin_token))
        assert_status(r, 400, msg="POST /suppliers/{id}/gate/4/complete invalid gate number")
        assert "gate must be 1, 2, or 3" in r.json()["detail"]

    def test_invalid_gate_zero(self, pam, admin_token):
        """Gate number 0 → 400 Bad Request."""
        r = pam.post(f"/suppliers/{SUPPLIER}/gate/0/complete", headers=self._auth(admin_token))
        assert r.status_code in (400, 422)

    # ── Happy path: sequential gate completion ───────────────────────────────

    def test_complete_gate_1(self, pam, admin_token, db):
        """Complete gate 1 → 200, DB updated."""
        r = pam.post(self._gate_url(1), headers=self._auth(admin_token))
        assert_status(r, 200, msg="POST /suppliers/{id}/gate/1/complete success")
        body = r.json()
        assert body["status"] == "ok"
        assert body["gate"] == 1
        assert body["new_state"] == "COMPLETE"

        cur = db.cursor()
        cur.execute("SELECT gate_1, last_updated_by FROM hitl_gate_status WHERE supplier_id=%s", (SUPPLIER,))
        row = cur.fetchone()
        assert row[0] == "COMPLETE"
        assert row[1] == "pam_admin"

    def test_sequential_gates_1_2_3(self, pam, admin_token, db):
        """Complete gates 1 → 2 → 3 in sequence, each returns 200."""
        for gate in (1, 2, 3):
            r = pam.post(self._gate_url(gate), headers=self._auth(admin_token))
            assert r.status_code == 200, f"Gate {gate} complete failed: {r.text}"

        cur = db.cursor()
        cur.execute(
            "SELECT gate_1, gate_2, gate_3 FROM hitl_gate_status WHERE supplier_id=%s",
            (SUPPLIER,),
        )
        row = cur.fetchone()
        assert row[0] == "COMPLETE"
        assert row[1] == "COMPLETE"
        assert row[2] == "COMPLETE"

    def test_skip_gate_2_after_gate_1(self, pam, admin_token):
        """After gate 1 complete, skip to gate 3 → 409."""
        pam.post(self._gate_url(1), headers=self._auth(admin_token))
        r = pam.post(self._gate_url(3), headers=self._auth(admin_token))
        assert_status(r, 409, msg="POST /suppliers/{id}/gate/3/complete skip gate 2 violation")

    def test_certify_after_3_complete(self, pam, admin_token, db):
        """After all 3 gates complete, certify → 200, gate_3='CERTIFIED'."""
        for gate in (1, 2, 3):
            pam.post(self._gate_url(gate), headers=self._auth(admin_token))

        r = pam.post(f"/suppliers/{SUPPLIER}/gate/3/certify", headers=self._auth(admin_token))
        assert_status(r, 200, msg="POST /suppliers/{id}/gate/3/certify success")
        body = r.json()
        assert body["status"] == "certified"
        assert body["supplier_id"] == SUPPLIER

        cur = db.cursor()
        cur.execute("SELECT gate_3 FROM hitl_gate_status WHERE supplier_id=%s", (SUPPLIER,))
        assert cur.fetchone()[0] == "CERTIFIED"

    # ── Browser layer ────────────────────────────────────────────────────────

    def test_gate_violation_cannot_skip_browser(self, pam_page: Page, admin_token, pam):
        """After certification, Chrissy portal shows CERTIFIED status."""
        # Complete all gates via API
        for gate in (1, 2, 3):
            pam.post(self._gate_url(gate), headers={"Authorization": f"Bearer {admin_token}"})
        pam.post(f"/suppliers/{SUPPLIER}/gate/3/certify", headers={"Authorization": f"Bearer {admin_token}"})

        @pytest.mark.hitl
        def visual_check():
            browser_login(pam_page, PAM_URL, "pam_admin", "certportal_admin")
            pam_page.goto(f"{PAM_URL}/suppliers")
            hitl(
                f"Verify: supplier '{SUPPLIER}' shows COMPLETE / CERTIFIED gates in the suppliers table. "
                "Navigate to http://localhost:8002/ as acme_supplier and confirm certification badge.",
                page=pam_page,
            )
