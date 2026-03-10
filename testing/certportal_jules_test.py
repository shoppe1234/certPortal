"""testing/certportal_jules_test.py — Jules CI Test Orchestrator.

Imports and runs SuiteA through SuiteI. Each suite returns a list of result dicts.

Usage:
    python -m testing.certportal_jules_test
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Load .env from project root so CERTPORTAL_DB_URL (and friends) are available
# without requiring the caller to pre-export them in the shell.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(Path(__file__).parent.parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed — caller must set env vars manually

from testing.suites import suite_a, suite_b, suite_c, suite_d, suite_e, suite_f, suite_g, suite_h, suite_i

SUITES = [
    ("SuiteA — Portal Health & Auth", suite_a),
    ("SuiteB — Agent Unit Tests", suite_b),
    ("SuiteC — Gate Enforcer", suite_c),
    ("SuiteD — Workspace Scope", suite_d),
    ("SuiteE — HITL Flow", suite_e),
    ("SuiteF — End-to-End Pipeline", suite_f),
    ("SuiteG — Moses Lifecycle Hook", suite_g),
    ("SuiteH — Sprint 4 Integration", suite_h),
    ("SuiteI — Kelly ADK Memory", suite_i),
]


def run_all() -> dict:
    """Run all nine suites and return a consolidated results dict."""
    start = datetime.now(timezone.utc)
    all_results: list[dict] = []
    suite_summaries: list[dict] = []

    for suite_name, suite_module in SUITES:
        suite_results = suite_module.run()
        all_results.extend(suite_results)

        passed = sum(1 for r in suite_results if r["status"].value == "PASS")
        failed = sum(1 for r in suite_results if r["status"].value == "FAIL")
        skipped = sum(1 for r in suite_results if r["status"].value == "SKIP")

        suite_summaries.append(
            {
                "suite": suite_name,
                "total": len(suite_results),
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
            }
        )

    end = datetime.now(timezone.utc)
    total_passed = sum(s["passed"] for s in suite_summaries)
    total_failed = sum(s["failed"] for s in suite_summaries)
    total_skipped = sum(s["skipped"] for s in suite_summaries)

    return {
        "run_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_s": (end - start).total_seconds(),
        "overall_status": "FAIL" if total_failed > 0 else "PASS" if total_passed > 0 else "SKIP",
        "totals": {
            "passed": total_passed,
            "failed": total_failed,
            "skipped": total_skipped,
        },
        "suites": suite_summaries,
    }


if __name__ == "__main__":
    results = run_all()
    print(json.dumps(results, indent=2, default=str))
    if results["overall_status"] == "FAIL":
        sys.exit(1)
