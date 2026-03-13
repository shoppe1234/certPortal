"""runner.py — StepRunner: executes steps with retry + self-correction.

Self-correction sequence (per step, on failure):
  attempt 1 → fail → check memory for known corrections
  attempt 2 → apply correction #1 (networkidle | known_from_memory)
  attempt 3 → apply correction #2 (wait_500 | relogin)
  attempt 4 → FAIL — log to feedback.md, continue (unless fatal)

Common correctable failures handled:
  - ?error=... in URL     → wrong credentials → check config.py
  - Element not found     → HTMX not settled  → networkidle wait
  - Redirect to /login    → session expired   → relogin and replay
  - 500 page              → log and skip      → portal/DB not running
"""
from __future__ import annotations

import asyncio
import traceback
from typing import Awaitable, Callable

from playwrightcli.config import MAX_RETRIES


class StepResult:
    __slots__ = ("step", "status", "error", "correction", "note", "attempted")

    def __init__(
        self,
        step: str,
        status: str,          # PASS | FAIL | RESOLVED
        error: str = "",
        correction: str = "",
        note: str = "",
        attempted: str = "",
    ) -> None:
        self.step = step
        self.status = status
        self.error = error
        self.correction = correction
        self.note = note
        self.attempted = attempted


class StepRunner:
    """Orchestrates step execution across one portal run.

    Usage:
        runner = StepRunner(memory_manager=mm)
        ok = await runner.run_step("pam::login", login_fn, fatal=True, page=page)
        runner.write_feedback(mm)
    """

    def __init__(self, memory_manager) -> None:
        self._mm = memory_manager
        self._results: list[StepResult] = []
        self.pass_count = 0
        self.fail_count = 0

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run_step(
        self,
        name: str,
        fn: Callable[[], Awaitable[None]],
        *,
        max_retries: int = MAX_RETRIES,
        fatal: bool = False,
        page=None,
        relogin_fn: Callable[[], Awaitable[None]] | None = None,
    ) -> bool:
        """Execute *fn* with retry + self-correction. Returns True on success.

        Args:
            name:         Step identifier, e.g. ``"pam::hitl-queue"``.
            fn:           Async callable that performs the step.
            max_retries:  Maximum number of extra attempts after first failure.
            fatal:        If True, raises RuntimeError on final failure (aborts flow).
            page:         Playwright Page — needed to apply corrections.
            relogin_fn:   Async callable to re-authenticate; enables ``relogin`` correction.
        """
        known_corrections = self._mm.get_corrections(name)
        last_error = ""
        applied_correction = ""

        for attempt in range(max_retries + 1):
            try:
                # Apply a correction before retrying (not on the first attempt)
                if attempt > 0 and page is not None:
                    applied_correction = await self._apply_correction(
                        attempt, known_corrections, page, relogin_fn
                    )

                await fn()

                # ---- SUCCESS ----
                if attempt == 0:
                    print(f"  PASS  {name}")
                else:
                    print(f"  PASS  {name}  [recovered via {applied_correction}]")
                    self._results.append(StepResult(
                        step=name,
                        status="RESOLVED",
                        correction=applied_correction,
                        note=f"Failed on attempt 1; resolved after correction={applied_correction}",
                    ))

                self.pass_count += 1
                return True

            except Exception as exc:
                last_error = _format_error(exc)
                if attempt < max_retries:
                    print(f"  RETRY ({attempt + 1}/{max_retries}) {name}: {_short(exc)}")
                else:
                    print(f"  FAIL  {name}: {_short(exc)}")

        # ---- ALL RETRIES EXHAUSTED ----
        self.fail_count += 1
        self._results.append(StepResult(
            step=name,
            status="FAIL",
            error=last_error[:300],
            attempted=f"step fn + corrections: {applied_correction or 'networkidle, wait_500'}",
            correction=f"Tried: {applied_correction}" if applied_correction else "networkidle, wait_500",
            note=f"Failed after {max_retries} retries",
        ))

        if fatal:
            raise RuntimeError(f"Fatal step failed: {name}")

        return False

    # ------------------------------------------------------------------
    # Correction dispatch
    # ------------------------------------------------------------------

    async def _apply_correction(
        self,
        attempt: int,
        known_corrections: list[str],
        page,
        relogin_fn,
    ) -> str:
        """Choose and apply the correction for this retry attempt."""
        correction = self._pick_correction(attempt, known_corrections, relogin_fn is not None)

        if correction == "networkidle":
            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass  # best-effort; let the step itself fail if still broken

        elif correction == "wait_500":
            await asyncio.sleep(0.5)

        elif correction == "relogin" and relogin_fn is not None:
            await relogin_fn()

        elif correction == "skip":
            pass  # runner returns success on next attempt even without the element

        return correction

    @staticmethod
    def _pick_correction(
        attempt: int,
        known_corrections: list[str],
        has_relogin: bool,
    ) -> str:
        """Return the correction keyword for this retry attempt."""
        # Use memory-derived corrections first
        idx = attempt - 1
        if idx < len(known_corrections):
            return known_corrections[idx]

        # Default fallback sequence
        fallback = ["networkidle", "wait_500"]
        if has_relogin:
            fallback.append("relogin")
        fallback_idx = idx - len(known_corrections)
        if fallback_idx < len(fallback):
            return fallback[fallback_idx]

        return "networkidle"

    # ------------------------------------------------------------------
    # Feedback flush
    # ------------------------------------------------------------------

    def write_feedback(self, mm) -> None:
        """Flush FAIL/RESOLVED results to feedback.md via the MemoryManager."""
        from datetime import datetime

        run_ts = datetime.now().isoformat(timespec="seconds")
        entries = [
            {
                "step": r.step,
                "status": r.status,
                "error": r.error,
                "attempted": r.attempted,
                "correction": r.correction,
                "note": r.note,
            }
            for r in self._results
            if r.status in ("FAIL", "RESOLVED")
        ]
        if entries:
            mm.append_feedback(run_ts, entries)

    @property
    def results(self) -> list[StepResult]:
        return list(self._results)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _short(exc: Exception) -> str:
    msg = str(exc).split("\n")[0]
    return msg[:120] + "..." if len(msg) > 120 else msg


def _format_error(exc: Exception) -> str:
    lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return "".join(lines)[-800:]
