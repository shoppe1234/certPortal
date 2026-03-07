"""
lifecycle_engine/exceptions.py

All exception classes for the lifecycle engine.

Hierarchy:
    LifecycleError                      — base
    ├── LifecycleConfigError            — bad or missing YAML configuration
    ├── MissingPONumberError            — PO# not extractable from payload
    ├── UnexpectedFirstDocumentError    — first doc in sequence is not 850 or 855
    ├── InvalidTransitionError          — state transition not in valid_transitions
    ├── QuantityChainError              — quantity waterfall violated
    ├── N1QualifierError                — N103 qualifier mismatch
    ├── TerminalStateViolationError     — document received after terminal state
    ├── POContinuityError               — PO# mismatch across documents
    └── LifecycleViolationError         — structured violation (wraps all above)
"""


class LifecycleError(Exception):
    """Base exception for all lifecycle_engine errors."""


class LifecycleConfigError(LifecycleError):
    """Raised when the YAML framework configuration is missing or invalid."""


class MissingPONumberError(LifecycleError):
    """Raised when the PO number cannot be extracted from the parsed payload."""


class UnexpectedFirstDocumentError(LifecycleError):
    """
    Raised when the first document for a PO is not an 850 or a vendor-initiated
    855 (reverse PO). Any other transaction arriving without an existing PO
    record is considered an out-of-sequence document.
    """


class InvalidTransitionError(LifecycleError):
    """
    Raised when the attempted lifecycle state transition is not in the list of
    valid_transitions for the current state.
    """


class QuantityChainError(LifecycleError):
    """
    Raised when the quantity waterfall rule is violated:
        ordered (850) >= changed (860) >= accepted (855)
                     >= shipped (856) >= invoiced (810)
    """


class N1QualifierError(LifecycleError):
    """
    Raised when the N103 identification code qualifier does not match the
    expected value for the transaction type (e.g., 850/860 expect '93',
    855/856 expect '94', 810 expects '92').
    """


class TerminalStateViolationError(LifecycleError):
    """
    Raised when a document is received for a PO that is already in a terminal
    state (e.g., 'invoiced'). No further transitions are allowed.
    """


class POContinuityError(LifecycleError):
    """
    Raised when a PO number mismatch is detected — i.e., the PO number in the
    current document does not match the established PO number for this lifecycle
    thread.
    """


class LifecycleViolationError(LifecycleError):
    """
    Structured violation wrapper used by engine.py to report violations to
    pipeline.py. Contains structured metadata for Postgres and S3 writes.

    Attributes:
        violation_type: One of the canonical violation type strings:
            'invalid_transition' | 'quantity_chain' | 'missing_po'
            | 'duplicate_terminal' | 'n1_qualifier' | 'po_continuity'
            | 'unexpected_first_doc'
        detail:         Human-readable description of the violation.
        po_number:      PO number affected (None if could not be extracted).
        correlation_id: Correlation ID from the pyedi_core pipeline run.
    """

    def __init__(
        self,
        violation_type: str,
        detail: str,
        po_number: "str | None",
        correlation_id: str,
    ) -> None:
        self.violation_type = violation_type
        self.detail = detail
        self.po_number = po_number
        self.correlation_id = correlation_id
        super().__init__(
            f"[{violation_type}] PO={po_number} corr={correlation_id}: {detail}"
        )
