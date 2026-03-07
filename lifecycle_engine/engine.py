"""
lifecycle_engine/engine.py

LifecycleEngine — the central orchestrator for order-to-cash state transitions.

process_event() execution sequence (from TRD §6.6):
    1. EXTRACT   — Extract PO# from payload.header.po_number
    2. LOAD STATE — Query StateStore for current PO state
    3. DETERMINE  — Map (transaction_set, direction) → target state
    4. VALIDATE   — Run all 5 validators in validators.py
    5. CAPTURE    — Extract fields from state's captures list
    6. PERSIST    — upsert_po + append_event in single Postgres transaction
    7. S3 WRITE   — On violation only: write to S3 for Monica
    8. RETURN     — LifecycleResult dataclass

Business rules (NC-02): all state definitions live in order_to_cash.yaml.
Python executes; YAML is the brain.
"""
from __future__ import annotations

import dataclasses
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from lifecycle_engine.exceptions import (
    LifecycleConfigError,
    LifecycleError,
    LifecycleViolationError,
    MissingPONumberError,
    UnexpectedFirstDocumentError,
)
from lifecycle_engine.loader import LifecycleLoader
from lifecycle_engine.state_store import StateStore
from lifecycle_engine.validators import (
    validate_n1_qualifier,
    validate_not_terminal,
    validate_po_number_continuity,
    validate_quantity_chain,
    validate_transition,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Transaction → target state map  (TRD §8)
# Entries with None are determined dynamically (855, 865 dual-path logic).
# ---------------------------------------------------------------------------
TRANSACTION_STATE_MAP: Dict[tuple, Optional[str]] = {
    ("850", "inbound"):  "po_originated",
    ("860", "inbound"):  "po_changed",
    ("855", "outbound"): None,   # dual-path: reverse_po_created or po_acknowledged
    ("865", "outbound"): None,   # dual-path: po_change_accepted or po_change_rejected
    ("856", "outbound"): "shipped",
    ("810", "outbound"): "invoiced",
}

# Quantity column updated by each transaction
_TX_QTY_FIELD: Dict[str, str] = {
    "850": "ordered_qty",
    "860": "changed_qty",
    "855": "accepted_qty",
    "856": "shipped_qty",
    "810": "invoiced_qty",
}


@dataclasses.dataclass
class LifecycleResult:
    """Return value of LifecycleEngine.process_event()."""
    success: bool
    po_number: str
    partner_id: str
    prior_state: Optional[str]
    new_state: str
    is_terminal: bool
    correlation_id: str
    violations: List[str]   # empty on success


class LifecycleEngine:
    """
    Stateless engine that orchestrates lifecycle transitions.

    All state is stored in Postgres (via StateStore). The engine itself
    holds only the loaded YAML config (LifecycleLoader) and the DSN.
    """

    def __init__(
        self,
        loader: LifecycleLoader,
        dsn: str,
        strict_mode: bool = False,
    ) -> None:
        self._loader = loader
        self._dsn = dsn
        self._strict_mode = strict_mode

    @classmethod
    def from_config(
        cls,
        config_path: Optional[str] = None,
        profile: str = "development",
    ) -> "LifecycleEngine":
        """
        Factory method: load lifecycle_engine/config.yaml and initialise engine.

        Args:
            config_path: Path to config.yaml. Defaults to lifecycle_engine/config.yaml
                         (resolved relative to this module's directory).
            profile:     'development' or 'production'. Controls strict_mode.
        """
        if config_path is None:
            config_path = str(Path(__file__).parent / "config.yaml")

        with open(config_path, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)

        engine_cfg = cfg.get("lifecycle_engine", {})
        framework_base = engine_cfg.get("framework_base_path", "../edi_framework")

        profiles = engine_cfg.get("profiles", {})
        profile_cfg = profiles.get(profile, {})
        strict_mode = profile_cfg.get("strict_mode", False)

        # Allow env override for profile selection
        env_profile = os.environ.get("LIFECYCLE_PROFILE", profile)
        if env_profile != profile:
            strict_mode = profiles.get(env_profile, {}).get("strict_mode", False)

        dsn = os.environ.get("CERTPORTAL_DB_URL", "")
        if not dsn:
            raise LifecycleConfigError(
                "CERTPORTAL_DB_URL environment variable is not set."
            )

        loader = LifecycleLoader(framework_base)
        loader.load()

        return cls(loader=loader, dsn=dsn, strict_mode=strict_mode)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_event(
        self,
        *,
        transaction_set: str,
        direction: str,
        payload: dict,
        source_file: str,
        correlation_id: str,
        partner_id: str = "lowes",
        workspace=None,  # S3AgentWorkspace — optional for standalone use
    ) -> LifecycleResult:
        """
        Process one document event through the lifecycle state machine.

        Args:
            transaction_set: '850','860','855','865','856','810'
            direction:       'inbound' or 'outbound'
            payload:         Full parsed JSON from pyedi_core (dict).
            source_file:     Original source file path/name.
            correlation_id:  UUID from pyedi_core pipeline run.
            partner_id:      Retailer slug (default 'lowes').
            workspace:       S3AgentWorkspace for violation writes (optional).

        Returns:
            LifecycleResult dataclass.

        Raises:
            LifecycleViolationError: on validation failure (in strict_mode).
        """
        store = StateStore(self._dsn)

        # ----------------------------------------------------------------
        # STEP 1: EXTRACT PO number
        # ----------------------------------------------------------------
        po_number = self._extract_po_number(payload)
        if po_number is None:
            return self._handle_violation(
                violation_type="missing_po",
                detail="PO number not found in payload.header.po_number",
                po_number=None,
                correlation_id=correlation_id,
                transaction_set=transaction_set,
                direction=direction,
                source_file=source_file,
                partner_id=partner_id,
                prior_state=None,
                attempted_event=f"{transaction_set}/{direction}",
                store=store,
                workspace=workspace,
            )

        # ----------------------------------------------------------------
        # STEP 2: LOAD STATE from Postgres
        # ----------------------------------------------------------------
        po_record = store.get_po(po_number)
        prior_state = po_record["current_state"] if po_record else None

        # ----------------------------------------------------------------
        # STEP 3: DETERMINE target state
        # ----------------------------------------------------------------
        key = (transaction_set, direction)
        target_state = TRANSACTION_STATE_MAP.get(key)

        if target_state is None and key not in TRANSACTION_STATE_MAP:
            # Unknown transaction+direction combo — skip lifecycle
            logger.warning(
                "engine: unknown (transaction_set=%s, direction=%s) — skipping lifecycle",
                transaction_set, direction,
            )
            return LifecycleResult(
                success=True,
                po_number=po_number,
                partner_id=partner_id,
                prior_state=prior_state,
                new_state=prior_state or "unknown",
                is_terminal=False,
                correlation_id=correlation_id,
                violations=[],
            )

        # Dual-path logic for 855
        if transaction_set == "855" and direction == "outbound":
            if po_record is None:
                target_state = "reverse_po_created"
            else:
                target_state = "po_acknowledged"

        # Dual-path logic for 865
        elif transaction_set == "865" and direction == "outbound":
            ack_type = (
                payload.get("header", {}).get("ack_type", "")
                if isinstance(payload, dict)
                else ""
            )
            if ack_type == "AT":
                target_state = "po_change_accepted"
            elif ack_type == "RJ":
                target_state = "po_change_rejected"
            else:
                logger.warning(
                    "engine: 865 with unknown ack_type='%s', po=%s — skipping lifecycle",
                    ack_type, po_number,
                )
                return LifecycleResult(
                    success=True,
                    po_number=po_number,
                    partner_id=partner_id,
                    prior_state=prior_state,
                    new_state=prior_state or "unknown",
                    is_terminal=False,
                    correlation_id=correlation_id,
                    violations=[],
                )

        # First document check
        if po_record is None and target_state not in (
            "po_originated", "reverse_po_created"
        ):
            return self._handle_violation(
                violation_type="unexpected_first_doc",
                detail=(
                    f"First document for this PO is {transaction_set}/{direction} "
                    f"(target={target_state}) — expected 850 or 855 reverse PO"
                ),
                po_number=po_number,
                correlation_id=correlation_id,
                transaction_set=transaction_set,
                direction=direction,
                source_file=source_file,
                partner_id=partner_id,
                prior_state=None,
                attempted_event=target_state,
                store=store,
                workspace=workspace,
            )

        # ----------------------------------------------------------------
        # STEP 4: VALIDATE
        # ----------------------------------------------------------------
        # 4a. Not already terminal
        if po_record is not None:
            try:
                validate_not_terminal(po_record)
            except Exception as exc:
                return self._handle_violation(
                    violation_type="duplicate_terminal",
                    detail=str(exc),
                    po_number=po_number,
                    correlation_id=correlation_id,
                    transaction_set=transaction_set,
                    direction=direction,
                    source_file=source_file,
                    partner_id=partner_id,
                    prior_state=prior_state,
                    attempted_event=target_state,
                    store=store,
                    workspace=workspace,
                )

        # 4b. Valid transition from current state
        if prior_state is not None:
            valid_transitions = self._loader.get_valid_transitions(prior_state)
            try:
                validate_transition(prior_state, target_state, valid_transitions)
            except Exception as exc:
                return self._handle_violation(
                    violation_type="invalid_transition",
                    detail=str(exc),
                    po_number=po_number,
                    correlation_id=correlation_id,
                    transaction_set=transaction_set,
                    direction=direction,
                    source_file=source_file,
                    partner_id=partner_id,
                    prior_state=prior_state,
                    attempted_event=target_state,
                    store=store,
                    workspace=workspace,
                )

        # 4c. Quantity chain
        incoming_qty = self._extract_qty(payload, transaction_set)
        if po_record is not None and incoming_qty is not None:
            try:
                validate_quantity_chain(po_record, transaction_set, incoming_qty)
            except Exception as exc:
                return self._handle_violation(
                    violation_type="quantity_chain",
                    detail=str(exc),
                    po_number=po_number,
                    correlation_id=correlation_id,
                    transaction_set=transaction_set,
                    direction=direction,
                    source_file=source_file,
                    partner_id=partner_id,
                    prior_state=prior_state,
                    attempted_event=target_state,
                    store=store,
                    workspace=workspace,
                )

        # 4d. N1 qualifier
        n1_map = self._loader.get_n1_qualifier_map()
        observed_n1 = self._extract_n1_qualifier(payload)
        try:
            validate_n1_qualifier(transaction_set, observed_n1, n1_map)
        except Exception as exc:
            return self._handle_violation(
                violation_type="n1_qualifier",
                detail=str(exc),
                po_number=po_number,
                correlation_id=correlation_id,
                transaction_set=transaction_set,
                direction=direction,
                source_file=source_file,
                partner_id=partner_id,
                prior_state=prior_state,
                attempted_event=target_state,
                store=store,
                workspace=workspace,
            )

        # 4e. PO number continuity (only if PO already exists)
        if po_record is not None:
            try:
                validate_po_number_continuity(
                    po_number, transaction_set, payload,
                    self._loader.get_primary_key_config(),
                )
            except Exception as exc:
                return self._handle_violation(
                    violation_type="po_continuity",
                    detail=str(exc),
                    po_number=po_number,
                    correlation_id=correlation_id,
                    transaction_set=transaction_set,
                    direction=direction,
                    source_file=source_file,
                    partner_id=partner_id,
                    prior_state=prior_state,
                    attempted_event=target_state,
                    store=store,
                    workspace=workspace,
                )

        # ----------------------------------------------------------------
        # STEP 5: CAPTURE fields from state definition
        # ----------------------------------------------------------------
        payload_snapshot = self._capture_fields(target_state, payload)

        # ----------------------------------------------------------------
        # STEP 6: PERSIST — single Postgres transaction
        # ----------------------------------------------------------------
        is_terminal = self._loader.is_terminal_state(target_state)
        qty_col = _TX_QTY_FIELD.get(transaction_set)
        qty_fields = {qty_col: incoming_qty} if qty_col and incoming_qty is not None else {}

        try:
            store.transition_and_record(
                po_number=po_number,
                partner_id=partner_id,
                prior_state=prior_state,
                new_state=target_state,
                is_terminal=is_terminal,
                qty_fields=qty_fields,
                event={
                    "event_type": target_state,
                    "transaction_set": transaction_set,
                    "direction": direction,
                    "source_file": source_file,
                    "correlation_id": correlation_id,
                    "qty_at_event": incoming_qty,
                    "payload_snapshot": payload_snapshot,
                },
            )
        except LifecycleError:
            raise

        # ----------------------------------------------------------------
        # STEP 7: S3 WRITE — violations only (none here — all validated)
        # ----------------------------------------------------------------

        # ----------------------------------------------------------------
        # STEP 8: RETURN
        # ----------------------------------------------------------------
        return LifecycleResult(
            success=True,
            po_number=po_number,
            partner_id=partner_id,
            prior_state=prior_state,
            new_state=target_state,
            is_terminal=is_terminal,
            correlation_id=correlation_id,
            violations=[],
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_po_number(self, payload: dict) -> Optional[str]:
        """Extract PO# from payload.header.po_number (all txns normalise here)."""
        if not isinstance(payload, dict):
            return None
        header = payload.get("header", {})
        if not isinstance(header, dict):
            return None
        val = header.get("po_number")
        return str(val) if val is not None else None

    def _extract_qty(self, payload: dict, transaction_set: str) -> Optional[float]:
        """Best-effort quantity extraction from payload header."""
        if not isinstance(payload, dict):
            return None
        header = payload.get("header", {})
        if not isinstance(header, dict):
            return None
        qty = header.get("quantity") or header.get("qty")
        if qty is None:
            return None
        try:
            return float(qty)
        except (TypeError, ValueError):
            return None

    def _extract_n1_qualifier(self, payload: dict) -> Optional[str]:
        """Extract N103 qualifier from payload.header.n1_qualifier if present."""
        if not isinstance(payload, dict):
            return None
        header = payload.get("header", {})
        if not isinstance(header, dict):
            return None
        return header.get("n1_qualifier")

    def _capture_fields(self, state_name: str, payload: dict) -> dict:
        """
        Extract snapshot fields defined in the state's 'captures' list.
        Returns a dict of captured key → value. Logs warning if a capture fails.
        """
        captures = self._loader.get_captures(state_name)
        snapshot = {}
        for cap in captures:
            key = cap.get("key")
            if not key:
                continue
            # Simple header extraction — complex paths (N1[ST].N104) are best-effort
            header = payload.get("header", {}) if isinstance(payload, dict) else {}
            val = header.get(key)
            if val is not None:
                snapshot[key] = val
        return snapshot

    def _handle_violation(
        self,
        *,
        violation_type: str,
        detail: str,
        po_number: Optional[str],
        correlation_id: str,
        transaction_set: str,
        direction: str,
        source_file: str,
        partner_id: str,
        prior_state: Optional[str],
        attempted_event: str,
        store: StateStore,
        workspace,
    ) -> LifecycleResult:
        """
        Record violation in Postgres + S3, then either raise (strict_mode=True)
        or return a failure LifecycleResult (strict_mode=False).
        """
        violation = {
            "po_number": po_number,
            "partner_id": partner_id,
            "transaction_set": transaction_set,
            "source_file": source_file,
            "correlation_id": correlation_id,
            "violation_type": violation_type,
            "violation_detail": detail,
            "current_state": prior_state,
            "attempted_event": attempted_event,
        }

        # Write to Postgres
        try:
            store.record_violation(violation)
        except Exception as exc:
            logger.error("engine: could not record violation to Postgres: %s", exc)

        # Write to S3 (non-blocking)
        if workspace is not None:
            from lifecycle_engine.s3_writer import write_violation_to_s3
            write_violation_to_s3(
                violation=violation,
                retailer_slug=partner_id,
                supplier_slug="",   # supplier_slug not available at engine level
                workspace=workspace,
            )

        logger.warning(
            "engine: lifecycle violation type=%s po=%s corr=%s: %s",
            violation_type, po_number, correlation_id, detail,
        )

        if self._strict_mode:
            raise LifecycleViolationError(
                violation_type=violation_type,
                detail=detail,
                po_number=po_number,
                correlation_id=correlation_id,
            )

        return LifecycleResult(
            success=False,
            po_number=po_number or "unknown",
            partner_id=partner_id,
            prior_state=prior_state,
            new_state=prior_state or "unknown",
            is_terminal=False,
            correlation_id=correlation_id,
            violations=[detail],
        )
