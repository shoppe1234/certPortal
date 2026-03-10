"""Migrated from testing/suites/suite_c.py — Gate Enforcer Tests (INV-03)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = [pytest.mark.unit]

ge = pytest.importorskip("certportal.core.gate_enforcer")
assert_gate_precondition = ge.assert_gate_precondition
get_gate_status = ge.get_gate_status
transition_gate = ge.transition_gate
GateOrderViolation = ge.GateOrderViolation


def _make_conn(fetchrow_result=None):
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    conn.execute = AsyncMock(return_value=None)
    return conn


class TestGatePrecondition:

    def test_01_gate1_always_allowed(self):
        for status in [
            {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"},
            {"gate_1": "COMPLETE", "gate_2": "COMPLETE", "gate_3": "CERTIFIED"},
            {},
        ]:
            assert_gate_precondition("supplier-X", 1, status)

    def test_02_gate2_allowed_when_gate1_complete(self):
        gate_status = {"gate_1": "COMPLETE", "gate_2": "PENDING", "gate_3": "PENDING"}
        assert_gate_precondition("supplier-X", 2, gate_status)

    def test_03_gate2_blocked_when_gate1_pending(self):
        gate_status = {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"}
        with pytest.raises(GateOrderViolation, match="Gate 2"):
            assert_gate_precondition("supplier-X", 2, gate_status)

    def test_04_gate3_allowed_when_gate2_complete(self):
        gate_status = {"gate_1": "COMPLETE", "gate_2": "COMPLETE", "gate_3": "PENDING"}
        assert_gate_precondition("supplier-X", 3, gate_status)

    def test_05_gate3_blocked_when_gate2_pending(self):
        gate_status = {"gate_1": "COMPLETE", "gate_2": "PENDING", "gate_3": "PENDING"}
        with pytest.raises(GateOrderViolation, match="Gate 3"):
            assert_gate_precondition("supplier-X", 3, gate_status)

    def test_06_invalid_gate_number_raises_valueerror(self):
        for bad_gate in (0, 4, 99, -1):
            with pytest.raises(ValueError, match=str(bad_gate)):
                assert_gate_precondition("supplier-X", bad_gate, {})


class TestGateStatusAsync:

    @pytest.mark.asyncio
    async def test_07_get_gate_status_row_found(self):
        db_row = {"gate_1": "COMPLETE", "gate_2": "COMPLETE", "gate_3": "PENDING"}
        conn = _make_conn(fetchrow_result=db_row)
        result = await get_gate_status("supplier-X", conn)
        assert result == db_row, f"Expected {db_row}, got {result}"
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_08_get_gate_status_no_row_returns_defaults(self):
        conn = _make_conn(fetchrow_result=None)
        result = await get_gate_status("new-supplier", conn)
        assert result == {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"}

    @pytest.mark.asyncio
    async def test_09_transition_gate1_to_complete(self):
        current_row = {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"}
        conn = _make_conn(fetchrow_result=current_row)
        await transition_gate("supplier-X", gate=1, new_state="COMPLETE", updated_by="alice", conn=conn)
        conn.execute.assert_called_once()
        sql_call = str(conn.execute.call_args)
        assert "gate_1" in sql_call
        assert "COMPLETE" in sql_call

    @pytest.mark.asyncio
    async def test_10_transition_gate2_blocked_when_gate1_pending(self):
        current_row = {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"}
        conn = _make_conn(fetchrow_result=current_row)
        with pytest.raises(GateOrderViolation):
            await transition_gate("supplier-X", gate=2, new_state="COMPLETE", updated_by="alice", conn=conn)
        conn.execute.assert_not_called()
