"""seed_generator.py — FieldInventory → Andy Path 3 wizard_payload JSON.

Maps a FieldInventory (output of extractor.py) directly into the
wizard_payload shape that agents/andy.py run_path3_wizard() accepts.

This makes YAML generation fully deterministic:
  PDF → (GPT-4o, schema-constrained) → FieldInventory → (pure Python) → wizard_payload
                                                                              ↓
                                                                   Andy Path 3 → YAML

The wizard_payload shape Andy expects:
  {
    "transaction_types": ["850"],
    "transactions": {
      "850": {
        "field_mappings": {
          "BEG": {"BEG01": "...", "BEG03": "..."},
          ...
        },
        "qualifiers": {
          "BEG01": ["00", "05"],
          ...
        },
        "business_rules": ["..."]
      }
    }
  }

No external dependencies — stdlib only.
"""
from __future__ import annotations

import json
from typing import Any

from lab_850.schema import FieldInventory


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_seed(
    inventory: FieldInventory,
    transaction_type: str = "850",
) -> dict[str, Any]:
    """Produce an Andy Path 3 wizard_payload from a FieldInventory.

    Args:
        inventory:        FieldInventory extracted from a retailer TPG PDF.
        transaction_type: X12 transaction code (default "850").

    Returns:
        A dict ready to pass to run_path3_wizard() or POST to /yaml-wizard/path3.
    """
    field_mappings: dict[str, dict[str, str]] = {}
    qualifiers: dict[str, list[str]] = {}

    for seg_id, seg_spec in inventory.segments.items():
        if not seg_spec.elements:
            continue

        seg_mappings: dict[str, str] = {}
        for elem_id, elem_spec in seg_spec.elements.items():
            # Build a human-readable description for this element's mapping entry.
            # Includes description + any constraints as a compact string.
            parts = [elem_spec.description] if elem_spec.description else []
            if elem_spec.constraints:
                parts.append("; ".join(elem_spec.constraints))
            required_flag = "required" if elem_spec.required else "optional"
            parts.append(f"[{required_flag}]")
            seg_mappings[elem_id] = " — ".join(parts) if parts else elem_id

            # Qualifiers — only include elements that have specific qualifier values
            if elem_spec.qualifier_values:
                qualifiers[elem_id] = list(elem_spec.qualifier_values)

        field_mappings[seg_id] = seg_mappings

    payload: dict[str, Any] = {
        "retailer_slug": inventory.retailer_slug,
        "transaction_types": [transaction_type],
        "transactions": {
            transaction_type: {
                "field_mappings": field_mappings,
                "qualifiers": qualifiers,
                "business_rules": list(inventory.business_rules),
            }
        },
        "_meta": {
            "generated_by": "lab_850.seed_generator",
            "source_pdf": inventory.source_pdf,
            "spec_version": inventory.spec_version,
            "extracted_at": inventory.extracted_at,
            "confidence": inventory.confidence,
        },
    }
    return payload


def generate_seed_json(inventory: FieldInventory, indent: int = 2) -> str:
    """Return the wizard_payload as a formatted JSON string."""
    return json.dumps(generate_seed(inventory), indent=indent)


# ---------------------------------------------------------------------------
# Multi-retailer merge: produce a common seed pre-filled from shared elements
# ---------------------------------------------------------------------------


def generate_merged_seed(
    inventories: list[FieldInventory],
    transaction_type: str = "850",
    require_all: bool = True,
) -> dict[str, Any]:
    """Merge multiple FieldInventory objects into a single seed.

    Args:
        inventories:      List of FieldInventory objects (one per retailer).
        transaction_type: X12 transaction code.
        require_all:      If True, only include elements present in ALL inventories.
                          If False, include elements present in ANY inventory (union).

    Returns:
        A wizard_payload with the shared/common field mappings pre-filled.
        Retailer-specific qualifiers are listed with their source retailer noted.
    """
    from collections import defaultdict

    if not inventories:
        raise ValueError("At least one FieldInventory is required.")

    n = len(inventories)

    # Count element occurrences across retailers
    # element_data[(seg_id, elem_id)] = list of ElementSpec (one per retailer)
    element_data: dict[tuple[str, str], list] = defaultdict(list)

    for inv in inventories:
        for seg_id, seg_spec in inv.segments.items():
            for elem_id, elem_spec in seg_spec.elements.items():
                element_data[(seg_id, elem_id)].append(elem_spec)

    field_mappings: dict[str, dict[str, str]] = {}
    qualifiers: dict[str, list[str]] = {}
    business_rules: list[str] = []

    for (seg_id, elem_id), specs in element_data.items():
        if require_all and len(specs) < n:
            continue  # Skip elements not present in all retailers

        # Use the first spec as representative; note divergence
        rep = specs[0]
        parts = [rep.description] if rep.description else []
        required_flag = "required" if rep.required else "optional"
        parts.append(f"[{required_flag}]")
        if rep.constraints:
            parts.append("; ".join(rep.constraints))

        field_mappings.setdefault(seg_id, {})[elem_id] = (
            " — ".join(parts) if parts else elem_id
        )

        # Merge qualifier values (union across all retailers)
        all_quals: list[str] = []
        for spec in specs:
            for q in spec.qualifier_values:
                if q not in all_quals:
                    all_quals.append(q)
        if all_quals:
            qualifiers[elem_id] = all_quals

    # Merge business rules (deduplicated)
    seen_rules: set[str] = set()
    for inv in inventories:
        for rule in inv.business_rules:
            if rule not in seen_rules:
                business_rules.append(rule)
                seen_rules.add(rule)

    retailer_slugs = [inv.retailer_slug for inv in inventories]

    payload: dict[str, Any] = {
        "retailer_slug": "__merged__",
        "transaction_types": [transaction_type],
        "transactions": {
            transaction_type: {
                "field_mappings": field_mappings,
                "qualifiers": qualifiers,
                "business_rules": business_rules,
            }
        },
        "_meta": {
            "generated_by": "lab_850.seed_generator.generate_merged_seed",
            "source_retailers": retailer_slugs,
            "merge_mode": "intersection" if require_all else "union",
            "retailer_count": n,
        },
    }
    return payload
