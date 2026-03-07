"""
lifecycle_engine/interface.py

Public API for the lifecycle engine — the ONLY file imported by pipeline.py.

This module owns the singleton LifecycleEngine instance and the direction map
used by pipeline.py to derive direction from transaction_type.

Usage in pyedi_core/pipeline.py (with ImportError guard per NC-04):

    try:
        from lifecycle_engine.interface import on_document_processed
        lifecycle_result = on_document_processed(
            transaction_set = transaction_type,
            direction       = direction,
            payload         = result_payload,
            source_file     = str(file_path),
            correlation_id  = correlation_id,
            partner_id      = config.get('partner_id', 'unknown')
        )
        logger.info('lifecycle_event',
                    state=lifecycle_result['new_state'],
                    po_number=lifecycle_result['po_number'])
    except ImportError:
        pass  # lifecycle_engine not installed — standalone pyedi_core use OK (NC-04)
    except LifecycleViolationError as e:
        error_handler.handle_error(e, stage='LIFECYCLE', ...)
        raise
"""
from __future__ import annotations

import dataclasses
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Direction map — used by pipeline.py hook to derive direction from tx type
# ---------------------------------------------------------------------------
DIRECTION_MAP: dict[str, str] = {
    "850": "inbound",
    "860": "inbound",
    "855": "outbound",
    "865": "outbound",
    "856": "outbound",
    "810": "outbound",
}

# ---------------------------------------------------------------------------
# Singleton engine
# ---------------------------------------------------------------------------
_engine = None


def _get_engine():
    """Return the singleton LifecycleEngine, initialising it on first call."""
    global _engine
    if _engine is None:
        from lifecycle_engine.engine import LifecycleEngine
        profile = os.environ.get("LIFECYCLE_PROFILE", "development")
        _engine = LifecycleEngine.from_config(profile=profile)
    return _engine


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def on_document_processed(
    transaction_set: str,
    direction: str,
    payload: dict,
    source_file: str,
    correlation_id: str,
    partner_id: str = "lowes",
    workspace=None,
) -> dict:
    """
    Called by pyedi_core/pipeline.py after a successful parse + write.

    Args:
        transaction_set: '850','860','855','865','856','810'
        direction:       'inbound' or 'outbound'
        payload:         Full parsed JSON dict from pyedi_core.
        source_file:     Original source file path or name.
        correlation_id:  UUID assigned by pipeline.py for this file.
        partner_id:      Retailer slug (default 'lowes').
        workspace:       Optional S3AgentWorkspace for violation S3 writes.

    Returns:
        LifecycleResult as a plain dict (dataclasses.asdict).

    Raises:
        LifecycleViolationError: if strict_mode=True and a violation is detected.
        LifecycleError:          for unrecoverable engine errors.
    """
    engine = _get_engine()
    result = engine.process_event(
        transaction_set=transaction_set,
        direction=direction,
        payload=payload,
        source_file=source_file,
        correlation_id=correlation_id,
        partner_id=partner_id,
        workspace=workspace,
    )
    return dataclasses.asdict(result)
