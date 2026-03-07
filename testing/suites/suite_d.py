"""
testing/suites/suite_d.py — Workspace Scope Tests (INV-06 + INV-05).

Tests certportal.core.workspace.S3AgentWorkspace using a mocked boto3 client.
No live S3 or OVH credentials required.

Architecture coverage:
  INV-06 — All S3 paths scoped to {retailer_slug}/{supplier_slug}/
  INV-05 — MONICA-MEMORY.md is append-only, routed to admin/ (never supplier scope)
  Security — path traversal rejection, cross-supplier write prevention
"""
from __future__ import annotations

import traceback
from enum import Enum
from typing import Callable
from unittest.mock import patch, MagicMock


class TestStatus(Enum):
    SKIP = "SKIP"
    PASS = "PASS"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

_WS_OK = False
_IMPORT_ERRORS: list[str] = []

try:
    from certportal.core.workspace import (  # type: ignore[import]
        S3AgentWorkspace,
        WorkspaceScopeViolation,
        FileNotFoundInWorkspace,
    )
    from botocore.exceptions import ClientError  # type: ignore[import]
    _WS_OK = True
except Exception as _e:  # noqa: BLE001
    _IMPORT_ERRORS.append(str(_e))


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_ws(retailer: str = "lowes", supplier: str = "acme") -> "S3AgentWorkspace":
    """Return a workspace with boto3.client replaced by a plain MagicMock.

    Each test that needs specific S3 behaviour then sets ws._client directly.
    """
    with patch("certportal.core.workspace.boto3.client"):
        ws = S3AgentWorkspace(retailer, supplier)
    return ws


def _make_body(content: bytes) -> MagicMock:
    """Return a mock S3 response body whose .read() returns content."""
    body = MagicMock()
    body.read.return_value = content
    return body


def _no_such_key() -> "ClientError":
    return ClientError({"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject")


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
# Tests 01-03: _scoped_key path construction and traversal rejection
# ---------------------------------------------------------------------------

def _test_01_scoped_key_correct_prefix() -> None:
    """_scoped_key prepends retailer/supplier/ to the relative key."""
    assert _WS_OK, f"workspace import failed: {_IMPORT_ERRORS}"
    ws = _make_ws("lowes", "acme-corp")
    key = ws._scoped_key("maps/850.yaml")
    assert key == "lowes/acme-corp/maps/850.yaml", \
        f"Expected 'lowes/acme-corp/maps/850.yaml', got {key!r}"


def _test_02_scoped_key_rejects_dotdot() -> None:
    """_scoped_key raises WorkspaceScopeViolation when '..' appears in key."""
    assert _WS_OK, f"workspace import failed: {_IMPORT_ERRORS}"
    ws = _make_ws()
    raised = False
    try:
        ws._scoped_key("../other-supplier/secret.json")
    except WorkspaceScopeViolation:
        raised = True
    assert raised, "Expected WorkspaceScopeViolation for '..' traversal"


def _test_03_scoped_key_rejects_absolute_path() -> None:
    """_scoped_key raises WorkspaceScopeViolation for absolute paths."""
    assert _WS_OK, f"workspace import failed: {_IMPORT_ERRORS}"
    ws = _make_ws()
    raised = False
    try:
        ws._scoped_key("/etc/passwd")
    except WorkspaceScopeViolation:
        raised = True
    assert raised, "Expected WorkspaceScopeViolation for absolute path '/etc/passwd'"


# ---------------------------------------------------------------------------
# Tests 04-05: upload and download happy paths
# ---------------------------------------------------------------------------

def _test_04_upload_puts_to_correct_key() -> None:
    """upload() calls put_object with the correctly scoped key and returns it."""
    assert _WS_OK, f"workspace import failed: {_IMPORT_ERRORS}"
    ws = _make_ws("lowes", "acme")
    mock_client = MagicMock()
    mock_client.put_object.return_value = {}
    ws._client = mock_client

    returned = ws.upload("maps/850.yaml", b"YAML content")

    expected_key = "lowes/acme/maps/850.yaml"
    assert returned == expected_key, f"Expected {expected_key!r}, got {returned!r}"
    mock_client.put_object.assert_called_once()
    kwargs = mock_client.put_object.call_args.kwargs
    assert kwargs["Key"] == expected_key, f"put_object Key mismatch: {kwargs['Key']!r}"
    assert kwargs["Body"] == b"YAML content"


def _test_05_download_returns_content() -> None:
    """download() calls get_object with the scoped key and returns body bytes."""
    assert _WS_OK, f"workspace import failed: {_IMPORT_ERRORS}"
    ws = _make_ws("lowes", "acme")
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": _make_body(b"EDI data")}
    ws._client = mock_client

    content = ws.download("results/val.json")

    assert content == b"EDI data", f"Expected b'EDI data', got {content!r}"
    kwargs = mock_client.get_object.call_args.kwargs
    assert kwargs["Key"] == "lowes/acme/results/val.json", \
        f"get_object Key mismatch: {kwargs['Key']!r}"


# ---------------------------------------------------------------------------
# Test 06: download missing key raises FileNotFoundInWorkspace
# ---------------------------------------------------------------------------

def _test_06_download_missing_key_raises() -> None:
    """download() raises FileNotFoundInWorkspace when S3 returns NoSuchKey."""
    assert _WS_OK, f"workspace import failed: {_IMPORT_ERRORS}"
    ws = _make_ws()
    mock_client = MagicMock()
    mock_client.get_object.side_effect = _no_such_key()
    ws._client = mock_client

    raised = False
    try:
        ws.download("missing/file.json")
    except FileNotFoundInWorkspace:
        raised = True
    assert raised, "Expected FileNotFoundInWorkspace for missing S3 key"


# ---------------------------------------------------------------------------
# Test 07: download_retailer_map uses retailer-only prefix (no supplier slug)
# ---------------------------------------------------------------------------

def _test_07_retailer_map_excludes_supplier_prefix() -> None:
    """download_retailer_map() reads from retailer/ only — no supplier in the key.

    A supplier-scoped workspace must still be able to read shared retailer files.
    (ADR-010: intentional cross-scope access for shared retailer resources.)
    """
    assert _WS_OK, f"workspace import failed: {_IMPORT_ERRORS}"
    ws = _make_ws("lowes", "acme")   # supplier-scoped workspace
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": _make_body(b"THESIS content")}
    ws._client = mock_client

    content = ws.download_retailer_map("THESIS.md")

    assert content == b"THESIS content"
    key_used = mock_client.get_object.call_args.kwargs["Key"]
    assert key_used == "lowes/THESIS.md", \
        f"Expected 'lowes/THESIS.md' (no supplier slug), got {key_used!r}"
    assert "acme" not in key_used, \
        f"Supplier slug 'acme' must NOT appear in retailer map key: {key_used!r}"


# ---------------------------------------------------------------------------
# Test 08: append_log MONICA-MEMORY.md routes to admin/ (INV-05)
# ---------------------------------------------------------------------------

def _test_08_monica_memory_routes_to_admin() -> None:
    """append_log('MONICA-MEMORY.MD', ...) writes to admin/MONICA-MEMORY.MD, not supplier scope.

    INV-05: MONICA-MEMORY.md is append-only and stored at the global admin/ prefix.
    """
    assert _WS_OK, f"workspace import failed: {_IMPORT_ERRORS}"
    ws = _make_ws("lowes", "acme")
    mock_client = MagicMock()
    # Simulate empty existing file (NoSuchKey on read)
    mock_client.get_object.side_effect = _no_such_key()
    mock_client.put_object.return_value = {}
    ws._client = mock_client

    ws.append_log("MONICA-MEMORY.MD", "Test log entry")

    key_written = mock_client.put_object.call_args.kwargs["Key"]
    assert key_written == "admin/MONICA-MEMORY.MD", \
        f"Expected 'admin/MONICA-MEMORY.MD', got {key_written!r}"
    assert "acme" not in key_written, \
        f"Supplier 'acme' must NOT appear in MONICA-MEMORY.MD path: {key_written!r}"

    body_text = mock_client.put_object.call_args.kwargs["Body"].decode("utf-8")
    assert "Test log entry" in body_text, "Log line must appear in uploaded content"


# ---------------------------------------------------------------------------
# Test 09: write_pam_status cross-supplier raises WorkspaceScopeViolation
# ---------------------------------------------------------------------------

def _test_09_write_pam_status_cross_supplier_blocked() -> None:
    """write_pam_status raises WorkspaceScopeViolation when supplier slugs differ.

    INV-06: A workspace scoped to 'acme' cannot write PAM-STATUS for 'other-supplier'.
    """
    assert _WS_OK, f"workspace import failed: {_IMPORT_ERRORS}"
    ws = _make_ws("lowes", "acme")

    raised = False
    try:
        ws.write_pam_status("other-supplier", {"hitl_flag": True})
    except WorkspaceScopeViolation as e:
        raised = True
        assert "acme" in str(e) or "other-supplier" in str(e), \
            f"Error should mention the scope conflict: {e}"
    assert raised, "Expected WorkspaceScopeViolation for cross-supplier PAM-STATUS write"


# ---------------------------------------------------------------------------
# Test 10: append_log normal key stays in supplier scope and appends content
# ---------------------------------------------------------------------------

def _test_10_append_log_normal_key_scoped_and_appends() -> None:
    """append_log() for a regular key writes to supplier scope and appends (not overwrites)."""
    assert _WS_OK, f"workspace import failed: {_IMPORT_ERRORS}"
    ws = _make_ws("lowes", "acme")
    mock_client = MagicMock()
    # Simulate existing file with prior content
    existing = b"prior line\n"
    mock_client.get_object.return_value = {"Body": _make_body(existing)}
    mock_client.put_object.return_value = {}
    ws._client = mock_client

    ws.append_log("logs/ops.log", "new log entry")

    key_written = mock_client.put_object.call_args.kwargs["Key"]
    assert key_written == "lowes/acme/logs/ops.log", \
        f"Expected supplier-scoped key, got {key_written!r}"

    body_text = mock_client.put_object.call_args.kwargs["Body"].decode("utf-8")
    assert "prior line" in body_text, "Existing content must be preserved (not overwritten)"
    assert "new log entry" in body_text, "New line must be appended"
    assert body_text.index("prior line") < body_text.index("new log entry"), \
        "Prior content must come before the appended line"


# ---------------------------------------------------------------------------
# Suite entry point
# ---------------------------------------------------------------------------

def run() -> list[dict]:
    """Run all 10 workspace scope tests. No live S3 required."""
    tests = [
        ("suite_d_test_01", "INV-06: scoped_key prepends retailer/supplier/ prefix",   _test_01_scoped_key_correct_prefix),
        ("suite_d_test_02", "INV-06: scoped_key rejects '..' traversal",               _test_02_scoped_key_rejects_dotdot),
        ("suite_d_test_03", "INV-06: scoped_key rejects absolute paths",               _test_03_scoped_key_rejects_absolute_path),
        ("suite_d_test_04", "INV-06: upload puts to correctly scoped S3 key",          _test_04_upload_puts_to_correct_key),
        ("suite_d_test_05", "INV-06: download reads from correctly scoped S3 key",     _test_05_download_returns_content),
        ("suite_d_test_06", "INV-06: download missing key raises FileNotFound",        _test_06_download_missing_key_raises),
        ("suite_d_test_07", "ADR-010: retailer_map uses retailer/ prefix only",        _test_07_retailer_map_excludes_supplier_prefix),
        ("suite_d_test_08", "INV-05: MONICA-MEMORY.MD routes to admin/ not supplier",  _test_08_monica_memory_routes_to_admin),
        ("suite_d_test_09", "INV-06: write_pam_status cross-supplier raises Violation",_test_09_write_pam_status_cross_supplier_blocked),
        ("suite_d_test_10", "INV-05: append_log appends without overwriting content",  _test_10_append_log_normal_key_scoped_and_appends),
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
