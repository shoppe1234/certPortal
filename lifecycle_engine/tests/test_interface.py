"""
Tests for lifecycle_engine/interface.py

Verifies: DIRECTION_MAP completeness, on_document_processed() contract,
singleton reuse, and the ImportError-guarded dict return.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from lifecycle_engine.interface import DIRECTION_MAP, on_document_processed
import lifecycle_engine.interface as _iface


# ---------------------------------------------------------------------------
# DIRECTION_MAP
# ---------------------------------------------------------------------------

class TestDirectionMap:
    def test_all_six_tx_types_present(self):
        assert set(DIRECTION_MAP.keys()) == {"850", "860", "855", "865", "856", "810"}

    def test_inbound_types(self):
        assert DIRECTION_MAP["850"] == "inbound"
        assert DIRECTION_MAP["860"] == "inbound"

    def test_outbound_types(self):
        for tx in ("855", "865", "856", "810"):
            assert DIRECTION_MAP[tx] == "outbound"


# ---------------------------------------------------------------------------
# on_document_processed
# ---------------------------------------------------------------------------

def _mock_engine_result():
    from lifecycle_engine.engine import LifecycleResult
    return LifecycleResult(
        success=True,
        po_number="P001",
        partner_id="lowes",
        prior_state=None,
        new_state="po_originated",
        is_terminal=False,
        correlation_id="corr-001",
        violations=[],
    )


class TestOnDocumentProcessed:
    def test_returns_dict(self):
        """on_document_processed must return a plain dict (not a dataclass)."""
        mock_engine = MagicMock()
        mock_engine.process_event.return_value = _mock_engine_result()

        with patch.object(_iface, "_engine", mock_engine):
            result = on_document_processed(
                transaction_set="850",
                direction="inbound",
                payload={"header": {"po_number": "P001"}},
                source_file="test.edi",
                correlation_id="corr-001",
                partner_id="lowes",
            )

        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["new_state"] == "po_originated"
        assert result["po_number"] == "P001"

    def test_passes_kwargs_to_process_event(self):
        """All arguments are forwarded to engine.process_event()."""
        mock_engine = MagicMock()
        mock_engine.process_event.return_value = _mock_engine_result()

        with patch.object(_iface, "_engine", mock_engine):
            on_document_processed(
                transaction_set="855",
                direction="outbound",
                payload={"header": {"po_number": "P002"}},
                source_file="855.edi",
                correlation_id="corr-002",
                partner_id="lowes",
            )

        mock_engine.process_event.assert_called_once_with(
            transaction_set="855",
            direction="outbound",
            payload={"header": {"po_number": "P002"}},
            source_file="855.edi",
            correlation_id="corr-002",
            partner_id="lowes",
            workspace=None,
        )

    def test_passes_workspace_when_provided(self):
        """workspace kwarg is forwarded to engine.process_event()."""
        mock_engine = MagicMock()
        mock_engine.process_event.return_value = _mock_engine_result()
        mock_ws = MagicMock()

        with patch.object(_iface, "_engine", mock_engine):
            on_document_processed(
                transaction_set="810",
                direction="outbound",
                payload={"header": {"po_number": "P003"}},
                source_file="810.edi",
                correlation_id="corr-003",
                partner_id="lowes",
                workspace=mock_ws,
            )

        _, call_kwargs = mock_engine.process_event.call_args
        assert call_kwargs["workspace"] is mock_ws

    def test_singleton_reuse(self):
        """_get_engine() should return the same engine object on second call."""
        # Reset singleton
        original = _iface._engine
        _iface._engine = None
        try:
            mock_engine = MagicMock()
            mock_engine.process_event.return_value = _mock_engine_result()

            with patch("lifecycle_engine.engine.LifecycleEngine.from_config",
                       return_value=mock_engine):
                e1 = _iface._get_engine()
                e2 = _iface._get_engine()
            assert e1 is e2
        finally:
            _iface._engine = original

    def test_failure_result_is_dict_with_success_false(self):
        """Violation results are also returned as dict."""
        from lifecycle_engine.engine import LifecycleResult
        fail_result = LifecycleResult(
            success=False,
            po_number="unknown",
            partner_id="lowes",
            prior_state=None,
            new_state="unknown",
            is_terminal=False,
            correlation_id="corr-bad",
            violations=["PO number not found in payload.header.po_number"],
        )
        mock_engine = MagicMock()
        mock_engine.process_event.return_value = fail_result

        with patch.object(_iface, "_engine", mock_engine):
            result = on_document_processed(
                transaction_set="850",
                direction="inbound",
                payload={"header": {}},
                source_file="bad.edi",
                correlation_id="corr-bad",
                partner_id="lowes",
            )

        assert isinstance(result, dict)
        assert result["success"] is False
        assert len(result["violations"]) == 1
