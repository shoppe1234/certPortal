#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Path bootstrap — runs before any schema_validators imports so that
# `python schema_validators/validate_all.py` works from repo root.
# ---------------------------------------------------------------------------
import sys as _sys
from pathlib import Path as _Path

_REPO_ROOT = _Path(__file__).parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))
# ---------------------------------------------------------------------------

"""
schema_validators/validate_all.py

CLI entry point and library-mode validator for edi_framework/ YAML files.

CLI usage:
    # Validate entire framework (dev / CI)
    python schema_validators/validate_all.py --framework-path ./edi_framework

    # Validate a single file (Andy Path 2 runtime gate)
    python schema_validators/validate_all.py --file ./uploaded_schema.yaml

    # CI mode — exits 1 on any failure
    python schema_validators/validate_all.py --ci

Library usage (Andy agent):
    from schema_validators.validate_all import validate_file
    validate_file(path, schema_type='transaction')   # raises SchemaError on failure
"""

import argparse
from pathlib import Path
from typing import Optional

from pykwalify.errors import SchemaError

from schema_validators.validate_transaction import validate_transaction, DEFAULT_META_DIR as _DEFAULT_META
from schema_validators.validate_mapping import validate_mapping
from schema_validators.validate_lifecycle import validate_lifecycle
from schema_validators.report import FileResult, ValidationReport, print_report

# ---------------------------------------------------------------------------
# Schema type → (subdirectory, validator function)
# ---------------------------------------------------------------------------
_SCHEMA_MAP = {
    "transaction": ("transactions", validate_transaction),
    "mapping":     ("mappings",     validate_mapping),
    "lifecycle":   ("lifecycle",    validate_lifecycle),
}

# Reverse map: subdirectory name → schema type string
_SUBDIR_TO_TYPE = {subdir: stype for stype, (subdir, _) in _SCHEMA_MAP.items()}


# ---------------------------------------------------------------------------
# Public library-mode API  (called by Andy agent — Path 2 runtime gate)
# ---------------------------------------------------------------------------

def validate_file(
    path,
    schema_type: Optional[str] = None,
    meta_dir: Optional[Path] = None,
) -> None:
    """
    Validate a single YAML file against its appropriate meta-schema.

    This is the library-mode entry point for Andy's Path 2 runtime gate.
    Call this BEFORE workspace.upload() to ensure schema compliance.

    Args:
        path:        Path to the YAML file to validate.
        schema_type: 'transaction' | 'mapping' | 'lifecycle'.
                     If None, auto-detected from the file's parent directory name.
        meta_dir:    Override path to edi_framework/meta/. Defaults to repo-relative.

    Raises:
        pykwalify.errors.SchemaError: validation failed — caller should reject the file.
        ValueError:  schema_type cannot be determined.
        FileNotFoundError: file or meta-schema not found.
    """
    path = Path(path)

    if schema_type is None:
        schema_type = _SUBDIR_TO_TYPE.get(path.parent.name)
        if schema_type is None:
            raise ValueError(
                f"Cannot auto-detect schema_type for '{path}'. "
                f"Parent dir '{path.parent.name}' is not in {list(_SUBDIR_TO_TYPE)}. "
                f"Pass schema_type='transaction'|'mapping'|'lifecycle' explicitly."
            )

    if schema_type not in _SCHEMA_MAP:
        raise ValueError(
            f"Unknown schema_type '{schema_type}'. "
            f"Expected one of: {list(_SCHEMA_MAP)}"
        )

    _, validator_fn = _SCHEMA_MAP[schema_type]
    kwargs = {"meta_dir": meta_dir} if meta_dir else {}
    validator_fn(path, **kwargs)


# ---------------------------------------------------------------------------
# Framework-wide validator  (used by CLI and CI)
# ---------------------------------------------------------------------------

def validate_framework(
    framework_path,
    meta_dir: Optional[Path] = None,
) -> ValidationReport:
    """
    Validate all YAML files in an edi_framework/ directory tree.

    Discovers files under:
      {framework_path}/transactions/*.yaml
      {framework_path}/mappings/*.yaml
      {framework_path}/lifecycle/*.yaml

    Args:
        framework_path: Path to the edi_framework/ root directory.
        meta_dir:       Override path to meta-schemas.

    Returns:
        ValidationReport with per-file results.
    """
    framework_path = Path(framework_path)
    report = ValidationReport()

    for schema_type, (subdir, validator_fn) in _SCHEMA_MAP.items():
        subdir_path = framework_path / subdir
        if not subdir_path.exists():
            continue

        for yaml_file in sorted(subdir_path.glob("*.yaml")):
            rel = str(yaml_file.relative_to(framework_path.parent))
            kwargs = {"meta_dir": meta_dir} if meta_dir else {}
            try:
                validator_fn(yaml_file, **kwargs)
                report.add(FileResult(path=rel, schema_type=schema_type, passed=True))
            except SchemaError as exc:
                report.add(
                    FileResult(
                        path=rel,
                        schema_type=schema_type,
                        passed=False,
                        error=str(exc),
                    )
                )
            except Exception as exc:
                report.add(
                    FileResult(
                        path=rel,
                        schema_type=schema_type,
                        passed=False,
                        error=f"Unexpected error: {exc}",
                    )
                )

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="validate_all",
        description="certPortal Layer 0 — edi_framework YAML schema validator",
    )
    p.add_argument(
        "--framework-path",
        default="./edi_framework",
        metavar="PATH",
        help="Path to edi_framework/ root (default: ./edi_framework)",
    )
    p.add_argument(
        "--file",
        metavar="PATH",
        help="Validate a single file instead of the full framework",
    )
    p.add_argument(
        "--schema-type",
        choices=list(_SCHEMA_MAP),
        metavar="TYPE",
        help="Schema type for --file: transaction | mapping | lifecycle (auto-detected if omitted)",
    )
    p.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: exit code 1 on any failure (always enabled; flag kept for compatibility)",
    )
    p.add_argument(
        "--meta-dir",
        metavar="PATH",
        help="Override path to edi_framework/meta/ directory",
    )
    return p


def main(argv=None) -> int:
    """CLI entry point. Returns exit code (0 = all passed, 1 = failures)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    meta_dir = Path(args.meta_dir) if args.meta_dir else None

    if args.file:
        # Single-file mode (Andy Path 2 runtime gate or manual check)
        try:
            validate_file(
                args.file,
                schema_type=args.schema_type,
                meta_dir=meta_dir,
            )
            print(f"  [OK]  {args.file}   PASSED")
            return 0
        except SchemaError as exc:
            print(f"  [!!]  {args.file}   FAILED")
            import sys
            print(f"        {exc}", file=sys.stderr)
            return 1
        except (ValueError, FileNotFoundError) as exc:
            import sys
            print(f"  [!!]  {args.file}   ERROR: {exc}", file=sys.stderr)
            return 1

    # Framework-wide mode
    report = validate_framework(
        framework_path=args.framework_path,
        meta_dir=meta_dir,
    )
    print_report(report)
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
