"""Migrated from testing/suites/suite_g.py — Moses Lifecycle Hook Tests."""
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = [pytest.mark.unit]

moses = pytest.importorskip("agents.moses")
_extract_po_from_edi = moses._extract_po_from_edi
_moses_run = moses.run

try:
    from certportal.core.workspace import FileNotFoundInWorkspace as _FNF
except Exception:
    class _FNF(Exception):
        pass


def _make_mock_workspace(retailer_slug="lowes", supplier_slug="test-supplier",
                         edi_content=b"ISA*00*~BEG*00*SA*PO12345*~SE*2*0001~",
                         thesis_bytes=b"# THESIS\nMinimal thesis for Moses testing.",
                         tx_type="850"):
    mock_ws = MagicMock()
    mock_ws._retailer_slug = retailer_slug
    mock_ws._supplier_slug = supplier_slug
    mock_ws.download_raw_edi.return_value = edi_content
    mock_ws.download_retailer_map.side_effect = [
        thesis_bytes,
        _FNF(f"maps/{tx_type}.yaml not found"),
    ]
    mock_ws.upload.return_value = f"{retailer_slug}/{supplier_slug}/results/test.json"
    return mock_ws


class TestExtractPoFromEdi:
    """Pure Python, zero mocks."""

    def test_01_extract_po_850(self):
        edi = "ISA*00*~GS*PO*~ST*850*0001~BEG*00*SA*PO12345*~N1*BY*LOWES~SE*5*0001~"
        assert _extract_po_from_edi(edi, "850") == "PO12345"

    def test_02_extract_po_860(self):
        edi = "ISA*00*~BCH*00*PC*PO67890*~SE*2*0001~"
        assert _extract_po_from_edi(edi, "860") == "PO67890"

    def test_03_extract_po_855(self):
        edi = "ISA*00*~BAK*00*AD*PO11111*20240101~SE*2*0001~"
        assert _extract_po_from_edi(edi, "855") == "PO11111"

    def test_04_extract_po_865(self):
        edi = "ISA*00*~BCA*00*AT*PO22222*~SE*2*0001~"
        assert _extract_po_from_edi(edi, "865") == "PO22222"

    def test_05_extract_po_856(self):
        edi = "ISA*00*~PRF*PO33333*~SE*2*0001~"
        assert _extract_po_from_edi(edi, "856") == "PO33333"

    def test_06_extract_po_810(self):
        edi = "ISA*00*~BIG*20240101*INV001*20231201*PO44444*~SE*2*0001~"
        assert _extract_po_from_edi(edi, "810") == "PO44444"

    def test_07_extract_po_missing_segment(self):
        edi = "ISA*00*~GS*PO*~ST*850*0001~N1*BY*LOWES~SE*3*0001~GE*1*~IEA*1*~"
        assert _extract_po_from_edi(edi, "850") is None

    def test_08_extract_po_unknown_tx(self):
        edi = "ISA*00*~ST*999*0001~SE*2*0001~"
        assert _extract_po_from_edi(edi, "999") is None


class TestLifecycleHookIntegration:
    """Lifecycle hook integration via moses.run()."""

    def test_09_lifecycle_hook_fires_850(self):
        edi = b"ISA*00*~BEG*00*SA*PO12345*~SE*2*0001~"
        mock_ws = _make_mock_workspace(edi_content=edi, tx_type="850")
        lc_return = {"new_state": "VALIDATED", "po_number": "PO12345", "success": True}

        with patch("agents.moses.S3AgentWorkspace", return_value=mock_ws), \
             patch("agents.moses.monica_logger"), \
             patch("agents.moses._insert_test_occurrence", new=AsyncMock(return_value=None)), \
             patch("agents.moses.pyedi_core") as mock_pyedi, \
             patch("lifecycle_engine.interface.on_document_processed",
                   return_value=lc_return) as mock_lc:
            mock_pyedi.validate.return_value = []
            result = _moses_run("lowes", "test-supplier", "raw/850.edi", "850", "edi-direct")

        assert mock_lc.called, "on_document_processed should have been called for 850"
        call_args = mock_lc.call_args
        pos = call_args.args if call_args.args else ()
        kw = call_args.kwargs if call_args.kwargs else {}
        arg_names = ["transaction_set", "direction", "payload", "source_file", "correlation_id"]
        combined = {**dict(zip(arg_names, pos)), **kw}
        assert combined.get("transaction_set") == "850"
        assert combined.get("direction") == "inbound"
        assert combined.get("partner_id") == "lowes"

    def test_10_lifecycle_hook_direction_outbound_855(self):
        edi = b"ISA*00*~BAK*00*AD*PO55555*20240101~SE*2*0001~"
        mock_ws = _make_mock_workspace(edi_content=edi, retailer_slug="lowes",
                                       supplier_slug="test-supplier", tx_type="855")
        lc_return = {"new_state": "VALIDATED", "po_number": "PO55555", "success": True}

        with patch("agents.moses.S3AgentWorkspace", return_value=mock_ws), \
             patch("agents.moses.monica_logger"), \
             patch("agents.moses._insert_test_occurrence", new=AsyncMock(return_value=None)), \
             patch("agents.moses.pyedi_core") as mock_pyedi, \
             patch("lifecycle_engine.interface.on_document_processed",
                   return_value=lc_return) as mock_lc:
            mock_pyedi.validate.return_value = []
            _moses_run("lowes", "test-supplier", "raw/855.edi", "855", "edi-direct")

        call_args = mock_lc.call_args
        pos = call_args.args if call_args.args else ()
        kw = call_args.kwargs if call_args.kwargs else {}
        arg_names = ["transaction_set", "direction", "payload", "source_file", "correlation_id"]
        combined = {**dict(zip(arg_names, pos)), **kw}
        assert combined.get("direction") == "outbound"

    def test_11_lifecycle_import_error_guard(self):
        edi = b"ISA*00*~BEG*00*SA*PO99999*~SE*2*0001~"
        mock_ws = _make_mock_workspace(edi_content=edi, tx_type="850")
        blocked = {"lifecycle_engine": None, "lifecycle_engine.interface": None}

        with patch("agents.moses.S3AgentWorkspace", return_value=mock_ws), \
             patch("agents.moses.monica_logger"), \
             patch("agents.moses._insert_test_occurrence", new=AsyncMock(return_value=None)), \
             patch("agents.moses.pyedi_core") as mock_pyedi, \
             patch.dict(sys.modules, blocked):
            mock_pyedi.validate.return_value = []
            result = _moses_run("lowes", "test-supplier", "raw/850.edi", "850", "edi-direct")

        assert result is not None
        assert result.status in ("PASS", "PARTIAL", "FAIL")

    def test_12_lifecycle_exception_nonfatal(self):
        edi = b"ISA*00*~BEG*00*SA*PO88888*~SE*2*0001~"
        mock_ws = _make_mock_workspace(edi_content=edi, tx_type="850")
        mock_monica = MagicMock()

        with patch("agents.moses.S3AgentWorkspace", return_value=mock_ws), \
             patch("agents.moses.monica_logger", mock_monica), \
             patch("agents.moses._insert_test_occurrence", new=AsyncMock(return_value=None)), \
             patch("agents.moses.pyedi_core") as mock_pyedi, \
             patch("lifecycle_engine.interface.on_document_processed",
                   side_effect=RuntimeError("lifecycle DB unavailable")):
            mock_pyedi.validate.return_value = []
            result = _moses_run("lowes", "test-supplier", "raw/850.edi", "850", "edi-direct")

        assert result is not None
        assert result.status in ("PASS", "PARTIAL", "FAIL")
        log_calls = [str(c) for c in mock_monica.log.call_args_list]
        assert any("lifecycle_hook_error" in c for c in log_calls)
