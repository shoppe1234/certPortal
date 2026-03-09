"""testing/integration/test_chr_04.py
CHR-04: Ryan Patch — Apply and Reject

Verified from source (portals/chrissy.py):
  - POST /patches/{patch_id}/mark-applied
    → 200: {"status":"applied","patch_id":<id>}
    → DB: patch_suggestions.applied=TRUE
    → S3: signals/moses_revalidate_{patch_id}_{ts}.json in workspace bucket
    → 404 if patch_id not found
  - POST /patches/{patch_id}/reject
    → 200: {"status":"rejected","patch_id":<id>}
    → DB: patch_suggestions.rejected=TRUE  (migration 003 column)
    → No S3 signal written
    → 404 if patch_id not found
  - GET  /patches/{patch_id}/content
    → 200 HTML (patch markdown rendered)
    → 404 if patch_id not found

Prerequisites:
  psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/seed_patch_suggestions.sql
"""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page

from .conftest import browser_login, hitl

pytestmark = [pytest.mark.live_portals, pytest.mark.live_db, pytest.mark.live_s3, pytest.mark.p1]

CHR_URL = "http://localhost:8002"


class TestCHR04:
    """CHR-04: Patch apply + reject flows."""

    @pytest.fixture
    def patch_ids(self, db) -> tuple[int, int]:
        """Seed and return (apply_patch_id, reject_patch_id)."""
        cur = db.cursor()
        # Seed two fresh patches (reset applied/rejected to FALSE)
        cur.execute(
            """
            INSERT INTO patch_suggestions
                (supplier_slug, retailer_slug, error_code, segment, element, summary, patch_s3_key, applied)
            VALUES
                ('acme','lowes','E001','BEG','BEG03','Truncate PO number','lowes/acme/patches/patch_beg03_test.yaml',FALSE),
                ('acme','lowes','E002','ISA','ISA13','Fix control number','lowes/acme/patches/patch_isa13_test.yaml',FALSE)
            RETURNING id
            """
        )
        ids = [row[0] for row in cur.fetchall()]
        db.commit()
        assert len(ids) == 2
        return ids[0], ids[1]

    @pytest.fixture(autouse=True)
    def upload_patch_content(self, s3_client, workspace_bucket, patch_ids):
        """Upload dummy patch .yaml content to S3 for /content endpoint."""
        apply_id, reject_id = patch_ids
        for patch_id, s3_key in [
            (apply_id, "lowes/acme/patches/patch_beg03_test.yaml"),
            (reject_id, "lowes/acme/patches/patch_isa13_test.yaml"),
        ]:
            content = (
                f"# Patch {patch_id}\n\n"
                "## Problem\nPO number too long or ISA13 non-numeric.\n\n"
                "## Fix\nUpdate the segment value to comply with Lowe's spec.\n"
            )
            s3_client.put_object(
                Bucket=workspace_bucket,
                Key=s3_key,
                Body=content.encode("utf-8"),
            )

    def _auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # ── mark-applied ──────────────────────────────────────────────────────────

    def test_mark_applied_success(self, chrissy, supplier_token, db, patch_ids, s3_client, workspace_bucket):
        """mark-applied → 200, applied=TRUE in DB, S3 signal written."""
        apply_id, _ = patch_ids
        r = chrissy.post(
            f"/patches/{apply_id}/mark-applied",
            headers=self._auth(supplier_token),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "applied"
        assert body["patch_id"] == apply_id

        # DB: applied=TRUE
        cur = db.cursor()
        cur.execute("SELECT applied FROM patch_suggestions WHERE id=%s", (apply_id,))
        assert cur.fetchone()[0] is True

        # S3: moses_revalidate signal written
        prefix = "lowes/acme/signals/"
        result = s3_client.list_objects_v2(Bucket=workspace_bucket, Prefix=prefix)
        keys = [obj["Key"] for obj in result.get("Contents", [])]
        revalidate_keys = [k for k in keys if f"moses_revalidate_{apply_id}_" in k]
        assert len(revalidate_keys) >= 1, (
            f"moses_revalidate signal not found for patch_id={apply_id} under {prefix}"
        )

        # S3 signal content
        resp = s3_client.get_object(Bucket=workspace_bucket, Key=revalidate_keys[0])
        signal = json.loads(resp["Body"].read())
        assert signal["trigger"] == "patch_applied"
        assert signal["patch_id"] == apply_id
        assert signal["supplier_slug"] == "acme"
        assert signal["retailer_slug"] == "lowes"

    def test_mark_applied_not_found(self, chrissy, supplier_token):
        """mark-applied on non-existent patch → 404."""
        r = chrissy.post(
            "/patches/999999/mark-applied",
            headers=self._auth(supplier_token),
        )
        assert r.status_code == 404

    # ── reject ────────────────────────────────────────────────────────────────

    def test_reject_success(self, chrissy, supplier_token, db, patch_ids):
        """reject → 200, rejected=TRUE in DB, no S3 signal."""
        _, reject_id = patch_ids
        r = chrissy.post(
            f"/patches/{reject_id}/reject",
            headers=self._auth(supplier_token),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "rejected"
        assert body["patch_id"] == reject_id

        # DB: rejected=TRUE (migration 003 column)
        cur = db.cursor()
        cur.execute("SELECT rejected FROM patch_suggestions WHERE id=%s", (reject_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] is True

    def test_reject_not_found(self, chrissy, supplier_token):
        """reject on non-existent patch → 404."""
        r = chrissy.post(
            "/patches/999999/reject",
            headers=self._auth(supplier_token),
        )
        assert r.status_code == 404

    # ── patch content ─────────────────────────────────────────────────────────

    def test_patch_content_accessible(self, chrissy, supplier_token, patch_ids):
        """GET /patches/{id}/content → 200 HTML with markdown content."""
        apply_id, _ = patch_ids
        r = chrissy.get(
            f"/patches/{apply_id}/content",
            headers=self._auth(supplier_token),
        )
        assert r.status_code == 200
        # Should contain the markdown content we uploaded
        assert "Patch" in r.text or "Problem" in r.text

    def test_patch_content_not_found(self, chrissy, supplier_token):
        """GET /patches/999999/content → 404."""
        r = chrissy.get(
            "/patches/999999/content",
            headers=self._auth(supplier_token),
        )
        assert r.status_code == 404

    # ── HITL gate ─────────────────────────────────────────────────────────────

    @pytest.mark.hitl
    def test_patch_content_hitl(self, chrissy_page: Page, patch_ids):
        """[HITL] Operator reads patch content and confirms it is actionable."""
        apply_id, _ = patch_ids
        browser_login(chrissy_page, CHR_URL, "acme_supplier", "certportal_supplier")
        chrissy_page.goto(f"{CHR_URL}/patches/{apply_id}/content")
        hitl(
            f"Read the patch content for patch_id={apply_id}. "
            "Confirm: the markdown describes the error, provides a concrete fix, "
            "and is actionable for an EDI developer.",
            page=chrissy_page,
        )
