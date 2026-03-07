"""
lifecycle_engine/s3_writer.py

Writes lifecycle violation records to S3 for Monica (INV-02).

Uses the existing S3AgentWorkspace abstraction from certportal.core.
Does NOT use raw boto3 directly.

S3 path pattern:
    {retailer_slug}/{supplier_slug}/lifecycle/violations/{correlation_id}.json

This module is imported by engine.py. If certportal.core is unavailable
(e.g., testing in a standalone pyedi_core environment), import errors are
handled by callers via try/except ImportError.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from certportal.core.workspace import S3AgentWorkspace

logger = logging.getLogger(__name__)


def write_violation_to_s3(
    violation: dict,
    retailer_slug: str,
    supplier_slug: str,
    workspace: "S3AgentWorkspace",
) -> None:
    """
    Write a structured violation record to S3 under the lifecycle/violations/ prefix.

    The workspace is scoped to {retailer_slug}/{supplier_slug}/, so the final
    S3 key becomes:
        {retailer_slug}/{supplier_slug}/lifecycle/violations/{correlation_id}.json

    Args:
        violation:      Violation dict (same structure as lifecycle_violations row).
        retailer_slug:  Retailer slug (e.g. 'lowes'). Used by S3AgentWorkspace scope.
        supplier_slug:  Supplier slug. Used by S3AgentWorkspace scope.
        workspace:      An initialised S3AgentWorkspace instance scoped to the
                        correct retailer/supplier pair.

    Note:
        This function does NOT raise on failure — it logs the error and returns.
        Per TRD §6.6, S3 write failures must not re-raise or fail the pipeline.
    """
    try:
        correlation_id = violation.get("correlation_id", "unknown")
        key = f"lifecycle/violations/{correlation_id}.json"

        # Add server-side timestamp for Monica's reference
        payload = {
            **violation,
            "written_at": datetime.now(tz=timezone.utc).isoformat(),
            "retailer_slug": retailer_slug,
            "supplier_slug": supplier_slug,
        }

        workspace.upload(key, json.dumps(payload, default=str, indent=2))

        logger.info(
            "s3_writer: violation written to S3 key='%s' type='%s' po='%s'",
            key,
            violation.get("violation_type"),
            violation.get("po_number"),
        )

    except Exception as exc:
        # Per TRD §6.6: log error, do not re-raise.
        logger.error(
            "s3_writer: failed to write violation to S3 for correlation_id=%s: %s",
            violation.get("correlation_id"),
            exc,
        )
