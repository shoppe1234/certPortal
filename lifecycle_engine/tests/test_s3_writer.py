"""
Tests for lifecycle_engine/s3_writer.py

All tests mock S3AgentWorkspace — no real S3 calls.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from lifecycle_engine.s3_writer import write_violation_to_s3


def _sample_violation(corr: str = "corr-test") -> dict:
    return {
        "po_number": "P001",
        "partner_id": "lowes",
        "transaction_set": "850",
        "source_file": "test.edi",
        "correlation_id": corr,
        "violation_type": "missing_po",
        "violation_detail": "PO number not found",
        "current_state": None,
        "attempted_event": "po_originated",
    }


class TestWriteViolationToS3:
    def test_calls_workspace_upload_with_json(self):
        """Violation dict is serialised to JSON and uploaded to correct key."""
        workspace = MagicMock()
        violation = _sample_violation("abc-123")

        write_violation_to_s3(
            violation=violation,
            retailer_slug="lowes",
            supplier_slug="acme",
            workspace=workspace,
        )

        workspace.upload.assert_called_once()
        call_args = workspace.upload.call_args
        key = call_args[0][0]
        payload_bytes = call_args[0][1]

        assert "lifecycle/violations/" in key
        assert "abc-123" in key
        # Payload is valid JSON containing the violation
        parsed = json.loads(payload_bytes)
        assert parsed["violation_type"] == "missing_po"
        assert parsed["po_number"] == "P001"

    def test_no_workspace_is_noop(self):
        """When workspace is None the function returns without error."""
        # Should not raise
        write_violation_to_s3(
            violation=_sample_violation(),
            retailer_slug="lowes",
            supplier_slug="acme",
            workspace=None,
        )

    def test_upload_exception_is_swallowed(self):
        """S3 errors must never propagate — lifecycle hook must not break pipeline."""
        workspace = MagicMock()
        workspace.upload.side_effect = RuntimeError("S3 unreachable")

        # Should NOT raise
        write_violation_to_s3(
            violation=_sample_violation(),
            retailer_slug="lowes",
            supplier_slug="acme",
            workspace=workspace,
        )
        workspace.upload.assert_called_once()

    def test_key_uses_correlation_id(self):
        """Output S3 key embeds the correlation_id for traceability."""
        workspace = MagicMock()
        write_violation_to_s3(
            violation=_sample_violation("unique-corr-id-xyz"),
            retailer_slug="lowes",
            supplier_slug="acme",
            workspace=workspace,
        )
        key = workspace.upload.call_args[0][0]
        assert "unique-corr-id-xyz" in key

    def test_payload_is_bytes_or_str(self):
        """workspace.upload receives bytes or str (not a raw dict)."""
        workspace = MagicMock()
        write_violation_to_s3(
            violation=_sample_violation(),
            retailer_slug="lowes",
            supplier_slug="acme",
            workspace=workspace,
        )
        payload = workspace.upload.call_args[0][1]
        assert isinstance(payload, (bytes, str))
