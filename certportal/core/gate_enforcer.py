"""certportal/core/gate_enforcer.py — HITL gate state machine.

INV-03: Gate ordering is enforced in code, not UI.
        GateOrderViolation is raised if Gate 2 is attempted before Gate 1 is COMPLETE,
        or Gate 3 before Gate 2 is COMPLETE.

Portals call assert_gate_precondition() or transition_gate() before any gate transition.
This is a deployment blocker (F7 quality gate).
"""
from __future__ import annotations


class GateOrderViolation(Exception):
    """Raised when a gate transition violates the required ordering."""


# Gate n requires gate (n-1) to be in required_state before it can be activated.
_GATE_PREREQUISITES: dict[int, tuple[int, str]] = {
    2: (1, "COMPLETE"),
    3: (2, "COMPLETE"),
}

_VALID_GATE_STATES: dict[int, frozenset[str]] = {
    1: frozenset({"PENDING", "COMPLETE"}),
    2: frozenset({"PENDING", "COMPLETE"}),
    3: frozenset({"PENDING", "COMPLETE", "CERTIFIED"}),
}


def assert_gate_precondition(
    supplier_id: str,
    target_gate: int,
    gate_status: dict,
) -> None:
    """Assert that prerequisite gate is COMPLETE before activating target_gate.

    Args:
        supplier_id:  The supplier being processed (used in error messages).
        target_gate:  The gate number to activate (1, 2, or 3).
        gate_status:  Dict with keys 'gate_1', 'gate_2', 'gate_3' and string states.

    Raises:
        GateOrderViolation: If the prerequisite gate is not yet COMPLETE.
        ValueError:         If target_gate is not 1, 2, or 3.
    """
    if target_gate not in (1, 2, 3):
        raise ValueError(f"target_gate must be 1, 2, or 3; got {target_gate!r}")

    if target_gate not in _GATE_PREREQUISITES:
        # Gate 1 has no prerequisite — always allowed.
        return

    prereq_gate, required_state = _GATE_PREREQUISITES[target_gate]
    current_state = gate_status.get(f"gate_{prereq_gate}", "PENDING")

    if current_state != required_state:
        raise GateOrderViolation(
            f"Cannot activate Gate {target_gate} for supplier '{supplier_id}': "
            f"Gate {prereq_gate} must be '{required_state}' but is '{current_state}'."
        )


async def get_gate_status(supplier_id: str, conn) -> dict:
    """Fetch current gate status from DB. Returns PENDING defaults if not found."""
    row = await conn.fetchrow(
        "SELECT gate_1, gate_2, gate_3 FROM hitl_gate_status WHERE supplier_id = $1",
        supplier_id,
    )
    if row is None:
        return {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"}
    return dict(row)


async def transition_gate(
    supplier_id: str,
    gate: int,
    new_state: str,
    updated_by: str,
    conn,
) -> None:
    """Transition a gate to new_state after asserting all preconditions.

    Performs an upsert into hitl_gate_status.

    Raises:
        GateOrderViolation: If preconditions are not met.
        ValueError:         If new_state is invalid for the target gate.
    """
    if new_state not in _VALID_GATE_STATES.get(gate, frozenset()):
        raise ValueError(
            f"Invalid state '{new_state}' for Gate {gate}. "
            f"Valid states: {sorted(_VALID_GATE_STATES[gate])}"
        )

    current_status = await get_gate_status(supplier_id, conn)
    assert_gate_precondition(supplier_id, gate, current_status)

    await conn.execute(
        f"""
        INSERT INTO hitl_gate_status
            (supplier_id, gate_{gate}, last_updated, last_updated_by)
        VALUES ($1, $2, now(), $3)
        ON CONFLICT (supplier_id) DO UPDATE
            SET gate_{gate} = $2,
                last_updated = now(),
                last_updated_by = $3
        """,
        supplier_id,
        new_state,
        updated_by,
    )
