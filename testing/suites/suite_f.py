"""
testing/suites/suite_f.py — End-to-End Lifecycle Engine Integration Tests.

Runs against live Postgres (CERTPORTAL_DB_URL).
Each test uses prefixed PO numbers (IT-*) that are cleaned up at suite start
so the suite is idempotent across re-runs.

TRD coverage:
  Step 16 — Happy path:  850 → 855 → 856 → 810
  Step 17 — Change path: 850 → 860 → 865 AT
  Step 18 — Violations:  over-invoiced, invalid transition, duplicate terminal
  Step 18d— Restart:     engine singleton reset, state survives in Postgres
"""
from __future__ import annotations

import os
import traceback
from enum import Enum
from typing import Callable

import psycopg2
import psycopg2.extras


class TestStatus(Enum):
    SKIP = "SKIP"
    PASS = "PASS"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Fixed PO numbers — cleaned at suite start for idempotency
# ---------------------------------------------------------------------------
PO_HAPPY  = "IT-HAPPY-001"   # 850 → 855 → 856 → 810
PO_CHANGE = "IT-CHANGE-001"  # 850 → 860 → 865
PO_PREFIX = "IT-"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _dsn() -> str:
    dsn = os.environ.get("CERTPORTAL_DB_URL", "")
    if not dsn:
        raise RuntimeError("CERTPORTAL_DB_URL not set — cannot run SuiteF")
    return dsn


def _cleanup(po_numbers: list[str] | None = None) -> None:
    """Delete test POs. If po_numbers is None, deletes all IT-* rows."""
    conn = psycopg2.connect(_dsn())
    try:
        cur = conn.cursor()
        if po_numbers:
            for po in po_numbers:
                cur.execute("DELETE FROM lifecycle_events     WHERE po_number = %s", (po,))
                cur.execute("DELETE FROM lifecycle_violations WHERE po_number = %s", (po,))
                cur.execute("DELETE FROM po_lifecycle         WHERE po_number = %s", (po,))
        else:
            cur.execute("DELETE FROM lifecycle_events     WHERE po_number LIKE %s", (PO_PREFIX + "%",))
            cur.execute("DELETE FROM lifecycle_violations WHERE po_number LIKE %s", (PO_PREFIX + "%",))
            cur.execute("DELETE FROM po_lifecycle         WHERE po_number LIKE %s", (PO_PREFIX + "%",))
        conn.commit()
        cur.close()
    finally:
        conn.close()


def _get_po(po_number: str) -> dict | None:
    conn = psycopg2.connect(_dsn())
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM po_lifecycle WHERE po_number = %s", (po_number,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _get_events(po_number: str) -> list[dict]:
    conn = psycopg2.connect(_dsn())
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM lifecycle_events WHERE po_number = %s ORDER BY id",
            (po_number,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _get_violations(po_number: str) -> list[dict]:
    conn = psycopg2.connect(_dsn())
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM lifecycle_violations WHERE po_number = %s ORDER BY id",
            (po_number,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Lifecycle engine call helper
# ---------------------------------------------------------------------------

def _lc(
    transaction_set: str,
    direction: str,
    po_number: str,
    qty: float | None = None,
    extra: dict | None = None,
) -> dict:
    """Call on_document_processed() with a minimal well-formed payload."""
    from lifecycle_engine.interface import on_document_processed
    payload: dict = {"header": {"po_number": po_number}}
    if qty is not None:
        payload["header"]["quantity"] = qty
    if extra:
        payload["header"].update(extra)
    return on_document_processed(
        transaction_set=transaction_set,
        direction=direction,
        payload=payload,
        source_file=f"suite_f_{transaction_set}.edi",
        correlation_id=f"suite-f-{transaction_set}-{po_number}",
        partner_id="lowes",
    )


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
# Tests — TRD Step 16: Happy path 850 → 855 → 856 → 810
# ---------------------------------------------------------------------------

def _test_01_happy_850() -> None:
    """850 inbound → po_originated. Row created with ordered_qty=200."""
    result = _lc("850", "inbound", PO_HAPPY, qty=200.0)
    assert result["success"] is True, result
    assert result["new_state"] == "po_originated"
    assert result["prior_state"] is None

    po = _get_po(PO_HAPPY)
    assert po is not None, "po_lifecycle row missing"
    assert po["current_state"] == "po_originated"
    assert float(po["ordered_qty"]) == 200.0
    assert po["is_terminal"] is False


def _test_02_happy_855() -> None:
    """855 outbound → po_acknowledged. Audit trail has 2 events."""
    result = _lc("855", "outbound", PO_HAPPY, qty=180.0)
    assert result["success"] is True, result
    assert result["new_state"] == "po_acknowledged"
    assert result["prior_state"] == "po_originated"

    po = _get_po(PO_HAPPY)
    assert po["current_state"] == "po_acknowledged"
    assert float(po["accepted_qty"]) == 180.0

    events = _get_events(PO_HAPPY)
    assert len(events) == 2, f"Expected 2 events, got {len(events)}"
    assert events[0]["prior_state"] is None           # first event: NULL
    assert events[1]["prior_state"] == "po_originated"


def _test_03_happy_856() -> None:
    """856 outbound → shipped."""
    result = _lc("856", "outbound", PO_HAPPY, qty=180.0)
    assert result["success"] is True, result
    assert result["new_state"] == "shipped"

    po = _get_po(PO_HAPPY)
    assert po["current_state"] == "shipped"
    assert float(po["shipped_qty"]) == 180.0


def _test_04_happy_810_terminal() -> None:
    """810 outbound → invoiced (terminal). is_terminal=True in Postgres."""
    result = _lc("810", "outbound", PO_HAPPY, qty=175.0)
    assert result["success"] is True, result
    assert result["new_state"] == "invoiced"
    assert result["is_terminal"] is True

    po = _get_po(PO_HAPPY)
    assert po["current_state"] == "invoiced"
    assert po["is_terminal"] is True
    assert float(po["invoiced_qty"]) == 175.0

    events = _get_events(PO_HAPPY)
    assert len(events) == 4, f"Expected 4 events, got {len(events)}"


# ---------------------------------------------------------------------------
# Tests — TRD Step 17: Change path 850 → 860 → 865
# ---------------------------------------------------------------------------

def _test_05_change_860() -> None:
    """850 + 860 inbound → po_changed with changed_qty."""
    r = _lc("850", "inbound", PO_CHANGE, qty=100.0)
    assert r["success"] is True, r
    assert r["new_state"] == "po_originated"

    r = _lc("860", "inbound", PO_CHANGE, qty=90.0)
    assert r["success"] is True, r
    assert r["new_state"] == "po_changed"
    assert r["prior_state"] == "po_originated"

    po = _get_po(PO_CHANGE)
    assert po["current_state"] == "po_changed"
    assert float(po["changed_qty"]) == 90.0


def _test_06_change_865_at() -> None:
    """865 AT outbound → po_change_accepted."""
    result = _lc("865", "outbound", PO_CHANGE, extra={"ack_type": "AT"})
    assert result["success"] is True, result
    assert result["new_state"] == "po_change_accepted"
    assert result["prior_state"] == "po_changed"

    po = _get_po(PO_CHANGE)
    assert po["current_state"] == "po_change_accepted"


# ---------------------------------------------------------------------------
# Tests — TRD Step 18: Violations
# ---------------------------------------------------------------------------

def _test_07_violation_over_invoiced() -> None:
    """810 qty > 850 ordered_qty → quantity_chain violation in Postgres."""
    po = "IT-VIOL-OI"
    _cleanup([po])
    _lc("850", "inbound",  po, qty=50.0)
    _lc("855", "outbound", po, qty=45.0)
    _lc("856", "outbound", po, qty=45.0)

    result = _lc("810", "outbound", po, qty=999.0)   # way over ordered_qty=50
    assert result["success"] is False, f"Expected failure, got: {result}"
    assert any("qty" in v.lower() or "quantity" in v.lower() for v in result["violations"]), \
        result["violations"]

    viols = _get_violations(po)
    assert len(viols) >= 1, "Expected violation row in lifecycle_violations"
    assert viols[0]["violation_type"] == "quantity_chain"


def _test_08_violation_invalid_transition() -> None:
    """865 AT arrives right after 850 (no 860 change exists) -> invalid_transition.

    po_originated valid transitions are: po_acknowledged, po_changed, shipped, invoiced.
    po_change_accepted is NOT in that list, so 865 AT from po_originated must fail.
    """
    po = "IT-VIOL-IT"
    _cleanup([po])
    _lc("850", "inbound", po, qty=100.0)   # -> po_originated

    # 865 AT maps to po_change_accepted, which is not reachable from po_originated
    result = _lc("865", "outbound", po, extra={"ack_type": "AT"})
    assert result["success"] is False, f"Expected failure, got: {result}"

    viols = _get_violations(po)
    assert len(viols) >= 1, "Expected violation row"
    assert viols[0]["violation_type"] == "invalid_transition", viols[0]


def _test_09_violation_duplicate_terminal() -> None:
    """Second 810 on an already-invoiced (terminal) PO → duplicate_terminal."""
    # PO_HAPPY is terminal from test_04
    result = _lc("810", "outbound", PO_HAPPY, qty=10.0)
    assert result["success"] is False, f"Expected failure on terminal PO: {result}"

    viols = _get_violations(PO_HAPPY)
    assert len(viols) >= 1, "Expected violation row"
    assert viols[-1]["violation_type"] == "duplicate_terminal", viols[-1]


# ---------------------------------------------------------------------------
# Test — TRD Step 18d: Process restart
# ---------------------------------------------------------------------------

def _test_10_process_restart_state_survives() -> None:
    """
    Reset the engine singleton (simulates process restart), then verify the
    existing PO state is read back correctly from Postgres — not from memory.
    """
    import lifecycle_engine.interface as _iface

    # Tear down singleton
    _iface._engine = None

    # PO_HAPPY is invoiced+terminal — after restart it must still reject new docs
    result = _lc("810", "outbound", PO_HAPPY, qty=5.0)
    assert result["success"] is False, "Terminal PO must be rejected after engine restart"

    po = _get_po(PO_HAPPY)
    assert po is not None
    assert po["is_terminal"] is True
    assert po["current_state"] == "invoiced"


# ---------------------------------------------------------------------------
# Suite entry point
# ---------------------------------------------------------------------------

def run() -> list[dict]:
    """Run all 10 lifecycle integration tests. Cleans IT-* data first."""
    try:
        dsn = _dsn()
    except RuntimeError as e:
        return [
            {"test": f"suite_f_test_{i:02d}", "status": TestStatus.SKIP, "reason": str(e)}
            for i in range(1, 11)
        ]

    try:
        _cleanup()
    except Exception as e:
        return [
            {"test": f"suite_f_test_{i:02d}", "status": TestStatus.FAIL,
             "reason": f"DB cleanup failed: {e}"}
            for i in range(1, 11)
        ]

    os.environ["CERTPORTAL_DB_URL"] = dsn
    os.environ.setdefault("LIFECYCLE_PROFILE", "development")

    try:
        import lifecycle_engine.interface as _iface
        _iface._engine = None   # fresh singleton for this suite run
    except ImportError as e:
        return [
            {"test": f"suite_f_test_{i:02d}", "status": TestStatus.SKIP,
             "reason": f"lifecycle_engine not importable: {e}"}
            for i in range(1, 11)
        ]

    tests = [
        ("suite_f_test_01", "850 -> po_originated",              _test_01_happy_850),
        ("suite_f_test_02", "855 -> po_acknowledged",            _test_02_happy_855),
        ("suite_f_test_03", "856 -> shipped",                    _test_03_happy_856),
        ("suite_f_test_04", "810 -> invoiced (terminal)",        _test_04_happy_810_terminal),
        ("suite_f_test_05", "860 -> po_changed",                 _test_05_change_860),
        ("suite_f_test_06", "865 AT -> po_change_accepted",      _test_06_change_865_at),
        ("suite_f_test_07", "Violation: over-invoiced",         _test_07_violation_over_invoiced),
        ("suite_f_test_08", "Violation: invalid transition",    _test_08_violation_invalid_transition),
        ("suite_f_test_09", "Violation: duplicate terminal",    _test_09_violation_duplicate_terminal),
        ("suite_f_test_10", "Restart: state survives restart",  _test_10_process_restart_state_survives),
    ]

    results = []
    for test_id, description, fn in tests:
        r = _run_test(test_id, fn)
        r["description"] = description
        results.append(r)
        status_str = r["status"].value
        reason_str = f" — {r['reason'][:120]}" if r["reason"] else ""
        print(f"  [{status_str:4s}] {test_id}: {description}{reason_str}")

    return results
