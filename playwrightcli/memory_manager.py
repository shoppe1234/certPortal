"""memory_manager.py — feedback.md + memory.md I/O for the self-correcting run loop.

feedback.md  — append-only failure/correction log (one section per run).
memory.md    — synthesized knowledge; rewritten on consolidation, read before each run.

Correction keywords the runner understands:
  networkidle  wait_for_load_state('networkidle') before step retry
  wait_500     asyncio.sleep(0.5) before step retry
  relogin      re-authenticate and replay step
  skip         accept absence of element (page may be legitimately empty)
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).parent

FEEDBACK_FILE = _HERE / "feedback.md"
MEMORY_FILE = _HERE / "memory.md"

# Correction keywords the runner can act on
CORRECTION_KEYWORDS = {"networkidle", "wait_500", "relogin", "skip"}


class MemoryManager:
    """Loads memory.md, appends to feedback.md, consolidates on demand."""

    def __init__(self) -> None:
        self._memory_text = ""
        self._load()

    # ------------------------------------------------------------------
    # Memory read helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if MEMORY_FILE.exists():
            self._memory_text = MEMORY_FILE.read_text(encoding="utf-8")
        else:
            self._memory_text = ""

    def get_corrections(self, step_name: str) -> list[str]:
        """Return ordered list of correction keywords for a step from memory.md.

        Checks both the exact step name (e.g. ``pam::hitl-queue``) and the
        ``all::`` shared pattern (e.g. ``all::htmx``).
        """
        corrections: list[str] = []
        portal, _, short = step_name.partition("::")
        search_terms = {step_name, f"all::{short}"}

        for line in self._memory_text.splitlines():
            if any(t in line for t in search_terms):
                for kw in CORRECTION_KEYWORDS:
                    if kw in line.lower() and kw not in corrections:
                        corrections.append(kw)
        return corrections

    def get_memory_lines(self) -> list[str]:
        """Return non-blank lines from memory.md (used by dry-run display)."""
        return [ln for ln in self._memory_text.splitlines() if ln.strip()]

    # ------------------------------------------------------------------
    # Feedback write (append-only)
    # ------------------------------------------------------------------

    def append_feedback(self, run_timestamp: str, entries: list[dict]) -> None:
        """Append a run's FAIL/RESOLVED entries to feedback.md."""
        if not entries:
            return

        lines: list[str] = [f"\n## Run {run_timestamp}"]
        for e in entries:
            status = e.get("status", "FAIL")
            step = e.get("step", "unknown")
            lines.append(f"### {status} {step}")
            if e.get("attempted"):
                lines.append(f"  attempted: {e['attempted']}")
            if e.get("error"):
                lines.append(f"  error: {e['error']}")
            if e.get("correction"):
                lines.append(f"  correction: {e['correction']}")
            if e.get("note"):
                lines.append(f"  note: {e['note']}")

        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    # ------------------------------------------------------------------
    # Consolidation — rewrites memory.md from feedback.md
    # ------------------------------------------------------------------

    def consolidate(self) -> None:
        """Read all feedback.md entries, deduplicate by step, rewrite memory.md.

        Runs automatically at the start of each CLI invocation (merges new
        feedback into memory so subsequent steps benefit immediately).
        """
        if not FEEDBACK_FILE.exists():
            return

        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8")
        patterns = self._parse_feedback(feedback_text)
        if not patterns:
            return

        self._write_memory(patterns)
        self._load()  # refresh in-memory cache

    def _parse_feedback(self, text: str) -> dict[str, dict]:
        """Parse feedback.md into {step_name: {status, error, correction, note}}."""
        patterns: dict[str, dict] = {}
        current_step: str | None = None
        current_entry: dict = {}

        for line in text.splitlines():
            m = re.match(r"^### (FAIL|RESOLVED) (.+)$", line)
            if m:
                # Save previous entry
                if current_step:
                    # Later entries (same run or subsequent runs) overwrite earlier ones.
                    # A RESOLVED entry always supersedes a FAIL for the same step.
                    existing = patterns.get(current_step, {})
                    if existing.get("status") != "RESOLVED" or current_entry.get("status") == "RESOLVED":
                        patterns[current_step] = current_entry
                current_step = m.group(2).strip()
                current_entry = {"status": m.group(1)}
            elif current_step:
                kv = re.match(r"^\s+(\w+):\s+(.+)$", line)
                if kv:
                    current_entry[kv.group(1)] = kv.group(2).strip()

        # Flush last entry
        if current_step and current_entry:
            existing = patterns.get(current_step, {})
            if existing.get("status") != "RESOLVED" or current_entry.get("status") == "RESOLVED":
                patterns[current_step] = current_entry

        return patterns

    def _write_memory(self, patterns: dict[str, dict]) -> None:
        shared = {k: v for k, v in patterns.items() if k.startswith("all::")}
        portal_specific = {k: v for k, v in patterns.items() if not k.startswith("all::")}

        lines: list[str] = [
            "# certPortal Playwright Memory",
            "",
            "<!-- Auto-generated by playwrightcli --consolidate. Hand-editable. -->",
            "",
        ]

        # Preserve any existing hand-written shared patterns not in feedback
        existing_shared = self._extract_existing_shared()
        merged_shared = {**existing_shared, **shared}  # feedback wins on conflict

        if merged_shared:
            lines.append("## Shared Patterns")
            for step, info in merged_shared.items():
                correction = info.get("correction_applied") or info.get("correction", "")
                note = info.get("note", "")
                lines.append(f"- {step}: {note}")
                if correction:
                    lines.append(f"  Correction: {correction}")
            lines.append("")

        if portal_specific:
            lines.append("## Portal-Specific Patterns")
            for step, info in portal_specific.items():
                correction = info.get("correction_applied") or info.get("correction", "")
                note = info.get("note", "")
                status = info.get("status", "FAIL")
                lines.append(f"- {step}: {note or 'failure recorded'}")
                if correction:
                    lines.append(f"  Correction: {correction}")
                if status == "RESOLVED":
                    lines.append(f"  Status: RESOLVED — correction succeeded")
            lines.append("")

        MEMORY_FILE.write_text("\n".join(lines), encoding="utf-8")

    def _extract_existing_shared(self) -> dict[str, dict]:
        """Pull existing all:: entries out of current memory.md (preserve hand edits)."""
        result: dict[str, dict] = {}
        if not self._memory_text:
            return result
        for line in self._memory_text.splitlines():
            m = re.match(r"^- (all::\S+):\s+(.*)$", line)
            if m:
                result[m.group(1)] = {"note": m.group(2)}
        return result
