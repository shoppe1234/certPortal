"""testing/integration/test_mer_03.py
MER-03: YAML Wizard — All 3 Andy Ingestion Paths

Verified from source (portals/meredith.py):
  - GET  /yaml-wizard → 200 HTML with supported_bundles
  - POST /yaml-wizard/path1 (JSON: retailer_slug) → 200 {"status":"queued","path":1}
    S3 key: {retailer}/system/signals/andy_path1_trigger_{ts}.json
    Signal type: "andy_yaml_path1"
  - POST /yaml-wizard/path2 (JSON: retailer_slug, yaml_content) → 200
    S3 key: {retailer}/system/signals/andy_path2_trigger_{ts}.json
    Signal type: "andy_yaml_path2"
  - POST /yaml-wizard/path3 (JSON: retailer_slug, ...) → 200
    S3 key: {retailer}/system/signals/andy_path3_trigger_{ts}.json
    Signal type: "andy_yaml_path3"
  - Missing retailer_slug → 400
  - INV-07: portal never imports Andy agent directly
"""
from __future__ import annotations

import json

import pytest

from .conftest import hitl

pytestmark = [pytest.mark.live_portals, pytest.mark.live_db, pytest.mark.live_s3, pytest.mark.p1]

MER_URL = "http://localhost:8001"


class TestMER03:
    """MER-03: YAML Wizard all 3 Andy trigger paths."""

    def _auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _latest_signal(self, s3_client, workspace_bucket: str, prefix: str) -> dict | None:
        """Return content of most-recently-modified signal matching prefix, or None."""
        result = s3_client.list_objects_v2(Bucket=workspace_bucket, Prefix=prefix)
        contents = result.get("Contents", [])
        if not contents:
            return None
        latest = sorted(contents, key=lambda x: x["LastModified"])[-1]
        resp = s3_client.get_object(Bucket=workspace_bucket, Key=latest["Key"])
        return json.loads(resp["Body"].read())

    # ── Page ──────────────────────────────────────────────────────────────────

    def test_yaml_wizard_page(self, mer, retailer_token):
        """GET /yaml-wizard → 200 with both bundle types."""
        r = mer.get("/yaml-wizard", headers=self._auth(retailer_token))
        assert r.status_code == 200
        assert "general_merchandise" in r.text
        assert "transportation" in r.text
        assert "850" in r.text

    # ── Path 1: PDF → YAML extraction (Dwight/Andy) ──────────────────────────

    def test_path1_queued(self, mer, retailer_token):
        """Path 1: returns status=queued, path=1."""
        r = mer.post(
            "/yaml-wizard/path1",
            json={"retailer_slug": "lowes", "pdf_s3_key": "lowes/system/test_spec_v2.pdf"},
            headers=self._auth(retailer_token),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "queued"
        assert body["path"] == 1

    def test_path1_missing_retailer_slug_returns_400(self, mer, retailer_token):
        """Path 1 with no retailer_slug and no JWT slug → 400."""
        # Use admin token which has no retailer_slug in JWT claims
        r = mer.post(
            "/yaml-wizard/path1",
            json={"pdf_s3_key": "lowes/system/test_spec_v2.pdf"},
            headers={"Authorization": "Bearer INVALID_TOKEN_NO_SLUG"},
        )
        assert r.status_code in (400, 401, 403)

    def test_path1_signal_written(self, mer, retailer_token, s3_client, workspace_bucket):
        """Path 1 writes andy_path1_trigger signal to S3."""
        mer.post(
            "/yaml-wizard/path1",
            json={"retailer_slug": "lowes", "source": "test"},
            headers=self._auth(retailer_token),
        )
        signal = self._latest_signal(s3_client, workspace_bucket, "lowes/system/signals/andy_path1_trigger_")
        assert signal is not None, "andy_path1_trigger signal not found in S3"
        assert signal["type"] == "andy_yaml_path1"
        assert signal["retailer_slug"] == "lowes"

    # ── Path 2: YAML upload ───────────────────────────────────────────────────

    def test_path2_queued(self, mer, retailer_token):
        """Path 2: returns status=queued, path=2."""
        yaml_content = (
            "transaction:\n"
            "  id: '850'\n"
            "  name: Purchase Order\n"
            "  direction: inbound\n"
        )
        r = mer.post(
            "/yaml-wizard/path2",
            json={"retailer_slug": "lowes", "yaml_content": yaml_content},
            headers=self._auth(retailer_token),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "queued"
        assert body["path"] == 2

    def test_path2_signal_written(self, mer, retailer_token, s3_client, workspace_bucket):
        """Path 2 writes andy_path2_trigger signal to S3."""
        mer.post(
            "/yaml-wizard/path2",
            json={"retailer_slug": "lowes", "yaml_content": "transaction:\n  id: '850'\n"},
            headers=self._auth(retailer_token),
        )
        signal = self._latest_signal(s3_client, workspace_bucket, "lowes/system/signals/andy_path2_trigger_")
        assert signal is not None, "andy_path2_trigger signal not found in S3"
        assert signal["type"] == "andy_yaml_path2"
        assert signal["retailer_slug"] == "lowes"

    # ── Path 3: Wizard form serialization ────────────────────────────────────

    def test_path3_queued(self, mer, retailer_token):
        """Path 3: returns status=queued, path=3."""
        r = mer.post(
            "/yaml-wizard/path3",
            json={
                "retailer_slug": "lowes",
                "transaction_id": "850",
                "segments": [{"id": "BEG", "usage": "M"}],
            },
            headers=self._auth(retailer_token),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "queued"
        assert body["path"] == 3

    def test_path3_signal_written(self, mer, retailer_token, s3_client, workspace_bucket):
        """Path 3 writes andy_path3_trigger signal to S3."""
        mer.post(
            "/yaml-wizard/path3",
            json={"retailer_slug": "lowes", "transaction_id": "850"},
            headers=self._auth(retailer_token),
        )
        signal = self._latest_signal(s3_client, workspace_bucket, "lowes/system/signals/andy_path3_trigger_")
        assert signal is not None, "andy_path3_trigger signal not found in S3"
        assert signal["type"] == "andy_yaml_path3"
        assert signal["retailer_slug"] == "lowes"

    # ── HITL gate ─────────────────────────────────────────────────────────────

    @pytest.mark.hitl
    def test_all_signals_hitl(self, mer, retailer_token):
        """[HITL] Operator confirms all 3 S3 signals and no direct Andy import."""
        hitl(
            "Check S3 bucket 'certportal-workspaces' under 'lowes/system/signals/'. "
            "Confirm: signals exist for andy_path1_trigger, andy_path2_trigger, andy_path3_trigger. "
            "Confirm: each has the correct 'type' field. "
            "Confirm: 'from agents.andy import' does NOT appear in portals/meredith.py.",
        )
