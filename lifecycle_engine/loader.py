"""
lifecycle_engine/loader.py

Loads and caches the edi_framework/lifecycle/order_to_cash.yaml state machine
definition at startup. Provides typed accessors for engine.py to query.

The loader is READ-ONLY against edi_framework/ (NC-01: never write to it).
File is re-read only on process restart; no hot-reload.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from lifecycle_engine.exceptions import LifecycleConfigError

logger = logging.getLogger(__name__)

_LIFECYCLE_FILE = "lifecycle/order_to_cash.yaml"


class LifecycleLoader:
    """
    Loads and provides typed access to the order_to_cash.yaml state machine.

    Usage:
        loader = LifecycleLoader(framework_base_path='../edi_framework')
        loader.load()
        transitions = loader.get_valid_transitions('po_originated')
        # → ['po_acknowledged', 'po_changed', 'shipped', 'invoiced']
    """

    def __init__(self, framework_base_path: str) -> None:
        """
        Args:
            framework_base_path: Path to the edi_framework/ root directory.
                                 Relative paths are resolved against this
                                 module's parent directory (lifecycle_engine/).
        """
        base = Path(framework_base_path)
        if not base.is_absolute():
            # Resolve relative to the lifecycle_engine/ package directory
            base = (Path(__file__).parent / framework_base_path).resolve()
        self._base_path = base
        self._data: Optional[Dict] = None
        self._states: Dict[str, Dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """
        Read and parse order_to_cash.yaml.

        Raises:
            LifecycleConfigError: if the file is missing or invalid YAML.
        """
        lifecycle_file = self._base_path / _LIFECYCLE_FILE
        if not lifecycle_file.exists():
            raise LifecycleConfigError(
                f"Lifecycle definition not found: {lifecycle_file}"
            )

        try:
            with open(lifecycle_file, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise LifecycleConfigError(
                f"Failed to parse lifecycle YAML: {exc}"
            ) from exc

        if not isinstance(raw, dict) or "lifecycle" not in raw:
            raise LifecycleConfigError(
                f"lifecycle.yaml missing top-level 'lifecycle' key: {lifecycle_file}"
            )

        self._data = raw["lifecycle"]
        self._states = self._data.get("states", {})
        logger.info(
            "LifecycleLoader: loaded %d states from %s",
            len(self._states),
            lifecycle_file,
        )

    def _require_loaded(self) -> None:
        if self._data is None:
            raise LifecycleConfigError(
                "LifecycleLoader.load() must be called before accessing state data."
            )

    def get_state(self, state_name: str) -> Dict:
        """
        Return the full state definition dict for a given state name.

        Raises:
            LifecycleConfigError: if state_name is not defined.
        """
        self._require_loaded()
        if state_name not in self._states:
            raise LifecycleConfigError(
                f"State '{state_name}' not defined in lifecycle YAML."
            )
        return self._states[state_name]

    def get_valid_transitions(self, state_name: str) -> List[str]:
        """
        Return list of valid *destination* state names from state_name.

        Each entry in the YAML's valid_transitions list is a map with
        {to, via, condition}. This method extracts only the 'to' values.

        Returns empty list for terminal states.
        """
        self._require_loaded()
        state = self._states.get(state_name, {})
        transitions = state.get("valid_transitions", [])
        result = []
        for t in transitions:
            if isinstance(t, dict):
                dest = t.get("to")
                if dest:
                    result.append(dest)
            elif isinstance(t, str):
                result.append(t)
        return result

    def get_transition_details(self, state_name: str) -> List[Dict]:
        """
        Return the full transition list (with to/via/condition) for a state.
        """
        self._require_loaded()
        state = self._states.get(state_name, {})
        return state.get("valid_transitions", [])

    def get_captures(self, state_name: str) -> List[Dict]:
        """Return the list of field capture specs for a state."""
        self._require_loaded()
        state = self._states.get(state_name, {})
        return state.get("captures", [])

    def get_validations(self, state_name: str) -> List[Dict]:
        """Return the list of validation specs for a state."""
        self._require_loaded()
        state = self._states.get(state_name, {})
        return state.get("validations", [])

    def get_primary_key_config(self) -> Dict:
        """Return the primary_key configuration block."""
        self._require_loaded()
        return self._data.get("primary_key", {})

    def get_quantity_chain_rule(self) -> Dict:
        """Return the quantity_chain configuration block."""
        self._require_loaded()
        return self._data.get("quantity_chain", {})

    def get_n1_qualifier_map(self) -> Dict:
        """
        Return a flat mapping of transaction_set → expected N103 qualifier.

        E.g.:  {'850': '93', '860': '93', '855': '94', '856': '94', '810': '92'}
        """
        self._require_loaded()
        n1_block = self._data.get("n1_qualifier_map", {})
        qual_map = n1_block.get("map", {})
        result = {}
        for tx_set, entry in qual_map.items():
            if isinstance(entry, dict):
                result[str(tx_set)] = entry.get("qualifier", "")
            elif isinstance(entry, str):
                result[str(tx_set)] = entry
        return result

    def is_terminal_state(self, state_name: str) -> bool:
        """
        Return True if state_name is a terminal state.

        A state is terminal if:
        - it has 'is_terminal: true' set explicitly, OR
        - it has no valid_transitions (empty or absent)
        """
        self._require_loaded()
        state = self._states.get(state_name, {})
        if state.get("is_terminal", False):
            return True
        transitions = state.get("valid_transitions", [])
        return len(transitions) == 0

    def all_state_names(self) -> List[str]:
        """Return all defined state names."""
        self._require_loaded()
        return list(self._states.keys())
