"""
testing/suites/suite_b.py — Agent Unit Tests (Andy + Ryan deterministic logic).

Runs entirely in-process — no live DB, no S3, no OpenAI calls.
Covers the pure-Python code paths that process every EDI transaction in production.

TRD coverage:
  Andy Path 2   — YAML validation (validate_yaml_against_x12)
  Andy internal — Bundle detection (_detect_bundle)
  Ryan internal — Thesis rule lookup (_find_thesis_rule)
  Ryan          — run() fast-path (empty error list)
"""
from __future__ import annotations

import traceback
from enum import Enum
from typing import Callable
from unittest.mock import patch


class TestStatus(Enum):
    SKIP = "SKIP"
    PASS = "PASS"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Lazy imports — agents require certportal.core.config (env vars). We guard
# import failures so the suite degrades to SKIP rather than crashing.
# ---------------------------------------------------------------------------

_ANDY_OK = False
_RYAN_OK = False
_MODELS_OK = False
_IMPORT_ERRORS: list[str] = []

try:
    from agents.andy import validate_yaml_against_x12, _detect_bundle  # type: ignore[import]
    _ANDY_OK = True
except Exception as _e:  # noqa: BLE001
    _IMPORT_ERRORS.append(f"agents.andy: {_e}")

try:
    from agents.ryan import _find_thesis_rule, run as _ryan_run  # type: ignore[import]
    _RYAN_OK = True
except Exception as _e:  # noqa: BLE001
    _IMPORT_ERRORS.append(f"agents.ryan: {_e}")

try:
    from certportal.core.models import ValidationResult  # type: ignore[import]
    _MODELS_OK = True
except Exception as _e:  # noqa: BLE001
    _IMPORT_ERRORS.append(f"certportal.core.models: {_e}")


# ---------------------------------------------------------------------------
# Test runner (mirrors suite_f.py pattern)
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
# Tests 01-06: Andy — validate_yaml_against_x12 (pure Python, zero mocks)
# ---------------------------------------------------------------------------

def _test_01_andy_850_all_valid() -> None:
    """850 YAML with all mandatory ISA, GS, BEG segments and elements -> 0 warnings."""
    assert _ANDY_OK, f"agents.andy import failed: {_IMPORT_ERRORS}"
    yaml_content = {
        "transaction_type": "850",
        "field_mappings": {
            "ISA": {"ISA01": "00", "ISA06": "LOWES", "ISA08": "SUPPLIER"},
            "GS":  {"GS01": "PO", "GS02": "LOWES",  "GS03": "SUPPLIER"},
            "BEG": {"BEG01": "00", "BEG02": "SA",   "BEG05": "20240101"},
        },
    }
    warnings = validate_yaml_against_x12(yaml_content, "850")
    assert warnings == [], f"Expected no warnings, got: {warnings}"


def _test_02_andy_850_missing_segment() -> None:
    """850 YAML missing ISA segment entirely -> warning mentioning 'ISA'."""
    assert _ANDY_OK, f"agents.andy import failed: {_IMPORT_ERRORS}"
    yaml_content = {
        "transaction_type": "850",
        "field_mappings": {
            # ISA deliberately omitted
            "GS":  {"GS01": "PO", "GS02": "LOWES", "GS03": "SUPPLIER"},
            "BEG": {"BEG01": "00", "BEG02": "SA",  "BEG05": "20240101"},
        },
    }
    warnings = validate_yaml_against_x12(yaml_content, "850")
    assert any("ISA" in w for w in warnings), f"Expected ISA warning, got: {warnings}"


def _test_03_andy_850_missing_element() -> None:
    """850 YAML with ISA present but ISA01 missing -> exactly 1 warning for ISA01."""
    assert _ANDY_OK, f"agents.andy import failed: {_IMPORT_ERRORS}"
    yaml_content = {
        "transaction_type": "850",
        "field_mappings": {
            "ISA": {"ISA06": "LOWES", "ISA08": "SUPPLIER"},  # ISA01 absent
            "GS":  {"GS01": "PO", "GS02": "LOWES", "GS03": "SUPPLIER"},
            "BEG": {"BEG01": "00", "BEG02": "SA",  "BEG05": "20240101"},
        },
    }
    warnings = validate_yaml_against_x12(yaml_content, "850")
    assert any("ISA01" in w for w in warnings), f"Expected ISA01 warning, got: {warnings}"
    assert len(warnings) == 1, f"Expected exactly 1 warning, got {len(warnings)}: {warnings}"


def _test_04_andy_unknown_tx_type() -> None:
    """YAML with transaction_type '999' (not in X12 mandatory table) -> 1 warning."""
    assert _ANDY_OK, f"agents.andy import failed: {_IMPORT_ERRORS}"
    warnings = validate_yaml_against_x12({"transaction_type": "999", "field_mappings": {}}, "999")
    assert len(warnings) == 1, f"Expected 1 warning, got: {warnings}"
    assert "999" in warnings[0], f"Warning should mention tx type '999': {warnings[0]}"


def _test_05_andy_850_empty_field_mappings() -> None:
    """850 YAML with field_mappings={} -> >=3 warnings (ISA, GS, BEG all missing)."""
    assert _ANDY_OK, f"agents.andy import failed: {_IMPORT_ERRORS}"
    yaml_content = {"transaction_type": "850", "field_mappings": {}}
    warnings = validate_yaml_against_x12(yaml_content, "850")
    assert len(warnings) >= 3, f"Expected >=3 warnings for empty mappings, got: {warnings}"
    segments_warned = " ".join(warnings)
    for seg in ("ISA", "GS", "BEG"):
        assert seg in segments_warned, f"Expected warning for segment '{seg}': {warnings}"


def _test_06_andy_855_all_valid() -> None:
    """855 YAML with mandatory ISA + BAK segments -> 0 warnings (non-850 tx coverage)."""
    assert _ANDY_OK, f"agents.andy import failed: {_IMPORT_ERRORS}"
    yaml_content = {
        "transaction_type": "855",
        "field_mappings": {
            "ISA": {"ISA01": "00", "ISA06": "LOWES", "ISA08": "SUPPLIER"},
            "BAK": {"BAK01": "00", "BAK02": "AD",   "BAK04": "20240101"},
        },
    }
    warnings = validate_yaml_against_x12(yaml_content, "855")
    assert warnings == [], f"Expected no warnings for valid 855, got: {warnings}"


# ---------------------------------------------------------------------------
# Tests 07-08: Andy — _detect_bundle (pure Python, zero mocks)
# ---------------------------------------------------------------------------

def _test_07_andy_detect_bundle_general() -> None:
    """PDF text with no transportation codes -> 'general_merchandise'."""
    assert _ANDY_OK, f"agents.andy import failed: {_IMPORT_ERRORS}"
    pdf_text = "This trading partner guide covers PO 850, 855, 856, and 810 transactions."
    bundle = _detect_bundle(pdf_text)
    assert bundle == "general_merchandise", f"Expected general_merchandise, got: {bundle!r}"


def _test_08_andy_detect_bundle_transportation() -> None:
    """PDF text containing '204' -> 'transportation'."""
    assert _ANDY_OK, f"agents.andy import failed: {_IMPORT_ERRORS}"
    pdf_text = "This guide covers Motor Carrier Shipment Information (204) and Carrier Response (990)."
    bundle = _detect_bundle(pdf_text)
    assert bundle == "transportation", f"Expected transportation, got: {bundle!r}"


# ---------------------------------------------------------------------------
# Tests 09-10: Ryan — _find_thesis_rule + run() fast path
# ---------------------------------------------------------------------------

def _test_09_ryan_find_thesis_rule() -> None:
    """_find_thesis_rule matches present segments and returns None for absent ones."""
    assert _RYAN_OK, f"agents.ryan import failed: {_IMPORT_ERRORS}"

    thesis = """# THESIS -- Lowe's Trading Partner Rules

## Segment Rules
The BEG segment begins the purchase order and is mandatory on all 850 transactions.
Position 03 of the BEG segment must carry the PO number issued by Lowe's procurement.
The ISA segment carries interchange control data for all transmissions.
ISA qualifier in position 06 must be set to '9254016003' for Lowe's suppliers.

## Known Retailer-Specific Rules
N1 qualifier '93' required on all inbound 850 transactions.
"""
    # Should find BEG
    rule = _find_thesis_rule(thesis, "BEG")
    assert rule is not None, "Expected a rule for 'BEG' segment"
    assert "BEG" in rule, f"Rule should reference BEG: {rule!r}"

    # Should NOT find ZZZ (not in THESIS)
    no_rule = _find_thesis_rule(thesis, "ZZZ")
    assert no_rule is None, f"Expected None for absent segment 'ZZZ', got: {no_rule!r}"

    # Empty thesis -> always None
    assert _find_thesis_rule("", "BEG") is None, "Empty thesis must return None"


def _test_10_ryan_run_no_errors() -> None:
    """ryan.run() with no validation errors returns [] without touching S3 or LLM."""
    assert _RYAN_OK and _MODELS_OK, f"Import failed: {_IMPORT_ERRORS}"
    vr = ValidationResult(
        supplier_slug="test-supplier",
        retailer_slug="lowes",
        transaction_type="850",
        channel="inbound",
        status="PASS",
        errors=[],
    )
    # Patch monica_logger so no S3/DB writes happen during the test
    with patch("agents.ryan.monica_logger") as _mock_log:
        result = _ryan_run("lowes", "test-supplier", vr)
    assert result == [], f"Expected empty patch list, got: {result}"
    # Verify Monica was still notified (log was called at least once)
    assert _mock_log.log.called, "monica_logger.log should have been called"


# ---------------------------------------------------------------------------
# Suite entry point
# ---------------------------------------------------------------------------

def run() -> list[dict]:
    """Run all 10 agent unit tests. No external services required."""
    tests = [
        ("suite_b_test_01", "Andy: 850 YAML all valid -> 0 warnings",              _test_01_andy_850_all_valid),
        ("suite_b_test_02", "Andy: 850 YAML missing ISA segment -> warning",        _test_02_andy_850_missing_segment),
        ("suite_b_test_03", "Andy: 850 YAML ISA present, ISA01 missing -> 1 warn",  _test_03_andy_850_missing_element),
        ("suite_b_test_04", "Andy: unknown tx type 999 -> unsupported warning",     _test_04_andy_unknown_tx_type),
        ("suite_b_test_05", "Andy: 850 empty field_mappings -> >=3 warnings",       _test_05_andy_850_empty_field_mappings),
        ("suite_b_test_06", "Andy: 855 YAML all valid -> 0 warnings",              _test_06_andy_855_all_valid),
        ("suite_b_test_07", "Andy: detect_bundle general merchandise",              _test_07_andy_detect_bundle_general),
        ("suite_b_test_08", "Andy: detect_bundle transportation (204 present)",     _test_08_andy_detect_bundle_transportation),
        ("suite_b_test_09", "Ryan: _find_thesis_rule found / not found / empty",   _test_09_ryan_find_thesis_rule),
        ("suite_b_test_10", "Ryan: run() empty errors returns [] (no S3/LLM)",     _test_10_ryan_run_no_errors),
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
