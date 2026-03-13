"""cli.py — argparse entry point for playwrightcli.

Usage:
  python -m playwrightcli --portal all            # run all portals, headed (default)
  python -m playwrightcli --portal pam --headless # PAM only, no browser window
  python -m playwrightcli --consolidate           # update memory.md from feedback.md
  python -m playwrightcli --portal all --dry-run  # show planned steps, read memory
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import urllib.error
import urllib.request
from datetime import datetime

from playwrightcli.config import PORTALS, TIMEOUTS
from playwrightcli.memory_manager import MemoryManager
from playwrightcli.runner import StepRunner


# ------------------------------------------------------------------
# Pre-flight
# ------------------------------------------------------------------

def _preflight(portal_names: list[str]) -> bool:
    """HTTP GET /health for each portal. Returns True if all respond 200."""
    all_ok = True
    for name in portal_names:
        url = PORTALS[name]["url"] + "/health"
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUTS["preflight"]) as resp:
                if resp.status == 200:
                    print(f"  OK    {name:10s} ({PORTALS[name]['url']})")
                else:
                    print(f"  WARN  {name:10s} HTTP {resp.status}")
        except urllib.error.URLError as exc:
            print(f"  FAIL  {name:10s} {exc.reason}")
            all_ok = False
        except Exception as exc:
            print(f"  FAIL  {name:10s} {exc}")
            all_ok = False
    return all_ok


# ------------------------------------------------------------------
# Per-portal async runner
# ------------------------------------------------------------------

async def _run_portal(name: str, headless: bool, runner: StepRunner) -> None:
    from playwright.async_api import async_playwright

    flow_map = {
        "pam": ("playwrightcli.flows.pam_flow", "PamFlow"),
        "meredith": ("playwrightcli.flows.meredith_flow", "MeredithFlow"),
        "chrissy": ("playwrightcli.flows.chrissy_flow", "ChrissyFlow"),
    }
    module_path, class_name = flow_map[name]
    import importlib
    mod = importlib.import_module(module_path)
    FlowClass = getattr(mod, class_name)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        try:
            flow = FlowClass(page=page, config=PORTALS[name], runner=runner)
            await flow.run()
        finally:
            await ctx.close()
            await browser.close()


# ------------------------------------------------------------------
# Dry-run display
# ------------------------------------------------------------------

def _dry_run(portal_names: list[str], mm: MemoryManager) -> None:
    from playwrightcli.flows.pam_flow import PAM_STEPS
    from playwrightcli.flows.meredith_flow import MEREDITH_STEPS
    from playwrightcli.flows.chrissy_flow import CHRISSY_STEPS

    step_map = {
        "pam": PAM_STEPS,
        "meredith": MEREDITH_STEPS,
        "chrissy": CHRISSY_STEPS,
    }

    print("\n--- DRY RUN (no browser opened) ---\n")
    print("memory.md contents:")
    mem_lines = mm.get_memory_lines()
    if mem_lines:
        for ln in mem_lines:
            print(f"  {ln}")
    else:
        print("  (empty — no memory recorded yet)")
    print()

    for portal in portal_names:
        print(f"=== {portal.upper()} ===")
        for step in step_map.get(portal, []):
            full_name = f"{portal}::{step}"
            corrections = mm.get_corrections(full_name)
            corr_str = f"  [known corrections: {', '.join(corrections)}]" if corrections else ""
            print(f"  {full_name}{corr_str}")
        print()


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="playwrightcli",
        description="Self-correcting Playwright E2E runner for certPortal portals.",
    )
    parser.add_argument(
        "--portal",
        choices=["pam", "meredith", "chrissy", "all"],
        default="all",
        help="Which portal(s) to test (default: all)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser headless — suppress the browser window (default: headed)",
    )
    parser.add_argument(
        "--consolidate",
        action="store_true",
        default=False,
        help="Consolidate feedback.md → memory.md and exit (no browser)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show planned steps and read memory; do not open a browser",
    )
    args = parser.parse_args()

    mm = MemoryManager()

    # ---- consolidate-only mode ----
    if args.consolidate:
        print("Consolidating feedback.md → memory.md ...")
        mm.consolidate()
        print("Done. memory.md updated.")
        return

    portal_names = (
        ["pam", "meredith", "chrissy"] if args.portal == "all" else [args.portal]
    )

    # Auto-consolidate so this run benefits from previous feedback
    mm.consolidate()

    # ---- dry-run mode ----
    if args.dry_run:
        _dry_run(portal_names, mm)
        return

    # ---- normal run ----
    print("\n--- certPortal Playwright CLI ---")
    print(f"Run started : {datetime.now().isoformat(timespec='seconds')}")
    print(f"Portals     : {', '.join(portal_names)}")
    print(f"Mode        : {'headless' if args.headless else 'headed (browser visible)'}")
    print()

    print("Pre-flight check:")
    if not _preflight(portal_names):
        print(
            "\nERROR: One or more portals are unreachable. Start them first:\n"
            "  uvicorn portals.pam:app --port 8000\n"
            "  uvicorn portals.meredith:app --port 8001\n"
            "  uvicorn portals.chrissy:app --port 8002"
        )
        sys.exit(1)
    print()

    runner = StepRunner(memory_manager=mm)

    for name in portal_names:
        print(f"=== {name.upper()} ===")
        asyncio.run(_run_portal(name, args.headless, runner))
        print()

    # Flush failures to feedback.md
    runner.write_feedback(mm)

    # Summary
    total = runner.pass_count + runner.fail_count
    print(
        f"Summary: {runner.pass_count}/{total} PASS  |  {runner.fail_count}/{total} FAIL"
    )
    if runner.fail_count > 0:
        print(
            "Failures logged → playwrightcli/feedback.md\n"
            "Run  python -m playwrightcli --consolidate  to update memory.md"
        )
    else:
        print("All steps passed.")
