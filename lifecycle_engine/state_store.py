"""
lifecycle_engine/state_store.py

Postgres persistence layer for the lifecycle state machine.
Uses psycopg2 directly — no SQLAlchemy, no ORM (per CLAUDE.md).
All writes execute in explicit BEGIN/COMMIT/ROLLBACK transactions.

lifecycle_events table is INSERT ONLY — never UPDATE or DELETE (mirrors INV-05).
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras

from lifecycle_engine.exceptions import LifecycleError

logger = logging.getLogger(__name__)


class StateStore:
    """
    Postgres-backed state store for po_lifecycle, lifecycle_events,
    and lifecycle_violations tables.

    All write methods execute in explicit transactions.
    upsert_po + append_event are always committed together (single txn).
    """

    def __init__(self, dsn: str) -> None:
        """
        Args:
            dsn: Postgres DSN string, e.g. CERTPORTAL_DB_URL env var.
        """
        self._dsn = dsn

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self):
        """Open a new psycopg2 connection. Caller must close."""
        return psycopg2.connect(self._dsn)

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_po(self, po_number: str) -> Optional[Dict]:
        """
        Fetch the po_lifecycle row for po_number.

        Returns None if not found.
        """
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM po_lifecycle WHERE po_number = %s",
                    (po_number,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def get_events(self, po_number: str) -> List[Dict]:
        """Return all lifecycle_events rows for po_number, ordered by processed_at."""
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM lifecycle_events WHERE po_number = %s "
                    "ORDER BY processed_at ASC",
                    (po_number,),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_violations(self, po_number: str) -> List[Dict]:
        """Return all lifecycle_violations rows for po_number."""
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM lifecycle_violations WHERE po_number = %s "
                    "ORDER BY failed_at ASC",
                    (po_number,),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_pos_in_state(self, state: str, partner_id: str) -> List[Dict]:
        """Return all po_lifecycle rows in a given state for partner_id."""
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM po_lifecycle "
                    "WHERE current_state = %s AND partner_id = %s",
                    (state, partner_id),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_stale_pos(self, older_than_hours: int) -> List[Dict]:
        """
        Return po_lifecycle rows whose updated_at is older than older_than_hours
        and that are not in a terminal state.
        """
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM po_lifecycle "
                    "WHERE is_terminal = FALSE "
                    "  AND updated_at < NOW() - INTERVAL '%s hours'",
                    (older_than_hours,),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Write methods — all explicit transactions
    # ------------------------------------------------------------------

    def transition_and_record(
        self,
        *,
        po_number: str,
        partner_id: str,
        prior_state: Optional[str],
        new_state: str,
        is_terminal: bool,
        qty_fields: Dict,
        event: Dict,
    ) -> None:
        """
        Execute upsert_po + append_event in a single Postgres transaction.

        This is the ONLY method that writes to po_lifecycle and
        lifecycle_events. Both writes always happen together.

        Args:
            po_number:   PO number (primary key).
            partner_id:  Retailer slug (e.g. 'lowes').
            prior_state: Previous state name (None if this is the first event).
            new_state:   New state name after this transition.
            is_terminal: Whether new_state is a terminal state.
            qty_fields:  Dict with optional keys:
                           ordered_qty, changed_qty, accepted_qty,
                           shipped_qty, invoiced_qty
            event:       Dict with keys:
                           event_type, transaction_set, direction,
                           source_file, correlation_id,
                           qty_at_event (optional),
                           payload_snapshot (optional, serialised to JSONB)

        Raises:
            LifecycleError: wraps any psycopg2 error.
        """
        conn = self._connect()
        try:
            cur = conn.cursor()

            # ---- Upsert po_lifecycle ----
            cur.execute(
                "SELECT id FROM po_lifecycle WHERE po_number = %s",
                (po_number,),
            )
            exists = cur.fetchone() is not None

            if exists:
                cur.execute(
                    """
                    UPDATE po_lifecycle SET
                        current_state   = %s,
                        is_terminal     = %s,
                        updated_at      = NOW(),
                        ordered_qty     = COALESCE(%s, ordered_qty),
                        changed_qty     = COALESCE(%s, changed_qty),
                        accepted_qty    = COALESCE(%s, accepted_qty),
                        shipped_qty     = COALESCE(%s, shipped_qty),
                        invoiced_qty    = COALESCE(%s, invoiced_qty)
                    WHERE po_number = %s
                    """,
                    (
                        new_state,
                        is_terminal,
                        qty_fields.get("ordered_qty"),
                        qty_fields.get("changed_qty"),
                        qty_fields.get("accepted_qty"),
                        qty_fields.get("shipped_qty"),
                        qty_fields.get("invoiced_qty"),
                        po_number,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO po_lifecycle (
                        po_number, partner_id, current_state, is_terminal,
                        ordered_qty, changed_qty, accepted_qty,
                        shipped_qty, invoiced_qty
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        po_number,
                        partner_id,
                        new_state,
                        is_terminal,
                        qty_fields.get("ordered_qty"),
                        qty_fields.get("changed_qty"),
                        qty_fields.get("accepted_qty"),
                        qty_fields.get("shipped_qty"),
                        qty_fields.get("invoiced_qty"),
                    ),
                )

            # ---- Append lifecycle_events (INSERT ONLY) ----
            payload_snapshot = event.get("payload_snapshot")
            if payload_snapshot is not None and not isinstance(payload_snapshot, str):
                payload_snapshot = json.dumps(payload_snapshot)

            cur.execute(
                """
                INSERT INTO lifecycle_events (
                    po_number, partner_id, event_type, transaction_set,
                    direction, source_file, correlation_id,
                    prior_state, new_state, qty_at_event, payload_snapshot
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    po_number,
                    partner_id,
                    event.get("event_type", new_state),
                    event["transaction_set"],
                    event["direction"],
                    event["source_file"],
                    event["correlation_id"],
                    prior_state,
                    new_state,
                    event.get("qty_at_event"),
                    payload_snapshot,
                ),
            )

            conn.commit()
            logger.debug(
                "StateStore: PO=%s transitioned %s → %s",
                po_number, prior_state, new_state,
            )

        except psycopg2.Error as exc:
            conn.rollback()
            raise LifecycleError(
                f"Postgres error during transition_and_record for PO={po_number}: {exc}"
            ) from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    def record_violation(self, violation: Dict) -> None:
        """
        Insert one row into lifecycle_violations.

        Args:
            violation: Dict with keys:
                po_number (optional), partner_id (optional),
                transaction_set, source_file, correlation_id,
                violation_type, violation_detail,
                current_state (optional), attempted_event
        """
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO lifecycle_violations (
                    po_number, partner_id, transaction_set, source_file,
                    correlation_id, violation_type, violation_detail,
                    current_state, attempted_event
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    violation.get("po_number"),
                    violation.get("partner_id"),
                    violation["transaction_set"],
                    violation["source_file"],
                    violation["correlation_id"],
                    violation["violation_type"],
                    violation["violation_detail"],
                    violation.get("current_state"),
                    violation["attempted_event"],
                ),
            )
            conn.commit()
        except psycopg2.Error as exc:
            conn.rollback()
            raise LifecycleError(
                f"Postgres error recording violation: {exc}"
            ) from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    # ------------------------------------------------------------------
    # Compatibility shims — TRD specifies these signatures
    # ------------------------------------------------------------------

    def upsert_po(
        self,
        po_number: str,
        partner_id: str,
        new_state: str,
        is_terminal: bool,
        qty_fields: Dict,
    ) -> None:
        """Single-call upsert (no event appended). Use transition_and_record
        in production — this exists for unit testing the upsert in isolation."""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM po_lifecycle WHERE po_number = %s",
                (po_number,),
            )
            exists = cur.fetchone() is not None
            if exists:
                cur.execute(
                    """
                    UPDATE po_lifecycle SET
                        current_state = %s, is_terminal = %s,
                        updated_at = NOW(),
                        ordered_qty  = COALESCE(%s, ordered_qty),
                        changed_qty  = COALESCE(%s, changed_qty),
                        accepted_qty = COALESCE(%s, accepted_qty),
                        shipped_qty  = COALESCE(%s, shipped_qty),
                        invoiced_qty = COALESCE(%s, invoiced_qty)
                    WHERE po_number = %s
                    """,
                    (
                        new_state, is_terminal,
                        qty_fields.get("ordered_qty"),
                        qty_fields.get("changed_qty"),
                        qty_fields.get("accepted_qty"),
                        qty_fields.get("shipped_qty"),
                        qty_fields.get("invoiced_qty"),
                        po_number,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO po_lifecycle (
                        po_number, partner_id, current_state, is_terminal,
                        ordered_qty, changed_qty, accepted_qty,
                        shipped_qty, invoiced_qty
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        po_number, partner_id, new_state, is_terminal,
                        qty_fields.get("ordered_qty"),
                        qty_fields.get("changed_qty"),
                        qty_fields.get("accepted_qty"),
                        qty_fields.get("shipped_qty"),
                        qty_fields.get("invoiced_qty"),
                    ),
                )
            conn.commit()
        except psycopg2.Error as exc:
            conn.rollback()
            raise LifecycleError(f"Postgres upsert_po error: {exc}") from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    def append_event(self, event: Dict) -> None:
        """Single-call event append (no upsert). Use transition_and_record
        in production — this exists for unit testing the append in isolation."""
        conn = self._connect()
        try:
            cur = conn.cursor()
            payload_snapshot = event.get("payload_snapshot")
            if payload_snapshot is not None and not isinstance(payload_snapshot, str):
                payload_snapshot = json.dumps(payload_snapshot)
            cur.execute(
                """
                INSERT INTO lifecycle_events (
                    po_number, partner_id, event_type, transaction_set,
                    direction, source_file, correlation_id,
                    prior_state, new_state, qty_at_event, payload_snapshot
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event["po_number"],
                    event["partner_id"],
                    event.get("event_type", event.get("new_state", "")),
                    event["transaction_set"],
                    event["direction"],
                    event["source_file"],
                    event["correlation_id"],
                    event.get("prior_state"),
                    event["new_state"],
                    event.get("qty_at_event"),
                    payload_snapshot,
                ),
            )
            conn.commit()
        except psycopg2.Error as exc:
            conn.rollback()
            raise LifecycleError(f"Postgres append_event error: {exc}") from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
