"""agents/kelly.py — Multi-Channel Communications.

INV-01: Kelly never imports from other agent files.
INV-04: No LangChain abstractions.

Kelly's 3-stage pipeline:
  Stage 1: Classify tone of thread (GPT-4o-mini)
  Stage 1.5: Consolidate thread memory (Gemini Flash-Lite, ADR-024) — optional
  Stage 2: Select persona from KELLY_TONE_PERSONA_MAP
  Stage 3: Draft message (GPT-4o-mini) OR queue for Monica HITL

Auto-send rules:
  - tone == "neutral" AND scenario_id in seen_scenarios (DB) → auto-send
  - All other drafts → monica.queue_for_approval()

Sentiment shift (neutral → frustrated) → GLOBAL-FEEDBACK.md + Monica HITL flag.

OpenAI usage: GPT-4o-mini for tone classification and draft generation (real calls).
Gemini usage: gemini-1.5-flash-8b for thread memory consolidation (ADR-024).

CLI: python -m agents.kelly --retailer <slug> --supplier <slug> \
         --channel <email|google_chat|ms_teams> --thread-id <id> --trigger <event>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Literal

import requests
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

    # Stage 1.5: Consolidate thread memory via Gemini Flash-Lite (ADR-024)
    # Fail-safe: missing GEMINI_API_KEY or API error returns empty summary silently.
    memory = consolidate_memory_adk(thread_id, thread_history)

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

    # Stage 3: Draft message (inject Gemini memory summary if available)
    draft = _draft_message(
        tone=tone,
        persona=persona,
        thread_history=thread_history,
        trigger_event=trigger_event,
        retailer_slug=retailer_slug,
        supplier_slug=supplier_slug,
        memory_summary=memory.get("summary", ""),
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
        "memory_consolidated": bool(memory.get("summary")),
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
# Thread memory consolidation — Gemini Flash-Lite (ADR-024)
# ---------------------------------------------------------------------------


def consolidate_memory_adk(thread_id: str, history: list[dict]) -> dict:
    """Summarise thread history using Gemini Flash-Lite (google-generativeai).

    ADR-024: always-on thread memory consolidation.
    Fail-safe: returns empty-summary dict on API error or missing GEMINI_API_KEY.
    All imports are lazy (inside function body) to avoid import-time failure when
    google-generativeai is not installed.

    Args:
        thread_id: Unique thread identifier (included in return dict).
        history:   List of message dicts (already loaded by run() from workspace).

    Returns:
        {thread_id, summary, sentiment_trend, key_exchanges, consolidated_at}
    """
    import os
    from datetime import datetime, timezone as _tz

    _empty: dict = {
        "thread_id": thread_id,
        "summary": "",
        "sentiment_trend": "unknown",
        "key_exchanges": len(history),
        "consolidated_at": None,
    }

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        monica_logger.log(
            "KELLY", "A",
            "GEMINI_API_KEY not set -- skipping memory consolidation",
        )
        return _empty

    try:
        import google.generativeai as genai  # noqa: PLC0415

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash-8b")

        history_text = "\n".join(
            f"[{m.get('role', '?')}]: {m.get('content', '')}" for m in history
        )
        prompt = (
            "Analyse this supplier-retailer communication thread.\n"
            "Respond with a JSON object (no markdown fences) with exactly these keys:\n"
            "  summary (str): 2-3 sentence narrative of the thread\n"
            "  sentiment_trend (str): one of improving | stable | deteriorating\n"
            "  key_exchanges (int): number of substantive back-and-forth exchanges\n\n"
            f"Thread:\n{history_text or '(empty thread)'}"
        )
        response = model.generate_content(prompt)
        import json as _json

        text = response.text.strip()
        # Strip optional markdown code fences Gemini may include
        if text.startswith("```"):
            text = text.split("```", 2)[-1] if text.count("```") >= 2 else text
            text = text.lstrip("json").strip().rstrip("```").strip()
        data = _json.loads(text)
        return {
            "thread_id": thread_id,
            "summary": str(data.get("summary", "")),
            "sentiment_trend": str(data.get("sentiment_trend", "unknown")),
            "key_exchanges": int(data.get("key_exchanges", len(history))),
            "consolidated_at": datetime.now(tz=_tz.utc).isoformat(),
        }
    except Exception as exc:
        monica_logger.log(
            "KELLY", "A",
            f"consolidate_memory_adk error: {type(exc).__name__}: {exc}",
        )
        return _empty


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
    memory_summary: str = "",
) -> str:
    """Draft a communication message using GPT-4o-mini. Single call, no retries.

    Args:
        memory_summary: Optional Gemini-consolidated thread summary (ADR-024).
                        Injected into context when non-empty to give GPT-4o-mini
                        a compressed view of the full thread history.
    """
    system_prompt = (
        f"You are Kelly, an EDI certification specialist at certPortal. "
        f"Your active persona is '{persona['name']}'. "
        f"Style: {persona['style']} "
        f"Always open with: \"{persona['opener']}\" "
        f"Keep responses under 200 words. Be specific, actionable, and professional. "
        f"Do not make commitments about timelines you cannot guarantee."
    )
    memory_block = (
        f"Thread summary (Gemini memory consolidation): {memory_summary}\n"
        if memory_summary else ""
    )
    context = (
        f"Trigger event: {trigger_event}\n"
        f"Retailer: {retailer_slug} | Supplier: {supplier_slug}\n"
        f"{memory_block}"
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


# ---------------------------------------------------------------------------
# Channel dispatch helpers (ADR-020)
# All helpers are fail-safe: missing env var → log warning + return, never raises.
# ---------------------------------------------------------------------------


def _dispatch_email(draft: str, retailer_slug: str, supplier_slug: str) -> None:
    """Send draft via SMTP (ADR-020). Env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM."""
    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("SMTP_FROM", "certportal@example.com")

    if not host or not user:
        monica_logger.log(
            "KELLY", "A",
            "DISPATCH email: SMTP_HOST/SMTP_USER not configured — skipping",
            retailer_slug=retailer_slug, supplier_slug=supplier_slug,
        )
        return

    msg = MIMEText(draft, "plain", "utf-8")
    msg["Subject"] = f"certPortal update — {retailer_slug}/{supplier_slug}"
    msg["From"] = from_addr
    msg["To"] = user  # in practice, supplier contact email from DB

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.sendmail(from_addr, [user], msg.as_string())
        monica_logger.log(
            "KELLY", "A",
            f"DISPATCH email sent to {user} (retailer={retailer_slug})",
            retailer_slug=retailer_slug, supplier_slug=supplier_slug,
        )
    except Exception as exc:  # noqa: BLE001
        monica_logger.log(
            "KELLY", "A",
            f"DISPATCH email failed: {type(exc).__name__}: {exc}",
            retailer_slug=retailer_slug, supplier_slug=supplier_slug,
        )


def _dispatch_google_chat(draft: str, thread_id: str, retailer_slug: str, supplier_slug: str) -> None:
    """Send draft to Google Chat thread (ADR-020). Env: KELLY_GOOGLE_CHAT_OAUTH_TOKEN_{RETAILER}."""
    token_key = f"KELLY_GOOGLE_CHAT_OAUTH_TOKEN_{retailer_slug.upper()}"
    token = os.environ.get(token_key, "")

    if not token:
        monica_logger.log(
            "KELLY", "A",
            f"DISPATCH google_chat: {token_key} not configured — skipping",
            retailer_slug=retailer_slug, supplier_slug=supplier_slug,
        )
        return

    url = f"https://chat.googleapis.com/v1/spaces/{thread_id}/messages"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"text": draft},
            timeout=10,
        )
        resp.raise_for_status()
        monica_logger.log(
            "KELLY", "A",
            f"DISPATCH google_chat sent to thread={thread_id} (status={resp.status_code})",
            retailer_slug=retailer_slug, supplier_slug=supplier_slug,
        )
    except Exception as exc:  # noqa: BLE001
        monica_logger.log(
            "KELLY", "A",
            f"DISPATCH google_chat failed: {type(exc).__name__}: {exc}",
            retailer_slug=retailer_slug, supplier_slug=supplier_slug,
        )


def _dispatch_teams(draft: str, retailer_slug: str, supplier_slug: str) -> None:
    """Send draft to Microsoft Teams via incoming webhook (ADR-020). Env: KELLY_TEAMS_WEBHOOK_{RETAILER}."""
    webhook_key = f"KELLY_TEAMS_WEBHOOK_{retailer_slug.upper()}"
    webhook_url = os.environ.get(webhook_key, "")

    if not webhook_url:
        monica_logger.log(
            "KELLY", "A",
            f"DISPATCH teams: {webhook_key} not configured — skipping",
            retailer_slug=retailer_slug, supplier_slug=supplier_slug,
        )
        return

    try:
        resp = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json"},
            json={"text": draft},
            timeout=10,
        )
        resp.raise_for_status()
        monica_logger.log(
            "KELLY", "A",
            f"DISPATCH teams sent via webhook (status={resp.status_code})",
            retailer_slug=retailer_slug, supplier_slug=supplier_slug,
        )
    except Exception as exc:  # noqa: BLE001
        monica_logger.log(
            "KELLY", "A",
            f"DISPATCH teams failed: {type(exc).__name__}: {exc}",
            retailer_slug=retailer_slug, supplier_slug=supplier_slug,
        )


def _dispatch_message(
    channel: ChannelType,
    thread_id: str,
    draft: str,
    supplier_slug: str,
    retailer_slug: str,
) -> None:
    """Dispatch approved message to channel (ADR-020).

    Routes to the appropriate helper. Missing env config → log + return (never raises).
    """
    monica_logger.log(
        "KELLY", "A",
        f"DISPATCH: channel={channel} thread={thread_id} supplier={supplier_slug} len={len(draft)}",
        retailer_slug=retailer_slug, supplier_slug=supplier_slug,
    )
    if channel == "email":
        _dispatch_email(draft, retailer_slug, supplier_slug)
    elif channel == "google_chat":
        _dispatch_google_chat(draft, thread_id, retailer_slug, supplier_slug)
    elif channel == "ms_teams":
        _dispatch_teams(draft, retailer_slug, supplier_slug)
    else:
        monica_logger.log(
            "KELLY", "A",
            f"DISPATCH: unknown channel {channel!r} — no action taken",
            retailer_slug=retailer_slug, supplier_slug=supplier_slug,
        )


def dispatch_approved() -> int:
    """Query hitl_queue for APPROVED rows and dispatch each via _dispatch_message().

    Returns the number of messages dispatched.
    CLI: python -m agents.kelly --dispatch-approved
    """
    import psycopg2
    import psycopg2.extras

    dsn = os.environ.get("CERTPORTAL_DB_URL", "")
    if not dsn:
        monica_logger.log("KELLY", "A", "dispatch_approved: CERTPORTAL_DB_URL not set — skipping")
        return 0

    dispatched = 0
    try:
        conn = psycopg2.connect(dsn)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT queue_id, retailer_slug, supplier_slug, agent, draft, "
                "thread_id, channel FROM hitl_queue WHERE status = 'APPROVED'"
            )
            rows = cur.fetchall()
            cur.close()
        finally:
            conn.close()

        for row in rows:
            _dispatch_message(
                channel=row["channel"] or "email",
                thread_id=row["thread_id"] or "",
                draft=row["draft"],
                supplier_slug=row["supplier_slug"],
                retailer_slug=row["retailer_slug"],
            )
            dispatched += 1

    except Exception as exc:  # noqa: BLE001
        monica_logger.log("KELLY", "A", f"dispatch_approved failed: {type(exc).__name__}: {exc}")

    return dispatched


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kelly — Multi-Channel Communications")
    parser.add_argument("--retailer", help="Retailer slug (required unless --dispatch-approved)")
    parser.add_argument("--supplier", help="Supplier slug (required unless --dispatch-approved)")
    parser.add_argument("--channel", choices=["email", "google_chat", "ms_teams"],
                        help="Channel (required unless --dispatch-approved)")
    parser.add_argument("--thread-id", help="Thread ID")
    parser.add_argument("--trigger", help="Trigger event string")
    parser.add_argument("--dispatch-approved", action="store_true",
                        help="Dispatch all APPROVED hitl_queue rows and exit (ADR-020)")
    args = parser.parse_args()

    if args.dispatch_approved:
        count = dispatch_approved()
        print(json.dumps({"dispatched": count}))
    else:
        if not (args.retailer and args.supplier and args.channel):
            parser.error("--retailer, --supplier, --channel are required unless --dispatch-approved is set")
        result = run(
            retailer_slug=args.retailer,
            supplier_slug=args.supplier,
            channel=args.channel,
            thread_id=args.thread_id or "",
            trigger_event=args.trigger or "",
        )
        print(json.dumps(result, indent=2, default=str))
