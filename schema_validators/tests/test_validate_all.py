"""
Tests for schema_validators — Layer 0 pykwalify YAML validation.

Covers:
  - All existing edi_framework/ files pass their schemas
  - New 865_po_change_ack.yaml passes transaction schema
  - Invalid files (bad direction, missing required key, bad rule type) fail
  - Library-mode validate_file() works with explicit and auto-detected schema_type
  - validate_framework() returns correct pass/fail summary
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pykwalify.errors import SchemaError

from schema_validators.validate_all import validate_file, validate_framework
from schema_validators.validate_transaction import validate_transaction
from schema_validators.validate_mapping import validate_mapping
from schema_validators.validate_lifecycle import validate_lifecycle

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent.parent
FRAMEWORK = REPO_ROOT / "edi_framework"
META_DIR = FRAMEWORK / "meta"

# ---------------------------------------------------------------------------
# Parametrized: all existing transaction files must pass
# ---------------------------------------------------------------------------
TRANSACTION_FILES = sorted((FRAMEWORK / "transactions").glob("*.yaml"))


@pytest.mark.parametrize("yaml_file", TRANSACTION_FILES, ids=lambda p: p.name)
def test_transaction_files_pass(yaml_file: Path) -> None:
    """Every file in edi_framework/transactions/ must pass transaction_schema.yaml."""
    validate_transaction(yaml_file, meta_dir=META_DIR)


# ---------------------------------------------------------------------------
# Parametrized: all existing mapping files must pass
# ---------------------------------------------------------------------------
MAPPING_FILES = sorted((FRAMEWORK / "mappings").glob("*.yaml"))


@pytest.mark.parametrize("yaml_file", MAPPING_FILES, ids=lambda p: p.name)
def test_mapping_files_pass(yaml_file: Path) -> None:
    """Every file in edi_framework/mappings/ must pass mapping_schema.yaml."""
    validate_mapping(yaml_file, meta_dir=META_DIR)


# ---------------------------------------------------------------------------
# Lifecycle file
# ---------------------------------------------------------------------------

def test_lifecycle_file_passes() -> None:
    """edi_framework/lifecycle/order_to_cash.yaml must pass lifecycle_schema.yaml."""
    lifecycle_file = FRAMEWORK / "lifecycle" / "order_to_cash.yaml"
    assert lifecycle_file.exists(), f"Missing: {lifecycle_file}"
    validate_lifecycle(lifecycle_file, meta_dir=META_DIR)


# ---------------------------------------------------------------------------
# Specific check: 865 file (newly created) passes
# ---------------------------------------------------------------------------

def test_865_transaction_passes() -> None:
    """865_po_change_ack.yaml specifically must exist and pass transaction schema."""
    file_865 = FRAMEWORK / "transactions" / "865_po_change_ack.yaml"
    assert file_865.exists(), "865_po_change_ack.yaml was not created"
    validate_transaction(file_865, meta_dir=META_DIR)


# ---------------------------------------------------------------------------
# Negative tests: bad files must fail
# ---------------------------------------------------------------------------

def test_transaction_bad_direction_fails(tmp_path: Path) -> None:
    """A transaction with direction='sideways' must raise SchemaError."""
    bad = tmp_path / "transactions" / "bad_tx.yaml"
    bad.parent.mkdir()
    bad.write_text(
        textwrap.dedent("""\
            transaction:
              id: "999"
              name: "Bad Transaction"
              functional_group: "XX"
              direction: sideways
              version: "004010"
              shared_refs:
                envelope: shared/envelope.yaml
              heading:
                SEG:
                  name: "Some Segment"
                  position: 10
                  usage: mandatory
        """)
    )
    with pytest.raises(SchemaError):
        validate_transaction(bad, meta_dir=META_DIR)


def test_transaction_missing_heading_fails(tmp_path: Path) -> None:
    """A transaction without 'heading' must raise SchemaError."""
    bad = tmp_path / "transactions" / "no_heading.yaml"
    bad.parent.mkdir()
    bad.write_text(
        textwrap.dedent("""\
            transaction:
              id: "850"
              name: "No Heading"
              functional_group: "PO"
              direction: inbound
              version: "004010"
              shared_refs:
                envelope: shared/envelope.yaml
        """)
    )
    with pytest.raises(SchemaError):
        validate_transaction(bad, meta_dir=META_DIR)


def test_mapping_bad_rule_type_fails(tmp_path: Path) -> None:
    """A mapping with an unknown rule type must raise SchemaError."""
    bad = tmp_path / "mappings" / "bad_map.yaml"
    bad.parent.mkdir()
    bad.write_text(
        textwrap.dedent("""\
            mapping:
              source: "850"
              target: "855"
              description: "Bad mapping"
            rules:
              - id: po_number
                name: "PO Number"
                rule: magic_copy
        """)
    )
    with pytest.raises(SchemaError):
        validate_mapping(bad, meta_dir=META_DIR)


def test_lifecycle_missing_states_fails(tmp_path: Path) -> None:
    """A lifecycle file without 'states' must raise SchemaError."""
    bad = tmp_path / "lifecycle" / "bad_lc.yaml"
    bad.parent.mkdir()
    bad.write_text(
        textwrap.dedent("""\
            lifecycle:
              name: "Bad Lifecycle"
              version: "1.0"
              primary_key:
                name: "purchase_order_number"
        """)
    )
    with pytest.raises(SchemaError):
        validate_lifecycle(bad, meta_dir=META_DIR)


# ---------------------------------------------------------------------------
# validate_file() library-mode
# ---------------------------------------------------------------------------

def test_validate_file_explicit_schema_type() -> None:
    """validate_file() works with explicit schema_type='transaction'."""
    file = FRAMEWORK / "transactions" / "850_stock_po.yaml"
    validate_file(file, schema_type="transaction", meta_dir=META_DIR)


def test_validate_file_auto_detect_transaction() -> None:
    """validate_file() auto-detects schema_type from parent directory name."""
    file = FRAMEWORK / "transactions" / "850_stock_po.yaml"
    validate_file(file, meta_dir=META_DIR)  # schema_type not specified


def test_validate_file_auto_detect_mapping() -> None:
    """validate_file() auto-detects 'mapping' schema type."""
    file = FRAMEWORK / "mappings" / "860_to_865_turnaround.yaml"
    validate_file(file, meta_dir=META_DIR)


def test_validate_file_auto_detect_lifecycle() -> None:
    """validate_file() auto-detects 'lifecycle' schema type."""
    file = FRAMEWORK / "lifecycle" / "order_to_cash.yaml"
    validate_file(file, meta_dir=META_DIR)


def test_validate_file_unknown_schema_type_raises() -> None:
    """validate_file() raises ValueError for unknown schema_type."""
    file = FRAMEWORK / "transactions" / "850_stock_po.yaml"
    with pytest.raises(ValueError, match="Unknown schema_type"):
        validate_file(file, schema_type="unknown_type", meta_dir=META_DIR)


def test_validate_file_cannot_auto_detect_raises(tmp_path: Path) -> None:
    """validate_file() raises ValueError when parent dir is not a known subdirectory."""
    mystery_file = tmp_path / "850_mystery.yaml"
    mystery_file.write_text("transaction:\n  id: '850'\n")
    with pytest.raises(ValueError, match="Cannot auto-detect"):
        validate_file(mystery_file, meta_dir=META_DIR)


# ---------------------------------------------------------------------------
# validate_framework() report
# ---------------------------------------------------------------------------

def test_validate_framework_all_pass() -> None:
    """validate_framework() on clean edi_framework/ returns all_passed=True."""
    report = validate_framework(FRAMEWORK, meta_dir=META_DIR)
    failures = [r for r in report.results if not r.passed]
    assert report.all_passed, (
        f"Expected all files to pass. Failures:\n"
        + "\n".join(f"  {r.path}: {r.error}" for r in failures)
    )
    # Should have validated transactions + mappings + lifecycle
    assert report.passed_count >= 13  # 6 tx + 6 mappings + 1 lifecycle (min)


def test_validate_framework_counts_failures(tmp_path: Path) -> None:
    """validate_framework() correctly counts failures in a broken framework dir."""
    # Create a minimal framework with one bad file
    (tmp_path / "transactions").mkdir()
    (tmp_path / "mappings").mkdir()
    (tmp_path / "lifecycle").mkdir()

    # One valid transaction
    (tmp_path / "transactions" / "good.yaml").write_text(
        textwrap.dedent("""\
            transaction:
              id: "850"
              name: "Good"
              functional_group: "PO"
              direction: inbound
              version: "004010"
              shared_refs:
                envelope: shared/envelope.yaml
              heading:
                BEG:
                  name: "BEG"
                  position: 10
                  usage: mandatory
        """)
    )
    # One bad transaction (direction invalid)
    (tmp_path / "transactions" / "bad.yaml").write_text(
        textwrap.dedent("""\
            transaction:
              id: "999"
              name: "Bad"
              functional_group: "XX"
              direction: diagonal
              version: "004010"
              shared_refs:
                envelope: shared/envelope.yaml
              heading:
                SEG:
                  name: "SEG"
                  position: 10
                  usage: mandatory
        """)
    )

    report = validate_framework(tmp_path, meta_dir=META_DIR)
    assert report.passed_count == 1
    assert report.failed_count == 1
    assert not report.all_passed
