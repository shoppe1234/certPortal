"""
schema_validators/report.py

Validation result types and console reporting for validate_all.py.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class FileResult:
    """Result of validating one YAML file."""
    path: str           # relative path for display
    schema_type: str    # 'transaction' | 'mapping' | 'lifecycle'
    passed: bool
    error: Optional[str] = None


@dataclass
class ValidationReport:
    """Aggregated results for a full validate_framework() run."""
    results: List[FileResult] = field(default_factory=list)

    def add(self, result: FileResult) -> None:
        self.results.append(result)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def all_passed(self) -> bool:
        return self.failed_count == 0


def _check(passed: bool) -> str:
    """Return PASS/FAIL indicator (ASCII-safe for Windows terminals)."""
    return "PASSED" if passed else "FAILED"


def print_report(report: ValidationReport, file=None) -> None:
    """
    Print a human-readable validation report to stdout (or given file).

    Format matches TRD §9.4 expected output.
    """
    out = file or sys.stdout

    # Column width for the path field
    max_path_len = max((len(r.path) for r in report.results), default=40)
    col = max(max_path_len + 2, 42)

    for r in report.results:
        status = _check(r.passed)
        marker = "[OK]" if r.passed else "[!!]"
        line = f"  {marker}  {r.path:<{col}} {status}"
        print(line, file=out)
        if not r.passed and r.error:
            # Indent error detail under the failing line
            for err_line in r.error.strip().splitlines():
                print(f"         {err_line}", file=out)

    print(file=out)
    print(
        f"  Summary: {report.passed_count} passed, {report.failed_count} failed",
        file=out,
    )
    print(
        f"  EXIT CODE: {'0' if report.all_passed else '1'}",
        file=out,
    )
