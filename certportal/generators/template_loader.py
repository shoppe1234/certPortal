"""
Template Loader — Reads partner registry, presets, lifecycles, and transactions.

Returns wizard pre-fill data for the frontend:
  - Available lifecycles (with summary)
  - Available presets (with summary)
  - Available transactions per X12 version
  - Per-transaction segment/element defaults from the selected preset

Architecture Decision: AD-6, AD-7 from wizard refactoring prompt.
Constraint: NC-01 — edi_framework/ is READ-ONLY at runtime.
Constraint: NC-02 — YAML is the brain; presets come from YAML, not Python constants.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Optional

import yaml

from certportal.generators.version_registry import (
    get_available_versions,
    get_transaction_sets_for_version,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File paths (relative to project root)
# ---------------------------------------------------------------------------

_EDI_FRAMEWORK_DIR = Path(__file__).resolve().parents[2] / "edi_framework"
_PARTNER_REGISTRY_PATH = _EDI_FRAMEWORK_DIR / "partner_registry.yaml"
_PRESETS_PATH = _EDI_FRAMEWORK_DIR / "templates" / "layer2_presets.yaml"
_LIFECYCLE_DIR = _EDI_FRAMEWORK_DIR / "lifecycle"
_TRANSACTIONS_DIR = _EDI_FRAMEWORK_DIR / "transactions"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return its contents as a dict."""
    if not path.is_file():
        logger.warning("YAML file not found: %s", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("Failed to load YAML %s: %s", path, exc)
        return {}


def _count_states(lifecycle_data: dict) -> int:
    """Count the number of states in a lifecycle definition."""
    lc = lifecycle_data.get("lifecycle", {})
    states = lc.get("states", {})
    return len(states) if isinstance(states, dict) else 0


def _count_transactions(lifecycle_data: dict) -> set[str]:
    """Extract unique transaction set IDs referenced in lifecycle triggers."""
    lc = lifecycle_data.get("lifecycle", {})
    states = lc.get("states", {})
    tx_ids = set()
    if isinstance(states, dict):
        for state_config in states.values():
            if isinstance(state_config, dict):
                trigger = state_config.get("trigger", {})
                doc = trigger.get("document", "")
                if doc:
                    tx_ids.add(doc)
    return tx_ids


def _count_preset_transactions(preset_data: dict) -> int:
    """Count the number of transaction types in a preset."""
    transactions = preset_data.get("transactions", {})
    return len(transactions) if isinstance(transactions, dict) else 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_available_lifecycles() -> list[dict]:
    """
    Enumerate all lifecycle YAML files under edi_framework/lifecycle/.

    Returns a list of dicts with keys:
      - name: Human-readable lifecycle name
      - version: Lifecycle version string
      - filename: File basename (e.g. "order_to_cash.yaml")
      - ref: Relative path from edi_framework/ (e.g. "lifecycle/order_to_cash.yaml")
      - state_count: Number of states defined
      - transaction_count: Number of unique transaction types referenced
      - transactions: List of transaction set IDs used
    """
    if not _LIFECYCLE_DIR.is_dir():
        logger.warning("Lifecycle directory not found: %s", _LIFECYCLE_DIR)
        return []

    results = []
    for yaml_path in sorted(_LIFECYCLE_DIR.glob("*.yaml")):
        data = _load_yaml(yaml_path)
        if not data:
            continue

        lc = data.get("lifecycle", {})
        name = lc.get("name", yaml_path.stem)
        version = lc.get("version", "unknown")
        state_count = _count_states(data)
        tx_ids = _count_transactions(data)

        results.append({
            "name": name,
            "version": version,
            "filename": yaml_path.name,
            "ref": f"lifecycle/{yaml_path.name}",
            "state_count": state_count,
            "transaction_count": len(tx_ids),
            "transactions": sorted(tx_ids),
        })

    return results


def load_available_presets() -> list[dict]:
    """
    Enumerate all presets from edi_framework/templates/layer2_presets.yaml.

    Returns a list of dicts with keys:
      - name: Display name (e.g. "Standard Retail")
      - key: Preset key in YAML (e.g. "standard_retail")
      - description: Human-readable description
      - recommended: Whether this is the recommended preset
      - transaction_count: Number of transaction types covered
      - transactions: List of transaction type IDs covered
    """
    data = _load_yaml(_PRESETS_PATH)
    presets = data.get("presets", {})
    if not isinstance(presets, dict):
        return []

    results = []
    for key, preset in presets.items():
        if not isinstance(preset, dict):
            continue

        tx_map = preset.get("transactions", {})
        tx_list = sorted(tx_map.keys()) if isinstance(tx_map, dict) else []

        results.append({
            "name": preset.get("name", key),
            "key": key,
            "description": preset.get("description", "").strip(),
            "recommended": preset.get("recommended", False),
            "transaction_count": len(tx_list),
            "transactions": tx_list,
        })

    return results


def load_preset_for_transaction(preset_name: str, transaction_type: str) -> dict:
    """
    Load preset defaults for a specific transaction type.

    Args:
        preset_name: Preset key (e.g. "standard_retail", "minimal", "blank").
        transaction_type: Transaction set code (e.g. "850", "855").

    Returns:
        A dict with keys: segments, business_rules, mapping_refs.
        Returns empty structure if preset or transaction not found.
    """
    empty = {"segments": {}, "business_rules": [], "mapping_refs": []}

    data = _load_yaml(_PRESETS_PATH)
    presets = data.get("presets", {})
    preset = presets.get(preset_name)
    if not isinstance(preset, dict):
        logger.warning("Preset '%s' not found in layer2_presets.yaml", preset_name)
        return copy.deepcopy(empty)

    transactions = preset.get("transactions", {})
    tx_config = transactions.get(transaction_type)
    if not isinstance(tx_config, dict):
        logger.warning(
            "Transaction '%s' not found in preset '%s'",
            transaction_type, preset_name,
        )
        return copy.deepcopy(empty)

    # Return a deep copy so callers can mutate without affecting the cache
    return copy.deepcopy({
        "segments": tx_config.get("segments", {}),
        "business_rules": tx_config.get("business_rules", []),
        "mapping_refs": tx_config.get("mapping_refs", []),
    })


def load_lifecycle_detail(lifecycle_ref: str) -> dict:
    """
    Load a specific lifecycle YAML file and return its full content.

    Args:
        lifecycle_ref: Path relative to edi_framework/ (e.g. "lifecycle/order_to_cash.yaml").

    Returns:
        The full lifecycle dict (deep copy), or empty dict if not found.
        Includes summary keys: _name, _version, _state_count, _transaction_count.
    """
    full_path = _EDI_FRAMEWORK_DIR / lifecycle_ref
    if not full_path.is_file():
        logger.warning("Lifecycle file not found: %s", full_path)
        return {}

    data = _load_yaml(full_path)
    if not data:
        return {}

    # Deep copy to protect edi_framework data
    result = copy.deepcopy(data)

    # Add summary metadata for convenience
    lc = result.get("lifecycle", {})
    result["_name"] = lc.get("name", "")
    result["_version"] = lc.get("version", "")
    result["_state_count"] = _count_states(result)
    result["_transaction_count"] = len(_count_transactions(result))

    return result


def load_partner_registry() -> dict:
    """
    Load the partner registry and return its full content (deep copy).

    Returns the partners dict from partner_registry.yaml.
    """
    data = _load_yaml(_PARTNER_REGISTRY_PATH)
    return copy.deepcopy(data.get("partners", {}))


def load_transaction_yaml(transaction_type: str) -> dict:
    """
    Load a transaction YAML from edi_framework/transactions/.

    Searches for files matching *{transaction_type}*.yaml.

    Args:
        transaction_type: Transaction set code (e.g. "850").

    Returns:
        The full transaction dict (deep copy), or empty dict if not found.
    """
    if not _TRANSACTIONS_DIR.is_dir():
        return {}

    for yaml_path in _TRANSACTIONS_DIR.glob("*.yaml"):
        data = _load_yaml(yaml_path)
        tx = data.get("transaction", {})
        if tx.get("id") == transaction_type:
            return copy.deepcopy(data)

    logger.warning("Transaction YAML not found for type '%s'", transaction_type)
    return {}
