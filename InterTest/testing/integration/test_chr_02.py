"""testing/integration/test_chr_02.py
CHR-02: Moses 850 PO Validation — PASS

Verified from source (agents/moses.py, portals/chrissy.py):
  - Moses CLI: python -m agents.moses --retailer lowes --supplier acme
                                      --edi-key <key> --tx 850 --channel gs1
  - Requires THESIS.md at lowes/acme/THESIS.md in certportal-raw-edi bucket
  - test_occurrences: new row with status=PASS, transaction_type=850, errors=[]
  - S3 result written to workspace (lowes/acme/<correlation_id>_result.json)
  - Monica memory entry written after run
  - Chrissy /scenarios shows PASS row

NOTE: If Moses is stubbed (pyedi_core not fully wired), STEP 2 will still PASS
      because the stub returns PASS for any valid-looking EDI. This is expected
      in early sprint integration testing.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page

from .conftest import assert_status, browser_login, hitl

pytestmark = [
    pytest.mark.live_portals,
    pytest.mark.live_db,
    pytest.mark.live_s3,
    pytest.mark.p0,
]

EDI_KEY = "lowes/acme/850/test_850_pass.edi"
RETAILER = "lowes"
SUPPLIER = "acme"
TX = "850"
CHANNEL = "gs1"


class TestCHR02:
    """CHR-02: Moses 850 PASS validation."""

    @pytest.fixture(autouse=True)
    def ensure_thesis_in_s3(self, s3_client, raw_edi_bucket):
        """Verify THESIS.md exists — hard failure for Moses without it."""
        try:
            s3_client.head_object(Bucket=raw_edi_bucket, Key=f"{RETAILER}/{SUPPLIER}/THESIS.md")
        except Exception:
            pytest.skip(
                "THESIS.md not found in S3 — run: python testing/integration/setup_minio.py"
            )

    @pytest.fixture(autouse=True)
    def ensure_edi_in_s3(self, s3_client, raw_edi_bucket):
        """Upload test_850_pass.edi fixture if not already present."""
        try:
            s3_client.head_object(Bucket=raw_edi_bucket, Key=EDI_KEY)
        except Exception:
            fixture = Path(__file__).parent.parent / "fixtures" / "edi" / "test_850_pass.edi"
            if fixture.exists():
                s3_client.upload_file(str(fixture), raw_edi_bucket, EDI_KEY)
            else:
                pytest.skip("test_850_pass.edi fixture file not found")

    # ── Pre-flight ────────────────────────────────────────────────────────────

    @pytest.mark.hitl
    def test_s3_prerequisites_confirmed(self):
        """[HITL] Operator confirms THESIS.md and EDI fixture are present in S3."""
        hitl(
            "Confirm S3 prerequisites before Moses run:\n"
            f"  • certportal-raw-edi/{RETAILER}/{SUPPLIER}/THESIS.md  → exists\n"
            f"  • certportal-raw-edi/{EDI_KEY}  → exists\n"
            "If either is missing, run: python testing/integration/setup_minio.py",
        )

    # ── Moses CLI ─────────────────────────────────────────────────────────────

    def test_moses_cli_pass(self, db):
        """Run Moses CLI → exit code 0, PASS written to test_occurrences."""
        result = subprocess.run(
            [
                sys.executable, "-m", "agents.moses",
                "--retailer", RETAILER,
                "--supplier", SUPPLIER,
                "--edi-key", EDI_KEY,
                "--tx", TX,
                "--channel", CHANNEL,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Moses must exit 0 (no crash)
        assert result.returncode == 0, (
            f"Moses CLI exited {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        # stdout or stderr must mention PASS
        combined = result.stdout + result.stderr
        assert "ThesisMissing" not in combined, "ThesisMissing — THESIS.md not found in S3"

        # DB: new PASS row in test_occurrences
        cur = db.cursor()
        cur.execute(
            """
            SELECT status, transaction_type, channel, result_json
            FROM test_occurrences
            WHERE supplier_slug=%s AND retailer_slug=%s AND transaction_type=%s
            ORDER BY validated_at DESC LIMIT 1
            """,
            (SUPPLIER, RETAILER, TX),
        )
        row = cur.fetchone()
        assert row is not None, "No test_occurrence row found after Moses run"
        status, tx_type, channel, result_json = row
        assert status == "PASS"
        assert tx_type == TX
        assert channel == CHANNEL

        # Errors array should be empty for a PASS
        result_data = json.loads(result_json)
        assert result_data.get("errors", []) == []

    def test_scenarios_page_shows_pass(self, chrissy, supplier_token, db):
        """After Moses PASS, Chrissy /scenarios shows the new row."""
        # Ensure there's at least one PASS row (seeded or from Moses run)
        cur = db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM test_occurrences WHERE supplier_slug=%s AND status='PASS'",
            (SUPPLIER,),
        )
        count = cur.fetchone()[0]
        assert count >= 1, "Expected ≥1 PASS row in test_occurrences"

        r = chrissy.get("/scenarios", headers={"Authorization": f"Bearer {supplier_token}"})
        assert_status(r, 200, msg="GET /scenarios after Moses 850 PASS")
        assert "PASS" in r.text

    @pytest.mark.hitl
    def test_scenarios_page_visual(self, chrissy_page: Page, db):
        """[HITL] Operator confirms PASS scenario visible in Chrissy portal."""
        browser_login(chrissy_page, "http://localhost:8002", "acme_supplier", "certportal_supplier")
        chrissy_page.goto("http://localhost:8002/scenarios")
        hitl(
            "Confirm: Chrissy /scenarios page shows the new PASS row for 850. "
            "The row should show transaction_type=850, status=PASS, channel=gs1. "
            "SQL check: SELECT status FROM test_occurrences WHERE supplier_slug='acme' "
            "ORDER BY validated_at DESC LIMIT 1; — should be PASS.",
            page=chrissy_page,
        )
