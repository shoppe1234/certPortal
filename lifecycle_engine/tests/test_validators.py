"""
Tests for lifecycle_engine/validators.py

All validators are pure functions — no DB, no S3, no YAML loading.
Tests cover the happy path (no exception) and all failure modes.
"""
import pytest

from lifecycle_engine.exceptions import (
    InvalidTransitionError,
    N1QualifierError,
    POContinuityError,
    QuantityChainError,
    TerminalStateViolationError,
)
from lifecycle_engine.validators import (
    validate_n1_qualifier,
    validate_not_terminal,
    validate_po_number_continuity,
    validate_quantity_chain,
    validate_transition,
)

# ---------------------------------------------------------------------------
# validate_transition
# ---------------------------------------------------------------------------

class TestValidateTransition:
    def test_valid_transition_succeeds(self):
        validate_transition("po_originated", "po_acknowledged", ["po_acknowledged", "shipped"])

    def test_invalid_transition_raises(self):
        with pytest.raises(InvalidTransitionError, match="po_acknowledged"):
            validate_transition("invoiced", "po_acknowledged", ["shipped"])

    def test_empty_transitions_always_fails(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("invoiced", "shipped", [])

    def test_same_state_not_in_transitions_raises(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("po_originated", "po_originated", ["po_acknowledged"])


# ---------------------------------------------------------------------------
# validate_quantity_chain
# ---------------------------------------------------------------------------

class TestValidateQuantityChain:
    _base_po = {
        "ordered_qty": 100.0,
        "changed_qty": None,
        "accepted_qty": None,
        "shipped_qty": None,
        "invoiced_qty": None,
    }

    def test_invoiced_under_ordered_passes(self):
        validate_quantity_chain(self._base_po, "810", 80.0)

    def test_invoiced_equal_ordered_passes(self):
        validate_quantity_chain(self._base_po, "810", 100.0)

    def test_invoiced_over_ordered_raises(self):
        with pytest.raises(QuantityChainError, match="850"):
            validate_quantity_chain(self._base_po, "810", 101.0)

    def test_shipped_over_accepted_raises(self):
        po = {**self._base_po, "accepted_qty": 50.0}
        with pytest.raises(QuantityChainError, match="855"):
            validate_quantity_chain(po, "856", 60.0)

    def test_none_incoming_qty_is_skipped(self):
        validate_quantity_chain(self._base_po, "810", None)

    def test_865_not_in_chain_skips(self):
        # 865 is not part of the quantity chain
        validate_quantity_chain(self._base_po, "865", 999.0)

    def test_changed_qty_greater_than_ordered_raises(self):
        with pytest.raises(QuantityChainError):
            validate_quantity_chain(self._base_po, "860", 110.0)

    def test_accepted_within_changed_passes(self):
        po = {**self._base_po, "changed_qty": 80.0}
        validate_quantity_chain(po, "855", 75.0)

    def test_all_none_upstream_passes(self):
        empty_po = {k: None for k in self._base_po}
        validate_quantity_chain(empty_po, "810", 50.0)


# ---------------------------------------------------------------------------
# validate_n1_qualifier
# ---------------------------------------------------------------------------

N1_MAP = {"850": "93", "860": "93", "855": "94", "856": "94", "810": "92"}


class TestValidateN1Qualifier:
    def test_correct_qualifier_850_passes(self):
        validate_n1_qualifier("850", "93", N1_MAP)

    def test_correct_qualifier_810_passes(self):
        validate_n1_qualifier("810", "92", N1_MAP)

    def test_wrong_qualifier_850_raises(self):
        with pytest.raises(N1QualifierError, match="expected N103='93'"):
            validate_n1_qualifier("850", "94", N1_MAP)

    def test_wrong_qualifier_810_raises(self):
        with pytest.raises(N1QualifierError, match="expected N103='92'"):
            validate_n1_qualifier("810", "93", N1_MAP)

    def test_none_qualifier_is_skipped(self):
        validate_n1_qualifier("850", None, N1_MAP)

    def test_unknown_transaction_skips(self):
        validate_n1_qualifier("865", "99", N1_MAP)  # 865 not in n1_map


# ---------------------------------------------------------------------------
# validate_not_terminal
# ---------------------------------------------------------------------------

class TestValidateNotTerminal:
    def test_non_terminal_passes(self):
        validate_not_terminal({"is_terminal": False, "current_state": "shipped", "po_number": "P001"})

    def test_terminal_raises(self):
        with pytest.raises(TerminalStateViolationError, match="invoiced"):
            validate_not_terminal({"is_terminal": True, "current_state": "invoiced", "po_number": "P001"})

    def test_missing_is_terminal_defaults_to_false(self):
        validate_not_terminal({"current_state": "po_originated", "po_number": "P001"})


# ---------------------------------------------------------------------------
# validate_po_number_continuity
# ---------------------------------------------------------------------------

class TestValidatePONumberContinuity:
    _primary_key_config = {"name": "purchase_order_number"}

    def test_matching_po_numbers_pass(self):
        validate_po_number_continuity(
            "P12345", "855",
            {"header": {"po_number": "P12345"}},
            self._primary_key_config,
        )

    def test_mismatching_po_numbers_raise(self):
        with pytest.raises(POContinuityError, match="P12345"):
            validate_po_number_continuity(
                "P12345", "856",
                {"header": {"po_number": "P99999"}},
                self._primary_key_config,
            )

    def test_none_payload_po_skips(self):
        # If payload has no po_number, skip (MissingPONumberError handled upstream)
        validate_po_number_continuity(
            "P12345", "810",
            {"header": {}},
            self._primary_key_config,
        )

    def test_string_vs_int_po_numbers_match(self):
        validate_po_number_continuity(
            "12345", "810",
            {"header": {"po_number": 12345}},
            self._primary_key_config,
        )
