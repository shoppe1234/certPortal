"""
Tests for lifecycle_engine/engine.py

Tests use mock StateStore and LifecycleLoader to avoid DB and filesystem
dependencies. The engine's orchestration logic (state determination, dual-path
routing, violation detection, strict_mode behaviour) is tested end-to-end.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
import yaml

from lifecycle_engine.engine import LifecycleEngine, LifecycleResult, TRANSACTION_STATE_MAP
from lifecycle_engine.exceptions import (
    LifecycleConfigError,
    LifecycleError,
    LifecycleViolationError,
    InvalidTransitionError,
    POContinuityError,
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


# ---------------------------------------------------------------------------
# from_config() factory  (lines 116-143)
# ---------------------------------------------------------------------------

class TestFromConfig:
    def _write_config(self, tmp_path, extra_profiles=None) -> str:
        cfg = {
            "lifecycle_engine": {
                "framework_base_path": "../edi_framework",
                "profiles": {
                    "development": {"strict_mode": False},
                    "production": {"strict_mode": True},
                },
            }
        }
        if extra_profiles:
            cfg["lifecycle_engine"]["profiles"].update(extra_profiles)
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(cfg), encoding="utf-8")
        return str(config_file)

    def test_from_config_happy_path(self, tmp_path):
        """from_config() returns a LifecycleEngine with the right strict_mode."""
        config_path = self._write_config(tmp_path)
        mock_loader = MagicMock(spec=LifecycleLoader)
        env = {"CERTPORTAL_DB_URL": "postgresql://test/db"}
        with patch.dict(os.environ, env):
            with patch("lifecycle_engine.engine.LifecycleLoader", return_value=mock_loader):
                engine = LifecycleEngine.from_config(
                    config_path=config_path, profile="development"
                )
        assert isinstance(engine, LifecycleEngine)
        assert engine._strict_mode is False
        assert engine._dsn == "postgresql://test/db"
        mock_loader.load.assert_called_once()

    def test_from_config_production_profile_sets_strict_mode(self, tmp_path):
        """from_config() with profile='production' enables strict_mode."""
        config_path = self._write_config(tmp_path)
        mock_loader = MagicMock(spec=LifecycleLoader)
        with patch.dict(os.environ, {"CERTPORTAL_DB_URL": "postgresql://test/db"}):
            with patch("lifecycle_engine.engine.LifecycleLoader", return_value=mock_loader):
                engine = LifecycleEngine.from_config(
                    config_path=config_path, profile="production"
                )
        assert engine._strict_mode is True

    def test_from_config_missing_dsn_raises(self, tmp_path):
        """from_config() raises LifecycleConfigError when CERTPORTAL_DB_URL is unset."""
        config_path = self._write_config(tmp_path)
        env = {k: v for k, v in os.environ.items() if k != "CERTPORTAL_DB_URL"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(LifecycleConfigError, match="CERTPORTAL_DB_URL"):
                LifecycleEngine.from_config(config_path=config_path)

    def test_from_config_lifecycle_profile_env_override(self, tmp_path):
        """LIFECYCLE_PROFILE env var overrides the profile argument."""
        config_path = self._write_config(tmp_path)
        mock_loader = MagicMock(spec=LifecycleLoader)
        env = {
            "CERTPORTAL_DB_URL": "postgresql://test/db",
            "LIFECYCLE_PROFILE": "production",   # override development → production
        }
        with patch.dict(os.environ, env):
            with patch("lifecycle_engine.engine.LifecycleLoader", return_value=mock_loader):
                engine = LifecycleEngine.from_config(
                    config_path=config_path, profile="development"
                )
        # LIFECYCLE_PROFILE=production overrides profile="development"
        assert engine._strict_mode is True


# ---------------------------------------------------------------------------
# Unknown transaction/direction + 865 unknown ack_type  (lines 212-218, 248-252)
# ---------------------------------------------------------------------------

class TestUnknownTransactions:
    def test_unknown_transaction_direction_skips_lifecycle(self):
        """Unknown (tx_set, direction) combo returns success=True without DB write."""
        engine = _make_engine()
        store = _mock_store(existing_po=None)
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="999",
                direction="unknown_direction",
                payload=_payload("P099"),
                source_file="unknown.edi",
                correlation_id="corr-unknown",
                partner_id="lowes",
            )
        assert result.success is True
        assert result.violations == []
        store.transition_and_record.assert_not_called()

    def test_865_unknown_ack_type_skips_lifecycle(self):
        """865 with ack_type other than AT/RJ returns success=True without DB write."""
        existing = {"po_number": "P098", "current_state": "po_changed",
                    "is_terminal": False, "ordered_qty": 50}
        engine = _make_engine()
        store = _mock_store(existing_po=existing)
        payload = {"header": {"po_number": "P098", "ack_type": "XX"}}
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="865",
                direction="outbound",
                payload=payload,
                source_file="865_bad.edi",
                correlation_id="corr-865-bad",
                partner_id="lowes",
            )
        assert result.success is True
        assert result.violations == []
        store.transition_and_record.assert_not_called()


# ---------------------------------------------------------------------------
# Additional violation paths  (lines 355-356, 378-379, 424-425)
# ---------------------------------------------------------------------------

class TestAdditionalViolations:
    def test_n1_qualifier_violation_returns_failure(self):
        """N1 qualifier mismatch triggers violation and returns success=False."""
        engine = _make_engine()
        store = _mock_store(existing_po=None)
        # Force n1_map to require "93" for 850 — payload sends "WRONG"
        with patch.object(
            engine._loader, "get_n1_qualifier_map", return_value={"850": "93"}
        ):
            payload = {"header": {"po_number": "P050", "n1_qualifier": "WRONG"}}
            with patch("lifecycle_engine.engine.StateStore", return_value=store):
                result = engine.process_event(
                    transaction_set="850",
                    direction="inbound",
                    payload=payload,
                    source_file="n1.edi",
                    correlation_id="corr-n1",
                    partner_id="lowes",
                )
        assert result.success is False
        assert "n1_qualifier" in str(store.record_violation.call_args)

    def test_po_continuity_violation_returns_failure(self):
        """PO continuity mismatch triggers violation and returns success=False."""
        existing = {"po_number": "P055", "current_state": "po_originated",
                    "is_terminal": False, "ordered_qty": 100}
        engine = _make_engine()
        store = _mock_store(existing_po=existing)
        with patch(
            "lifecycle_engine.engine.validate_po_number_continuity",
            side_effect=POContinuityError("PO# mismatch on 855"),
        ):
            with patch("lifecycle_engine.engine.StateStore", return_value=store):
                result = engine.process_event(
                    transaction_set="855",
                    direction="outbound",
                    payload=_payload("P055"),
                    source_file="cont.edi",
                    correlation_id="corr-cont",
                    partner_id="lowes",
                )
        assert result.success is False
        assert "po_continuity" in str(store.record_violation.call_args)

    def test_transition_and_record_lifecycle_error_reraises(self):
        """LifecycleError from store.transition_and_record propagates out of process_event."""
        engine = _make_engine()
        store = _mock_store(existing_po=None)
        store.transition_and_record.side_effect = LifecycleError("state store failed")
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            with pytest.raises(LifecycleError, match="state store failed"):
                engine.process_event(
                    transaction_set="850",
                    direction="inbound",
                    payload=_payload("P060"),
                    source_file="test.edi",
                    correlation_id="corr-060",
                    partner_id="lowes",
                )


# ---------------------------------------------------------------------------
# Internal helper type guards  (lines 452, 455, 462, 465, 471-472, 477, 480)
# ---------------------------------------------------------------------------

class TestInternalHelpers:
    def test_extract_po_number_non_dict_payload(self):
        """_extract_po_number() returns None for non-dict payload."""
        engine = _make_engine()
        assert engine._extract_po_number("not a dict") is None
        assert engine._extract_po_number(None) is None
        assert engine._extract_po_number(42) is None

    def test_extract_po_number_non_dict_header(self):
        """_extract_po_number() returns None when payload.header is not a dict."""
        engine = _make_engine()
        assert engine._extract_po_number({"header": "not a dict"}) is None
        assert engine._extract_po_number({"header": 123}) is None

    def test_extract_qty_non_dict_payload(self):
        """_extract_qty() returns None for non-dict payload."""
        engine = _make_engine()
        assert engine._extract_qty("not a dict", "850") is None
        assert engine._extract_qty(None, "850") is None

    def test_extract_qty_non_dict_header(self):
        """_extract_qty() returns None when payload.header is not a dict."""
        engine = _make_engine()
        assert engine._extract_qty({"header": "not a dict"}, "850") is None

    def test_extract_qty_bad_float_returns_none(self):
        """_extract_qty() returns None when quantity cannot be cast to float."""
        engine = _make_engine()
        assert engine._extract_qty({"header": {"quantity": "not-a-number"}}, "850") is None
        assert engine._extract_qty({"header": {"quantity": []}}, "850") is None

    def test_extract_n1_qualifier_non_dict_payload(self):
        """_extract_n1_qualifier() returns None for non-dict payload."""
        engine = _make_engine()
        assert engine._extract_n1_qualifier("not a dict") is None
        assert engine._extract_n1_qualifier(None) is None

    def test_extract_n1_qualifier_non_dict_header(self):
        """_extract_n1_qualifier() returns None when payload.header is not a dict."""
        engine = _make_engine()
        assert engine._extract_n1_qualifier({"header": "not a dict"}) is None

    def test_capture_fields_skips_entry_with_empty_key(self):
        """_capture_fields() skips capture entries that have no 'key' field."""
        engine = _make_engine()
        # Inject a state whose captures list has an entry without a 'key' field
        engine._loader._states["_test_empty_key_capture"] = {
            "captures": [
                {"description": "entry with no key"},   # no 'key' field → skipped
                {"key": "po_number", "path": "header.po_number"},
            ]
        }
        result = engine._capture_fields(
            "_test_empty_key_capture",
            {"header": {"po_number": "P999"}},
        )
        # Only the entry with a key should be captured
        assert "po_number" in result
        assert result["po_number"] == "P999"


# ---------------------------------------------------------------------------
# _handle_violation: store exception + S3 workspace write  (lines 536-537, 541-542)
# ---------------------------------------------------------------------------

class TestHandleViolation:
    def test_store_record_violation_exception_is_swallowed(self):
        """_handle_violation() logs but does not re-raise if store.record_violation fails."""
        engine = _make_engine()
        store = _mock_store()
        store.record_violation.side_effect = Exception("DB connection lost")

        # Trigger a violation (missing PO#) — the DB write fails but should not crash
        with patch("lifecycle_engine.engine.StateStore", return_value=store):
            result = engine.process_event(
                transaction_set="850",
                direction="inbound",
                payload={"header": {}},   # no po_number → missing_po violation
                source_file="test.edi",
                correlation_id="corr-store-err",
                partner_id="lowes",
            )
        # Violation was detected; DB write failed silently
        assert result.success is False
        assert len(result.violations) > 0

    def test_handle_violation_writes_to_s3_when_workspace_provided(self):
        """_handle_violation() calls write_violation_to_s3() when workspace is set."""
        engine = _make_engine()
        store = _mock_store()
        mock_ws = MagicMock()

        with patch("lifecycle_engine.engine.StateStore", return_value=store), \
             patch("lifecycle_engine.s3_writer.write_violation_to_s3") as mock_s3:
            result = engine.process_event(
                transaction_set="850",
                direction="inbound",
                payload={"header": {}},   # no po_number → missing_po violation
                source_file="test.edi",
                correlation_id="corr-s3",
                partner_id="lowes",
                workspace=mock_ws,         # S3 write enabled
            )
        assert result.success is False
        mock_s3.assert_called_once()
        # Workspace must have been passed through
        call_kwargs = mock_s3.call_args.kwargs
        assert call_kwargs["workspace"] is mock_ws
