"""Migrated from testing/suites/suite_b.py — Agent Unit Tests (Andy + Ryan)."""
import pytest
from unittest.mock import patch

pytestmark = [pytest.mark.unit]

# Lazy imports via importorskip
andy = pytest.importorskip("agents.andy")
validate_yaml_against_x12 = andy.validate_yaml_against_x12
_detect_bundle = andy._detect_bundle

ryan = pytest.importorskip("agents.ryan")
_find_thesis_rule = ryan._find_thesis_rule
_ryan_run = ryan.run

models = pytest.importorskip("certportal.core.models")
ValidationResult = models.ValidationResult


class TestAndyYamlValidation:
    """Andy: validate_yaml_against_x12 (pure Python, zero mocks)."""

    def test_01_850_all_valid(self):
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

    def test_02_850_missing_segment(self):
        yaml_content = {
            "transaction_type": "850",
            "field_mappings": {
                "GS":  {"GS01": "PO", "GS02": "LOWES", "GS03": "SUPPLIER"},
                "BEG": {"BEG01": "00", "BEG02": "SA",  "BEG05": "20240101"},
            },
        }
        warnings = validate_yaml_against_x12(yaml_content, "850")
        assert any("ISA" in w for w in warnings), f"Expected ISA warning, got: {warnings}"

    def test_03_850_missing_element(self):
        yaml_content = {
            "transaction_type": "850",
            "field_mappings": {
                "ISA": {"ISA06": "LOWES", "ISA08": "SUPPLIER"},
                "GS":  {"GS01": "PO", "GS02": "LOWES", "GS03": "SUPPLIER"},
                "BEG": {"BEG01": "00", "BEG02": "SA",  "BEG05": "20240101"},
            },
        }
        warnings = validate_yaml_against_x12(yaml_content, "850")
        assert any("ISA01" in w for w in warnings), f"Expected ISA01 warning, got: {warnings}"
        assert len(warnings) == 1, f"Expected exactly 1 warning, got {len(warnings)}: {warnings}"

    def test_04_unknown_tx_type(self):
        warnings = validate_yaml_against_x12({"transaction_type": "999", "field_mappings": {}}, "999")
        assert len(warnings) == 1, f"Expected 1 warning, got: {warnings}"
        assert "999" in warnings[0], f"Warning should mention tx type '999': {warnings[0]}"

    def test_05_850_empty_field_mappings(self):
        yaml_content = {"transaction_type": "850", "field_mappings": {}}
        warnings = validate_yaml_against_x12(yaml_content, "850")
        assert len(warnings) >= 3, f"Expected >=3 warnings for empty mappings, got: {warnings}"
        segments_warned = " ".join(warnings)
        for seg in ("ISA", "GS", "BEG"):
            assert seg in segments_warned, f"Expected warning for segment '{seg}': {warnings}"

    def test_06_855_all_valid(self):
        yaml_content = {
            "transaction_type": "855",
            "field_mappings": {
                "ISA": {"ISA01": "00", "ISA06": "LOWES", "ISA08": "SUPPLIER"},
                "BAK": {"BAK01": "00", "BAK02": "AD",   "BAK04": "20240101"},
            },
        }
        warnings = validate_yaml_against_x12(yaml_content, "855")
        assert warnings == [], f"Expected no warnings for valid 855, got: {warnings}"


class TestAndyBundleDetection:
    """Andy: _detect_bundle (pure Python, zero mocks)."""

    def test_07_detect_bundle_general(self):
        pdf_text = "This trading partner guide covers PO 850, 855, 856, and 810 transactions."
        bundle = _detect_bundle(pdf_text)
        assert bundle == "general_merchandise", f"Expected general_merchandise, got: {bundle!r}"

    def test_08_detect_bundle_transportation(self):
        pdf_text = "This guide covers Motor Carrier Shipment Information (204) and Carrier Response (990)."
        bundle = _detect_bundle(pdf_text)
        assert bundle == "transportation", f"Expected transportation, got: {bundle!r}"


class TestRyan:
    """Ryan: _find_thesis_rule + run() fast path."""

    def test_09_find_thesis_rule(self):
        thesis = """# THESIS -- Lowe's Trading Partner Rules

## Segment Rules
The BEG segment begins the purchase order and is mandatory on all 850 transactions.
Position 03 of the BEG segment must carry the PO number issued by Lowe's procurement.
The ISA segment carries interchange control data for all transmissions.
ISA qualifier in position 06 must be set to '9254016003' for Lowe's suppliers.

## Known Retailer-Specific Rules
N1 qualifier '93' required on all inbound 850 transactions.
"""
        rule = _find_thesis_rule(thesis, "BEG")
        assert rule is not None, "Expected a rule for 'BEG' segment"
        assert "BEG" in rule, f"Rule should reference BEG: {rule!r}"

        no_rule = _find_thesis_rule(thesis, "ZZZ")
        assert no_rule is None, f"Expected None for absent segment 'ZZZ', got: {no_rule!r}"

        assert _find_thesis_rule("", "BEG") is None, "Empty thesis must return None"

    def test_10_run_no_errors(self):
        vr = ValidationResult(
            supplier_slug="test-supplier",
            retailer_slug="lowes",
            transaction_type="850",
            channel="inbound",
            status="PASS",
            errors=[],
        )
        with patch("agents.ryan.monica_logger") as _mock_log:
            result = _ryan_run("lowes", "test-supplier", vr)
        assert result == [], f"Expected empty patch list, got: {result}"
        assert _mock_log.log.called, "monica_logger.log should have been called"
