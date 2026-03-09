"""testing/integration/test_mer_02.py
MER-02: Spec Upload → Dwight Agent S3 Signal

Verified from source (portals/meredith.py):
  - POST /spec-setup/upload (JSON body: pdf_s3_key, retailer_slug)
    → 200: {"status":"queued","message":"...","retailer_slug":..,"pdf_s3_key":..}
    → 400: {"detail":"pdf_s3_key and retailer_slug required"} if fields missing
  - S3 signal key: {retailer}/system/signals/dwight_trigger_{ts}.json
  - Signal body: {"type":"dwight_spec_analysis","pdf_s3_key":..,"retailer_slug":..}
  - retailer_slug falls back to JWT claim if not in request body
  - INV-07: portal writes S3 signal — never imports or calls dwight agent directly
"""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page

from .conftest import hitl

pytestmark = [pytest.mark.live_portals, pytest.mark.live_db, pytest.mark.live_s3, pytest.mark.p1]

MER_URL = "http://localhost:8001"
PDF_S3_KEY = "lowes/system/test_spec_v2.pdf"


class TestMER02:
    """MER-02: Spec upload triggers Dwight S3 signal."""

    def _auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # ── Negative ─────────────────────────────────────────────────────────────

    def test_missing_body_returns_400(self, mer, retailer_token):
        """Empty body → 400."""
        r = mer.post(
            "/spec-setup/upload",
            json={},
            headers=self._auth(retailer_token),
        )
        assert r.status_code == 400
        assert "required" in r.json()["detail"].lower()

    def test_missing_pdf_key_returns_400(self, mer, retailer_token):
        """Body with only retailer_slug, no pdf_s3_key → 400."""
        r = mer.post(
            "/spec-setup/upload",
            json={"retailer_slug": "lowes"},
            headers=self._auth(retailer_token),
        )
        assert r.status_code == 400

    def test_unauthenticated_blocked(self, mer):
        """No token → 302 or 401."""
        r = mer.post(
            "/spec-setup/upload",
            json={"pdf_s3_key": PDF_S3_KEY, "retailer_slug": "lowes"},
        )
        assert r.status_code in (302, 401, 403)

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_valid_upload_trigger(self, mer, retailer_token):
        """Valid payload → 200 queued response."""
        r = mer.post(
            "/spec-setup/upload",
            json={"pdf_s3_key": PDF_S3_KEY, "retailer_slug": "lowes"},
            headers=self._auth(retailer_token),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "queued"
        assert body["retailer_slug"] == "lowes"
        assert body["pdf_s3_key"] == PDF_S3_KEY

    def test_retailer_slug_fallback_from_jwt(self, mer, retailer_token):
        """Body with no retailer_slug → fallback to JWT claim (lowes)."""
        r = mer.post(
            "/spec-setup/upload",
            json={"pdf_s3_key": PDF_S3_KEY},
            headers=self._auth(retailer_token),
        )
        assert r.status_code == 200
        assert r.json()["retailer_slug"] == "lowes"

    def test_dwight_signal_written_to_s3(self, mer, retailer_token, s3_client, workspace_bucket):
        """S3 workspace signal written under lowes/system/signals/dwight_trigger_*.json."""
        r = mer.post(
            "/spec-setup/upload",
            json={"pdf_s3_key": PDF_S3_KEY, "retailer_slug": "lowes"},
            headers=self._auth(retailer_token),
        )
        assert r.status_code == 200

        # List signals directory and find a dwight_trigger signal
        prefix = "lowes/system/signals/"
        result = s3_client.list_objects_v2(Bucket=workspace_bucket, Prefix=prefix)
        keys = [obj["Key"] for obj in result.get("Contents", [])]
        dwight_keys = [k for k in keys if "dwight_trigger_" in k]
        assert len(dwight_keys) >= 1, f"No dwight_trigger signal found under {prefix}"

        # Read most recent signal and validate content
        latest = sorted(dwight_keys)[-1]
        resp = s3_client.get_object(Bucket=workspace_bucket, Key=latest)
        signal = json.loads(resp["Body"].read())
        assert signal["type"] == "dwight_spec_analysis"
        assert signal["pdf_s3_key"] == PDF_S3_KEY
        assert signal["retailer_slug"] == "lowes"

    @pytest.mark.hitl
    def test_s3_signal_content_hitl(self, mer, retailer_token, s3_client, workspace_bucket):
        """[HITL] Operator confirms Dwight signal content is correct in S3."""
        mer.post(
            "/spec-setup/upload",
            json={"pdf_s3_key": PDF_S3_KEY, "retailer_slug": "lowes"},
            headers={"Authorization": f"Bearer {retailer_token}"},
        )
        hitl(
            "Check S3 bucket 'certportal-workspaces' under path 'lowes/system/signals/'. "
            "Confirm: a file named dwight_trigger_<timestamp>.json exists and contains "
            '{"type":"dwight_spec_analysis","pdf_s3_key":"lowes/system/test_spec_v2.pdf","retailer_slug":"lowes"}. '
            "Confirm NO direct import of dwight agent in portal code (grep: 'from agents.dwight import').",
        )
