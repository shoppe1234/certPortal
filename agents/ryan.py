"""agents/ryan.py — Patch Generator.

INV-01: Ryan never imports from other agent files.
INV-04: No LangChain abstractions.

Ryan's patch pipeline:
  1. Read ValidationResult errors array
  2. For each error: check if THESIS.md has a rule for the segment
  3. If rule exists: generate human-readable fix summary (GPT-4o-mini)
  4. If no rule: write ambiguity flag to PAM-STATUS.json + GLOBAL-FEEDBACK.md, skip
  5. Write patch .md file to supplier workspace (patches/ folder)
  6. Insert patch_suggestions DB row
  7. Log all patches to Monica

Hard rules:
  - Never modifies the original EDI file
  - Never sends patches to supplier directly (Chrissy portal surfaces them)
  - Ambiguity → write flag + return early for that error (process remaining errors)

OpenAI usage: GPT-4o-mini for human-readable fix summaries (real calls).

CLI: python -m agents.ryan --retailer <slug> --supplier <slug> --result-key <s3-key>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone

from openai import OpenAI

from certportal.core import monica_logger
from certportal.core.config import settings
from certportal.core.models import PatchSuggestion, ValidationResult, ValidationError
from certportal.core.workspace import S3AgentWorkspace, FileNotFoundInWorkspace

_openai_client = OpenAI(api_key=settings.openai_api_key)

RYAN_PATCH_PROMPT = """You are an EDI compliance expert helping a supplier fix a validation error.
Segment: {segment}
Element: {element}
Error code: {error_code}
Error message: {error_message}
Retailer rule from THESIS: {thesis_rule}
Write a clear, actionable fix instruction for a non-technical EDI coordinator.
- Maximum 3 sentences
- Use plain English, not EDI jargon
- End with the exact corrected value if deterministic
Return only the instruction text. No preamble."""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run(
    retailer_slug: str,
    supplier_slug: str,
    validation_result: ValidationResult,
) -> list[PatchSuggestion]:
    """Generate patch suggestions for each error in the ValidationResult.

    Args:
        retailer_slug:      Retailer identifier
        supplier_slug:      Supplier identifier
        validation_result:  The ValidationResult from Moses

    Returns:
        List of PatchSuggestion models (one per actionable error)
    """
    monica_logger.log(
        "RYAN",
        "A",
        f"Patch generation started. supplier={supplier_slug} "
        f"tx={validation_result.transaction_type} errors={len(validation_result.errors)}",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    if not validation_result.errors:
        monica_logger.log(
            "RYAN",
            "A",
            "No errors to patch — ValidationResult has no errors.",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )
        return []

    workspace = S3AgentWorkspace(retailer_slug, supplier_slug)

    # Download THESIS.md for rule lookup
    thesis_rules = _load_thesis_rules(workspace, retailer_slug, supplier_slug)

    patches: list[PatchSuggestion] = []

    for error in validation_result.errors:
        # Check THESIS.md for a rule covering this segment
        thesis_rule = _find_thesis_rule(thesis_rules, error.segment)

        if not thesis_rule:
            # INV-02: ambiguity → write flag + return early for this error
            _write_ambiguity_flag(workspace, supplier_slug, error, retailer_slug, supplier_slug)
            monica_logger.log(
                "RYAN",
                "Q",
                f"Ambiguity: no THESIS.md rule for segment {error.segment} "
                f"(error {error.code}). HITL flag raised.",
                retailer_slug=retailer_slug,
                supplier_slug=supplier_slug,
            )
            continue  # Process remaining errors

        # Generate fix summary (GPT-4o-mini)
        try:
            summary = _generate_patch_summary(error, thesis_rule)
        except Exception as exc:  # noqa: BLE001
            monica_logger.log(
                "RYAN",
                "Q",
                f"GPT-4o-mini call failed for {error.code}: {exc!r}. Skipping.",
                retailer_slug=retailer_slug,
                supplier_slug=supplier_slug,
            )
            continue

        # Write patch .md to supplier workspace (never modifies original EDI)
        patch_key = _write_patch_file(
            workspace=workspace,
            error=error,
            summary=summary,
            transaction_type=validation_result.transaction_type,
        )

        patch = PatchSuggestion(
            error_code=error.code,
            segment=error.segment,
            element=error.element,
            summary=summary,
            patch_s3_key=patch_key,
            applied=False,
            created_by="ryan",
        )
        patches.append(patch)

        # Mirror to DB (best-effort)
        try:
            asyncio.run(
                _insert_patch_suggestion(
                    patch=patch,
                    retailer_slug=retailer_slug,
                    supplier_slug=supplier_slug,
                )
            )
        except Exception as exc:  # noqa: BLE001
            monica_logger.log(
                "RYAN",
                "Q",
                f"DB write failed for patch {error.code} (non-fatal): {exc!r}",
                retailer_slug=retailer_slug,
                supplier_slug=supplier_slug,
            )

        monica_logger.log(
            "RYAN",
            "A",
            f"Patch written for {error.code} [{error.segment}]. key={patch_key}",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )

    monica_logger.log(
        "RYAN",
        "A",
        f"Patch generation complete. {len(patches)} patches produced from "
        f"{len(validation_result.errors)} errors.",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    return patches


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_thesis_rules(
    workspace: S3AgentWorkspace,
    retailer_slug: str,
    supplier_slug: str,
) -> str:
    """Download THESIS.md and return its text. Returns empty string if absent."""
    try:
        raw = workspace.download_retailer_map("THESIS.md")
        return raw.decode("utf-8")
    except FileNotFoundInWorkspace:
        monica_logger.log(
            "RYAN",
            "Q",
            f"THESIS.md not found for retailer '{retailer_slug}'. "
            "Rule lookups will fail — all segments will flag as ambiguous.",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )
        return ""


def _find_thesis_rule(thesis_text: str, segment: str) -> str | None:
    """Search THESIS.md for a rule referencing segment. Returns rule text or None."""
    if not thesis_text:
        return None

    # Look for the segment name in THESIS.md (case-insensitive)
    pattern = re.compile(
        rf"(?:^|\n)(?:.*?\b{re.escape(segment)}\b.*)(?:\n(?![#]).*)*",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(thesis_text)
    if match:
        return match.group(0).strip()[:500]  # Cap at 500 chars

    # Also check under the "Known Retailer-Specific Rules" section
    rules_section = re.search(
        r"## Known Retailer-Specific Rules\n(.*?)(?=\n## |\Z)",
        thesis_text,
        re.DOTALL,
    )
    if rules_section:
        rules_text = rules_section.group(1)
        if re.search(rf"\b{re.escape(segment)}\b", rules_text, re.IGNORECASE):
            return rules_text.strip()[:500]

    return None


def _generate_patch_summary(error: ValidationError, thesis_rule: str) -> str:
    """Call GPT-4o-mini to generate a human-readable fix instruction. Single call."""
    prompt = RYAN_PATCH_PROMPT.format(
        segment=error.segment,
        element=error.element or "N/A",
        error_code=error.code,
        error_message=error.message,
        thesis_rule=thesis_rule[:300],
    )
    response = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.0,
    )
    return response.choices[0].message.content.strip()


def _write_patch_file(
    workspace: S3AgentWorkspace,
    error: ValidationError,
    summary: str,
    transaction_type: str,
) -> str:
    """Write a human-readable patch .md file to the patches/ folder in supplier workspace.

    NEVER modifies the original EDI file.
    Returns the full S3 key of the written patch file.
    """
    ts = _utcnow_ts()
    filename = f"patches/{transaction_type}_{error.segment}_{error.code}_{ts}.md"

    content = f"""# EDI Patch — {error.code}

**Transaction:** {transaction_type}
**Segment:** {error.segment}
**Element:** {error.element or "N/A"}
**Error severity:** {error.severity}
**Generated at:** {_utcnow_iso()}
**Generated by:** Ryan

## Error
{error.message}

## Fix Instruction
{summary}

---
*This patch suggestion was generated automatically by certPortal.*
*Original EDI file was NOT modified.*
"""
    return workspace.upload(filename, content)


def _write_ambiguity_flag(
    workspace: S3AgentWorkspace,
    supplier_slug: str,
    error: ValidationError,
    retailer_slug: str,
    _supplier_slug: str,
) -> None:
    """Write ambiguity flag to PAM-STATUS.json and GLOBAL-FEEDBACK.md (INV-02)."""
    flag_key = f"ryan_ambiguity_{error.segment}_{error.code}"

    workspace.write_pam_status(
        supplier_slug,
        {
            "hitl_flag": True,
            "agent": "ryan",
            "reason": f"No THESIS.md rule for segment {error.segment} (error {error.code})",
            "hitl_flags": {
                flag_key: {
                    "agent": "ryan",
                    "reason": f"No THESIS.md rule for segment {error.segment}",
                    "error_code": error.code,
                    "segment": error.segment,
                    "status": "PENDING",
                    "timestamp": _utcnow_iso(),
                }
            },
        },
    )

    workspace.append_log(
        "GLOBAL-FEEDBACK.md",
        f"[{_utcnow_iso()}] [RYAN] AMBIGUITY: No THESIS.md rule for segment "
        f"{error.segment} (error {error.code}). HITL flag raised.",
    )


async def _insert_patch_suggestion(
    patch: PatchSuggestion,
    retailer_slug: str,
    supplier_slug: str,
) -> None:
    from certportal.core.database import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO patch_suggestions
                (supplier_slug, retailer_slug, error_code, segment, element,
                 summary, patch_s3_key, applied)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            supplier_slug,
            retailer_slug,
            patch.error_code,
            patch.segment,
            patch.element,
            patch.summary,
            patch.patch_s3_key,
            patch.applied,
        )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utcnow_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ryan — Patch Generator")
    parser.add_argument("--retailer", required=True, help="Retailer slug")
    parser.add_argument("--supplier", required=True, help="Supplier slug")
    parser.add_argument(
        "--result-key",
        required=True,
        help="S3 key of ValidationResult JSON in supplier workspace",
    )
    args = parser.parse_args()

    workspace = S3AgentWorkspace(args.retailer, args.supplier)
    raw = workspace.download(args.result_key)
    result = ValidationResult.model_validate_json(raw)

    patches = run(
        retailer_slug=args.retailer,
        supplier_slug=args.supplier,
        validation_result=result,
    )
    print(json.dumps([p.model_dump() for p in patches], indent=2, default=str))
