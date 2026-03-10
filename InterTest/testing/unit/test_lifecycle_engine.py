"""Migrated from testing/suites/suite_f.py — Lifecycle Engine Integration Tests.

Requires live Postgres (CERTPORTAL_DB_URL). Tests are ordered — happy path chain
must run sequentially: 850 -> 855 -> 856 -> 810.
"""
import os
import pytest
import psycopg2
import psycopg2.extras

pytestmark = [pytest.mark.unit, pytest.mark.live_db]

PO_HAPPY = "IT-HAPPY-001"
PO_CHANGE = "IT-CHANGE-001"
PO_PREFIX = "IT-"


def _dsn():
    dsn = os.environ.get("CERTPORTAL_DB_URL", "")
    if not dsn:
        pytest.skip("CERTPORTAL_DB_URL not set")
    return dsn


def _cleanup(po_numbers=None):
    conn = psycopg2.connect(_dsn())
    try:
        cur = conn.cursor()
        if po_numbers:
            for po in po_numbers:
                cur.execute("DELETE FROM lifecycle_events WHERE po_number = %s", (po,))
                cur.execute("DELETE FROM lifecycle_violations WHERE po_number = %s", (po,))
                cur.execute("DELETE FROM po_lifecycle WHERE po_number = %s", (po,))
        else:
            cur.execute("DELETE FROM lifecycle_events WHERE po_number LIKE %s", (PO_PREFIX + "%",))
            cur.execute("DELETE FROM lifecycle_violations WHERE po_number LIKE %s", (PO_PREFIX + "%",))
            cur.execute("DELETE FROM po_lifecycle WHERE po_number LIKE %s", (PO_PREFIX + "%",))
        conn.commit()
        cur.close()
    finally:
        conn.close()


def _get_po(po_number):
    conn = psycopg2.connect(_dsn())
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM po_lifecycle WHERE po_number = %s", (po_number,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _get_events(po_number):
    conn = psycopg2.connect(_dsn())
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM lifecycle_events WHERE po_number = %s ORDER BY id", (po_number,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _get_violations(po_number):
    conn = psycopg2.connect(_dsn())
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM lifecycle_violations WHERE po_number = %s ORDER BY id", (po_number,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _lc(transaction_set, direction, po_number, qty=None, extra=None):
    from lifecycle_engine.interface import on_document_processed
    payload = {"header": {"po_number": po_number}}
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


class TestLifecycleEngine:
    """Sequential lifecycle engine tests. Run in order."""

    @classmethod
    def setup_class(cls):
        """Clean IT-* data and reset engine singleton before all tests."""
        try:
            _cleanup()
        except Exception as e:
            pytest.skip(f"DB cleanup failed: {e}")
        os.environ.setdefault("LIFECYCLE_PROFILE", "development")
        try:
            import lifecycle_engine.interface as _iface
            _iface._engine = None
        except ImportError as e:
            pytest.skip(f"lifecycle_engine not importable: {e}")

    def test_01_happy_850(self):
        result = _lc("850", "inbound", PO_HAPPY, qty=200.0)
        assert result["success"] is True, result
        assert result["new_state"] == "po_originated"
        po = _get_po(PO_HAPPY)
        assert po is not None, "po_lifecycle row missing"
        assert po["current_state"] == "po_originated"
        assert float(po["ordered_qty"]) == 200.0
        assert po["is_terminal"] is False

    def test_02_happy_855(self):
        result = _lc("855", "outbound", PO_HAPPY, qty=180.0)
        assert result["success"] is True, result
        assert result["new_state"] == "po_acknowledged"
        po = _get_po(PO_HAPPY)
        assert po["current_state"] == "po_acknowledged"
        assert float(po["accepted_qty"]) == 180.0
        events = _get_events(PO_HAPPY)
        assert len(events) == 2, f"Expected 2 events, got {len(events)}"

    def test_03_happy_856(self):
        result = _lc("856", "outbound", PO_HAPPY, qty=180.0)
        assert result["success"] is True, result
        assert result["new_state"] == "shipped"
        po = _get_po(PO_HAPPY)
        assert float(po["shipped_qty"]) == 180.0

    def test_04_happy_810_terminal(self):
        result = _lc("810", "outbound", PO_HAPPY, qty=175.0)
        assert result["success"] is True, result
        assert result["new_state"] == "invoiced"
        assert result["is_terminal"] is True
        po = _get_po(PO_HAPPY)
        assert po["is_terminal"] is True
        events = _get_events(PO_HAPPY)
        assert len(events) == 4

    def test_05_change_860(self):
        r = _lc("850", "inbound", PO_CHANGE, qty=100.0)
        assert r["success"] is True
        r = _lc("860", "inbound", PO_CHANGE, qty=90.0)
        assert r["success"] is True
        assert r["new_state"] == "po_changed"
        po = _get_po(PO_CHANGE)
        assert float(po["changed_qty"]) == 90.0

    def test_06_change_865_at(self):
        result = _lc("865", "outbound", PO_CHANGE, extra={"ack_type": "AT"})
        assert result["success"] is True
        assert result["new_state"] == "po_change_accepted"
        po = _get_po(PO_CHANGE)
        assert po["current_state"] == "po_change_accepted"

    def test_07_violation_over_invoiced(self):
        po = "IT-VIOL-OI"
        _cleanup([po])
        _lc("850", "inbound", po, qty=50.0)
        _lc("855", "outbound", po, qty=45.0)
        _lc("856", "outbound", po, qty=45.0)
        result = _lc("810", "outbound", po, qty=999.0)
        assert result["success"] is False
        viols = _get_violations(po)
        assert len(viols) >= 1
        assert viols[0]["violation_type"] == "quantity_chain"

    def test_08_violation_invalid_transition(self):
        po = "IT-VIOL-IT"
        _cleanup([po])
        _lc("850", "inbound", po, qty=100.0)
        result = _lc("865", "outbound", po, extra={"ack_type": "AT"})
        assert result["success"] is False
        viols = _get_violations(po)
        assert len(viols) >= 1
        assert viols[0]["violation_type"] == "invalid_transition"

    def test_09_violation_duplicate_terminal(self):
        result = _lc("810", "outbound", PO_HAPPY, qty=10.0)
        assert result["success"] is False
        viols = _get_violations(PO_HAPPY)
        assert len(viols) >= 1
        assert viols[-1]["violation_type"] == "duplicate_terminal"

    def test_10_process_restart_state_survives(self):
        import lifecycle_engine.interface as _iface
        _iface._engine = None
        result = _lc("810", "outbound", PO_HAPPY, qty=5.0)
        assert result["success"] is False
        po = _get_po(PO_HAPPY)
        assert po is not None
        assert po["is_terminal"] is True
        assert po["current_state"] == "invoiced"
