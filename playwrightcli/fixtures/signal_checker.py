"""playwrightcli/fixtures/signal_checker.py — Standalone S3 signal scanner.

Used by signal integration tests (Step #2) to verify that portal actions
correctly write workspace signals for agent pickup (INV-01, INV-07).

Isolation: uses boto3 directly and parses .env from the project root.
MUST NOT import from certportal.core or any main-codebase module
(feedback_isolation constraint — all playwrightcli/ test code is isolated).

Requirement IDs verified through this module:
  SIG-YAML2-01/02/03  YAML Wizard Path 2 → andy_path2_trigger_*.json
  SIG-PATCH-01/02/03  Patch Mark-Applied  → moses_revalidate_*.json
  SIG-HITL-01/02/03   HITL Approve        → kelly_approved_{queue_id}.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# .env loader — no python-dotenv dependency
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
# SignalChecker
# ---------------------------------------------------------------------------

class SignalChecker:
    """Queries MinIO/OVH S3 for workspace signal files written by portal actions.

    Instantiate once per test run and share across all signal verification calls.
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

    def list_signals_since(self, prefix: str, since_epoch: float) -> list[dict]:
        """Return S3 object metadata for keys under *prefix* created at or after *since_epoch*.

        Args:
            prefix:      S3 key prefix, e.g. ``"lowes/system/signals/andy_path2"``.
            since_epoch: Unix timestamp (float). Objects with
                         LastModified < since_epoch are excluded.

        Returns:
            List of dicts (Key, LastModified, Size). Empty list on any error.
        """
        try:
            resp = self._s3.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
        except Exception:
            return []

        return [
            {
                "Key": o["Key"],
                "LastModified": o["LastModified"],
                "Size": o["Size"],
            }
            for o in resp.get("Contents", [])
            if o["LastModified"].timestamp() >= since_epoch
        ]

    def object_exists(self, key: str) -> bool:
        """Return True if *key* exists in the workspace bucket."""
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def get_object_json(self, key: str) -> dict[str, Any] | None:
        """Fetch and JSON-parse *key*. Returns None on any error."""
        try:
            resp = self._s3.get_object(Bucket=self._bucket, Key=key)
            return json.loads(resp["Body"].read())
        except Exception:
            return None

    def find_signal(self, signal_type: str, retries: int = 3, delay: float = 2.0) -> dict[str, Any] | None:
        """Find the most recent signal file matching *signal_type* prefix.

        Searches under common signal prefixes with retry logic for eventual
        consistency. Returns the parsed JSON payload, or None if not found.
        """
        import time
        since = time.time() - 3600  # look back 1 hour
        scopes = ("lowes/system/signals/", "lowes/acme/signals/")
        for attempt in range(retries):
            for scope in scopes:
                hits = self.list_signals_since(f"{scope}{signal_type}", since)
                if hits:
                    latest = sorted(hits, key=lambda o: o["LastModified"], reverse=True)[0]
                    return self.get_object_json(latest["Key"])
            if attempt < retries - 1:
                time.sleep(delay)
        return None

    @property
    def bucket(self) -> str:
        return self._bucket
