"""
Layer 2 Builder — Merges preset defaults with user overrides into Layer 2 YAML.

Takes: transaction_type + x12_version + preset_name + user_overrides -> Layer 2 YAML

The output is a valid transaction YAML that conforms to
edi_framework/meta/transaction_schema.yaml.

Architecture Decision: AD-6 from wizard refactoring prompt.
Constraint: NC-01 — edi_framework/ is READ-ONLY at runtime.
Constraint: NC-02 — YAML is the brain; presets come from YAML, not Python constants.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Optional

import yaml
from pykwalify.core import Core
from pykwalify.errors import SchemaError

from certportal.generators.template_loader import (
    load_preset_for_transaction,
    load_transaction_yaml,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_EDI_FRAMEWORK_DIR = Path(__file__).resolve().parents[2] / "edi_framework"
_META_DIR = _EDI_FRAMEWORK_DIR / "meta"
_TRANSACTION_SCHEMA_PATH = _META_DIR / "transaction_schema.yaml"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dicts. Values from override win on conflict.

    - Dicts are merged recursively.
    - Lists from override replace lists in base entirely.
    - Scalar values from override replace base values.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _get_transaction_metadata(transaction_type: str) -> dict:
    """
    Get base transaction metadata from edi_framework/transactions/*.yaml.

    Returns a dict with keys: id, name, functional_group, direction, version,
    shared_refs. Falls back to sensible defaults if the file is missing.
    """
    tx_data = load_transaction_yaml(transaction_type)
    tx = tx_data.get("transaction", {})

    # Transaction name lookup table (fallback when YAML not found)
    _TX_NAMES = {
        "850": ("Stock Purchase Order", "PO", "inbound"),
        "855": ("Purchase Order Acknowledgment", "PR", "outbound"),
        "856": ("Ship Notice/Manifest", "SH", "outbound"),
        "860": ("Purchase Order Change Request - Buyer Initiated", "PC", "inbound"),
        "865": ("PO Change Acknowledgment (Seller Initiated)", "PC", "outbound"),
        "810": ("Invoice", "IN", "outbound"),
    }

    if tx:
        return {
            "id": tx.get("id", transaction_type),
            "name": tx.get("name", ""),
            "functional_group": tx.get("functional_group", ""),
            "direction": tx.get("direction", "inbound"),
            "version": tx.get("version", "004010"),
            "shared_refs": tx.get("shared_refs", {
                "envelope": "shared/envelope.yaml",
                "common": "shared/common_segments.yaml",
                "codelists": "shared/codelists.yaml",
            }),
        }

    # Fallback
    name, fg, direction = _TX_NAMES.get(
        transaction_type, (f"Transaction {transaction_type}", "XX", "inbound")
    )
    return {
        "id": transaction_type,
        "name": name,
        "functional_group": fg,
        "direction": direction,
        "version": "004010",
        "shared_refs": {
            "envelope": "shared/envelope.yaml",
            "common": "shared/common_segments.yaml",
            "codelists": "shared/codelists.yaml",
        },
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_layer2(yaml_content: str) -> list[str]:
    """
    Validate Layer 2 YAML content against the transaction meta-schema.

    Args:
        yaml_content: YAML string to validate.

    Returns:
        List of validation error messages. Empty list means valid.
    """
    errors: list[str] = []

    # Parse YAML
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        errors.append(f"YAML parse error: {exc}")
        return errors

    if not isinstance(data, dict):
        errors.append("Layer 2 YAML must be a mapping at the top level")
        return errors

    # Load schema
    if not _TRANSACTION_SCHEMA_PATH.is_file():
        errors.append(f"Transaction meta-schema not found: {_TRANSACTION_SCHEMA_PATH}")
        return errors

    try:
        with open(_TRANSACTION_SCHEMA_PATH, "r", encoding="utf-8") as fh:
            schema_data = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError) as exc:
        errors.append(f"Failed to load transaction meta-schema: {exc}")
        return errors

    # Validate with pykwalify
    try:
        c = Core(source_data=data, schema_data=schema_data)
        c.validate(raise_exception=True)
    except SchemaError as exc:
        for err in exc.errors:
            errors.append(str(err))
        if not exc.errors:
            errors.append(str(exc))

    return errors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_layer2(
    transaction_type: str,
    x12_version: str = "004010",
    preset_name: str = "standard_retail",
    overrides: Optional[dict] = None,
) -> str:
    """
    Build a Layer 2 YAML string for a given transaction type.

    Resolution order:
      1. Load preset defaults from layer2_presets.yaml
      2. Merge user overrides (user values win on conflict)
      3. Wrap in valid transaction YAML structure
      4. Return as YAML string

    Args:
        transaction_type: X12 transaction set code (e.g. "850", "855").
        x12_version: X12 version (e.g. "004010").
        preset_name: Preset key (e.g. "standard_retail", "minimal", "blank").
        overrides: Optional dict of user overrides with structure:
                   {
                     "segments": {
                       "BEG": {
                         "elements": {
                           "BEG01": {"qualifier": "05", "note": "Replace"}
                         }
                       }
                     },
                     "business_rules": [...],
                     "mapping_refs": [...]
                   }

    Returns:
        Valid Layer 2 YAML string conforming to transaction_schema.yaml.
    """
    # 1. Load preset defaults
    preset = load_preset_for_transaction(preset_name, transaction_type)

    # 2. Merge user overrides
    if overrides and isinstance(overrides, dict):
        preset = _deep_merge(preset, overrides)

    # 3. Get base transaction metadata
    meta = _get_transaction_metadata(transaction_type)

    # Override version if user specified a different one
    meta["version"] = x12_version

    # 4. Build the transaction YAML structure
    # Split segments into heading and detail based on original transaction structure
    heading_segments = {}
    detail_segments = {}

    # Load original transaction to determine segment placement
    tx_data = load_transaction_yaml(transaction_type)
    tx = tx_data.get("transaction", {})
    original_heading_keys = set((tx.get("heading") or {}).keys())
    original_detail_keys = set((tx.get("detail") or {}).keys())

    for seg_name, seg_config in preset.get("segments", {}).items():
        if seg_name in original_detail_keys:
            detail_segments[seg_name] = seg_config
        else:
            # Default to heading for segments not found or in heading
            heading_segments[seg_name] = seg_config

    # Build the output structure
    transaction = {
        "transaction": {
            "id": meta["id"],
            "name": meta["name"],
            "functional_group": meta["functional_group"],
            "direction": meta["direction"],
            "version": meta["version"],
            "shared_refs": meta["shared_refs"],
            "heading": heading_segments if heading_segments else {"_placeholder": {"name": "placeholder"}},
        }
    }

    # Add detail section if there are detail segments
    if detail_segments:
        transaction["transaction"]["detail"] = detail_segments

    # Add business rules if present
    business_rules = preset.get("business_rules", [])
    if business_rules:
        transaction["transaction"]["business_rules"] = business_rules

    # Add mapping references if present
    mapping_refs = preset.get("mapping_refs", [])
    if mapping_refs:
        transaction["transaction"]["mapping_refs"] = mapping_refs

    # Remove placeholder if heading has real segments
    heading = transaction["transaction"]["heading"]
    if "_placeholder" in heading and len(heading) > 1:
        del heading["_placeholder"]

    return yaml.dump(
        transaction, default_flow_style=False, allow_unicode=True, sort_keys=False
    )


def get_mergeable_fields(transaction_type: str, preset_name: str) -> dict:
    """
    Return what fields can be overridden for a given transaction and preset.

    This is used by the frontend to render the override form — it shows
    which segments and elements the preset defines, so the user knows
    what can be customized.

    Args:
        transaction_type: X12 transaction set code (e.g. "850").
        preset_name: Preset key (e.g. "standard_retail").

    Returns:
        A dict with keys:
          - segments: dict of segment_name -> dict of element info
          - business_rules: list of rule dicts from the preset
          - mapping_refs: list of mapping file references
    """
    preset = load_preset_for_transaction(preset_name, transaction_type)

    # Build a flattened view of mergeable fields
    segments_info: dict = {}
    for seg_name, seg_config in preset.get("segments", {}).items():
        if not isinstance(seg_config, dict):
            continue

        elements = seg_config.get("elements", {})
        overrides = seg_config.get("overrides", {})
        instances = seg_config.get("instances", [])

        seg_info: dict = {
            "elements": {},
            "has_instances": bool(instances),
            "instance_count": len(instances) if isinstance(instances, list) else 0,
        }

        # Collect element info
        for elem_name, elem_config in elements.items():
            if not isinstance(elem_config, dict):
                continue
            seg_info["elements"][elem_name] = {
                "qualifier": elem_config.get("qualifier"),
                "allowed_codes": elem_config.get("allowed_codes"),
                "note": elem_config.get("note", ""),
                "format": elem_config.get("format"),
                "constraints": elem_config.get("constraints"),
                "codelist_ref": elem_config.get("codelist_ref"),
            }

        # Collect override info
        for ovr_name, ovr_config in overrides.items():
            if not isinstance(ovr_config, dict):
                continue
            seg_info["elements"][ovr_name] = {
                "qualifier": ovr_config.get("qualifier") or ovr_config.get("fixed_value"),
                "allowed_codes": ovr_config.get("allowed_codes"),
                "note": ovr_config.get("note", ""),
                "is_override": True,
            }

        segments_info[seg_name] = seg_info

    return {
        "segments": segments_info,
        "business_rules": preset.get("business_rules", []),
        "mapping_refs": preset.get("mapping_refs", []),
    }
