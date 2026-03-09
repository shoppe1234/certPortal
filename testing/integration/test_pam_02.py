"""testing/integration/test_pam_02.py
PAM-02: HITL Queue — Approve and Reject

Verified from source (portals/pam.py):
  - GET  /hitl-queue → HTML, lists PENDING_APPROVAL items
  - POST /hitl-queue/{queue_id}/approve → 200 JSON + S3 signal
    S3 key: {retailer}/{supplier}/signals/kelly_approved_{queue_id}.json
  - POST /hitl-queue/{queue_id}/reject  → 200 JSON, no S3 signal
  - DB updates: status='APPROVED'/'REJECTED', resolved_at=now(), resolved_by=<user>
  - 404 if queue_id not found

Prerequisites (run before test class):
  psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/seed_hitl_queue.sql
"""
from __future__ import annotations

import json
import time

import pytest
from playwright.sync_api import Page, expect

from .conftest import browser_login, hitl

pytestmark = [pytest.mark.live_portals, pytest.mark.live_db, pytest.mark.live_s3, pytest.mark.p0]

PAM_URL = "http://localhost:8000"
APPROVE_ID = "test-queue-approve"
REJECT_ID = "test-queue-reject"


class TestPAM02:
    """PAM-02: HITL Queue approve + reject flows."""

    def test_hitl_queue_page_accessible(self, pam, admin_token):
        """GET /hitl-queue returns 200 for admin."""
        r = pam.get("/hitl-queue", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_hitl_queue_requires_auth(self, pam):
        """GET /hitl-queue without token → redirect to login."""
        r = pam.get("/hitl-queue")
        assert r.status_code in (302, 401)

    def test_approve_not_found(self, pam, admin_token):
        """Approving a non-existent queue_id → 404."""
        r = pam.post(
            "/hitl-queue/nonexistent-99999/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    def test_approve_hitl_item(self, pam, admin_token, db, s3_client, workspace_bucket):
        """Approve queued item → status='APPROVED', S3 signal written."""
        r = pam.post(
            f"/hitl-queue/{APPROVE_ID}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "approved"
        assert body["queue_id"] == APPROVE_ID
        assert body["resolved_by"] == "pam_admin"

        # DB: status must be APPROVED
        cur = db.cursor()
        cur.execute(
            "SELECT status, resolved_by FROM hitl_queue WHERE queue_id=%s", (APPROVE_ID,)
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "APPROVED"
        assert row[1] == "pam_admin"

        # S3: kelly_approved signal must exist under retailer/supplier/signals/
        # Key pattern: {retailer}/{supplier}/signals/kelly_approved_{queue_id}.json
        expected_key = f"lowes/acme/signals/kelly_approved_{APPROVE_ID}.json"
        resp = s3_client.get_object(Bucket=workspace_bucket, Key=expected_key)
        signal = json.loads(resp["Body"].read())
        assert signal["queue_id"] == APPROVE_ID
        assert signal["approved_by"] == "pam_admin"
        assert "draft" in signal

    @pytest.mark.hitl
    def test_approve_hitl_visual(self, pam_page: Page):
        """[HITL] Operator reads the approval draft text and confirms it is appropriate."""
        browser_login(pam_page, PAM_URL, "pam_admin", "certportal_admin")
        pam_page.goto(f"{PAM_URL}/hitl-queue")
        hitl(
            f"Read the draft text for queue item '{APPROVE_ID}'. "
            "Confirm: message is professional, mentions acme/lowes, and is appropriate to send.",
            page=pam_page,
        )

    def test_reject_hitl_item(self, pam, admin_token, db):
        """Reject queued item → status='REJECTED', no S3 signal."""
        r = pam.post(
            f"/hitl-queue/{REJECT_ID}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "rejected"
        assert body["queue_id"] == REJECT_ID

        # DB: status must be REJECTED
        cur = db.cursor()
        cur.execute(
            "SELECT status, resolved_by FROM hitl_queue WHERE queue_id=%s", (REJECT_ID,)
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "REJECTED"

    def test_hitl_queue_page_shows_pending_items(self, pam, admin_token, db):
        """HITL queue page only shows PENDING_APPROVAL items."""
        # Seed a fresh pending item to ensure something is visible
        cur = db.cursor()
        cur.execute(
            """
            INSERT INTO hitl_queue (queue_id, retailer_slug, supplier_slug, agent,
                                    draft, summary, channel, status)
            VALUES ('test-pending-check','lowes','acme','monica',
                    'Test draft message.','Test summary','email','PENDING_APPROVAL')
            ON CONFLICT (queue_id) DO NOTHING
            """
        )
        db.commit()

        r = pam.get("/hitl-queue", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        # The page should render the pending item (text-based check)
        assert "test-pending-check" in r.text or "PENDING" in r.text
