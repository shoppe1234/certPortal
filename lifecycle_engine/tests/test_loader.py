"""
Tests for lifecycle_engine/loader.py

Covers all loader error paths and every accessor method, including the
string-entry backwards-compatibility branches and the terminal-state
detection by explicit flag vs. empty transitions.

No live DB or S3 required — uses the real edi_framework/ YAML files plus
tmp_path fixtures for error-path scenarios.
"""
from __future__ import annotations

import textwrap

import pytest

from lifecycle_engine.exceptions import LifecycleConfigError
from lifecycle_engine.loader import LifecycleLoader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loader() -> LifecycleLoader:
    """Return a loaded LifecycleLoader backed by the real order_to_cash.yaml."""
    loader = LifecycleLoader("../edi_framework")
    loader.load()
    return loader


# ---------------------------------------------------------------------------
# load() error paths  (lines 64, 71-72, 77)
# ---------------------------------------------------------------------------

class TestLoaderLoadErrors:
    def test_missing_lifecycle_file_raises(self, tmp_path):
        """load() raises LifecycleConfigError when order_to_cash.yaml does not exist."""
        # Point loader at a directory that has no lifecycle/ subdirectory
        loader = LifecycleLoader(str(tmp_path))
        with pytest.raises(LifecycleConfigError, match="not found"):
            loader.load()

    def test_malformed_yaml_raises(self, tmp_path):
        """load() raises LifecycleConfigError when order_to_cash.yaml is not valid YAML."""
        lifecycle_dir = tmp_path / "lifecycle"
        lifecycle_dir.mkdir()
        bad_yaml = lifecycle_dir / "order_to_cash.yaml"
        bad_yaml.write_text("key: [unclosed bracket\n  bad: indent\n", encoding="utf-8")
        loader = LifecycleLoader(str(tmp_path))
        with pytest.raises(LifecycleConfigError, match="Failed to parse"):
            loader.load()

    def test_missing_lifecycle_key_raises(self, tmp_path):
        """load() raises LifecycleConfigError when YAML has no top-level 'lifecycle' key."""
        lifecycle_dir = tmp_path / "lifecycle"
        lifecycle_dir.mkdir()
        ok_yaml = lifecycle_dir / "order_to_cash.yaml"
        ok_yaml.write_text("unrelated_key: some_value\n", encoding="utf-8")
        loader = LifecycleLoader(str(tmp_path))
        with pytest.raises(LifecycleConfigError, match="top-level 'lifecycle' key"):
            loader.load()


# ---------------------------------------------------------------------------
# _require_loaded guard  (line 91)
# ---------------------------------------------------------------------------

class TestLoaderBeforeLoad:
    def test_require_loaded_guard_on_get_state(self):
        """Any accessor called before load() raises LifecycleConfigError."""
        loader = LifecycleLoader("../edi_framework")
        # Do NOT call loader.load()
        with pytest.raises(LifecycleConfigError, match="load\\(\\)"):
            loader.get_state("po_originated")


# ---------------------------------------------------------------------------
# get_state  (lines 102-107)
# ---------------------------------------------------------------------------

class TestGetState:
    def test_get_state_returns_dict_for_known_state(self):
        """get_state() returns the state definition dict for a valid state name."""
        loader = _make_loader()
        state = loader.get_state("po_originated")
        assert isinstance(state, dict)

    def test_get_state_raises_for_unknown_state(self):
        """get_state() raises LifecycleConfigError for a state name not in the YAML."""
        loader = _make_loader()
        with pytest.raises(LifecycleConfigError, match="not defined"):
            loader.get_state("__no_such_state__")


# ---------------------------------------------------------------------------
# get_valid_transitions — string entry fallback  (lines 127-128)
# ---------------------------------------------------------------------------

class TestGetValidTransitionsStringFallback:
    def test_string_transition_entries_are_included(self):
        """get_valid_transitions() handles plain-string entries (backwards compat)."""
        loader = _make_loader()
        # Inject a state whose transitions are bare strings, not {to: ...} dicts
        loader._states["_test_string_state"] = {
            "valid_transitions": ["next_state_a", "next_state_b"]
        }
        transitions = loader.get_valid_transitions("_test_string_state")
        assert "next_state_a" in transitions
        assert "next_state_b" in transitions

    def test_mixed_dict_and_string_transitions(self):
        """get_valid_transitions() handles a mix of dict and string entries."""
        loader = _make_loader()
        loader._states["_test_mixed_state"] = {
            "valid_transitions": [
                {"to": "dict_target", "via": "some_event"},
                "string_target",
            ]
        }
        transitions = loader.get_valid_transitions("_test_mixed_state")
        assert "dict_target" in transitions
        assert "string_target" in transitions


# ---------------------------------------------------------------------------
# get_transition_details  (lines 135-137)
# ---------------------------------------------------------------------------

class TestGetTransitionDetails:
    def test_returns_list_for_known_state(self):
        """get_transition_details() returns the raw transition list for a state."""
        loader = _make_loader()
        details = loader.get_transition_details("po_originated")
        assert isinstance(details, list)

    def test_returns_empty_for_terminal_state(self):
        """get_transition_details() returns [] for a terminal state with no transitions."""
        loader = _make_loader()
        # 'invoiced' is a known terminal state with no outgoing transitions
        details = loader.get_transition_details("invoiced")
        assert details == []

    def test_returns_empty_for_unknown_state(self):
        """get_transition_details() returns [] (no error) for an unknown state name."""
        loader = _make_loader()
        details = loader.get_transition_details("__no_such_state__")
        assert details == []


# ---------------------------------------------------------------------------
# get_validations  (lines 147-149)
# ---------------------------------------------------------------------------

class TestGetValidations:
    def test_returns_list_for_known_state(self):
        """get_validations() returns the validation spec list for a state."""
        loader = _make_loader()
        validations = loader.get_validations("po_originated")
        assert isinstance(validations, list)

    def test_returns_empty_for_unknown_state(self):
        """get_validations() returns [] (no error) for an unknown state name."""
        loader = _make_loader()
        validations = loader.get_validations("__no_such_state__")
        assert validations == []


# ---------------------------------------------------------------------------
# get_quantity_chain_rule  (lines 158-159)
# ---------------------------------------------------------------------------

class TestGetQuantityChainRule:
    def test_returns_dict(self):
        """get_quantity_chain_rule() returns the quantity_chain config block."""
        loader = _make_loader()
        rule = loader.get_quantity_chain_rule()
        assert isinstance(rule, dict)

    def test_missing_block_returns_empty_dict(self):
        """Returns {} when quantity_chain is absent from the YAML."""
        loader = _make_loader()
        # Temporarily remove the block to simulate absence
        original = loader._data.pop("quantity_chain", {})
        try:
            result = loader.get_quantity_chain_rule()
            assert result == {}
        finally:
            if original:
                loader._data["quantity_chain"] = original


# ---------------------------------------------------------------------------
# get_n1_qualifier_map — string entry fallback  (lines 174-175)
# ---------------------------------------------------------------------------

class TestGetN1QualifierMapStringFallback:
    def test_string_qualifier_entry(self):
        """get_n1_qualifier_map() handles plain-string qualifier entries."""
        loader = _make_loader()
        # Inject a string-style N1 entry (backwards-compat format)
        n1_block = loader._data.setdefault("n1_qualifier_map", {})
        qual_map = n1_block.setdefault("map", {})
        qual_map["_test_tx"] = "99"
        result = loader.get_n1_qualifier_map()
        assert result["_test_tx"] == "99"


# ---------------------------------------------------------------------------
# is_terminal_state — explicit flag  (line 189)
# ---------------------------------------------------------------------------

class TestIsTerminalStateExplicitFlag:
    def test_explicit_is_terminal_true(self):
        """is_terminal_state() returns True when state has 'is_terminal: true'."""
        loader = _make_loader()
        # Inject a state that is terminal via explicit flag (not empty transitions)
        loader._states["_explicit_terminal_test"] = {
            "is_terminal": True,
            "description": "test terminal state",
            "valid_transitions": [],
        }
        assert loader.is_terminal_state("_explicit_terminal_test") is True

    def test_terminal_by_empty_transitions(self):
        """is_terminal_state() returns True when state has no valid_transitions."""
        loader = _make_loader()
        # Inject a state with no transitions and no explicit is_terminal
        loader._states["_empty_transition_state"] = {
            "description": "orphan state with no outgoing transitions",
            "valid_transitions": [],
        }
        assert loader.is_terminal_state("_empty_transition_state") is True

    def test_non_terminal_has_transitions(self):
        """is_terminal_state() returns False when state has outgoing transitions."""
        loader = _make_loader()
        # po_originated is a well-known non-terminal state
        assert loader.is_terminal_state("po_originated") is False
