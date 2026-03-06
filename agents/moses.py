"""agents/moses.py — Payload Analyst (EDI validation).

INV-01: Moses never imports from other agent files.
INV-04: No LangChain abstractions.
Moses is FULLY DETERMINISTIC — no OpenAI calls.

Pipeline:
  1. Verify supplier workspace scope (raises WorkspaceScopeViolation on path escape)
  2. Download raw EDI from certportal-raw-edi bucket
  3. Download THESIS.md — raises ThesisMissing if not found (hard failure)
  4. Download {transaction_type}.yaml from retailer maps
  5. Call pyedi_core.validate() (Sprint 1: stubbed)
  6. Write ValidationResult to test_occurrences DB table
  7. Write result JSON to supplier workspace S3
  8. Log to Monica
  9. If FAIL: trigger Ryan by writing signal to workspace (does NOT call ryan.run())

CLI: python -m agents.moses --retailer <slug> --supplier <slug> --edi-key <key> --tx <850> --channel <gs1>
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone

from certportal.core import monica_logger
from certportal.core.models import ValidationError, ValidationResult
from certportal.core.workspace import S3AgentWorkspace, FileNotFoundInWorkspace, WorkspaceScopeViolation

# ---------------------------------------------------------------------------
# pyedi_core stub (Sprint 1)
# Sprint 2: replace with: import pyedi_core
# ---------------------------------------------------------------------------

try:
    import pyedi_core  # type: ignore[import]
    _PYEDI_AVAILABLE = True
except ImportError:
    _PYEDI_AVAILABLE = False

    class _PyEdiCoreStub:
        """Sprint 1 stub for pyedi_core.validate(). Returns no errors (always PASS)."""

        @staticmethod
        def validate(
            edi_content: str,
            transaction_type: str,
            thesis_rules: dict | None = None,
            yaml_map: dict | None = None,
        ) -> list[dict]:
            # Sprint 1: stub returns no validation errors
            return []

    pyedi_core = _PyEdiCoreStub()  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ThesisMissing(Exception):
    """Moses cannot run without THESIS.md. This is a hard failure (not a warning)."""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run(
    retailer_slug: str,
    supplier_slug: str,
    raw_edi_s3_key: str,
    transaction_type: str,
    channel: str,
) -> ValidationResult:
    """Run Moses's EDI validation pipeline.

    Args:
        retailer_slug:    Retailer identifier
        supplier_slug:    Supplier identifier
        raw_edi_s3_key:   S3 key in certportal-raw-edi bucket
        transaction_type: X12 transaction code (e.g. "850")
        channel:          Communication channel (e.g. "gs1", "edi-direct")

    Returns:
        ValidationResult with status PASS, FAIL, or PARTIAL

    Raises:
        ThesisMissing:          If THESIS.md is not found for retailer
        WorkspaceScopeViolation: If supplier workspace scope is violated
    """
    monica_logger.log(
        "MOSES",
        "A",
        f"Validation started. retailer={retailer_slug} supplier={supplier_slug} "
        f"tx={transaction_type} channel={channel} edi_key={raw_edi_s3_key}",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    # 1. Initialise scoped workspace — INV-06 enforced by constructor
    workspace = S3AgentWorkspace(retailer_slug, supplier_slug)

    # Verify scope (explicit check in addition to class invariant)
    _verify_supplier_scope(workspace, retailer_slug, supplier_slug)

    # 2. Download raw EDI
    edi_bytes = workspace.download_raw_edi(raw_edi_s3_key)
    edi_content = edi_bytes.decode("utf-8", errors="replace")
    monica_logger.log(
        "MOSES",
        "A",
        f"Raw EDI downloaded: {raw_edi_s3_key} ({len(edi_bytes)} bytes)",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    # 3. Download THESIS.md — hard failure if absent
    try:
        thesis_bytes = workspace.download_retailer_map("THESIS.md")
        thesis_text = thesis_bytes.decode("utf-8")
    except FileNotFoundInWorkspace:
        monica_logger.log(
            "MOSES",
            "Q",
            f"HARD FAILURE: THESIS.md not found for retailer '{retailer_slug}'. "
            f"Run Dwight first.",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )
        raise ThesisMissing(
            f"THESIS.md not found for retailer '{retailer_slug}'. "
            "Run Dwight's spec analysis before Moses."
        )

    thesis_rules = _parse_thesis_rules(thesis_text)

    # 4. Download transaction YAML map
    yaml_map: dict | None = None
    try:
        yaml_bytes = workspace.download_retailer_map(f"maps/{transaction_type}.yaml")
        import yaml as _yaml
        yaml_map = _yaml.safe_load(yaml_bytes.decode("utf-8"))
        monica_logger.log(
            "MOSES",
            "A",
            f"Loaded maps/{transaction_type}.yaml for retailer {retailer_slug}.",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )
    except FileNotFoundInWorkspace:
        monica_logger.log(
            "MOSES",
            "Q",
            f"No YAML map found for tx {transaction_type} — validating without map.",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )

    # 5. Run pyedi_core.validate() (Sprint 1: stubbed)
    raw_errors: list[dict] = pyedi_core.validate(
        edi_content=edi_content,
        transaction_type=transaction_type,
        thesis_rules=thesis_rules,
        yaml_map=yaml_map,
    )

    # 6. Build ValidationResult
    errors = [
        ValidationError(
            code=e.get("code", "UNKNOWN"),
            segment=e.get("segment", "?"),
            element=e.get("element"),
            message=e.get("message", ""),
            severity=e.get("severity", "ERROR"),
        )
        for e in raw_errors
    ]

    status: str
    if not errors:
        status = "PASS"
    elif all(e.severity == "WARNING" for e in errors):
        status = "PARTIAL"
    else:
        status = "FAIL"

    result = ValidationResult(
        supplier_slug=supplier_slug,
        retailer_slug=retailer_slug,
        transaction_type=transaction_type,
        channel=channel,
        status=status,  # type: ignore[arg-type]
        errors=errors,
        passed_at=datetime.now(timezone.utc) if status == "PASS" else None,
        validated_by="moses",
    )

    # 7. Write result JSON to supplier workspace
    result_key = f"results/{transaction_type}_{_utcnow_ts()}.json"
    workspace.upload(result_key, result.model_dump_json(indent=2))
    monica_logger.log(
        "MOSES",
        "A",
        f"Result ({status}) written to {result_key}. Errors: {len(errors)}",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    # 8. Mirror to DB (best-effort)
    try:
        asyncio.run(_insert_test_occurrence(result))
    except Exception as exc:  # noqa: BLE001
        monica_logger.log(
            "MOSES",
            "Q",
            f"DB write failed (non-fatal): {exc!r}",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )

    # 9. If FAIL: trigger Ryan via workspace signal (INV-01: no direct call)
    if status == "FAIL":
        signal = {
            "trigger": "ryan",
            "validation_result_key": result_key,
            "retailer_slug": retailer_slug,
            "supplier_slug": supplier_slug,
            "transaction_type": transaction_type,
            "error_count": len(errors),
            "triggered_at": _utcnow_iso(),
        }
        workspace.upload(
            f"signals/ryan_trigger_{transaction_type}_{_utcnow_ts()}.json",
            json.dumps(signal, indent=2),
        )
        monica_logger.log(
            "MOSES",
            "Q",
            f"FAIL result. Ryan trigger signal written for {transaction_type}.",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )

    monica_logger.log(
        "MOSES",
        "A",
        f"Validation complete. Status={status} Errors={len(errors)}",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verify_supplier_scope(
    workspace: S3AgentWorkspace,
    retailer_slug: str,
    supplier_slug: str,
) -> None:
    """Explicit scope verification. WorkspaceScopeViolation raised on mismatch."""
    if workspace._retailer_slug != retailer_slug:
        raise WorkspaceScopeViolation(
            f"Workspace retailer '{workspace._retailer_slug}' does not match "
            f"expected '{retailer_slug}'."
        )
    if workspace._supplier_slug != supplier_slug:
        raise WorkspaceScopeViolation(
            f"Workspace supplier '{workspace._supplier_slug}' does not match "
            f"expected '{supplier_slug}'."
        )


def _parse_thesis_rules(thesis_text: str) -> dict:
    """Extract key rules from THESIS.md for use in validation."""
    rules: dict = {"raw_thesis": thesis_text}
    # Parse transaction requirements block (between ## Transaction Requirements and ## Channel)
    import re
    tx_match = re.search(
        r"## Transaction Requirements\n(.*?)(?=\n## |\Z)",
        thesis_text,
        re.DOTALL,
    )
    if tx_match:
        rules["transaction_requirements_raw"] = tx_match.group(1).strip()

    rules_match = re.search(
        r"## Known Retailer-Specific Rules\n(.*?)(?=\n## |\Z)",
        thesis_text,
        re.DOTALL,
    )
    if rules_match:
        rules["retailer_specific_rules_raw"] = rules_match.group(1).strip()

    return rules


async def _insert_test_occurrence(result: ValidationResult) -> None:
    from certportal.core.database import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO test_occurrences
                (supplier_slug, retailer_slug, transaction_type, channel, status, result_json)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            result.supplier_slug,
            result.retailer_slug,
            result.transaction_type,
            result.channel,
            result.status,
            result.model_dump_json(),
        )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utcnow_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Moses — EDI Payload Analyst (deterministic)")
    parser.add_argument("--retailer", required=True, help="Retailer slug")
    parser.add_argument("--supplier", required=True, help="Supplier slug")
    parser.add_argument("--edi-key", required=True, help="S3 key in certportal-raw-edi bucket")
    parser.add_argument("--tx", required=True, help="X12 transaction code (e.g. 850)")
    parser.add_argument("--channel", required=True, help="Channel (e.g. gs1, edi-direct)")
    args = parser.parse_args()

    result = run(
        retailer_slug=args.retailer,
        supplier_slug=args.supplier,
        raw_edi_s3_key=args.edi_key,
        transaction_type=args.tx,
        channel=args.channel,
    )
    print(result.model_dump_json(indent=2))
