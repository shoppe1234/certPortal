"""agents/andy.py — YAML Mapper (3-Path Ingestion).

INV-01: Andy never imports from other agent files.
INV-04: No LangChain abstractions.

Three ingestion paths:
  Path 1: PDF → YAML maps (LLM-assisted — GPT-4o-mini)
  Path 2: Uploaded YAML → validated + stored (fully deterministic)
  Path 3: Wizard form payload → YAML (fully deterministic; advisory lock)

CLI: python -m agents.andy --path {1|2|3} --retailer <slug> [--pdf-key|--yaml-key|--wizard-json <json>]
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI

from certportal.core import monica_logger
from certportal.core.config import settings
from certportal.core.workspace import S3AgentWorkspace, FileNotFoundInWorkspace

_openai_client = OpenAI(api_key=settings.openai_api_key)

SUPPORTED_BUNDLES: dict[str, list[str]] = {
    "general_merchandise": ["850", "855", "856", "810", "997"],
    "transportation": ["204", "990", "210", "214"],  # Sprint 2
}

# X12 005010 mandatory elements per transaction (minimal reference for validation)
_X12_MANDATORY: dict[str, dict[str, list[str]]] = {
    "850": {"ISA": ["ISA01", "ISA06", "ISA08"], "GS": ["GS01", "GS02", "GS03"], "BEG": ["BEG01", "BEG02", "BEG05"]},
    "855": {"ISA": ["ISA01", "ISA06", "ISA08"], "BAK": ["BAK01", "BAK02", "BAK04"]},
    "856": {"ISA": ["ISA01", "ISA06", "ISA08"], "BSN": ["BSN01", "BSN02", "BSN03", "BSN04"]},
    "810": {"ISA": ["ISA01", "ISA06", "ISA08"], "BIG": ["BIG01", "BIG02"]},
    "997": {"ISA": ["ISA01", "ISA06", "ISA08"], "AK1": ["AK101", "AK102"]},
}


# ---------------------------------------------------------------------------
# Path 1 — PDF → YAML (LLM-assisted)
# ---------------------------------------------------------------------------


def run_path1_pdf(retailer_slug: str, pdf_s3_key: str) -> list[str]:
    """Download retailer Trading Partner Guide PDF and extract YAML transaction maps.

    Uses GPT-4o-mini to extract transaction field mappings from PDF text.
    Returns list of S3 keys of written YAML maps.

    Note: THESIS.md is Dwight's output. Andy extracts YAML maps for validation.
    """
    import io
    import pdfplumber

    monica_logger.log(
        "ANDY",
        "A",
        f"Path 1 started. retailer={retailer_slug} pdf={pdf_s3_key}",
        retailer_slug=retailer_slug,
    )

    workspace = S3AgentWorkspace(retailer_slug)

    # Download PDF
    pdf_bytes = workspace.download_raw_edi(pdf_s3_key)

    # Extract text
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    pdf_text = "\n\n".join(text_parts)[:80_000]

    written_keys: list[str] = []
    bundle = _detect_bundle(pdf_text)
    transaction_codes = SUPPORTED_BUNDLES.get(bundle, SUPPORTED_BUNDLES["general_merchandise"])

    for tx_code in transaction_codes:
        yaml_content = _extract_yaml_for_transaction(pdf_text, tx_code, retailer_slug)
        if yaml_content:
            key = f"maps/{tx_code}.yaml"
            full_key = workspace.upload(key, yaml_content)
            written_keys.append(full_key)
            monica_logger.log(
                "ANDY",
                "A",
                f"Path 1: wrote {key} for {retailer_slug}",
                retailer_slug=retailer_slug,
            )

    monica_logger.log(
        "ANDY",
        "A",
        f"Path 1 complete. {len(written_keys)} YAML maps written.",
        retailer_slug=retailer_slug,
    )
    return written_keys


# ---------------------------------------------------------------------------
# Path 2 — Uploaded YAML → validated + stored (deterministic)
# ---------------------------------------------------------------------------


def run_path2_upload(retailer_slug: str, yaml_s3_key: str) -> list[str]:
    """Validate and persist an uploaded YAML map. Fully deterministic — no LLM.

    Args:
        retailer_slug: Retailer identifier
        yaml_s3_key:   S3 key (in raw-edi bucket) of the uploaded YAML

    Returns:
        List of S3 keys written to workspace
    """
    import yaml as _yaml

    monica_logger.log(
        "ANDY",
        "A",
        f"Path 2 started. retailer={retailer_slug} yaml_key={yaml_s3_key}",
        retailer_slug=retailer_slug,
    )

    workspace = S3AgentWorkspace(retailer_slug)

    # Download uploaded YAML
    raw_bytes = workspace.download_raw_edi(yaml_s3_key)
    yaml_content = _yaml.safe_load(raw_bytes.decode("utf-8"))

    if not isinstance(yaml_content, dict):
        monica_logger.log(
            "ANDY",
            "Q",
            f"Path 2: uploaded YAML is not a mapping. Aborting. key={yaml_s3_key}",
            retailer_slug=retailer_slug,
        )
        return []

    transaction_type = yaml_content.get("transaction_type", "unknown")
    warnings = validate_yaml_against_x12(yaml_content, transaction_type)
    if warnings:
        for w in warnings:
            monica_logger.log("ANDY", "Q", f"Path 2 validation warning: {w}", retailer_slug=retailer_slug)

    # Store in workspace maps/
    import yaml as _yaml_out
    key = f"maps/{transaction_type}.yaml"
    full_key = workspace.upload(key, _yaml_out.dump(yaml_content, default_flow_style=False))

    monica_logger.log(
        "ANDY",
        "A",
        f"Path 2 complete. Wrote {key}. Warnings: {len(warnings)}",
        retailer_slug=retailer_slug,
    )
    return [full_key]


# ---------------------------------------------------------------------------
# Path 3 — Wizard form → YAML (deterministic; advisory lock)
# ---------------------------------------------------------------------------


def run_path3_wizard(retailer_slug: str, wizard_payload: dict) -> list[str]:
    """Serialize Meredith portal wizard form state to validated YAML.

    Fully deterministic — no LLM.
    Acquires PostgreSQL advisory lock before write (OD-02).
    Releases lock on completion OR exception (try/finally).

    Returns list of S3 keys of written YAML maps.
    """
    monica_logger.log(
        "ANDY",
        "A",
        f"Path 3 started. retailer={retailer_slug}",
        retailer_slug=retailer_slug,
    )

    written_keys = asyncio.run(_run_path3_wizard_async(retailer_slug, wizard_payload))

    monica_logger.log(
        "ANDY",
        "A",
        f"Path 3 complete. {len(written_keys)} YAML maps written.",
        retailer_slug=retailer_slug,
    )
    return written_keys


async def _run_path3_wizard_async(retailer_slug: str, wizard_payload: dict) -> list[str]:
    import yaml as _yaml

    from certportal.core.database import get_pool

    workspace = S3AgentWorkspace(retailer_slug)
    pool = await get_pool()
    written_keys: list[str] = []

    # OD-02: PostgreSQL advisory lock keyed to retailer_slug
    lock_key = hash(f"andy_path3_{retailer_slug}") & 0x7FFFFFFFFFFFFFFF

    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock($1)", lock_key)
        try:
            transaction_types = wizard_payload.get("transaction_types", [])
            for tx_code in transaction_types:
                tx_config = wizard_payload.get("transactions", {}).get(tx_code, {})
                yaml_doc = {
                    "transaction_type": tx_code,
                    "retailer_slug": retailer_slug,
                    "generated_by": "andy_path3_wizard",
                    "generated_at": _utcnow_iso(),
                    "field_mappings": tx_config.get("field_mappings", {}),
                    "qualifiers": tx_config.get("qualifiers", {}),
                    "business_rules": tx_config.get("business_rules", []),
                }
                warnings = validate_yaml_against_x12(yaml_doc, tx_code)
                for w in warnings:
                    monica_logger.log(
                        "ANDY", "Q", f"Path 3 wizard warning [{tx_code}]: {w}",
                        retailer_slug=retailer_slug,
                    )

                key = f"maps/{tx_code}.yaml"
                full_key = workspace.upload(key, _yaml.dump(yaml_doc, default_flow_style=False))
                written_keys.append(full_key)
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", lock_key)

    return written_keys


# ---------------------------------------------------------------------------
# Validation helper (deterministic, no LLM)
# ---------------------------------------------------------------------------


def validate_yaml_against_x12(yaml_content: dict, transaction_type: str) -> list[str]:
    """Validate a YAML map against X12 005010 schema.

    Returns list of validation warnings (empty list = valid).
    Never raises — warnings only.
    """
    warnings: list[str] = []

    if transaction_type not in _X12_MANDATORY:
        warnings.append(
            f"Transaction type '{transaction_type}' is not in the supported X12 005010 set: "
            f"{list(_X12_MANDATORY.keys())}."
        )
        return warnings

    required_segments = _X12_MANDATORY[transaction_type]
    field_mappings = yaml_content.get("field_mappings", {})

    for segment, elements in required_segments.items():
        segment_map = field_mappings.get(segment)
        if segment_map is None:
            warnings.append(
                f"Missing required segment '{segment}' mapping for transaction {transaction_type}."
            )
            continue
        for elem in elements:
            if elem not in segment_map:
                warnings.append(
                    f"Missing required element '{elem}' in segment '{segment}' "
                    f"for transaction {transaction_type}."
                )

    return warnings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _detect_bundle(pdf_text: str) -> str:
    """Heuristically detect which transaction bundle this TPG covers."""
    if any(code in pdf_text for code in ["204", "990", "210", "214"]):
        return "transportation"
    return "general_merchandise"


def _extract_yaml_for_transaction(pdf_text: str, tx_code: str, retailer_slug: str) -> str | None:
    """Use GPT-4o-mini to extract a YAML field mapping for one transaction code."""
    prompt = (
        f"You are an EDI mapping specialist. From the Trading Partner Guide below, "
        f"extract field-level mappings for transaction set {tx_code} (X12 005010). "
        f"Return a YAML document with keys: transaction_type, field_mappings, qualifiers, business_rules. "
        f"If this transaction is not described in the guide, return the word NULL only.\n\n"
        f"{pdf_text[:30_000]}"
    )
    response = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
        temperature=0.0,
    )
    content = response.choices[0].message.content.strip()
    if content == "NULL":
        return None
    return content


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Andy — YAML Mapper (3-Path Ingestion)")
    parser.add_argument("--path", choices=["1", "2", "3"], required=True)
    parser.add_argument("--retailer", required=True, help="Retailer slug")
    parser.add_argument("--pdf-key", help="S3 key for Path 1")
    parser.add_argument("--yaml-key", help="S3 key for Path 2")
    parser.add_argument("--wizard-json", help="JSON string of wizard payload for Path 3")
    args = parser.parse_args()

    if args.path == "1":
        assert args.pdf_key, "--pdf-key required for Path 1"
        keys = run_path1_pdf(args.retailer, args.pdf_key)
    elif args.path == "2":
        assert args.yaml_key, "--yaml-key required for Path 2"
        keys = run_path2_upload(args.retailer, args.yaml_key)
    else:
        assert args.wizard_json, "--wizard-json required for Path 3"
        keys = run_path3_wizard(args.retailer, json.loads(args.wizard_json))

    print(json.dumps(keys, indent=2))
