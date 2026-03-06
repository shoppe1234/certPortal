"""agents/kelly.py — Multi-Channel Communications.

INV-01: Kelly never imports from other agent files.
INV-04: No LangChain abstractions.

Kelly's 3-stage pipeline:
  Stage 1: Classify tone of thread (GPT-4o-mini)
  Stage 2: Select persona from KELLY_TONE_PERSONA_MAP
  Stage 3: Draft message (GPT-4o-mini) OR queue for Monica HITL

Auto-send rules:
  - tone == "neutral" AND scenario_id in seen_scenarios (DB) → auto-send
  - All other drafts → monica.queue_for_approval()

Sentiment shift (neutral → frustrated) → GLOBAL-FEEDBACK.md + Monica HITL flag.

OpenAI usage: GPT-4o-mini for tone classification and draft generation (real calls).

Sprint 2 stub: consolidate_memory_adk() — Google ADK + Gemini Flash-Lite.

CLI: python -m agents.kelly --retailer <slug> --supplier <slug> \
         --channel <email|google_chat|ms_teams> --thread-id <id> --trigger <event>
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Literal

from openai import OpenAI

from certportal.core import monica_logger
from certportal.core.config import settings
from certportal.core.workspace import S3AgentWorkspace, FileNotFoundInWorkspace

_openai_client = OpenAI(api_key=settings.openai_api_key)

# ---------------------------------------------------------------------------
# Persona map
# ---------------------------------------------------------------------------

KELLY_TONE_PERSONA_MAP: dict[str, dict[str, str]] = {
    "frustrated": {
        "name": "De-escalation Kelly",
        "style": "Calm, validating, immediate fix path. Never defensive.",
        "opener": "I completely understand how frustrating this has been.",
    },
    "neutral": {
        "name": "Precise Kelly",
        "style": "Bullet-pointed, segment-level technical detail.",
        "opener": "Here's what the validation result shows:",
    },
    "warm": {
        "name": "Enthusiastic Kelly",
        "style": "Energetic, progress-affirming, forward-looking.",
        "opener": "Great progress — you're almost there!",
    },
    "formal": {
        "name": "Professional Kelly",
        "style": "Measured, no commitments, escalation path clearly stated.",
        "opener": "Thank you for your message. I am reviewing your submission.",
    },
}

ToneLabel = Literal["frustrated", "neutral", "warm", "formal"]
ChannelType = Literal["email", "google_chat", "ms_teams"]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run(
    retailer_slug: str,
    supplier_slug: str,
    channel: ChannelType,
    thread_id: str,
    trigger_event: str,
) -> dict:
    """Kelly's full communication pipeline.

    Returns:
        {
            "draft": str,
            "tone": str,
            "persona": str,
            "queued_for_hitl": bool,
            "queue_id": str | None,
        }
    """
    monica_logger.log(
        "KELLY",
        "A",
        f"Communication run started. supplier={supplier_slug} channel={channel} "
        f"thread={thread_id} trigger={trigger_event}",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    workspace = S3AgentWorkspace(retailer_slug, supplier_slug)

    # Load thread history from workspace
    thread_history = _load_thread_history(workspace, thread_id)
    previous_tone = _get_previous_tone(workspace, thread_id)

    # Stage 1: Classify tone
    compressed = compress_thread(thread_history, max_tokens=200)
    tone = classify_tone(compressed)

    # Detect sentiment escalation (neutral → frustrated)
    if previous_tone == "neutral" and tone == "frustrated":
        _record_sentiment_escalation(workspace, thread_id, supplier_slug)
        monica_logger.log(
            "KELLY",
            "Q",
            f"SENTIMENT_ESCALATION detected: thread_id={thread_id} "
            f"neutral→frustrated. HITL flag written.",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )

    # Persist current tone
    _save_current_tone(workspace, thread_id, tone)

    # Stage 2: Select persona
    persona = KELLY_TONE_PERSONA_MAP[tone]
    monica_logger.log(
        "KELLY",
        "A",
        f"Tone classified: {tone}. Persona: {persona['name']}",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    # Stage 3: Draft message
    draft = _draft_message(
        tone=tone,
        persona=persona,
        thread_history=thread_history,
        trigger_event=trigger_event,
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )

    # Decide: auto-send or queue for HITL
    scenario_id = _derive_scenario_id(trigger_event, thread_id)
    should_auto_send = tone == "neutral" and asyncio.run(
        _scenario_in_seen(retailer_slug, supplier_slug, scenario_id)
    )

    queued_for_hitl = False
    queue_id: str | None = None

    if should_auto_send:
        # Auto-send path — channel dispatch (Sprint 1: logged only)
        _dispatch_message(channel, thread_id, draft, supplier_slug, retailer_slug)
        monica_logger.log(
            "KELLY",
            "A",
            f"Auto-sent draft to {channel} thread {thread_id} (neutral, seen scenario).",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )
    else:
        # INV-01: never import from agents.monica — write queue entry directly.
        # _queue_for_monica_hitl replicates Monica's HITL queue logic in-process.
        queue_id = _queue_for_monica_hitl(
            draft=draft,
            thread_id=thread_id,
            channel=channel,
            supplier_slug=supplier_slug,
            retailer_slug=retailer_slug,
            workspace=workspace,
        )
        queued_for_hitl = True
        monica_logger.log(
            "KELLY",
            "Q",
            f"Draft queued for HITL approval. queue_id={queue_id}",
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )

    return {
        "draft": draft,
        "tone": tone,
        "persona": persona["name"],
        "queued_for_hitl": queued_for_hitl,
        "queue_id": queue_id,
    }


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def compress_thread(thread_history: list[dict], max_tokens: int = 200) -> str:
    """Compress thread to max_tokens via deterministic truncation.

    Concatenates messages (newest last) and truncates by character estimate
    (1 token ≈ 4 characters for English EDI communications).
    """
    max_chars = max_tokens * 4
    parts: list[str] = []
    total = 0
    for msg in reversed(thread_history):
        line = f"[{msg.get('role', 'user')}]: {msg.get('content', '')}"
        if total + len(line) > max_chars:
            remaining = max_chars - total
            if remaining > 0:
                parts.insert(0, line[:remaining] + "…")
            break
        parts.insert(0, line)
        total += len(line) + 1
    return "\n".join(parts)


def classify_tone(compressed_thread: str) -> ToneLabel:
    """Classify thread tone via single GPT-4o-mini call. No retry loops.

    Returns one of: "frustrated", "neutral", "warm", "formal"
    """
    response = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a tone classifier for B2B EDI support communications. "
                    "Given a supplier communication thread, classify the overall tone as exactly "
                    "one of: frustrated, neutral, warm, formal. "
                    "Return only the single word label. Nothing else."
                ),
            },
            {"role": "user", "content": compressed_thread or "(empty thread)"},
        ],
        max_tokens=5,
        temperature=0.0,
    )
    raw = response.choices[0].message.content.strip().lower()
    valid: set[str] = {"frustrated", "neutral", "warm", "formal"}
    if raw in valid:
        return raw  # type: ignore[return-value]
    # Default to neutral if unexpected output
    return "neutral"


# ---------------------------------------------------------------------------
# Sprint 2 stub
# ---------------------------------------------------------------------------


def consolidate_memory_adk(thread_id: str) -> dict:
    # TODO Sprint 2: Google ADK + Gemini Flash-Lite for always-on thread memory
    raise NotImplementedError("Sprint 2: Google ADK integration")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_thread_history(workspace: S3AgentWorkspace, thread_id: str) -> list[dict]:
    """Load thread message history from workspace. Returns empty list if absent."""
    try:
        raw = workspace.download(f"threads/{thread_id}.json")
        return json.loads(raw.decode("utf-8"))
    except FileNotFoundInWorkspace:
        return []


def _get_previous_tone(workspace: S3AgentWorkspace, thread_id: str) -> str | None:
    """Get the tone from the previous Kelly run for this thread."""
    try:
        raw = workspace.download(f"threads/{thread_id}_tone.json")
        return json.loads(raw.decode("utf-8")).get("tone")
    except FileNotFoundInWorkspace:
        return None


def _save_current_tone(workspace: S3AgentWorkspace, thread_id: str, tone: str) -> None:
    workspace.upload(
        f"threads/{thread_id}_tone.json",
        json.dumps({"tone": tone, "updated_at": _utcnow_iso()}),
    )


def _record_sentiment_escalation(
    workspace: S3AgentWorkspace,
    thread_id: str,
    supplier_slug: str,
) -> None:
    """Write escalation to GLOBAL-FEEDBACK.md and PAM-STATUS.json."""
    workspace.append_log(
        "GLOBAL-FEEDBACK.md",
        f"[{_utcnow_iso()}] [KELLY] SENTIMENT_ESCALATION thread_id={thread_id} "
        f"supplier={supplier_slug}",
    )
    workspace.write_pam_status(
        supplier_slug,
        {
            "hitl_flags": {
                f"kelly_escalation_{thread_id}": {
                    "agent": "kelly",
                    "reason": f"Sentiment escalation: neutral→frustrated on thread {thread_id}",
                    "thread_id": thread_id,
                    "status": "PENDING",
                    "flagged_at": _utcnow_iso(),
                }
            }
        },
    )


def _draft_message(
    tone: str,
    persona: dict,
    thread_history: list[dict],
    trigger_event: str,
    retailer_slug: str,
    supplier_slug: str,
) -> str:
    """Draft a communication message using GPT-4o-mini. Single call, no retries."""
    system_prompt = (
        f"You are Kelly, an EDI certification specialist at certPortal. "
        f"Your active persona is '{persona['name']}'. "
        f"Style: {persona['style']} "
        f"Always open with: \"{persona['opener']}\" "
        f"Keep responses under 200 words. Be specific, actionable, and professional. "
        f"Do not make commitments about timelines you cannot guarantee."
    )
    context = (
        f"Trigger event: {trigger_event}\n"
        f"Retailer: {retailer_slug} | Supplier: {supplier_slug}\n"
        f"Recent thread (last 3 messages):\n"
        + "\n".join(
            f"[{m.get('role', '?')}]: {m.get('content', '')}"
            for m in thread_history[-3:]
        )
    )
    response = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ],
        max_tokens=300,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def _queue_for_monica_hitl(
    draft: str,
    thread_id: str,
    channel: str,
    supplier_slug: str,
    retailer_slug: str,
    workspace: S3AgentWorkspace,
) -> str:
    """Write HITL queue entry directly to PAM-STATUS.json (INV-01 compliant).

    Monica reads this and surfaces it in the Pam portal.
    Uses a short GPT-4o-mini summary for human reviewers.
    """
    import uuid

    queue_id = str(uuid.uuid4())

    # Brief summary for human review
    try:
        resp = _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Summarise this Kelly draft in 1-2 sentences for a human reviewer.",
                },
                {"role": "user", "content": draft[:1000]},
            ],
            max_tokens=80,
            temperature=0.0,
        )
        summary = resp.choices[0].message.content.strip()
    except Exception:  # noqa: BLE001
        summary = draft[:120] + "…"

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
    return queue_id


def _derive_scenario_id(trigger_event: str, thread_id: str) -> str:
    """Derive a stable scenario ID from trigger event."""
    return f"{trigger_event.split(':')[0]}_{thread_id.split('-')[0]}"


async def _scenario_in_seen(
    retailer_slug: str,
    supplier_slug: str,
    scenario_id: str,
) -> bool:
    """Check if scenario_id exists in seen_scenarios DB table."""
    try:
        from certportal.core.database import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM seen_scenarios WHERE supplier_slug=$1 AND retailer_slug=$2 AND scenario_id=$3",
                supplier_slug,
                retailer_slug,
                scenario_id,
            )
            return row is not None
    except Exception:  # noqa: BLE001
        return False


def _dispatch_message(
    channel: ChannelType,
    thread_id: str,
    draft: str,
    supplier_slug: str,
    retailer_slug: str,
) -> None:
    """Dispatch approved message to channel. Sprint 1: logs only.
    Sprint 2: real Google Chat / Teams / email dispatch.
    """
    # TODO Sprint 2: implement real channel dispatch via OAuth tokens
    monica_logger.log(
        "KELLY",
        "A",
        f"DISPATCH (Sprint 1 stub): channel={channel} thread={thread_id} "
        f"supplier={supplier_slug} message_length={len(draft)}",
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
    )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kelly — Multi-Channel Communications")
    parser.add_argument("--retailer", required=True)
    parser.add_argument("--supplier", required=True)
    parser.add_argument("--channel", required=True, choices=["email", "google_chat", "ms_teams"])
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--trigger", required=True, help="Trigger event string")
    args = parser.parse_args()

    result = run(
        retailer_slug=args.retailer,
        supplier_slug=args.supplier,
        channel=args.channel,
        thread_id=args.thread_id,
        trigger_event=args.trigger,
    )
    print(json.dumps(result, indent=2, default=str))
