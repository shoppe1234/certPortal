"""certportal/core/workspace.py — S3AgentWorkspace: the ONLY S3 client in the codebase.

INV-06: All paths scoped to {retailer_slug}/{supplier_slug}/.
         WorkspaceScopeViolation raised on any path traversal or cross-supplier access.
INV-05: MONICA-MEMORY.md is append-only via append_log().
         No file in the codebase may open MONICA-MEMORY.md with mode "w" or "r+".

All agents and portals use this class exclusively.
No boto3 calls outside this file.
"""
from __future__ import annotations

import json

import boto3
from botocore.exceptions import ClientError

from certportal.core.config import settings


class WorkspaceScopeViolation(Exception):
    """Raised when a key would escape the tenant-scoped workspace prefix."""


class FileNotFoundInWorkspace(Exception):
    """Raised when a requested S3 key does not exist."""


class S3AgentWorkspace:
    """Scoped S3 client for certPortal workspaces.

    All paths are bound to {retailer_slug}/{supplier_slug}/ (or {retailer_slug}/
    for retailer-level operations). Any key that escapes this prefix raises
    WorkspaceScopeViolation.
    """

    def __init__(self, retailer_slug: str, supplier_slug: str | None = None) -> None:
        self._retailer_slug = retailer_slug
        self._supplier_slug = supplier_slug
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.ovh_s3_endpoint,
            aws_access_key_id=settings.ovh_s3_key,
            aws_secret_access_key=settings.ovh_s3_secret,
            region_name=settings.ovh_s3_region,
        )
        self._workspace_bucket = settings.ovh_s3_workspace_bucket
        self._raw_edi_bucket = settings.ovh_s3_raw_edi_bucket

    # ------------------------------------------------------------------
    # Internal scope enforcement
    # ------------------------------------------------------------------

    def _scoped_key(self, key: str) -> str:
        """Prepend tenant scope prefix and validate for path traversal.

        Raises WorkspaceScopeViolation if key contains '..' or absolute paths.
        """
        if ".." in key or key.startswith("/"):
            raise WorkspaceScopeViolation(
                f"Key '{key}' contains path traversal sequences or is absolute."
            )
        if self._supplier_slug:
            prefix = f"{self._retailer_slug}/{self._supplier_slug}/"
        else:
            prefix = f"{self._retailer_slug}/"
        full_key = prefix + key
        if not full_key.startswith(prefix):
            raise WorkspaceScopeViolation(
                f"Resolved key '{full_key}' escapes workspace scope '{prefix}'."
            )
        return full_key

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def upload(self, key: str, content: bytes | str) -> str:
        """Upload content to scoped key. Returns full S3 key."""
        full_key = self._scoped_key(key)
        if isinstance(content, str):
            content = content.encode("utf-8")
        self._client.put_object(
            Bucket=self._workspace_bucket,
            Key=full_key,
            Body=content,
        )
        return full_key

    def download(self, key: str) -> bytes:
        """Download content from scoped key. Raises FileNotFoundInWorkspace if absent."""
        full_key = self._scoped_key(key)
        try:
            response = self._client.get_object(
                Bucket=self._workspace_bucket, Key=full_key
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise FileNotFoundInWorkspace(
                    f"Key not found in workspace: {full_key}"
                ) from e
            raise

    def download_raw_edi(self, key: str) -> bytes:
        """Download a raw EDI file from the raw-edi bucket.

        The key must already be fully qualified (no scope prefix added).
        """
        try:
            response = self._client.get_object(
                Bucket=self._raw_edi_bucket, Key=key
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise FileNotFoundInWorkspace(
                    f"Key not found in raw-edi bucket: {key}"
                ) from e
            raise

    def download_retailer_map(self, key: str) -> bytes:
        """Download a YAML map from the retailer-level scope (no supplier prefix).

        Used by moses to read transaction YAML maps.
        Key is relative to {retailer_slug}/.
        """
        if ".." in key or key.startswith("/"):
            raise WorkspaceScopeViolation(
                f"Retailer map key '{key}' contains path traversal sequences."
            )
        full_key = f"{self._retailer_slug}/{key}"
        try:
            response = self._client.get_object(
                Bucket=self._workspace_bucket, Key=full_key
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise FileNotFoundInWorkspace(
                    f"Retailer map key not found: {full_key}"
                ) from e
            raise

    def exists(self, key: str) -> bool:
        """Return True if the scoped key exists in the workspace bucket."""
        full_key = self._scoped_key(key)
        try:
            self._client.head_object(Bucket=self._workspace_bucket, Key=full_key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "403"):
                return False
            raise

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys under a scoped prefix. Returns full S3 keys."""
        full_prefix = self._scoped_key(prefix) if prefix else self._scoped_key("")
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self._workspace_bucket, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    # ------------------------------------------------------------------
    # Append-only log (INV-05)
    # ------------------------------------------------------------------

    def append_log(self, key: str, line: str) -> None:
        """Append a single line to a log file.

        For MONICA-MEMORY.md: stored at admin/MONICA-MEMORY.md (global, unscoped).
        For all other keys: stored at the scoped supplier workspace path.

        Pattern: download existing → append line → re-upload.
        Creates file if it does not exist.

        INV-05 compliance: never opens the file with mode "w" or "r+".
        """
        # Route MONICA-MEMORY.md to the global admin path
        if key.upper() in ("MONICA-MEMORY.MD",):
            full_key = f"admin/{key}"
        else:
            full_key = self._scoped_key(key)

        # Download existing content (creates if absent)
        try:
            response = self._client.get_object(
                Bucket=self._workspace_bucket, Key=full_key
            )
            existing = response["Body"].read().decode("utf-8")
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                existing = ""
            else:
                raise

        # Append — never truncate
        if existing and not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + line.rstrip("\n") + "\n"

        self._client.put_object(
            Bucket=self._workspace_bucket,
            Key=full_key,
            Body=new_content.encode("utf-8"),
        )

    # ------------------------------------------------------------------
    # PAM-STATUS.json helpers
    # ------------------------------------------------------------------

    def write_pam_status(self, supplier_slug: str, patch: dict) -> None:
        """Merge patch dict into existing PAM-STATUS.json for supplier_slug.

        INV-06: If this workspace is scoped to a supplier, it cannot write
        PAM-STATUS for a different supplier.
        Never overwrites wholesale — always merges patch into existing data.
        """
        if self._supplier_slug and self._supplier_slug != supplier_slug:
            raise WorkspaceScopeViolation(
                f"Workspace scoped to '{self._supplier_slug}' cannot write "
                f"PAM-STATUS for '{supplier_slug}'."
            )
        full_key = f"{self._retailer_slug}/{supplier_slug}/PAM-STATUS.json"

        # Read existing
        try:
            response = self._client.get_object(
                Bucket=self._workspace_bucket, Key=full_key
            )
            existing = json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                existing = {}
            else:
                raise

        # Deep merge (top-level keys)
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(existing.get(k), dict):
                existing[k].update(v)
            else:
                existing[k] = v

        self._client.put_object(
            Bucket=self._workspace_bucket,
            Key=full_key,
            Body=json.dumps(existing, indent=2, default=str).encode("utf-8"),
        )

    def read_pam_status(self, supplier_slug: str) -> dict:
        """Read PAM-STATUS.json for supplier_slug. Returns empty dict if absent.

        INV-06: If this workspace is scoped to a supplier, it cannot read
        PAM-STATUS for a different supplier.
        """
        if self._supplier_slug and self._supplier_slug != supplier_slug:
            raise WorkspaceScopeViolation(
                f"Workspace scoped to '{self._supplier_slug}' cannot read "
                f"PAM-STATUS for '{supplier_slug}'."
            )
        full_key = f"{self._retailer_slug}/{supplier_slug}/PAM-STATUS.json"
        try:
            response = self._client.get_object(
                Bucket=self._workspace_bucket, Key=full_key
            )
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return {}
            raise

    # ------------------------------------------------------------------
    # Session key
    # ------------------------------------------------------------------

    @property
    def session_key(self) -> str:
        """Returns: pipeline:{retailer_slug}:{supplier_slug}:{role}"""
        return f"pipeline:{self._retailer_slug}:{self._supplier_slug or 'admin'}:workspace"
