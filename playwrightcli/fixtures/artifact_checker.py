"""playwrightcli/fixtures/artifact_checker.py — Standalone S3 artifact checker.

Used by wizard E2E flows (Phase P) to verify that generated artifacts
(MD/HTML/PDF) exist in the S3 workspace bucket after Layer 2 wizard
completes artifact generation.

Isolation: uses boto3 directly and parses .env from the project root.
MUST NOT import from certportal.core or any main-codebase module
(ADR-027 — all playwrightcli/ test code is isolated).

Artifact S3 path convention:
  {retailer_slug}/specs/{x12_version}/{tx_code}.{ext}

Public API:
  check_artifact_exists(retailer_slug, tx_code, x12_version, ext) -> bool
  list_artifacts(retailer_slug) -> list[str]
"""
from __future__ import annotations

import os
from pathlib import Path


# ---------------------------------------------------------------------------
# .env loader — no python-dotenv dependency (copied from signal_checker.py)
# ---------------------------------------------------------------------------

def _load_dotenv() -> dict[str, str]:
    """Parse .env from the project root (two levels above this file)."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    result: dict[str, str] = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


# ---------------------------------------------------------------------------
# ArtifactChecker
# ---------------------------------------------------------------------------

class ArtifactChecker:
    """Queries S3 for generated spec artifacts written by the Layer 2 wizard.

    Instantiate once per test run and share across all artifact verification calls.
    All public methods degrade gracefully: S3 errors return empty/None/False
    rather than raising, so a misconfigured S3 only causes SKIP, not crash.
    """

    def __init__(self) -> None:
        env = _load_dotenv()

        def _cfg(key: str, default: str) -> str:
            return os.environ.get(key) or env.get(key) or default

        self._bucket  = _cfg("OVH_S3_WORKSPACE_BUCKET", "certportal-workspaces")
        endpoint      = _cfg("OVH_S3_ENDPOINT",          "http://192.168.68.89:9000")
        access_key    = _cfg("OVH_S3_KEY",               "minioadmin")
        secret_key    = _cfg("OVH_S3_SECRET",            "minioadmin")
        region        = _cfg("OVH_S3_REGION",            "us-east-1")

        import boto3
        from botocore.client import Config

        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def check_artifact_exists(
        self,
        retailer_slug: str,
        tx_code: str,
        x12_version: str = "004010",
        ext: str = "md",
    ) -> bool:
        """Return True if the artifact file exists in S3.

        Expected key: {retailer_slug}/specs/{x12_version}/{tx_code}.{ext}
        """
        key = f"{retailer_slug}/specs/{x12_version}/{tx_code}.{ext}"
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def list_artifacts(self, retailer_slug: str) -> list[str]:
        """Return list of S3 keys under {retailer_slug}/specs/.

        Returns empty list on any error.
        """
        prefix = f"{retailer_slug}/specs/"
        try:
            resp = self._s3.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
            return [o["Key"] for o in resp.get("Contents", [])]
        except Exception:
            return []

    def get_artifact_content(
        self,
        retailer_slug: str,
        tx_code: str,
        x12_version: str = "004010",
        ext: str = "md",
    ) -> str | None:
        """Fetch artifact content as string. Returns None on any error."""
        key = f"{retailer_slug}/specs/{x12_version}/{tx_code}.{ext}"
        try:
            resp = self._s3.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read().decode("utf-8", errors="replace")
        except Exception:
            return None

    @property
    def bucket(self) -> str:
        return self._bucket
