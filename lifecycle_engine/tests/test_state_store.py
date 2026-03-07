"""
Tests for lifecycle_engine/state_store.py using psycopg2 mocks.

All DB calls are intercepted at psycopg2.connect so no real Postgres needed.
Tests verify: SQL execution, transaction discipline (commit/rollback),
upsert INSERT vs UPDATE branching, and LifecycleError wrapping.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import psycopg2
import pytest

from lifecycle_engine.exceptions import LifecycleError
from lifecycle_engine.state_store import StateStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_cursor(rows=None, fetchone_val=None):
    """
    Return a mock cursor suited for read methods (used as context manager).
    """
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_val
    cur.fetchall.return_value = rows or []
    return cur


def _read_conn(cursor):
    """Return a mock connection whose cursor() context manager yields cursor."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


def _write_cursor(fetchone_val=None):
    """
    Return a mock cursor for write methods (NOT used as context manager,
    e.g. cur = conn.cursor() then cur.execute()).
    """
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_val
    return cur


def _write_conn(cursor):
    """Return a mock connection whose cursor() returns the cursor directly."""
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


# ---------------------------------------------------------------------------
# Read methods
# ---------------------------------------------------------------------------

class TestGetPo:
    def test_returns_none_when_no_row(self):
        cur = _read_cursor(fetchone_val=None)
        conn = _read_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            result = store.get_po("P001")
        assert result is None
        conn.close.assert_called_once()

    def test_returns_dict_when_row_found(self):
        row = {"po_number": "P001", "current_state": "po_originated", "is_terminal": False}
        cur = _read_cursor(fetchone_val=row)
        conn = _read_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            result = store.get_po("P001")
        assert result == row


class TestGetEvents:
    def test_returns_list_of_dicts(self):
        rows = [
            {"event_type": "po_originated", "transaction_set": "850"},
            {"event_type": "po_acknowledged", "transaction_set": "855"},
        ]
        cur = _read_cursor(rows=rows)
        conn = _read_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            result = store.get_events("P001")
        assert result == rows

    def test_returns_empty_list_when_no_events(self):
        cur = _read_cursor(rows=[])
        conn = _read_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            result = store.get_events("P001")
        assert result == []


class TestGetViolations:
    def test_returns_violations(self):
        rows = [{"violation_type": "missing_po", "po_number": None}]
        cur = _read_cursor(rows=rows)
        conn = _read_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            result = store.get_violations("P001")
        assert len(result) == 1
        assert result[0]["violation_type"] == "missing_po"


class TestGetPosInState:
    def test_returns_rows_for_state(self):
        rows = [{"po_number": "P001"}, {"po_number": "P002"}]
        cur = _read_cursor(rows=rows)
        conn = _read_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            result = store.get_pos_in_state("po_originated", "lowes")
        assert len(result) == 2


class TestGetStalePOs:
    def test_returns_stale_rows(self):
        rows = [{"po_number": "P099", "current_state": "po_originated"}]
        cur = _read_cursor(rows=rows)
        conn = _read_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            result = store.get_stale_pos(older_than_hours=72)
        assert result == rows


# ---------------------------------------------------------------------------
# Write methods
# ---------------------------------------------------------------------------

class TestTransitionAndRecord:
    _event = {
        "event_type": "po_originated",
        "transaction_set": "850",
        "direction": "inbound",
        "source_file": "test.edi",
        "correlation_id": "corr-001",
        "qty_at_event": 100.0,
        "payload_snapshot": {"header": {"po_number": "P001"}},
    }

    def test_insert_branch_when_po_does_not_exist(self):
        """When SELECT returns None → INSERT into po_lifecycle."""
        cur = _write_cursor(fetchone_val=None)
        conn = _write_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            store.transition_and_record(
                po_number="P001",
                partner_id="lowes",
                prior_state=None,
                new_state="po_originated",
                is_terminal=False,
                qty_fields={"ordered_qty": 100.0},
                event=self._event,
            )
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()
        cur.close.assert_called_once()

    def test_update_branch_when_po_exists(self):
        """When SELECT returns a row → UPDATE po_lifecycle."""
        cur = _write_cursor(fetchone_val=(1,))
        conn = _write_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            store.transition_and_record(
                po_number="P001",
                partner_id="lowes",
                prior_state="po_originated",
                new_state="po_acknowledged",
                is_terminal=False,
                qty_fields={"accepted_qty": 80.0},
                event=self._event,
            )
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()

    def test_psycopg2_error_triggers_rollback_and_raises(self):
        """psycopg2.Error must be wrapped in LifecycleError and rolled back."""
        cur = _write_cursor()
        cur.execute.side_effect = psycopg2.OperationalError("connection refused")
        conn = _write_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            with pytest.raises(LifecycleError, match="Postgres error"):
                store.transition_and_record(
                    po_number="P001",
                    partner_id="lowes",
                    prior_state=None,
                    new_state="po_originated",
                    is_terminal=False,
                    qty_fields={},
                    event=self._event,
                )
        conn.rollback.assert_called_once()

    def test_payload_snapshot_serialised_to_json(self):
        """Dict payload_snapshot is converted to JSON string before INSERT."""
        cur = _write_cursor(fetchone_val=None)
        conn = _write_conn(cur)
        event_with_dict_snapshot = {**self._event, "payload_snapshot": {"key": "value"}}
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            store.transition_and_record(
                po_number="P001", partner_id="lowes",
                prior_state=None, new_state="po_originated",
                is_terminal=False, qty_fields={},
                event=event_with_dict_snapshot,
            )
        # Check that one of the execute calls received a JSON string
        all_calls = cur.execute.call_args_list
        payloads = [str(c) for c in all_calls]
        assert any('{"key": "value"}' in p for p in payloads)


class TestRecordViolation:
    _violation = {
        "po_number": "P001",
        "partner_id": "lowes",
        "transaction_set": "850",
        "source_file": "test.edi",
        "correlation_id": "corr-001",
        "violation_type": "missing_po",
        "violation_detail": "PO not found",
        "current_state": None,
        "attempted_event": "po_originated",
    }

    def test_commits_on_success(self):
        cur = _write_cursor()
        conn = _write_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            store.record_violation(self._violation)
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()

    def test_rollback_and_raise_on_psycopg2_error(self):
        cur = _write_cursor()
        cur.execute.side_effect = psycopg2.OperationalError("DB down")
        conn = _write_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            with pytest.raises(LifecycleError, match="Postgres error"):
                store.record_violation(self._violation)
        conn.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# Shim methods
# ---------------------------------------------------------------------------

class TestUpsertPo:
    def test_insert_when_not_exists(self):
        cur = _write_cursor(fetchone_val=None)
        conn = _write_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            store.upsert_po(
                po_number="P001",
                partner_id="lowes",
                new_state="po_originated",
                is_terminal=False,
                qty_fields={"ordered_qty": 100.0},
            )
        conn.commit.assert_called_once()

    def test_update_when_exists(self):
        cur = _write_cursor(fetchone_val=(1,))
        conn = _write_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            store.upsert_po(
                po_number="P001",
                partner_id="lowes",
                new_state="po_acknowledged",
                is_terminal=False,
                qty_fields={},
            )
        conn.commit.assert_called_once()

    def test_rollback_on_psycopg2_error(self):
        cur = _write_cursor()
        cur.execute.side_effect = psycopg2.OperationalError("timeout")
        conn = _write_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            with pytest.raises(LifecycleError, match="upsert_po error"):
                store.upsert_po("P001", "lowes", "po_originated", False, {})
        conn.rollback.assert_called_once()


class TestAppendEvent:
    _event = {
        "po_number": "P001",
        "partner_id": "lowes",
        "event_type": "po_originated",
        "transaction_set": "850",
        "direction": "inbound",
        "source_file": "test.edi",
        "correlation_id": "corr-001",
        "new_state": "po_originated",
        "payload_snapshot": None,
    }

    def test_commits_on_success(self):
        cur = _write_cursor()
        conn = _write_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            store.append_event(self._event)
        conn.commit.assert_called_once()

    def test_rollback_on_psycopg2_error(self):
        cur = _write_cursor()
        cur.execute.side_effect = psycopg2.OperationalError("DB error")
        conn = _write_conn(cur)
        with patch("psycopg2.connect", return_value=conn):
            store = StateStore("mock_dsn")
            with pytest.raises(LifecycleError, match="append_event error"):
                store.append_event(self._event)
        conn.rollback.assert_called_once()
