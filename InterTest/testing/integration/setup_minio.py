"""testing/integration/setup_minio.py
One-time MinIO bucket creation + fixture upload for integration tests.

Run once after starting MinIO (docker compose -f docker-compose.minio.yml up -d):
    python testing/integration/setup_minio.py

What it does:
  1. Creates certportal-workspaces and certportal-raw-edi buckets (idempotent)
  2. Uploads THESIS.md for lowes/acme and lowes/bolt (required by Moses — ThesisMissing
     is a hard failure without it)
  3. Uploads all 5 EDI fixture files from testing/fixtures/edi/ to the correct S3 paths

MinIO ↔ OVHcloud: controlled entirely by OVH_S3_ENDPOINT in .env.
  Local dev:   OVH_S3_ENDPOINT=http://localhost:9000
  Production:  OVH_S3_ENDPOINT=https://s3.gra.io.cloud.ovh.net
No code changes required.
"""
from __future__ import annotations

import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Ensure the project root is on the path for certportal imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from certportal.core.config import settings  # noqa: E402 (after sys.path update)

# ---------------------------------------------------------------------------
# S3 client
# ---------------------------------------------------------------------------

s3 = boto3.client(
    "s3",
    endpoint_url=settings.ovh_s3_endpoint,
    aws_access_key_id=settings.ovh_s3_key,
    aws_secret_access_key=settings.ovh_s3_secret,
    region_name=settings.ovh_s3_region,
)

BUCKETS = [settings.ovh_s3_workspace_bucket, settings.ovh_s3_raw_edi_bucket]

EDI_DIR = Path(__file__).parent.parent / "fixtures" / "edi"

# THESIS.md content — minimal but valid for Moses ThesisMissing check
THESIS_CONTENT = """\
# Lowe's EDI Specification

## Overview
This thesis document describes Lowe's EDI transaction requirements for certPortal integration tests.

## 850 Purchase Order
- BEG03 (Purchase Order Number): max 22 characters, alphanumeric
- ISA13 (Interchange Control Number): 9-digit numeric, must be sequential

## 855 Purchase Order Acknowledgment
- BAK02: Original PO number from 850, max 22 characters

## 856 Ship Notice / Manifest
- BSN02: Shipment identification number, max 30 characters

## 810 Invoice
- BIG02: Invoice number, max 22 characters

## General Rules
- All segments must be properly terminated with ~
- Elements separated with *
- ISA envelope required on all transactions
""".encode("utf-8")


# ---------------------------------------------------------------------------
# Bucket creation (idempotent)
# ---------------------------------------------------------------------------

def ensure_bucket(bucket: str) -> None:
    try:
        s3.create_bucket(Bucket=bucket)
        print(f"  ✓ Created bucket: {bucket}")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"  · Bucket exists:  {bucket}")
        else:
            raise


# ---------------------------------------------------------------------------
# THESIS.md upload (required by Moses)
# ---------------------------------------------------------------------------

THESIS_PATHS = [
    "lowes/acme/THESIS.md",
    "lowes/bolt/THESIS.md",
]

def upload_thesis(bucket: str) -> None:
    for key in THESIS_PATHS:
        s3.put_object(Bucket=bucket, Key=key, Body=THESIS_CONTENT)
        print(f"  ✓ THESIS.md → s3://{bucket}/{key}")


# ---------------------------------------------------------------------------
# EDI fixture upload
# ---------------------------------------------------------------------------

# Maps fixture filename → S3 key relative to lowes/acme/
EDI_KEY_MAP = {
    "test_850_pass.edi": "lowes/acme/850/test_850_pass.edi",
    "test_850_fail.edi": "lowes/acme/850/test_850_fail.edi",
    "test_855_pass.edi": "lowes/acme/855/test_855_pass.edi",
    "test_856_pass.edi": "lowes/acme/856/test_856_pass.edi",
    "test_810_pass.edi": "lowes/acme/810/test_810_pass.edi",
}

def upload_edi_fixtures(bucket: str) -> None:
    for filename, s3_key in EDI_KEY_MAP.items():
        local_path = EDI_DIR / filename
        if not local_path.exists():
            print(f"  ⚠ Missing fixture (skipped): {local_path}")
            continue
        s3.upload_file(str(local_path), bucket, s3_key)
        print(f"  ✓ {filename} → s3://{bucket}/{s3_key}")


# ---------------------------------------------------------------------------
# Upload dummy PDF for Meredith spec tests (MER-02)
# ---------------------------------------------------------------------------

DUMMY_PDF_KEY = "lowes/system/test_spec_v2.pdf"
DUMMY_PDF_CONTENT = b"%PDF-1.4 dummy test spec file for certPortal integration tests"

def upload_dummy_pdf(bucket: str) -> None:
    s3.put_object(Bucket=bucket, Key=DUMMY_PDF_KEY, Body=DUMMY_PDF_CONTENT,
                  ContentType="application/pdf")
    print(f"  ✓ Dummy PDF → s3://{bucket}/{DUMMY_PDF_KEY}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n=== certPortal MinIO Setup ===")
    print(f"Endpoint: {settings.ovh_s3_endpoint}")
    print()

    print("Creating buckets...")
    for bucket in BUCKETS:
        ensure_bucket(bucket)

    print()
    print(f"Uploading THESIS.md files to {settings.ovh_s3_raw_edi_bucket}...")
    upload_thesis(settings.ovh_s3_raw_edi_bucket)

    print()
    print(f"Uploading EDI fixtures to {settings.ovh_s3_raw_edi_bucket}...")
    upload_edi_fixtures(settings.ovh_s3_raw_edi_bucket)

    print()
    print(f"Uploading dummy PDF to {settings.ovh_s3_raw_edi_bucket}...")
    upload_dummy_pdf(settings.ovh_s3_raw_edi_bucket)

    print()
    print("=== Setup complete. Ready to run integration tests. ===")
    print()
    print("Next steps:")
    print("  1. Start portals:   uvicorn portals.pam:app --port 8000 &")
    print("                      uvicorn portals.meredith:app --port 8001 &")
    print("                      uvicorn portals.chrissy:app --port 8002 &")
    print("  2. Run smoke check: pytest testing/integration/ --collect-only -q")
    print("  3. Run P0 suite:    CERTPORTAL_CI=true pytest testing/integration/ -v -m 'p0 and not hitl'")


if __name__ == "__main__":
    main()
