"""
Lifecycle Builder — Build lifecycle YAML in three modes: use, copy, create.

Modes:
  1. use    — Return existing lifecycle YAML as-is (deep copy)
  2. copy   — Deep clone, rename, allow modifications to states/transitions
  3. create — Build new lifecycle from scratch with user-provided states/transitions

Validates output against edi_framework/meta/lifecycle_schema.yaml using pykwalify.

Architecture Decision: AD-1 from wizard refactoring prompt.
Constraint: lifecycle_engine/ and order_to_cash.yaml are UNTOUCHED.
Constraint: NC-01 — edi_framework/ is READ-ONLY at runtime.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Optional

import yaml
from pykwalify.core import Core
from pykwalify.errors import SchemaError

from certportal.generators.template_loader import load_lifecycle_detail

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_EDI_FRAMEWORK_DIR = Path(__file__).resolve().parents[2] / "edi_framework"
_META_DIR = _EDI_FRAMEWORK_DIR / "meta"
_LIFECYCLE_SCHEMA_PATH = _META_DIR / "lifecycle_schema.yaml"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_lifecycle(yaml_content: str) -> list[str]:
    """
    Validate lifecycle YAML content against the lifecycle meta-schema.

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
        errors.append("Lifecycle YAML must be a mapping at the top level")
        return errors

    # Load schema
    if not _LIFECYCLE_SCHEMA_PATH.is_file():
        errors.append(f"Lifecycle meta-schema not found: {_LIFECYCLE_SCHEMA_PATH}")
        return errors

    try:
        with open(_LIFECYCLE_SCHEMA_PATH, "r", encoding="utf-8") as fh:
            schema_data = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError) as exc:
        errors.append(f"Failed to load lifecycle meta-schema: {exc}")
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
# Builder
# ---------------------------------------------------------------------------

def build_lifecycle(
    mode: str,
    lifecycle_ref: Optional[str] = None,
    x12_version: str = "004010",
    name: str = "Custom Lifecycle",
    states_config: Optional[dict] = None,
) -> str:
    """
    Build a lifecycle YAML string.

    Args:
        mode: One of "use", "copy", "create".
        lifecycle_ref: Path relative to edi_framework/ for use/copy modes
                       (e.g. "lifecycle/order_to_cash.yaml").
        x12_version: X12 version string (used in metadata).
        name: Name for the lifecycle (used in copy/create modes).
        states_config: For copy mode: dict of modifications to apply.
                       For create mode: dict defining the full state machine.
                       Format:
                         {
                           "states": {
                             "state_name": {
                               "trigger": {"document": "850", "direction": "inbound"},
                               "description": "...",
                               "valid_transitions": [
                                 {"to": "next_state", "via": "855"}
                               ]
                             },
                             ...
                           },
                           "primary_key": { ... }  # optional for create
                         }

    Returns:
        Valid lifecycle YAML string.

    Raises:
        ValueError: If mode is invalid, lifecycle_ref is missing for use/copy,
                    or states_config is missing for create mode.
    """
    if mode not in ("use", "copy", "create"):
        raise ValueError(f"Invalid mode: {mode!r}. Must be 'use', 'copy', or 'create'.")

    if mode == "use":
        return _build_use(lifecycle_ref)
    elif mode == "copy":
        return _build_copy(lifecycle_ref, name, x12_version, states_config)
    else:
        return _build_create(name, x12_version, states_config)


def _build_use(lifecycle_ref: Optional[str]) -> str:
    """Mode: use — Return existing lifecycle YAML as-is."""
    if not lifecycle_ref:
        raise ValueError("lifecycle_ref is required for 'use' mode")

    data = load_lifecycle_detail(lifecycle_ref)
    if not data:
        raise ValueError(f"Lifecycle not found: {lifecycle_ref}")

    # Remove summary metadata added by template_loader
    clean = copy.deepcopy(data)
    for key in list(clean.keys()):
        if key.startswith("_"):
            del clean[key]

    return yaml.dump(clean, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _build_copy(
    lifecycle_ref: Optional[str],
    name: str,
    x12_version: str,
    states_config: Optional[dict],
) -> str:
    """Mode: copy — Deep clone, rename, apply modifications."""
    if not lifecycle_ref:
        raise ValueError("lifecycle_ref is required for 'copy' mode")

    data = load_lifecycle_detail(lifecycle_ref)
    if not data:
        raise ValueError(f"Lifecycle not found: {lifecycle_ref}")

    # Deep copy and clean metadata
    clean = copy.deepcopy(data)
    for key in list(clean.keys()):
        if key.startswith("_"):
            del clean[key]

    lc = clean.get("lifecycle", {})

    # Rename
    lc["name"] = name
    lc["version"] = "1.0"

    # Apply state modifications if provided
    if states_config and isinstance(states_config, dict):
        existing_states = lc.get("states", {})

        # Remove states listed for deletion
        remove_states = states_config.get("remove_states", [])
        for state_name in remove_states:
            if state_name in existing_states:
                del existing_states[state_name]
                # Also remove transitions pointing to this state
                for remaining_state in existing_states.values():
                    if isinstance(remaining_state, dict):
                        transitions = remaining_state.get("valid_transitions", [])
                        if isinstance(transitions, list):
                            remaining_state["valid_transitions"] = [
                                t for t in transitions
                                if not (isinstance(t, dict) and t.get("to") == state_name)
                            ]

        # Add or update states
        add_states = states_config.get("states", {})
        if isinstance(add_states, dict):
            for state_name, state_def in add_states.items():
                if isinstance(state_def, dict):
                    if state_name in existing_states:
                        # Merge into existing state
                        existing_states[state_name].update(state_def)
                    else:
                        # Add new state
                        existing_states[state_name] = state_def

        # Update primary_key if provided
        if "primary_key" in states_config:
            lc["primary_key"] = states_config["primary_key"]

    clean["lifecycle"] = lc
    return yaml.dump(clean, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _build_create(
    name: str,
    x12_version: str,
    states_config: Optional[dict],
) -> str:
    """Mode: create — Build new lifecycle from user-provided states."""
    if not states_config or not isinstance(states_config, dict):
        raise ValueError("states_config is required for 'create' mode")

    states = states_config.get("states", {})
    if not states:
        raise ValueError("states_config must contain at least one state under 'states' key")

    # Build primary key config
    primary_key = states_config.get("primary_key", {
        "name": "purchase_order_number",
        "description": "The PO number linking all documents in this lifecycle.",
        "max_digits": 9,
        "format": "zero-suppressed",
    })

    # Build lifecycle structure
    lifecycle_data = {
        "lifecycle": {
            "name": name,
            "version": "1.0",
            "primary_key": primary_key,
            "states": {},
        }
    }

    # Add each state
    for state_name, state_def in states.items():
        if not isinstance(state_def, dict):
            continue

        state_entry = {}

        # Trigger is required
        trigger = state_def.get("trigger", {})
        if not trigger:
            raise ValueError(
                f"State '{state_name}' must have a 'trigger' with 'document' and 'direction'"
            )
        state_entry["trigger"] = trigger

        # Description is optional but recommended
        if "description" in state_def:
            state_entry["description"] = state_def["description"]

        # Captures are optional
        if "captures" in state_def:
            state_entry["captures"] = state_def["captures"]

        # Valid transitions are optional (terminal states have none)
        if "valid_transitions" in state_def:
            state_entry["valid_transitions"] = state_def["valid_transitions"]

        # Terminal flag
        if state_def.get("is_terminal"):
            state_entry["is_terminal"] = True

        # Any other user-provided keys
        for key, value in state_def.items():
            if key not in ("trigger", "description", "captures", "valid_transitions", "is_terminal"):
                state_entry[key] = value

        lifecycle_data["lifecycle"]["states"][state_name] = state_entry

    return yaml.dump(
        lifecycle_data, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
