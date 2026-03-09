"""testing/integration/test_e2e_02.py
E2E-02: Failure Recovery Loop (FAIL → Patch → Re-validate → PASS)

Scenario:
  1. Moses validates malformed 850 → FAIL recorded in test_occurrences
  2. Ryan patch suggestion seeded in DB
  3. Supplier marks patch as applied (CHR-04 mark-applied)
  4. S3 signal triggers Moses re-validation
  5. Moses runs again with corrected EDI → PASS
  6. Chrissy /errors shows resolved state

Tests that the full failure→recovery→success loop works end-to-end.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page

from .conftest import browser_login, hitl

pytestmark = [
    pytest.mark.live_portals,
    pytest.mark.live_db,
    pytest.mark.live_s3,
    pytest.mark.p0,
]

RETAILER = "lowes"
SUPPLIER = "acme"
CHANNEL = "gs1"
CHR_URL = "http://localhost:8002"


def _moses(tx: str, edi_key: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, "-m", "agents.moses",
            "--retailer", RETAILER,
            "--supplier", SUPPLIER,
            "--edi-key", edi_key,
            "--tx", tx,
            "--channel", CHANNEL,
        ],
        capture_output=True, text=True, timeout=60,
    )


class TestE2E02:
    """E2E-02: Failure recovery loop."""

    @pytest.fixture
    def fail_row(self, db):
        """Seed a FAIL test_occurrence for recovery flow."""
        cur = db.cursor()
        cur.execute(
            """
            INSERT INTO test_occurrences
                (supplier_slug, retailer_slug, transaction_type, channel, status, result_json)
            VALUES (%s, %s, '850', %s, 'FAIL', %s)
            RETURNING id
            """,
            (
                SUPPLIER, RETAILER, CHANNEL,
                json.dumps({
                    "status": "FAIL",
                    "po_number": "PO-E2E-FAIL",
                    "errors": [
                        {"code": "E001", "segment": "BEG", "element": "BEG03",
                         "message": "PO number exceeds 22 characters"},
                    ],
                }),
            ),
        )
        row_id = cur.fetchone()[0]
        db.commit()
        return row_id

    @pytest.fixture
    def recovery_patch(self, db, s3_client, workspace_bucket):
        """Seed a patch suggestion + upload patch content to S3."""
        cur = db.cursor()
        cur.execute(
            """
            INSERT INTO patch_suggestions
                (supplier_slug, retailer_slug, error_code, segment, element, summary, patch_s3_key, applied)
            VALUES (%s, %s, 'E001', 'BEG', 'BEG03', 'Truncate PO number for recovery',
                    'lowes/acme/patches/e2e_recovery_patch.yaml', FALSE)
            RETURNING id
            """,
            (SUPPLIER, RETAILER),
        )
        patch_id = cur.fetchone()[0]
        db.commit()

        # Upload patch content
        content = (
            "# Recovery Patch E001\n\n"
            "## Problem\nPO number in BEG03 exceeds 22 characters.\n\n"
            "## Fix\nTruncate PO-E2E-FAIL to PO-E2E-OK (22 chars max).\n"
        )
        s3_client.put_object(
            Bucket=workspace_bucket,
            Key="lowes/acme/patches/e2e_recovery_patch.yaml",
            Body=content.encode("utf-8"),
        )
        return patch_id

    # ── Step 1: FAIL state ────────────────────────────────────────────────────

    def test_fail_state_exists(self, fail_row, db):
        """FAIL row seeded in test_occurrences."""
        cur = db.cursor()
        cur.execute("SELECT status FROM test_occurrences WHERE id=%s", (fail_row,))
        assert cur.fetchone()[0] == "FAIL"

    def test_errors_page_shows_fail(self, chrissy, supplier_token, fail_row):
        """Chrissy /errors shows the FAIL row."""
        r = chrissy.get("/errors", headers={"Authorization": f"Bearer {supplier_token}"})
        assert r.status_code == 200
        assert "E001" in r.text or "FAIL" in r.text

    # ── Step 2: Patch applied ─────────────────────────────────────────────────

    def test_mark_patch_applied(self, chrissy, supplier_token, recovery_patch, db, s3_client, workspace_bucket):
        """Supplier marks patch applied → S3 revalidation signal written."""
        r = chrissy.post(
            f"/patches/{recovery_patch}/mark-applied",
            headers={"Authorization": f"Bearer {supplier_token}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "applied"

        # DB: applied=TRUE
        cur = db.cursor()
        cur.execute("SELECT applied FROM patch_suggestions WHERE id=%s", (recovery_patch,))
        assert cur.fetchone()[0] is True

        # S3 signal written
        prefix = f"{RETAILER}/{SUPPLIER}/signals/"
        result = s3_client.list_objects_v2(Bucket=workspace_bucket, Prefix=prefix)
        keys = [obj["Key"] for obj in result.get("Contents", [])]
        assert any(f"moses_revalidate_{recovery_patch}_" in k for k in keys), (
            "moses_revalidate signal not found after patch applied"
        )

    # ── Step 3: Re-validate ───────────────────────────────────────────────────

    def test_revalidation_with_pass_edi(self, db, s3_client, raw_edi_bucket):
        """Moses re-validates with corrected (PASS) EDI → new PASS row."""
        edi_key = f"{RETAILER}/{SUPPLIER}/850/test_850_pass.edi"
        try:
            s3_client.head_object(Bucket=raw_edi_bucket, Key=edi_key)
        except Exception:
            pytest.skip("test_850_pass.edi not in S3 — run setup_minio.py")

        result = _moses("850", edi_key)
        assert result.returncode == 0

        cur = db.cursor()
        cur.execute(
            """
            SELECT status FROM test_occurrences
            WHERE supplier_slug=%s AND transaction_type='850'
            ORDER BY validated_at DESC LIMIT 1
            """,
            (SUPPLIER,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] in ("PASS", "PARTIAL"), f"Expected PASS after recovery, got {row[0]}"

    # ── HITL gate ─────────────────────────────────────────────────────────────

    @pytest.mark.hitl
    def test_recovery_complete_visual(self, chrissy_page: Page):
        """[HITL] Operator confirms error resolved and PASS visible."""
        browser_login(chrissy_page, CHR_URL, "acme_supplier", "certportal_supplier")
        chrissy_page.goto(f"{CHR_URL}/scenarios")
        hitl(
            "E2E-02 recovery loop complete. Confirm:\n"
            "  • /scenarios shows PASS row (most recent 850) — this is the re-validated PASS\n"
            "  • /errors page still shows the original FAIL row (historical — not deleted)\n"
            "  • /patches shows the recovery patch with applied=TRUE\n"
            "SQL: SELECT status FROM test_occurrences WHERE supplier_slug='acme' "
            "ORDER BY validated_at DESC LIMIT 2; — most recent should be PASS.",
            page=chrissy_page,
        )
