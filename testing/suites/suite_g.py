"""
testing/suites/suite_g.py — Moses Lifecycle Hook Tests.

Runs entirely in-process — no live DB, no S3, no pyedi_core calls.
Covers the two code paths added in Step 13b:

  Group 1 — _extract_po_from_edi() (8 tests, pure Python, zero mocks)
    All six X12 transaction types (850/860/855/865/856/810) plus missing-segment
    and unknown-transaction-type edge cases.

  Group 2 — Lifecycle hook inside moses.run() (4 tests)
    Hook fires and passes correct args to on_document_processed()
    Direction mapping: inbound vs outbound per transaction type
    ImportError guard: lifecycle_engine absent -> Moses completes silently
    Non-fatal exception guard: on_document_processed raises -> result returned,
      error logged to Monica

Architecture coverage:
  CLAUDE.md Step 13b — Moses -> lifecycle_engine direct integration
  NC-04              — pyedi_core works standalone without lifecycle_engine
  INV-01             — no direct inter-agent imports; S3 is the channel
"""
from __future__ import annotations

import sys
import traceback
from enum import Enum
from typing import Callable
from unittest.mock import AsyncMock, MagicMock, patch


class TestStatus(Enum):
    SKIP = "SKIP"
    PASS = "PASS"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Lazy imports — guard so suite degrades to SKIP rather than crashing
# ---------------------------------------------------------------------------

_MOSES_OK = False
_IMPORT_ERRORS: list[str] = []

try:
    from agents.moses import _extract_po_from_edi, run as _moses_run  # type: ignore[import]
    _MOSES_OK = True
except Exception as _e:  # noqa: BLE001
    _IMPORT_ERRORS.append(f"agents.moses: {_e}")

# FileNotFoundInWorkspace is needed to simulate missing YAML map (non-fatal)
_FNF: type | None = None
try:
    from certportal.core.workspace import FileNotFoundInWorkspace as _FNF  # type: ignore[import]
except Exception as _e2:  # noqa: BLE001
    _IMPORT_ERRORS.append(f"certportal.core.workspace: {_e2}")
    # Fallback so tests that need it can still skip gracefully
    class _FNF(Exception):  # type: ignore[no-redef]
        pass


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def _run_test(name: str, fn: Callable[[], None]) -> dict:
    try:
        fn()
        return {"test": name, "status": TestStatus.PASS, "reason": ""}
    except AssertionError as e:
        return {"test": name, "status": TestStatus.FAIL, "reason": f"AssertionError: {e}"}
    except Exception as e:
        return {
            "test": name,
            "status": TestStatus.FAIL,
            "reason": f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}",
        }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_mock_workspace(
    retailer_slug: str = "lowes",
    supplier_slug: str = "test-supplier",
    edi_content: bytes = b"ISA*00*~BEG*00*SA*PO12345*~SE*2*0001~",
    thesis_bytes: bytes = b"# THESIS\nMinimal thesis for Moses testing.",
    tx_type: str = "850",
) -> MagicMock:
    """Return a pre-configured MagicMock S3AgentWorkspace.

    _retailer_slug / _supplier_slug are set so _verify_supplier_scope passes.
    download_raw_edi returns edi_content.
    download_retailer_map: first call returns thesis_bytes (THESIS.md),
                           second call raises FileNotFoundInWorkspace (YAML map — non-fatal).
    upload returns a plausible S3 key string.
    """
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


def _std_patches(mock_ws: MagicMock) -> list:
    """Return a list of patch() context managers shared by all integration tests."""
    return [
        patch("agents.moses.S3AgentWorkspace", return_value=mock_ws),
        patch("agents.moses.monica_logger"),
        patch("agents.moses._insert_test_occurrence", new=AsyncMock(return_value=None)),
    ]


# ---------------------------------------------------------------------------
# Group 1: _extract_po_from_edi() — pure Python, zero mocks (tests 01-08)
# ---------------------------------------------------------------------------

def _test_01_extract_po_850() -> None:
    """850 EDI: BEG segment -> BEG03 carries the PO number."""
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    edi = "ISA*00*~GS*PO*~ST*850*0001~BEG*00*SA*PO12345*~N1*BY*LOWES~SE*5*0001~"
    result = _extract_po_from_edi(edi, "850")
    assert result == "PO12345", f"Expected 'PO12345', got: {result!r}"


def _test_02_extract_po_860() -> None:
    """860 EDI: BCH segment -> BCH03 carries the PO number."""
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    edi = "ISA*00*~BCH*00*PC*PO67890*~SE*2*0001~"
    result = _extract_po_from_edi(edi, "860")
    assert result == "PO67890", f"Expected 'PO67890', got: {result!r}"


def _test_03_extract_po_855() -> None:
    """855 EDI: BAK segment -> BAK03 carries the PO number."""
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    edi = "ISA*00*~BAK*00*AD*PO11111*20240101~SE*2*0001~"
    result = _extract_po_from_edi(edi, "855")
    assert result == "PO11111", f"Expected 'PO11111', got: {result!r}"


def _test_04_extract_po_865() -> None:
    """865 EDI: BCA segment -> BCA03 carries the PO number."""
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    edi = "ISA*00*~BCA*00*AT*PO22222*~SE*2*0001~"
    result = _extract_po_from_edi(edi, "865")
    assert result == "PO22222", f"Expected 'PO22222', got: {result!r}"


def _test_05_extract_po_856() -> None:
    """856 EDI: PRF segment -> PRF01 carries the PO number (no qualifier elements)."""
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    edi = "ISA*00*~PRF*PO33333*~SE*2*0001~"
    result = _extract_po_from_edi(edi, "856")
    assert result == "PO33333", f"Expected 'PO33333', got: {result!r}"


def _test_06_extract_po_810() -> None:
    """810 EDI: BIG segment -> BIG04 carries the PO number (after date, inv#, po_date)."""
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    # BIG*<inv_date>*<inv_num>*<po_date>*<PO#>
    edi = "ISA*00*~BIG*20240101*INV001*20231201*PO44444*~SE*2*0001~"
    result = _extract_po_from_edi(edi, "810")
    assert result == "PO44444", f"Expected 'PO44444', got: {result!r}"


def _test_07_extract_po_missing_segment() -> None:
    """850 EDI with no BEG segment -> returns None (non-fatal; lifecycle logs violation)."""
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    edi = "ISA*00*~GS*PO*~ST*850*0001~N1*BY*LOWES~SE*3*0001~GE*1*~IEA*1*~"
    result = _extract_po_from_edi(edi, "850")
    assert result is None, f"Expected None for missing BEG segment, got: {result!r}"


def _test_08_extract_po_unknown_tx() -> None:
    """Unknown tx type '999' falls back to BEG pattern; BEG absent -> None."""
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    edi = "ISA*00*~ST*999*0001~SE*2*0001~"  # no BEG present
    result = _extract_po_from_edi(edi, "999")
    assert result is None, (
        f"Expected None for unknown tx type with no BEG segment, got: {result!r}"
    )


# ---------------------------------------------------------------------------
# Group 2: Lifecycle hook integration via moses.run() (tests 09-12)
# ---------------------------------------------------------------------------

def _test_09_lifecycle_hook_fires_850() -> None:
    """moses.run() calls on_document_processed() with correct args for an 850 document.

    Verifies: transaction_set='850', direction='inbound', partner_id='lowes'.
    """
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    edi = b"ISA*00*~BEG*00*SA*PO12345*~SE*2*0001~"
    mock_ws = _make_mock_workspace(edi_content=edi, tx_type="850")
    lc_return = {"new_state": "VALIDATED", "po_number": "PO12345", "success": True}

    with patch("agents.moses.S3AgentWorkspace", return_value=mock_ws), \
         patch("agents.moses.monica_logger"), \
         patch("agents.moses._insert_test_occurrence", new=AsyncMock(return_value=None)), \
         patch("agents.moses.pyedi_core") as mock_pyedi, \
         patch(
             "lifecycle_engine.interface.on_document_processed",
             return_value=lc_return,
         ) as mock_lc:
        mock_pyedi.validate.return_value = []
        result = _moses_run("lowes", "test-supplier", "raw/850.edi", "850", "edi-direct")

    assert mock_lc.called, "on_document_processed should have been called for 850"

    # Normalise positional + keyword args into a single dict for assertion
    call_args = mock_lc.call_args
    pos = call_args.args if call_args.args else ()
    kw = call_args.kwargs if call_args.kwargs else {}
    arg_names = ["transaction_set", "direction", "payload", "source_file", "correlation_id"]
    combined = {**dict(zip(arg_names, pos)), **kw}

    assert combined.get("transaction_set") == "850", (
        f"Expected transaction_set='850', got: {combined}"
    )
    assert combined.get("direction") == "inbound", (
        f"Expected direction='inbound' for 850, got: {combined}"
    )
    assert combined.get("partner_id") == "lowes", (
        f"Expected partner_id='lowes', got: {combined}"
    )
    assert result.status in ("PASS", "PARTIAL", "FAIL")


def _test_10_lifecycle_hook_direction_outbound_855() -> None:
    """moses.run() with an 855 document passes direction='outbound' to the lifecycle hook.

    Verifies the DIRECTION_MAP outbound path (855/865/856/810 -> 'outbound').
    """
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    edi = b"ISA*00*~BAK*00*AD*PO55555*20240101~SE*2*0001~"
    mock_ws = _make_mock_workspace(
        edi_content=edi,
        retailer_slug="lowes",
        supplier_slug="test-supplier",
        tx_type="855",
    )
    lc_return = {"new_state": "VALIDATED", "po_number": "PO55555", "success": True}

    with patch("agents.moses.S3AgentWorkspace", return_value=mock_ws), \
         patch("agents.moses.monica_logger"), \
         patch("agents.moses._insert_test_occurrence", new=AsyncMock(return_value=None)), \
         patch("agents.moses.pyedi_core") as mock_pyedi, \
         patch(
             "lifecycle_engine.interface.on_document_processed",
             return_value=lc_return,
         ) as mock_lc:
        mock_pyedi.validate.return_value = []
        _moses_run("lowes", "test-supplier", "raw/855.edi", "855", "edi-direct")

    assert mock_lc.called, "on_document_processed should have been called for 855"

    call_args = mock_lc.call_args
    pos = call_args.args if call_args.args else ()
    kw = call_args.kwargs if call_args.kwargs else {}
    arg_names = ["transaction_set", "direction", "payload", "source_file", "correlation_id"]
    combined = {**dict(zip(arg_names, pos)), **kw}

    assert combined.get("direction") == "outbound", (
        f"Expected direction='outbound' for 855, got: {combined}"
    )


def _test_11_lifecycle_import_error_guard() -> None:
    """When lifecycle_engine is absent, the ImportError guard fires silently.

    Moses must complete and return a valid ValidationResult — NC-04 compliance.
    Simulated by injecting None into sys.modules (Python treats that as a blocked import).
    """
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    edi = b"ISA*00*~BEG*00*SA*PO99999*~SE*2*0001~"
    mock_ws = _make_mock_workspace(edi_content=edi, tx_type="850")

    # sys.modules[key] = None -> any `import key` raises ImportError (ModuleNotFoundError)
    blocked = {
        "lifecycle_engine": None,
        "lifecycle_engine.interface": None,
    }

    with patch("agents.moses.S3AgentWorkspace", return_value=mock_ws), \
         patch("agents.moses.monica_logger"), \
         patch("agents.moses._insert_test_occurrence", new=AsyncMock(return_value=None)), \
         patch("agents.moses.pyedi_core") as mock_pyedi, \
         patch.dict(sys.modules, blocked):
        mock_pyedi.validate.return_value = []
        result = _moses_run("lowes", "test-supplier", "raw/850.edi", "850", "edi-direct")

    # Must not raise — ImportError caught by the guard
    assert result is not None, "run() must return a ValidationResult even without lifecycle_engine"
    assert result.status in ("PASS", "PARTIAL", "FAIL"), (
        f"Unexpected status when lifecycle_engine absent: {result.status!r}"
    )


def _test_12_lifecycle_exception_nonfatal() -> None:
    """on_document_processed raising an exception must not abort moses.run().

    Verifies the non-fatal except-Exception guard: moses returns a result AND logs
    'lifecycle_hook_error' to Monica.
    """
    assert _MOSES_OK, f"agents.moses import failed: {_IMPORT_ERRORS}"
    edi = b"ISA*00*~BEG*00*SA*PO88888*~SE*2*0001~"
    mock_ws = _make_mock_workspace(edi_content=edi, tx_type="850")
    mock_monica = MagicMock()

    with patch("agents.moses.S3AgentWorkspace", return_value=mock_ws), \
         patch("agents.moses.monica_logger", mock_monica), \
         patch("agents.moses._insert_test_occurrence", new=AsyncMock(return_value=None)), \
         patch("agents.moses.pyedi_core") as mock_pyedi, \
         patch(
             "lifecycle_engine.interface.on_document_processed",
             side_effect=RuntimeError("lifecycle DB unavailable"),
         ):
        mock_pyedi.validate.return_value = []
        result = _moses_run("lowes", "test-supplier", "raw/850.edi", "850", "edi-direct")

    # Must not raise — exception swallowed by the non-fatal guard
    assert result is not None, "run() must return a result even when lifecycle hook raises"
    assert result.status in ("PASS", "PARTIAL", "FAIL")

    # Monica must have received the lifecycle_hook_error log entry
    log_calls = [str(c) for c in mock_monica.log.call_args_list]
    assert any("lifecycle_hook_error" in c for c in log_calls), (
        f"Expected 'lifecycle_hook_error' in Monica log calls.\nCalls: {log_calls}"
    )


# ---------------------------------------------------------------------------
# Suite entry point
# ---------------------------------------------------------------------------

def run() -> list[dict]:
    """Run all 12 Moses lifecycle hook tests. No external services required."""
    tests = [
        # Group 1 — _extract_po_from_edi() pure-Python coverage
        ("suite_g_test_01", "_extract_po_from_edi: 850 -> BEG03 = PO number",
         _test_01_extract_po_850),
        ("suite_g_test_02", "_extract_po_from_edi: 860 -> BCH03 = PO number",
         _test_02_extract_po_860),
        ("suite_g_test_03", "_extract_po_from_edi: 855 -> BAK03 = PO number",
         _test_03_extract_po_855),
        ("suite_g_test_04", "_extract_po_from_edi: 865 -> BCA03 = PO number",
         _test_04_extract_po_865),
        ("suite_g_test_05", "_extract_po_from_edi: 856 -> PRF01 = PO number",
         _test_05_extract_po_856),
        ("suite_g_test_06", "_extract_po_from_edi: 810 -> BIG04 = PO number",
         _test_06_extract_po_810),
        ("suite_g_test_07", "_extract_po_from_edi: missing segment -> None",
         _test_07_extract_po_missing_segment),
        ("suite_g_test_08", "_extract_po_from_edi: unknown tx type -> None (BEG absent)",
         _test_08_extract_po_unknown_tx),
        # Group 2 — lifecycle hook integration via moses.run()
        ("suite_g_test_09", "lifecycle hook: 850 -> on_document_processed called (inbound)",
         _test_09_lifecycle_hook_fires_850),
        ("suite_g_test_10", "lifecycle hook: 855 -> direction=outbound passed to engine",
         _test_10_lifecycle_hook_direction_outbound_855),
        ("suite_g_test_11", "lifecycle hook: ImportError guard -> run() succeeds silently (NC-04)",
         _test_11_lifecycle_import_error_guard),
        ("suite_g_test_12", "lifecycle hook: exception non-fatal -> result returned + logged",
         _test_12_lifecycle_exception_nonfatal),
    ]

    results = []
    for test_id, description, fn in tests:
        r = _run_test(test_id, fn)
        r["description"] = description
        results.append(r)
        status_str = r["status"].value
        reason_str = f" -- {r['reason'][:120]}" if r["reason"] else ""
        print(f"  [{status_str:4s}] {test_id}: {description}{reason_str}")

    return results
