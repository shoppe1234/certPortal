"""
testing/suites/suite_c.py — Gate Enforcer Tests (INV-03).

Tests certportal.core.gate_enforcer using mocked asyncpg connections.
No live DB required — all DB interactions are AsyncMock objects.

TRD / Architecture coverage:
  INV-03  — Gate ordering enforced in code, not in the UI
  Gate 1  — always activatable (no prerequisites)
  Gate 2  — requires Gate 1 = COMPLETE before it can be activated
  Gate 3  — requires Gate 2 = COMPLETE before it can be activated
"""
from __future__ import annotations

import asyncio
import traceback
from enum import Enum
from typing import Callable
from unittest.mock import AsyncMock, MagicMock


class TestStatus(Enum):
    SKIP = "SKIP"
    PASS = "PASS"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Lazy import guard
# ---------------------------------------------------------------------------

_GE_OK = False
_IMPORT_ERRORS: list[str] = []

try:
    from certportal.core.gate_enforcer import (  # type: ignore[import]
        assert_gate_precondition,
        get_gate_status,
        transition_gate,
        GateOrderViolation,
    )
    _GE_OK = True
except Exception as _e:  # noqa: BLE001
    _IMPORT_ERRORS.append(f"certportal.core.gate_enforcer: {_e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine synchronously inside a test function."""
    return asyncio.run(coro)


def _make_conn(fetchrow_result=None):
    """Build a minimal asyncpg-compatible mock connection.

    fetchrow_result: dict-like returned by fetchrow, or None (simulates no row).
    conn.execute is an AsyncMock so transition_gate's INSERT/UPDATE can be tracked.
    """
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    conn.execute = AsyncMock(return_value=None)
    return conn


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
# Tests 01-06: assert_gate_precondition (pure Python, zero async, zero mocks)
# ---------------------------------------------------------------------------

def _test_01_gate1_always_allowed() -> None:
    """Gate 1 has no prerequisites — assert_gate_precondition never raises for gate=1."""
    assert _GE_OK, f"gate_enforcer import failed: {_IMPORT_ERRORS}"
    # Any gate_status is fine; Gate 1 has no prerequisite
    for status in [
        {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"},
        {"gate_1": "COMPLETE", "gate_2": "COMPLETE", "gate_3": "CERTIFIED"},
        {},  # empty dict — missing keys default to PENDING inside the function
    ]:
        assert_gate_precondition("supplier-X", 1, status)  # must not raise


def _test_02_gate2_allowed_when_gate1_complete() -> None:
    """Gate 2 is allowed when Gate 1 = COMPLETE."""
    assert _GE_OK, f"gate_enforcer import failed: {_IMPORT_ERRORS}"
    gate_status = {"gate_1": "COMPLETE", "gate_2": "PENDING", "gate_3": "PENDING"}
    assert_gate_precondition("supplier-X", 2, gate_status)  # must not raise


def _test_03_gate2_blocked_when_gate1_pending() -> None:
    """Gate 2 is blocked when Gate 1 = PENDING -> GateOrderViolation."""
    assert _GE_OK, f"gate_enforcer import failed: {_IMPORT_ERRORS}"
    gate_status = {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"}
    raised = False
    try:
        assert_gate_precondition("supplier-X", 2, gate_status)
    except GateOrderViolation as e:
        raised = True
        assert "Gate 2" in str(e), f"Error should mention Gate 2: {e}"
        assert "Gate 1" in str(e), f"Error should mention Gate 1: {e}"
    assert raised, "Expected GateOrderViolation when Gate 1 is PENDING"


def _test_04_gate3_allowed_when_gate2_complete() -> None:
    """Gate 3 is allowed when Gate 2 = COMPLETE."""
    assert _GE_OK, f"gate_enforcer import failed: {_IMPORT_ERRORS}"
    gate_status = {"gate_1": "COMPLETE", "gate_2": "COMPLETE", "gate_3": "PENDING"}
    assert_gate_precondition("supplier-X", 3, gate_status)  # must not raise


def _test_05_gate3_blocked_when_gate2_pending() -> None:
    """Gate 3 is blocked when Gate 2 = PENDING -> GateOrderViolation."""
    assert _GE_OK, f"gate_enforcer import failed: {_IMPORT_ERRORS}"
    # Gate 1 is COMPLETE but Gate 2 is still PENDING
    gate_status = {"gate_1": "COMPLETE", "gate_2": "PENDING", "gate_3": "PENDING"}
    raised = False
    try:
        assert_gate_precondition("supplier-X", 3, gate_status)
    except GateOrderViolation as e:
        raised = True
        assert "Gate 3" in str(e), f"Error should mention Gate 3: {e}"
        assert "Gate 2" in str(e), f"Error should mention Gate 2: {e}"
    assert raised, "Expected GateOrderViolation when Gate 2 is PENDING"


def _test_06_invalid_gate_number_raises_valueerror() -> None:
    """Gate numbers outside (1, 2, 3) raise ValueError."""
    assert _GE_OK, f"gate_enforcer import failed: {_IMPORT_ERRORS}"
    for bad_gate in (0, 4, 99, -1):
        raised = False
        try:
            assert_gate_precondition("supplier-X", bad_gate, {})
        except ValueError as e:
            raised = True
            assert str(bad_gate) in str(e), f"Error should mention bad gate {bad_gate}: {e}"
        assert raised, f"Expected ValueError for gate={bad_gate}"


# ---------------------------------------------------------------------------
# Tests 07-08: get_gate_status (async — mocked asyncpg conn)
# ---------------------------------------------------------------------------

def _test_07_get_gate_status_row_found() -> None:
    """get_gate_status returns the DB row values when a row exists."""
    assert _GE_OK, f"gate_enforcer import failed: {_IMPORT_ERRORS}"
    db_row = {"gate_1": "COMPLETE", "gate_2": "COMPLETE", "gate_3": "PENDING"}
    conn = _make_conn(fetchrow_result=db_row)

    result = _run_async(get_gate_status("supplier-X", conn))

    assert result == db_row, f"Expected {db_row}, got {result}"
    conn.fetchrow.assert_called_once()
    # Confirm supplier_id was passed to the query
    call_args = conn.fetchrow.call_args
    assert "supplier-X" in call_args.args or "supplier-X" in str(call_args), \
        "fetchrow should be called with the supplier_id"


def _test_08_get_gate_status_no_row_returns_defaults() -> None:
    """get_gate_status returns all-PENDING defaults when no DB row exists."""
    assert _GE_OK, f"gate_enforcer import failed: {_IMPORT_ERRORS}"
    conn = _make_conn(fetchrow_result=None)  # simulates missing supplier row

    result = _run_async(get_gate_status("new-supplier", conn))

    assert result == {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"}, \
        f"Expected all-PENDING defaults for missing supplier, got: {result}"


# ---------------------------------------------------------------------------
# Tests 09-10: transition_gate (async — mocked asyncpg conn)
# ---------------------------------------------------------------------------

def _test_09_transition_gate1_to_complete() -> None:
    """transition_gate Gate 1 -> COMPLETE: precondition passes, conn.execute called once."""
    assert _GE_OK, f"gate_enforcer import failed: {_IMPORT_ERRORS}"
    # Gate 1 has no prerequisite — any initial state is fine
    current_row = {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"}
    conn = _make_conn(fetchrow_result=current_row)

    # Should not raise
    _run_async(transition_gate("supplier-X", gate=1, new_state="COMPLETE", updated_by="alice", conn=conn))

    # execute must have been called (the UPSERT)
    conn.execute.assert_called_once()
    sql_call = str(conn.execute.call_args)
    assert "gate_1" in sql_call, f"Expected gate_1 in SQL call: {sql_call}"
    assert "COMPLETE" in sql_call, f"Expected COMPLETE in SQL call: {sql_call}"


def _test_10_transition_gate2_blocked_when_gate1_pending() -> None:
    """transition_gate Gate 2 when Gate 1 = PENDING -> GateOrderViolation, no DB write."""
    assert _GE_OK, f"gate_enforcer import failed: {_IMPORT_ERRORS}"
    current_row = {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"}
    conn = _make_conn(fetchrow_result=current_row)

    raised = False
    try:
        _run_async(
            transition_gate("supplier-X", gate=2, new_state="COMPLETE", updated_by="alice", conn=conn)
        )
    except GateOrderViolation:
        raised = True

    assert raised, "Expected GateOrderViolation when Gate 1 is PENDING"
    # Critical: the UPSERT must NOT have been called — gate ordering is enforced
    conn.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Suite entry point
# ---------------------------------------------------------------------------

def run() -> list[dict]:
    """Run all 10 gate enforcer tests. No live DB required."""
    tests = [
        ("suite_c_test_01", "Gate 1: no prerequisites, always allowed",               _test_01_gate1_always_allowed),
        ("suite_c_test_02", "Gate 2: Gate 1=COMPLETE -> allowed",                     _test_02_gate2_allowed_when_gate1_complete),
        ("suite_c_test_03", "Gate 2: Gate 1=PENDING -> GateOrderViolation",           _test_03_gate2_blocked_when_gate1_pending),
        ("suite_c_test_04", "Gate 3: Gate 2=COMPLETE -> allowed",                     _test_04_gate3_allowed_when_gate2_complete),
        ("suite_c_test_05", "Gate 3: Gate 2=PENDING -> GateOrderViolation",           _test_05_gate3_blocked_when_gate2_pending),
        ("suite_c_test_06", "Invalid gate numbers -> ValueError",                      _test_06_invalid_gate_number_raises_valueerror),
        ("suite_c_test_07", "get_gate_status: row found -> returns DB values",        _test_07_get_gate_status_row_found),
        ("suite_c_test_08", "get_gate_status: no row -> all-PENDING defaults",        _test_08_get_gate_status_no_row_returns_defaults),
        ("suite_c_test_09", "transition_gate 1->COMPLETE: execute called once",       _test_09_transition_gate1_to_complete),
        ("suite_c_test_10", "transition_gate 2 blocked: Gate 1 PENDING, no execute",  _test_10_transition_gate2_blocked_when_gate1_pending),
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
