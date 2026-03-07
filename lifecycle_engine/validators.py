"""
lifecycle_engine/validators.py

Pure business-rule validators for the lifecycle state machine.

Each function:
  - Is independently callable and independently testable (NC-02)
  - Takes only plain Python types (no DB, no S3, no YAML loading)
  - Raises a specific LifecycleError subclass on failure
  - Is a no-op (returns None) on success

These are called by engine.py in a fixed sequence during process_event().
"""
from __future__ import annotations

from lifecycle_engine.exceptions import (
    InvalidTransitionError,
    N1QualifierError,
    POContinuityError,
    QuantityChainError,
    TerminalStateViolationError,
)

# ---------------------------------------------------------------------------
# Quantity waterfall column name → ordering
# ---------------------------------------------------------------------------
_QTY_CHAIN: list[tuple[str, str]] = [
    ("ordered_qty",  "850"),
    ("changed_qty",  "860"),
    ("accepted_qty", "855"),
    ("shipped_qty",  "856"),
    ("invoiced_qty", "810"),
]

# Map from transaction_set to the column that stores its quantity
_TX_TO_QTY_COL: dict[str, str] = {tx: col for col, tx in _QTY_CHAIN}


def validate_transition(
    current_state: str,
    target_state: str,
    valid_transitions: list[str],
) -> None:
    """
    Verify that target_state is a valid next state from current_state.

    Args:
        current_state:     The PO's current state name.
        target_state:      The proposed next state name.
        valid_transitions: List of allowed destination state names from
                           LifecycleLoader.get_valid_transitions(current_state).

    Raises:
        InvalidTransitionError: if target_state is not in valid_transitions.
    """
    if target_state not in valid_transitions:
        raise InvalidTransitionError(
            f"Cannot transition from '{current_state}' to '{target_state}'. "
            f"Valid transitions: {valid_transitions}"
        )


def validate_quantity_chain(
    po_record: dict,
    transaction_set: str,
    incoming_qty: "float | None",
) -> None:
    """
    Enforce the quantity waterfall:
        ordered (850) >= changed (860) >= accepted (855)
                     >= shipped (856) >= invoiced (810)

    Only checks the specific step introduced by transaction_set.
    If incoming_qty is None, the check is skipped (quantity not provided).

    Args:
        po_record:       Row from po_lifecycle table (as dict).
        transaction_set: The transaction being processed (e.g. '810').
        incoming_qty:    The quantity value from the current document.

    Raises:
        QuantityChainError: if the waterfall constraint is violated.
    """
    if incoming_qty is None:
        return

    # Find the position of this transaction in the chain
    tx_position = None
    for i, (col, tx) in enumerate(_QTY_CHAIN):
        if tx == transaction_set:
            tx_position = i
            break

    if tx_position is None:
        # Transaction not in quantity chain (e.g. 865) — skip
        return

    # Check that incoming_qty <= all quantities upstream (lower index)
    for i in range(tx_position):
        upstream_col, upstream_tx = _QTY_CHAIN[i]
        upstream_qty = po_record.get(upstream_col)
        if upstream_qty is not None and incoming_qty > float(upstream_qty):
            raise QuantityChainError(
                f"Quantity chain violated: {transaction_set} qty={incoming_qty} "
                f"exceeds {upstream_tx} qty={upstream_qty} "
                f"({upstream_col} >= {_TX_TO_QTY_COL.get(transaction_set, '?')} rule)"
            )


def validate_n1_qualifier(
    transaction_set: str,
    observed_qualifier: "str | None",
    n1_map: dict[str, str],
) -> None:
    """
    Verify that the N103 identification code qualifier matches the expected
    value for this transaction type.

    Args:
        transaction_set:    The transaction being processed (e.g. '850').
        observed_qualifier: The N103 value found in the document.
                            If None, the check is skipped.
        n1_map:             Dict mapping transaction_set → expected N103.
                            From LifecycleLoader.get_n1_qualifier_map().

    Raises:
        N1QualifierError: if observed_qualifier != expected_qualifier.
    """
    if observed_qualifier is None:
        return

    expected = n1_map.get(transaction_set)
    if expected is None:
        # No qualifier rule defined for this transaction — skip
        return

    if observed_qualifier != expected:
        raise N1QualifierError(
            f"N1 qualifier mismatch for {transaction_set}: "
            f"expected N103='{expected}', observed N103='{observed_qualifier}'"
        )


def validate_not_terminal(po_record: dict) -> None:
    """
    Verify that the PO is not already in a terminal state.

    Args:
        po_record: Row from po_lifecycle table (as dict).
                   Must have 'is_terminal' and 'current_state' keys.

    Raises:
        TerminalStateViolationError: if po_record['is_terminal'] is True.
    """
    if po_record.get("is_terminal", False):
        state = po_record.get("current_state", "unknown")
        po = po_record.get("po_number", "unknown")
        raise TerminalStateViolationError(
            f"PO '{po}' is already in terminal state '{state}'. "
            f"No further documents can be processed for this lifecycle."
        )


def validate_po_number_continuity(
    po_number: str,
    transaction_set: str,
    payload: dict,
    primary_key_config: dict,
) -> None:
    """
    Verify that the PO number in the current document matches the established
    PO number for this lifecycle thread.

    The PO number is extracted from payload.header.po_number (all six
    transaction types normalize to this path per TRD §7).

    Args:
        po_number:          The established PO number from po_lifecycle.
        transaction_set:    Current transaction being processed.
        payload:            Full parsed JSON payload from pyedi_core.
        primary_key_config: From LifecycleLoader.get_primary_key_config().
                            Reserved for future per-transaction path overrides.

    Raises:
        POContinuityError: if the PO number in the payload doesn't match.
    """
    # Extract PO number from normalised payload path
    header = payload.get("header", {}) if isinstance(payload, dict) else {}
    payload_po = header.get("po_number")

    if payload_po is None:
        # PO# not in payload — continuity cannot be checked
        # MissingPONumberError is raised upstream; skip here
        return

    if str(payload_po) != str(po_number):
        raise POContinuityError(
            f"PO number mismatch on {transaction_set}: "
            f"expected '{po_number}', found '{payload_po}' in payload"
        )
