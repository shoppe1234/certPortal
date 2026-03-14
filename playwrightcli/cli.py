"""cli.py — argparse entry point for playwrightcli.

Usage:
  python -m playwrightcli --portal all            # run all portals, headed (default)
  python -m playwrightcli --portal pam --headless # PAM only, no browser window
  python -m playwrightcli --portal all --observe  # run + real-time design observer
  python -m playwrightcli --portal all --verify   # run + business requirements verification
  python -m playwrightcli --consolidate           # update memory.md from feedback.md
  python -m playwrightcli --portal all --dry-run  # show planned steps, read memory
  python -m playwrightcli --portal meredith --human          # human-in-the-loop: you click, harness verifies
  python -m playwrightcli --portal meredith --human --verify # human mode + requirements verification
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
        if name in ("scope", "rbac", "lifecycle-wizard", "layer2-wizard", "wizard-session", "health"):
            continue  # standalone flows check portals already covered by pam/meredith/chrissy
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

async def _run_portal(
    name: str,
    headless: bool,
    runner: StepRunner,
    observer_queue: asyncio.Queue | None = None,
    verifier=None,
    human_mode: bool = False,
) -> None:
    from playwright.async_api import async_playwright

    flow_map = {
        "pam":              ("playwrightcli.flows.pam_flow",              "PamFlow"),
        "meredith":         ("playwrightcli.flows.meredith_flow",         "MeredithFlow"),
        "chrissy":          ("playwrightcli.flows.chrissy_flow",          "ChrissyFlow"),
        "scope":            ("playwrightcli.flows.scope_flow",            "ScopeFlow"),
        "rbac":             ("playwrightcli.flows.rbac_flow",             "RbacFlow"),
        "lifecycle-wizard": ("playwrightcli.flows.lifecycle_wizard_flow", "LifecycleWizardFlow"),
        "layer2-wizard":    ("playwrightcli.flows.layer2_wizard_flow",    "Layer2WizardFlow"),
        "wizard-session":   ("playwrightcli.flows.wizard_session_flow",   "WizardSessionFlow"),
        "health":           ("playwrightcli.flows.health_flow",            "HealthFlow"),
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
            # Standalone flows — no portal config or observer queue
            if name in ("scope", "rbac", "lifecycle-wizard", "layer2-wizard", "wizard-session", "health"):
                flow = FlowClass(page=page, runner=runner, verifier=verifier)
            else:
                flow = FlowClass(
                    page=page,
                    config=PORTALS[name],
                    runner=runner,
                    observer_queue=observer_queue,
                    verifier=verifier,
                    human_mode=human_mode,
                )
            await flow.run()
        finally:
            await ctx.close()
            await browser.close()


# ------------------------------------------------------------------
# Observed run — Playwright + observer consumer as concurrent tasks
# ------------------------------------------------------------------

async def _run_observed(
    portal_names: list[str],
    headless: bool,
    runner: StepRunner,
    verifiers: dict | None = None,
    human_mode: bool = False,
) -> None:
    """Run portal flows with a concurrent design observer consuming screenshots."""
    from playwrightcli.observer import DesignObserver

    queue: asyncio.Queue = asyncio.Queue()
    observer = DesignObserver(queue)

    # Start the observer consumer as a background task
    consumer_task = asyncio.create_task(observer.run())

    # Run each portal sequentially (they share a StepRunner),
    # but the observer processes screenshots concurrently
    for name in portal_names:
        print(f"=== {name.upper()} ===")
        verifier = verifiers.get(name) if verifiers else None
        await _run_portal(name, headless, runner, observer_queue=queue, verifier=verifier, human_mode=human_mode)
        print()

    # Signal observer to stop and wait for it to finish processing
    await queue.put(None)
    await consumer_task

    # Write analysis reports
    observer.write_reports()

    print(f"Screenshots: {observer.frame_count} frames captured")


# ------------------------------------------------------------------
# Dry-run display
# ------------------------------------------------------------------

def _dry_run(portal_names: list[str], mm: MemoryManager, verify: bool = False) -> None:
    from playwrightcli.flows.pam_flow import PAM_STEPS
    from playwrightcli.flows.meredith_flow import MEREDITH_STEPS
    from playwrightcli.flows.chrissy_flow import CHRISSY_STEPS
    from playwrightcli.flows.scope_flow import SCOPE_STEPS
    from playwrightcli.flows.rbac_flow import RBAC_STEPS
    from playwrightcli.flows.lifecycle_wizard_flow import LIFECYCLE_WIZARD_STEPS
    from playwrightcli.flows.layer2_wizard_flow import LAYER2_WIZARD_STEPS
    from playwrightcli.flows.wizard_session_flow import WIZARD_SESSION_STEPS
    from playwrightcli.flows.health_flow import HEALTH_STEPS

    step_map = {
        "pam":              PAM_STEPS,
        "meredith":         MEREDITH_STEPS,
        "chrissy":          CHRISSY_STEPS,
        "scope":            SCOPE_STEPS,
        "rbac":             RBAC_STEPS,
        "lifecycle-wizard": LIFECYCLE_WIZARD_STEPS,
        "layer2-wizard":    LAYER2_WIZARD_STEPS,
        "wizard-session":   WIZARD_SESSION_STEPS,
        "health":           HEALTH_STEPS,
    }

    # Requirement IDs that will be checked per step
    req_map = {
        "pam::login": ["PAM-AUTH-03..08", "PAM-DASH-01..04", "XPORT-02,03,05"],
        "pam::retailers": ["PAM-RET-01..03"],
        "pam::suppliers": ["PAM-SUP-01..04"],
        "pam::hitl-queue": ["PAM-HITL-01..04"],
        "pam::hitl-approve-signal": ["SIG-HITL-01..03"],
        "pam::gate-enforcement":    ["INV03-GATE-01..03"],
        "pam::password-reset":      ["PW-RESET-01..05"],
        "pam::jwt-revocation":      ["JWT-REV-01..03"],
        "pam::monica-memory": ["PAM-MEM-01..03"],
        "meredith::login": ["MER-AUTH-02,04", "XPORT-02,03,05"],
        "meredith::spec-setup": ["MER-SPEC-01..05"],
        "meredith::supplier-status": ["MER-STATUS-01..05"],
        "meredith::yaml-wizard-signal": ["SIG-YAML2-01..03"],
        "meredith::deprecated-path1": ["DEPR-02"],
        "meredith::deprecated-upload": ["DEPR-01"],
        "meredith::yaml-wizard-path3-signal": ["SIG-YAML3-01..03"],
        "chrissy::login": ["CHR-AUTH-02,04", "CHR-DASH-01..05", "XPORT-02,03,05"],
        "chrissy::scenarios": ["CHR-SCEN-01..05"],
        "chrissy::errors": ["CHR-ERR-01..04"],
        "chrissy::patches": ["CHR-PATCH-01..06"],
        "chrissy::patch-apply-signal": ["SIG-PATCH-01..03"],
        "chrissy::certification": ["CHR-CERT-01..02"],
        "scope::supplier-a-patches":   ["SCOPE-SUP-01", "SCOPE-SUP-02"],
        "scope::supplier-a-scenarios": ["SCOPE-SUP-03", "SCOPE-SUP-04"],
        "scope::supplier-b-patches":   ["SCOPE-SUP-05", "SCOPE-SUP-06"],
        "scope::supplier-b-scenarios": ["SCOPE-SUP-07", "SCOPE-SUP-08"],
        "scope::retailer-a-status":    ["SCOPE-RET-01", "SCOPE-RET-02"],
        "scope::retailer-b-status":    ["SCOPE-RET-03", "SCOPE-RET-04"],
        "scope::cert-dashboard":       ["CHR-CERT-03"],
        "scope::cert-certification":   ["CHR-CERT-04"],
        "rbac::supplier-rejects-admin-route":    ["RBAC-01"],
        "rbac::retailer-rejects-supplier-route": ["RBAC-02"],
        "rbac::supplier-rejects-retailer-route": ["RBAC-03"],
        # Lifecycle Wizard
        "lifecycle-wizard::landing":        ["LC-WIZ-01"],
        "lifecycle-wizard::version-select": ["LC-WIZ-02"],
        "lifecycle-wizard::tx-select":      ["LC-WIZ-03"],
        "lifecycle-wizard::mode-select":    ["LC-WIZ-04"],
        "lifecycle-wizard::generate":       ["LC-WIZ-05", "LC-WIZ-06"],
        "lifecycle-wizard::verify-db":      ["LC-WIZ-07"],
        "lifecycle-wizard::resume":         ["LC-WIZ-08"],
        # Layer 2 Wizard
        "layer2-wizard::preset-select":       ["L2-WIZ-01"],
        "layer2-wizard::segment-config":      ["L2-WIZ-02"],
        "layer2-wizard::generate-yaml":       ["L2-WIZ-03", "L2-WIZ-04"],
        "layer2-wizard::generate-artifacts":  ["L2-WIZ-05", "L2-WIZ-06"],
        "layer2-wizard::download":            ["L2-WIZ-07"],
        "layer2-wizard::verify-db":           ["L2-WIZ-08", "L2-WIZ-09"],
        # Wizard Session
        "wizard-session::start-lifecycle":  ["WIZ-SESS-01"],
        "wizard-session::resume-lifecycle": ["WIZ-SESS-03"],
        "wizard-session::resume-layer2":    ["WIZ-SESS-04"],
        "wizard-session::verify-both-db":   ["WIZ-SESS-02"],
        # Health
        "health::pam":      ["HEALTH-HTMX-01..02", "HEALTH-SRI-01..02", "HEALTH-BTN-01..02", "HEALTH-CONSOLE-01", "HEALTH-ASSET-01..03"],
        "health::meredith": ["HEALTH-HTMX-01..02", "HEALTH-SRI-01..02", "HEALTH-BTN-01..02", "HEALTH-CONSOLE-01", "HEALTH-ASSET-01..03"],
        "health::chrissy":  ["HEALTH-HTMX-01..02", "HEALTH-SRI-01..02", "HEALTH-BTN-01..02", "HEALTH-CONSOLE-01", "HEALTH-ASSET-01..03"],
        "health::wizard":   ["HEALTH-WIZ-01..02", "HEALTH-CONSOLE-02"],
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

    # Load requirements history for trend context
    req_mem = None
    if verify:
        from playwrightcli.requirements_memory import RequirementsMemory
        req_mem = RequirementsMemory()
        run_count = req_mem.get_run_count()
        if run_count > 0:
            print(f"Requirements history: {run_count} previous run(s) recorded\n")

    for portal in portal_names:
        print(f"=== {portal.upper()} ===")
        for step in step_map.get(portal, []):
            full_name = f"{portal}::{step}"
            corrections = mm.get_corrections(full_name)
            corr_str = f"  [known corrections: {', '.join(corrections)}]" if corrections else ""
            print(f"  {full_name}{corr_str}")
            if verify and full_name in req_map:
                req_ids_str = ", ".join(req_map[full_name])
                print(f"    -> verify: {req_ids_str}")
                # Show history for failing requirements
                if req_mem and req_mem.get_run_count() > 0:
                    for req_range in req_map[full_name]:
                        # Parse individual IDs from ranges like "PAM-AUTH-03..08"
                        # For display, just show latest status from history
                        latest = req_mem.get_latest_status(req_range)
                        if latest and latest == "FAIL":
                            consec = req_mem.get_consecutive_failures(req_range)
                            print(f"       {req_range}: FAIL ({consec} consecutive)")
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
        choices=["pam", "meredith", "chrissy", "scope", "rbac",
                 "lifecycle-wizard", "layer2-wizard", "wizard-session", "health", "all"],
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
        "--observe",
        action="store_true",
        default=False,
        help="Enable real-time design observer: capture screenshots, analyze via Claude Vision",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        default=False,
        help="Enable business requirements verification: DOM assertions against requirements checklist",
    )
    parser.add_argument(
        "--consolidate",
        action="store_true",
        default=False,
        help="Consolidate feedback.md -> memory.md and exit (no browser)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show planned steps and read memory; do not open a browser",
    )
    parser.add_argument(
        "--human",
        action="store_true",
        default=False,
        help=(
            "Human-in-the-loop mode: login is automated, then the terminal prompts "
            "you to perform each step manually in the browser. "
            "The harness verifies DOM state after each action. "
            "Always headed (ignores --headless). "
            "Currently supported: meredith. "
            "Combine with --verify to run requirement checks after each step."
        ),
    )
    args = parser.parse_args()

    mm = MemoryManager()

    # ---- consolidate-only mode ----
    if args.consolidate:
        print("Consolidating feedback.md -> memory.md ...")
        mm.consolidate()
        print("Done. memory.md updated.")

        # Also consolidate requirements memory if history exists
        from playwrightcli.requirements_memory import RequirementsMemory
        req_mem = RequirementsMemory()
        if req_mem.get_run_count() > 0:
            print("Consolidating requirements_history.jsonl -> requirements_memory.md ...")
            req_mem.consolidate()
            print(f"Done. requirements_memory.md updated ({req_mem.get_run_count()} runs analyzed).")
        return

    portal_names = (
        ["pam", "meredith", "chrissy", "scope", "rbac",
         "lifecycle-wizard", "layer2-wizard", "wizard-session", "health"]
        if args.portal == "all" else [args.portal]
    )

    # Auto-consolidate so this run benefits from previous feedback
    mm.consolidate()

    # ---- dry-run mode ----
    if args.dry_run:
        _dry_run(portal_names, mm, verify=args.verify)
        return

    # Human mode is always headed — override --headless if supplied together
    if args.human and args.headless:
        print("  NOTE  --human overrides --headless; browser will be visible")
    headless = args.headless and not args.human

    # ---- normal run ----
    print("\n--- certPortal Playwright CLI ---")
    print(f"Run started : {datetime.now().isoformat(timespec='seconds')}")
    print(f"Portals     : {', '.join(portal_names)}")
    if args.human:
        print(f"Mode        : HUMAN-IN-THE-LOOP (you click, harness verifies)")
    else:
        print(f"Mode        : {'headless' if headless else 'headed (browser visible)'}")
    print(f"Observer    : {'ACTIVE — screenshots + Claude Vision analysis' if args.observe else 'off'}")
    print(f"Verifier    : {'ACTIVE — DOM-based requirements checks' if args.verify else 'off'}")
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

    # ---- create per-portal verifiers if --verify is active ----
    verifiers: dict | None = None
    if args.verify:
        from playwrightcli.requirements_verifier import RequirementsVerifier

        # Build S3 signal checker for signal integration tests (Step #2).
        # Degrades gracefully: if boto3 is missing or S3 is unreachable, signal
        # checks are recorded as SKIP rather than crashing the run.
        signal_checker = None
        try:
            from playwrightcli.fixtures.signal_checker import SignalChecker
            signal_checker = SignalChecker()
        except Exception as sc_err:
            print(f"  WARN  SignalChecker unavailable — SIG-* checks will SKIP ({sc_err})")

        verifiers = {
            name: RequirementsVerifier(portal=name, signal_checker=signal_checker)
            for name in portal_names
        }

    # Start human control server before any portal run, stop it after (even on error)
    if args.human:
        from playwrightcli.human_control import start_server, stop_server, CONTROL_PORT
        start_server()
        print(f"  Control page : http://localhost:{CONTROL_PORT}  (open this in your browser)\n")

    try:
        if args.observe:
            # Run with concurrent observer (single event loop)
            asyncio.run(_run_observed(portal_names, headless, runner, verifiers=verifiers, human_mode=args.human))
        else:
            # Original behavior — no observer
            for name in portal_names:
                print(f"=== {name.upper()} ===")
                verifier = verifiers.get(name) if verifiers else None
                asyncio.run(_run_portal(name, headless, runner, verifier=verifier, human_mode=args.human))
                print()
    finally:
        if args.human:
            stop_server()

    # Flush failures to feedback.md
    runner.write_feedback(mm)

    # ---- write requirements reports if --verify was active ----
    if verifiers:
        from playwrightcli.requirements_verifier import write_summary
        from playwrightcli.requirements_memory import RequirementsMemory

        print("\n--- Requirements Verification ---")
        report_paths = []
        for name, v in verifiers.items():
            path = v.write_report()
            report_paths.append(path)
            total_v = v.pass_count + v.fail_count + v.skip_count
            print(f"  {name.upper():10s}  PASS: {v.pass_count}  FAIL: {v.fail_count}  SKIP: {v.skip_count}  ({total_v} checks)")

        summary_path = write_summary(list(verifiers.values()))
        print(f"\n  Reports written to: requirements_reports/")
        print(f"  Summary: {summary_path}")

        # Record this run to requirements memory (feedback + JSONL history)
        req_mem = RequirementsMemory()
        req_mem.record_run(list(verifiers.values()))
        req_mem.consolidate()
        run_count = req_mem.get_run_count()
        print(f"  History: run #{run_count} recorded -> requirements_memory.md updated")

        # Show trend alerts if we have history
        if run_count > 1:
            verifier_list = list(verifiers.values())
            for v in verifier_list:
                for r in v.results:
                    consec = req_mem.get_consecutive_failures(r.req_id)
                    if consec >= 3:
                        print(f"  ALERT: {r.req_id} has failed {consec} consecutive runs")

        # Overall requirements verdict
        total_fail = sum(v.fail_count for v in verifiers.values())
        if total_fail > 0:
            print(f"\n  {total_fail} requirement(s) FAILED — see reports for details.")
        else:
            print("\n  All requirements PASSED.")
        print()

    # Summary
    total = runner.pass_count + runner.fail_count
    print(
        f"Summary: {runner.pass_count}/{total} PASS  |  {runner.fail_count}/{total} FAIL"
    )
    if runner.fail_count > 0:
        print(
            "Failures logged -> playwrightcli/feedback.md\n"
            "Run  python -m playwrightcli --consolidate  to update memory.md"
        )
    else:
        print("All steps passed.")
