"""certportal/core/gate_enforcer.py — HITL gate state machine.

INV-03: Gate ordering is enforced in code, not UI.
        Full gate chain: A → B → 1 → 2 → 3.
        GateOrderViolation is raised on any out-of-order transition.

Gate model (6-step onboarding):
    Gate A  — Specs acknowledged
    Gate B  — Company + contact info complete
    Gate 1  — Connection method + test EDI IDs
    Gate 2  — All required scenarios CERTIFIED|EXEMPT, 0 pending exceptions
    Gate 3  — Production IDs confirmed + PAM admin certification

Portals call assert_gate_precondition() or transition_gate() before any gate transition.
This is a deployment blocker (F7 quality gate).
"""
from __future__ import annotations

# Gate identifier type: "a", "b", 1, 2, 3
GateId = int | str


class GateOrderViolation(Exception):
    """Raised when a gate transition violates the required ordering."""


# Gate n requires the named prerequisite gate to be COMPLETE before activation.
# Gate A has no prerequisite — always allowed.
_GATE_PREREQUISITES: dict[GateId, tuple[GateId, str]] = {
    "b": ("a", "COMPLETE"),
    1: ("b", "COMPLETE"),
    2: (1, "COMPLETE"),
    3: (2, "COMPLETE"),
}

_VALID_GATE_STATES: dict[GateId, frozenset[str]] = {
    "a": frozenset({"PENDING", "COMPLETE"}),
    "b": frozenset({"PENDING", "COMPLETE"}),
    1: frozenset({"PENDING", "COMPLETE"}),
    2: frozenset({"PENDING", "COMPLETE"}),
    3: frozenset({"PENDING", "COMPLETE", "CERTIFIED"}),
}

# All recognized gate identifiers (for validation)
_ALL_GATES: frozenset[GateId] = frozenset({"a", "b", 1, 2, 3})


def _gate_col(gate: GateId) -> str:
    """Return the DB column name for a gate identifier."""
    return f"gate_{gate}"


def assert_gate_precondition(
    supplier_id: str,
    target_gate: GateId,
    gate_status: dict,
) -> None:
    """Assert that prerequisite gate is COMPLETE before activating target_gate.

    Args:
        supplier_id:  The supplier being processed (used in error messages).
        target_gate:  The gate to activate ("a", "b", 1, 2, or 3).
        gate_status:  Dict with keys 'gate_a', 'gate_b', 'gate_1', 'gate_2', 'gate_3'.

    Raises:
        GateOrderViolation: If the prerequisite gate is not yet COMPLETE.
        ValueError:         If target_gate is not a recognized gate.
    """
    if target_gate not in _ALL_GATES:
        raise ValueError(f"target_gate must be one of {sorted(_ALL_GATES, key=str)}; got {target_gate!r}")

    if target_gate not in _GATE_PREREQUISITES:
        # Gate A has no prerequisite — always allowed.
        return

    prereq_gate, required_state = _GATE_PREREQUISITES[target_gate]
    current_state = gate_status.get(_gate_col(prereq_gate), "PENDING")

    if current_state != required_state:
        raise GateOrderViolation(
            f"Cannot activate Gate {target_gate} for supplier '{supplier_id}': "
            f"Gate {prereq_gate} must be '{required_state}' but is '{current_state}'."
        )


async def get_gate_status(supplier_id: str, conn) -> dict:
    """Fetch current gate status from DB. Returns PENDING defaults if not found."""
    row = await conn.fetchrow(
        "SELECT gate_a, gate_b, gate_1, gate_2, gate_3 FROM hitl_gate_status WHERE supplier_id = $1",
        supplier_id,
    )
    if row is None:
        return {
            "gate_a": "PENDING",
            "gate_b": "PENDING",
            "gate_1": "PENDING",
            "gate_2": "PENDING",
            "gate_3": "PENDING",
        }
    return dict(row)


async def transition_gate(
    supplier_id: str,
    gate: GateId,
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
    if gate not in _ALL_GATES:
        raise ValueError(f"gate must be one of {sorted(_ALL_GATES, key=str)}; got {gate!r}")

    if new_state not in _VALID_GATE_STATES.get(gate, frozenset()):
        raise ValueError(
            f"Invalid state '{new_state}' for Gate {gate}. "
            f"Valid states: {sorted(_VALID_GATE_STATES[gate])}"
        )

    current_status = await get_gate_status(supplier_id, conn)
    assert_gate_precondition(supplier_id, gate, current_status)

    col = _gate_col(gate)
    await conn.execute(
        f"""
        INSERT INTO hitl_gate_status
            (supplier_id, {col}, last_updated, last_updated_by)
        VALUES ($1, $2, now(), $3)
        ON CONFLICT (supplier_id) DO UPDATE
            SET {col} = $2,
                last_updated = now(),
                last_updated_by = $3
        """,
        supplier_id,
        new_state,
        updated_by,
    )


async def get_onboarding_profile(supplier_slug: str, conn) -> dict | None:
    """Fetch supplier onboarding profile. Returns None if not started."""
    row = await conn.fetchrow(
        "SELECT * FROM supplier_onboarding WHERE supplier_slug = $1",
        supplier_slug,
    )
    return dict(row) if row else None


async def compute_current_step(supplier_slug: str, conn) -> int:
    """Determine the current onboarding step (1-6) from gate state + onboarding data."""
    gates = await get_gate_status(supplier_slug, conn)
    profile = await get_onboarding_profile(supplier_slug, conn)

    # Step 1: Acknowledge specs (Gate A)
    if gates.get("gate_a") != "COMPLETE":
        return 1
    # Step 2: Company + contact (Gate B)
    if gates.get("gate_b") != "COMPLETE":
        return 2
    # Step 3: Connection + test IDs (Gate 1)
    if gates.get("gate_1") != "COMPLETE":
        return 3
    # Step 4: Item data
    if profile and not profile.get("items_complete"):
        return 4
    # Step 5: Test scenarios (Gate 2)
    if gates.get("gate_2") != "COMPLETE":
        return 5
    # Step 6: Go-live (Gate 3)
    return 6
