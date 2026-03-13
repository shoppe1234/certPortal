"""observer.py — Real-time design observer that runs concurrently with Playwright flows.

Architecture: asyncio producer-consumer.
  - Producer: BaseFlow.screenshot() pushes (portal, step, png_bytes) to an asyncio.Queue
  - Consumer: DesignObserver.run() pulls frames, sends to Claude Vision API, streams analysis

The observer accumulates context across frames — it sees the *sequence* of states, not
isolated snapshots, so it can reason about transitions, layout consistency across pages,
and whether HTMX partial renders settled correctly.

Output: screenshots/{portal}/{step}.png  +  design_review_{portal}.md
"""
from __future__ import annotations

import asyncio
import base64
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Where screenshots and analysis reports land
SCREENSHOT_DIR = Path(__file__).parent.parent / "screenshots"
REVIEW_DIR = Path(__file__).parent.parent / "design_reviews"

DESIGN_REVIEW_SYSTEM = """\
You are a senior UI/UX design reviewer specializing in modern SaaS web applications.
You are reviewing a live portal being navigated in real-time via Playwright.
You receive screenshots sequentially as the user navigates through the application.

Your analysis framework:

1. **Visual Hierarchy & Typography**
   - Font size scale, weight contrast, heading/body separation
   - Readability: contrast ratios (WCAG AA minimum), line height, letter spacing
   - Monospace vs sans-serif appropriateness for data density

2. **Spacing & Layout**
   - Consistency with an 4/8px grid system (Tailwind convention)
   - Whitespace balance: too dense vs too sparse for the portal's role
   - Responsive readiness: will this break at narrower viewports?

3. **Color System**
   - Semantic consistency: do success/warn/error colors mean the same thing everywhere?
   - Contrast against backgrounds (especially light text on dark, or amber on white)
   - Overuse of brand color vs neutral palette balance

4. **Component Quality**
   - Buttons: touch target size (minimum 44x44px), visual affordance, state feedback
   - Tables: header distinction, row hover states, empty states
   - Cards: shadow/border consistency, padding regularity
   - Badges/pills: legibility at small sizes, padding balance

5. **Tailwind CSS Migration Path**
   - Map current custom CSS patterns to Tailwind utility equivalents
   - Identify where Tailwind's design tokens would enforce better consistency
   - Note where custom CSS is doing something Tailwind handles out of the box

6. **Anthropic / Modern SaaS Best Practices**
   - Clean, purposeful interfaces — no decoration without function
   - Information density appropriate to user role (admin=dense, supplier=guided)
   - Progressive disclosure over overwhelming dashboards
   - Accessible by default: focus indicators, screen reader landmarks, color-blind safe

Build your analysis incrementally. Each screenshot adds to your understanding.
When you see a new page, note how it relates to the previous one (navigation consistency,
visual language continuity, header/footer persistence).
"""


class ObserverFrame:
    """One captured frame from a Playwright step."""
    __slots__ = ("portal", "step", "png_bytes", "url", "timestamp")

    def __init__(self, portal: str, step: str, png_bytes: bytes, url: str) -> None:
        self.portal = portal
        self.step = step
        self.png_bytes = png_bytes
        self.url = url
        self.timestamp = datetime.now().isoformat(timespec="seconds")


class DesignObserver:
    """Consumes screenshots from a queue and analyzes them via Claude Vision API.

    Usage (from cli.py):
        queue = asyncio.Queue()
        observer = DesignObserver(queue)
        # Start consumer task alongside Playwright flows
        consumer = asyncio.create_task(observer.run())
        # ... flows push frames via queue ...
        await queue.put(None)  # sentinel to stop consumer
        await consumer
        observer.write_reports()
    """

    def __init__(self, queue: asyncio.Queue, *, use_api: bool = True) -> None:
        self._queue = queue
        self._use_api = use_api and bool(os.environ.get("ANTHROPIC_API_KEY"))
        # Per-portal accumulation: portal_name -> list of analysis chunks
        self._portal_frames: dict[str, list[ObserverFrame]] = {}
        self._portal_analyses: dict[str, list[str]] = {}
        self._frame_count = 0

    async def run(self) -> None:
        """Consumer loop — runs until a None sentinel arrives on the queue."""
        print("  [observer] Design observer started")

        while True:
            frame = await self._queue.get()
            if frame is None:
                break

            self._frame_count += 1
            portal = frame.portal
            step = frame.step

            # Save screenshot to disk
            self._save_screenshot(frame)

            # Accumulate frames per portal
            self._portal_frames.setdefault(portal, []).append(frame)
            self._portal_analyses.setdefault(portal, [])

            print(f"  [observer] Frame {self._frame_count}: {portal}::{step} ({len(frame.png_bytes)} bytes)")

            # Analyze via Claude Vision API if available
            if self._use_api:
                analysis = await self._analyze_frame(frame)
                if analysis:
                    self._portal_analyses[portal].append(analysis)
                    # Print a one-line summary to stdout
                    first_line = analysis.split("\n")[0][:100]
                    print(f"  [observer] Analysis: {first_line}")

        print(f"  [observer] Observer finished — {self._frame_count} frames captured")

    def _save_screenshot(self, frame: ObserverFrame) -> None:
        """Write PNG to screenshots/{portal}/{step}.png."""
        portal_dir = SCREENSHOT_DIR / frame.portal
        portal_dir.mkdir(parents=True, exist_ok=True)
        # Sanitize step name for filename
        safe_step = frame.step.replace("::", "_").replace("/", "_")
        path = portal_dir / f"{safe_step}.png"
        path.write_bytes(frame.png_bytes)

    async def _analyze_frame(self, frame: ObserverFrame) -> str:
        """Send a screenshot to Claude Vision API and get design analysis."""
        try:
            import anthropic
        except ImportError:
            print("  [observer] anthropic SDK not installed — skipping API analysis")
            self._use_api = False
            return ""

        client = anthropic.Anthropic()
        b64_data = base64.standard_b64encode(frame.png_bytes).decode("ascii")

        portal_history = self._portal_frames.get(frame.portal, [])
        frame_index = len(portal_history)

        # Build message content: the current screenshot + context about sequence
        user_content: list[dict] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64_data,
                },
            },
            {
                "type": "text",
                "text": (
                    f"Portal: {frame.portal} | Step: {frame.step} | URL: {frame.url}\n"
                    f"Frame {frame_index} of this portal's session.\n"
                    f"Timestamp: {frame.timestamp}\n\n"
                    "Analyze this page's design against modern SaaS best practices. "
                    "Be specific about CSS improvements — reference exact visual elements "
                    "you see. If this is not the first frame, note consistency with "
                    "previous pages in this portal.\n\n"
                    "Format: bullet points grouped by category. Lead with the most "
                    "impactful findings. Include Tailwind utility class equivalents "
                    "where a custom CSS pattern could be replaced."
                ),
            },
        ]

        # Include previous analysis as assistant context for rolling state
        messages: list[dict] = []
        prior = self._portal_analyses.get(frame.portal, [])
        if prior:
            messages.append({
                "role": "assistant",
                "content": f"[Prior analysis for {frame.portal} portal — {len(prior)} pages reviewed so far]\n\n"
                           + "\n---\n".join(prior[-3:]),  # last 3 analyses for context window
            })

        messages.append({"role": "user", "content": user_content})

        try:
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=1500,
                system=DESIGN_REVIEW_SYSTEM,
                messages=messages,
            )
            return response.content[0].text
        except Exception as exc:
            print(f"  [observer] Claude API error: {exc}")
            return ""

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def write_reports(self) -> None:
        """Write per-portal design review markdown files."""
        if not self._portal_analyses:
            return

        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for portal, analyses in self._portal_analyses.items():
            if not analyses:
                continue

            frames = self._portal_frames.get(portal, [])
            report_path = REVIEW_DIR / f"design_review_{portal}_{timestamp}.md"

            lines = [
                f"# Design Review: {portal.upper()} Portal",
                f"",
                f"Generated: {datetime.now().isoformat(timespec='seconds')}",
                f"Frames analyzed: {len(frames)}",
                f"Pages visited: {', '.join(f.step for f in frames)}",
                f"",
                f"---",
                f"",
            ]

            for i, (frame, analysis) in enumerate(zip(frames, analyses)):
                lines.extend([
                    f"## {i + 1}. {frame.step}",
                    f"",
                    f"**URL:** {frame.url}  ",
                    f"**Screenshot:** `screenshots/{portal}/{frame.step.replace('::', '_').replace('/', '_')}.png`",
                    f"",
                    analysis,
                    f"",
                    f"---",
                    f"",
                ])

            report_path.write_text("\n".join(lines), encoding="utf-8")
            print(f"  [observer] Report written: {report_path}")

    @property
    def frame_count(self) -> int:
        return self._frame_count
