"""
Tests for lifecycle_engine/engine.py

Tests use mock StateStore and LifecycleLoader to avoid DB and filesystem
dependencies. The engine's orchestration logic (state determination, dual-path
routing, violation detection, strict_mode behaviour) is tested end-to-end.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lifecycle_engine.engine import LifecycleEngine, LifecycleResult, TRANSACTION_STATE_MAP
from lifecycle_engine.exceptions import (
    LifecycleViolationError,
    InvalidTransitionError,
    QuantityChainError,
)
from lifecycle_engine.loader import LifecycleLoader

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

REPO_ROOT_STR = str(__import__("pathlib").Path(__file__).parent.parent.parent)


def _make_loader() -> LifecycleLoader:
    """Load real order_to_cash.yaml for integration-style tests."""
    loader = LifecycleLoader("../edi_framework")
    loader.load()
    return loader


def _make_engine(strict_mode: bool = False, loader=None) -> LifecycleEngine:
    loader = loader or _make_loader()
    return LifecycleEngine(loader=loader, dsn="mock_dsn", strict_mode=strict_mode)


def _payload(po_number: str = "P12345", *, n1_qualifier: str = None, qty: float = None) -> dict:
    h = {"po_number": po_number}
    if n1_qualifier is not None:
        h["n1_qualifier"] = n1_qualifier
    if qty is not None:
        h["quantity"] = qty
    return {"header": h}


def _mock_store(existing_po: dict = None):
    store = MagicMock()
    store.get_po.return_value = existing_po
    store.record_violation.return_value = None
    store.transition_and_record.return_value = None
    return store


# ---------------------------------------------------------------------------
# TRANSACTION_STATE_MAP sanity
# ---------------------------------------------------------------------------

class TestTransactionStateMap:
    def test_all_six_transaction_types_covered(self):
        expected_keys = {
            ("850", "inbound"), ("860", "inbound"), ("855", "outbound"),
            ("865", "outbound"), ("856", "outbound"), ("810", "outbound"),
        }
        assert expected_keys == set(TRANSACTION_STATE_MAP.keys())

    def test_850_maps_to_po_originated(self):
        assert TRANSACTION_STATE_MAP[("850", "inbound")] == "po_originated"

    def test_810_maps_to_invoiced(self):
        assert TRANSACTION_STATE_MAP[("810", "outbound")] == "invoiced"

    def test_855_and_865_are_none_dynamic(self):
        assert TRANSACTION_STATE_MAP[("855", "outbound")] is None
        assert TRANSACTION_STATE_MAP[("865", "outbound")] is None


# ---------------------------------------------------------------------------
# process_event — happy paths (mocked StateStore)
# ---------------------------------------------------------------------------

class TestProcessEventHappyPath:
    def test_850_creates_po_originated(self):
        engine = _make_engine()
        store = _mock_store(existing_po=None)
        with patch.object(engine, "_dsn", "mock"), \
             patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="850", direction="inbound",
                payload=_payload("P001"), source_file="test.edi",
                correlation_id="corr-001", partner_id="lowes",
            )
        assert result.success is True
        assert result.new_state == "po_originated"
        assert result.prior_state is None
        assert result.is_terminal is False
        store.transition_and_record.assert_called_once()

    def test_855_after_850_is_po_acknowledged(self):
        existing = {"po_number": "P001", "current_state": "po_originated",
                    "is_terminal": False, "ordered_qty": 100}
        engine = _make_engine()
        store = _mock_store(existing_po=existing)
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="855", direction="outbound",
                payload=_payload("P001"), source_file="855.edi",
                correlation_id="corr-002", partner_id="lowes",
            )
        assert result.success is True
        assert result.new_state == "po_acknowledged"

    def test_855_with_no_prior_record_is_reverse_po_created(self):
        engine = _make_engine()
        store = _mock_store(existing_po=None)
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="855", direction="outbound",
                payload=_payload("P002"), source_file="reverse.edi",
                correlation_id="corr-003", partner_id="lowes",
            )
        assert result.success is True
        assert result.new_state == "reverse_po_created"

    def test_865_AT_is_po_change_accepted(self):
        existing = {"po_number": "P003", "current_state": "po_changed",
                    "is_terminal": False, "ordered_qty": 50}
        engine = _make_engine()
        store = _mock_store(existing_po=existing)
        payload = {"header": {"po_number": "P003", "ack_type": "AT"}}
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="865", direction="outbound",
                payload=payload, source_file="865.edi",
                correlation_id="corr-004", partner_id="lowes",
            )
        assert result.success is True
        assert result.new_state == "po_change_accepted"

    def test_865_RJ_is_po_change_rejected(self):
        existing = {"po_number": "P004", "current_state": "po_changed",
                    "is_terminal": False, "ordered_qty": 50}
        engine = _make_engine()
        store = _mock_store(existing_po=existing)
        payload = {"header": {"po_number": "P004", "ack_type": "RJ"}}
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="865", direction="outbound",
                payload=payload, source_file="865.edi",
                correlation_id="corr-005", partner_id="lowes",
            )
        assert result.success is True
        assert result.new_state == "po_change_rejected"

    def test_810_is_terminal(self):
        existing = {"po_number": "P005", "current_state": "shipped",
                    "is_terminal": False, "ordered_qty": 100, "shipped_qty": 100}
        engine = _make_engine()
        store = _mock_store(existing_po=existing)
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="810", direction="outbound",
                payload=_payload("P005"), source_file="810.edi",
                correlation_id="corr-006", partner_id="lowes",
            )
        assert result.success is True
        assert result.new_state == "invoiced"
        assert result.is_terminal is True


# ---------------------------------------------------------------------------
# process_event — violation paths
# ---------------------------------------------------------------------------

class TestProcessEventViolations:
    def test_missing_po_number_returns_failure(self):
        engine = _make_engine(strict_mode=False)
        store = _mock_store()
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="850", direction="inbound",
                payload={"header": {}},   # no po_number
                source_file="test.edi", correlation_id="corr", partner_id="lowes",
            )
        assert result.success is False
        assert "missing_po" in result.violations[0].lower() or len(result.violations) > 0
        store.record_violation.assert_called_once()

    def test_missing_po_strict_mode_raises(self):
        engine = _make_engine(strict_mode=True)
        store = _mock_store()
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            with pytest.raises(LifecycleViolationError) as exc_info:
                engine.process_event(
                    transaction_set="850", direction="inbound",
                    payload={"header": {}},
                    source_file="test.edi", correlation_id="corr", partner_id="lowes",
                )
        assert exc_info.value.violation_type == "missing_po"

    def test_unexpected_first_doc_returns_failure(self):
        """810 as the first document should fail with unexpected_first_doc."""
        engine = _make_engine(strict_mode=False)
        store = _mock_store(existing_po=None)
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="810", direction="outbound",
                payload=_payload("P999"), source_file="orphan.edi",
                correlation_id="corr-orphan", partner_id="lowes",
            )
        assert result.success is False
        store.record_violation.assert_called_once()

    def test_terminal_state_violation(self):
        """Processing any document for an already-invoiced PO should fail."""
        existing = {"po_number": "P010", "current_state": "invoiced",
                    "is_terminal": True, "ordered_qty": 100}
        engine = _make_engine(strict_mode=False)
        store = _mock_store(existing_po=existing)
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="810", direction="outbound",
                payload=_payload("P010"), source_file="dup.edi",
                correlation_id="corr-dup", partner_id="lowes",
            )
        assert result.success is False
        assert "duplicate_terminal" in str(store.record_violation.call_args)

    def test_invalid_transition_returns_failure(self):
        """Trying to go from invoiced → po_acknowledged should fail."""
        existing = {"po_number": "P011", "current_state": "invoiced",
                    "is_terminal": False, "ordered_qty": 100}
        engine = _make_engine(strict_mode=False)
        store = _mock_store(existing_po=existing)
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="855", direction="outbound",
                payload=_payload("P011"), source_file="bad.edi",
                correlation_id="corr-bad", partner_id="lowes",
            )
        assert result.success is False

    def test_quantity_chain_violation(self):
        """Invoicing more than ordered should fail."""
        existing = {
            "po_number": "P012", "current_state": "shipped",
            "is_terminal": False,
            "ordered_qty": 50, "changed_qty": None,
            "accepted_qty": 45, "shipped_qty": 45, "invoiced_qty": None,
        }
        engine = _make_engine(strict_mode=False)
        store = _mock_store(existing_po=existing)
        payload = {"header": {"po_number": "P012", "quantity": 60.0}}
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="810", direction="outbound",
                payload=payload, source_file="over.edi",
                correlation_id="corr-over", partner_id="lowes",
            )
        assert result.success is False
        assert "quantity_chain" in str(store.record_violation.call_args)


# ---------------------------------------------------------------------------
# Loader integration
# ---------------------------------------------------------------------------

class TestLoaderIntegration:
    def test_loader_has_correct_states(self):
        loader = _make_loader()
        states = loader.all_state_names()
        expected = {
            "po_originated", "po_changed", "po_change_accepted",
            "po_change_rejected", "reverse_po_created", "po_acknowledged",
            "reverse_po_modified", "reverse_po_cancelled", "shipped", "invoiced",
        }
        assert expected == set(states)

    def test_invoiced_is_terminal(self):
        loader = _make_loader()
        assert loader.is_terminal_state("invoiced") is True

    def test_po_originated_not_terminal(self):
        loader = _make_loader()
        assert loader.is_terminal_state("po_originated") is False

    def test_reverse_po_cancelled_is_terminal(self):
        loader = _make_loader()
        assert loader.is_terminal_state("reverse_po_cancelled") is True
