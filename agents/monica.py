"""agents/monica.py — Orchestrator + HITL Keeper.

INV-01: Monica never imports from other agent files.
INV-02: All inter-agent questions route through Monica (via PAM-STATUS.json).
INV-04: No LangChain abstractions. Explicit OpenAI calls only.

OpenAI usage:
  - GPT-4o-mini: HITL flag summarisation (real call, Sprint 1)
  - GPT-4o pattern analysis on MONICA-MEMORY.md: TODO Sprint 2 (Google ADK)

CLI: python -m agents.monica --retailer <slug> --supplier <slug>
"""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from openai import OpenAI

from certportal.core import monica_logger
from certportal.core.config import settings
from certportal.core.gate_enforcer import GateOrderViolation, assert_gate_precondition
from certportal.core.workspace import S3AgentWorkspace, FileNotFoundInWorkspace

_openai_client = OpenAI(api_key=settings.openai_api_key)

MAX_LOOP_ITERATIONS = 50


class MonicaLoopGuard(Exception):
    """Raised if Monica's internal loop exceeds MAX_LOOP_ITERATIONS."""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run(retailer_slug: str, supplier_slug: str) -> dict:
    """Monica's pipeline coordination run.

    Responsibilities:
    - Read PAM-STATUS.json for current gate state
    - Check for pending HITL flags from any agent
    - Enforce gate ordering (read-only; portals perform transitions)
    - Process Kelly sentiment escalations
    - Write all exchanges to MONICA-MEMORY.md via monica_logger
    - Return summary dict of actions taken

    Explicit termination: runs once per invocation. Max iterations on any
    internal loop: MAX_LOOP_ITERATIONS (raises MonicaLoopGuard if exceeded).
    """
    monica_logger.log(
        "MONICA",
        "A",
        f"Pipeline run started for {retailer_slug}/{supplier_slug}",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    workspace = S3AgentWorkspace(retailer_slug, supplier_slug)
    summary: dict = {
        "retailer_slug": retailer_slug,
        "supplier_slug": supplier_slug,
        "hitl_flags_processed": 0,
        "gate_status": {},
        "actions_taken": [],
        "run_at": _utcnow_iso(),
    }

    # 1. Read PAM-STATUS
    pam_status = workspace.read_pam_status(supplier_slug)
    summary["pam_status_keys"] = list(pam_status.keys())

    # 2. Check gate ordering (read-only — portals do the transitions)
    gate_status = {
        "gate_1": pam_status.get("gate_1", "PENDING"),
        "gate_2": pam_status.get("gate_2", "PENDING"),
        "gate_3": pam_status.get("gate_3", "PENDING"),
    }
    summary["gate_status"] = gate_status

    # 3. Validate gate ordering is consistent (detect portal bypasses)
    _validate_gate_consistency(supplier_slug, gate_status)

    # 4. Process HITL flags
    flags = process_hitl_flags(workspace)
    summary["hitl_flags_processed"] = len(flags)

    if flags:
        monica_logger.log(
            "MONICA",
            "Q",
            f"Found {len(flags)} pending HITL flag(s) for {supplier_slug}. Surfacing to portal.",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )
        summary["actions_taken"].append(f"surfaced_{len(flags)}_hitl_flags")

    # 5. Check for Kelly sentiment escalations and queue each for HITL (ADR-022)
    escalations = _check_kelly_escalations(workspace, supplier_slug)
    if escalations:
        summary["actions_taken"].append(f"kelly_escalations_detected:{len(escalations)}")
        monica_logger.log(
            "MONICA",
            "Q",
            f"Kelly sentiment escalation detected for {supplier_slug}: {escalations}",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )
        for thread_id in escalations:
            inserted = _queue_escalation_for_hitl(supplier_slug, retailer_slug, thread_id)
            if inserted:
                summary["actions_taken"].append(f"escalation_queued:{thread_id}")

    monica_logger.log(
        "MONICA",
        "A",
        f"Pipeline run complete for {retailer_slug}/{supplier_slug}. "
        f"Flags: {len(flags)}. Gates: {gate_status}.",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    return summary


# ---------------------------------------------------------------------------
# HITL queue management
# ---------------------------------------------------------------------------


def queue_for_approval(
    draft: str,
    thread_id: str,
    channel: str,
    supplier_slug: str,
    retailer_slug: str,
) -> str:
    """Queue a Kelly communication draft for Monica's HITL approval.

    Writes a queue entry to workspace PAM-STATUS.json.
    Returns queue_id (UUID4 string).
    """
    queue_id = str(uuid.uuid4())
    workspace = S3AgentWorkspace(retailer_slug, supplier_slug)

    # Summarise draft for human reviewer (GPT-4o-mini — real call)
    summary = _summarise_for_hitl(draft)

    workspace.write_pam_status(
        supplier_slug,
        {
            "hitl_queue": {
                queue_id: {
                    "queue_id": queue_id,
                    "draft": draft,
                    "summary": summary,
                    "thread_id": thread_id,
                    "channel": channel,
                    "status": "PENDING_APPROVAL",
                    "queued_at": _utcnow_iso(),
                }
            }
        },
    )

    monica_logger.log(
        "MONICA",
        "Q",
        f"Kelly draft queued for HITL approval. "
        f"queue_id={queue_id} channel={channel} thread={thread_id}",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    return queue_id


def process_hitl_flags(workspace: S3AgentWorkspace) -> list[dict]:
    """Read all pending HITL flags from PAM-STATUS.json.

    Surfaces them to the appropriate portal (pam or meredith) by writing
    updated status back to PAM-STATUS.json.
    Never resolves flags automatically — humans resolve via portal.

    Returns list of flags processed this run.
    Raises MonicaLoopGuard if flag count exceeds MAX_LOOP_ITERATIONS.
    """
    supplier_slug = workspace._supplier_slug or "unknown"
    pam_status = workspace.read_pam_status(supplier_slug)

    flags: list[dict] = []
    iteration = 0

    pending_flags = pam_status.get("hitl_flags", {})

    for flag_id, flag in pending_flags.items():
        if iteration >= MAX_LOOP_ITERATIONS:
            raise MonicaLoopGuard(
                f"process_hitl_flags exceeded {MAX_LOOP_ITERATIONS} iterations. "
                f"Investigate PAM-STATUS.json for {supplier_slug}."
            )
        iteration += 1

        if flag.get("status", "PENDING") != "PENDING":
            continue

        # Mark as surfaced (human will resolve)
        flag["surfaced_at"] = _utcnow_iso()
        flag["surfaced_by"] = "monica"
        flags.append(flag)

    # Write surfaced timestamps back
    if flags:
        workspace.write_pam_status(supplier_slug, {"hitl_flags": pending_flags})

    return flags


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_gate_consistency(supplier_slug: str, gate_status: dict) -> None:
    """Detect impossible gate states (e.g. Gate 2 COMPLETE but Gate 1 PENDING).

    Logs a warning but does NOT raise — Monica observes; portals enforce.
    """
    for target_gate in (2, 3):
        try:
            assert_gate_precondition(supplier_slug, target_gate, gate_status)
        except GateOrderViolation as exc:
            monica_logger.log(
                "MONICA",
                "Q",
                f"GATE CONSISTENCY WARNING for {supplier_slug}: {exc}",
            )


def _check_kelly_escalations(workspace: S3AgentWorkspace, supplier_slug: str) -> list[str]:
    """Check GLOBAL-FEEDBACK.md for Kelly sentiment escalation markers.

    Returns list of escalation thread IDs found.
    """
    try:
        content = workspace.download("GLOBAL-FEEDBACK.md").decode("utf-8")
        escalations = [
            line.split("thread_id=")[1].split()[0]
            for line in content.splitlines()
            if "SENTIMENT_ESCALATION" in line and "thread_id=" in line
        ]
        return escalations
    except FileNotFoundInWorkspace:
        return []


def _queue_escalation_for_hitl(
    supplier_slug: str,
    retailer_slug: str,
    thread_id: str,
) -> bool:
    """Write one hitl_queue row for a Kelly sentiment escalation (ADR-022).

    Idempotent: ON CONFLICT (queue_id) DO NOTHING.
    Returns True if inserted, False if already queued or DB unavailable.
    Uses psycopg2 (sync) — consistent with Kelly's dispatch_approved() pattern.
    """
    import os
    import time
    import psycopg2

    dsn = os.environ.get("CERTPORTAL_DB_URL", "")
    if not dsn:
        monica_logger.log(
            "MONICA", "A",
            "CERTPORTAL_DB_URL not set — skipping escalation HITL insert",
        )
        return False

    queue_id = f"escalation_{thread_id}_{int(time.time())}"
    draft = (
        f"SENTIMENT ESCALATION ALERT\n\n"
        f"Supplier: {supplier_slug}\n"
        f"Retailer: {retailer_slug}\n"
        f"Thread: {thread_id}\n\n"
        f"Kelly detected a negative sentiment pattern requiring human review. "
        f"Please authorize a follow-up response."
    )
    summary_text = f"Kelly sentiment escalation: {supplier_slug}/{thread_id}"

    try:
        conn = psycopg2.connect(dsn)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO hitl_queue "
                "  (queue_id, retailer_slug, supplier_slug, agent, draft, summary,"
                "   thread_id, channel, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (queue_id) DO NOTHING",
                (
                    queue_id, retailer_slug, supplier_slug,
                    "KELLY", draft, summary_text,
                    thread_id, "email", "PENDING_APPROVAL",
                ),
            )
            inserted = cur.rowcount > 0
            conn.commit()
            cur.close()
        finally:
            conn.close()
        return inserted
    except Exception as exc:
        monica_logger.log(
            "MONICA", "A",
            f"_queue_escalation_for_hitl error: {type(exc).__name__}: {exc}",
        )
        return False


def _summarise_for_hitl(draft: str) -> str:
    """Use GPT-4o-mini to create a concise HITL review summary. Single call, no retries."""
    response = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a triage assistant. Summarise the following Kelly communication "
                    "draft in 1-2 sentences for a human reviewer. Focus on tone and key action items."
                ),
            },
            {"role": "user", "content": draft[:2000]},  # Guard against huge drafts
        ],
        max_tokens=100,
        temperature=0.0,
    )
    return response.choices[0].message.content.strip()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monica — certPortal Orchestrator + HITL Keeper")
    parser.add_argument("--retailer", required=True, help="Retailer slug (e.g. elior)")
    parser.add_argument("--supplier", required=True, help="Supplier slug (e.g. acme-foods)")
    args = parser.parse_args()

    result = run(retailer_slug=args.retailer, supplier_slug=args.supplier)
    print(json.dumps(result, indent=2, default=str))
