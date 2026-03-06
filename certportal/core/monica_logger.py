"""certportal/core/monica_logger.py — MONICA-MEMORY.md append-only writer + DB mirror.

INV-05: This module ONLY appends to MONICA-MEMORY.md via S3AgentWorkspace.append_log().
        The file is NEVER opened with mode "w" or "r+" anywhere in this codebase.

Dual-write:
  1. Appends formatted entry to certportal-workspaces/admin/MONICA-MEMORY.md (S3)
  2. Inserts row into monica_memory PostgreSQL table (best-effort, non-blocking)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Literal


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(
    agent: str,
    direction: Literal["Q", "A"],
    message: str,
    retailer_slug: str | None = None,
    supplier_slug: str | None = None,
) -> None:
    """Append a log entry and mirror to DB.

    Entry format:
        [2026-03-05T14:32:17Z] [KELLY] [Q] {message}

    S3 destination: certportal-workspaces/admin/MONICA-MEMORY.md
    DB destination: monica_memory table

    Failures in either write are caught and printed — they must not crash agents.
    """
    from certportal.core.workspace import S3AgentWorkspace  # late import avoids circular

    timestamp = _utcnow_iso()
    entry = f"[{timestamp}] [{agent.upper()}] [{direction}] {message}"

    # 1. Append to S3 MONICA-MEMORY.md (INV-05: append_log only, never "w")
    try:
        # Use retailer_slug or "admin" as the retailer context; supplier_slug is None
        # so workspace has no supplier scope — admin-level operation
        workspace = S3AgentWorkspace(retailer_slug=retailer_slug or "admin")
        workspace.append_log("MONICA-MEMORY.md", entry)
    except Exception as exc:  # noqa: BLE001
        print(f"[MONICA-LOGGER][S3 WRITE FAIL] {exc!r} — entry: {entry}")

    # 2. Mirror to PostgreSQL (best-effort, non-blocking)
    try:
        _db_insert_sync(
            timestamp=timestamp,
            agent=agent.upper(),
            direction=direction,
            message=message,
            retailer_slug=retailer_slug,
            supplier_slug=supplier_slug,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[MONICA-LOGGER][DB WRITE FAIL] {exc!r} — entry: {entry}")


def _db_insert_sync(
    timestamp: str,
    agent: str,
    direction: str,
    message: str,
    retailer_slug: str | None,
    supplier_slug: str | None,
) -> None:
    """Synchronous wrapper that schedules the async DB insert."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(
                _db_insert_async(
                    timestamp, agent, direction, message, retailer_slug, supplier_slug
                )
            )
        else:
            loop.run_until_complete(
                _db_insert_async(
                    timestamp, agent, direction, message, retailer_slug, supplier_slug
                )
            )
    except RuntimeError:
        asyncio.run(
            _db_insert_async(
                timestamp, agent, direction, message, retailer_slug, supplier_slug
            )
        )


async def _db_insert_async(
    timestamp: str,
    agent: str,
    direction: str,
    message: str,
    retailer_slug: str | None,
    supplier_slug: str | None,
) -> None:
    from certportal.core.database import get_pool  # late import avoids circular

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO monica_memory
                (timestamp, agent, direction, message, retailer_slug, supplier_slug)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
            agent,
            direction,
            message,
            retailer_slug,
            supplier_slug,
        )
