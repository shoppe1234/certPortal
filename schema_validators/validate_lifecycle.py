"""
schema_validators/validate_lifecycle.py

Validates edi_framework/lifecycle/*.yaml files against
edi_framework/meta/lifecycle_schema.yaml using pykwalify.
"""
from pathlib import Path

import yaml
from pykwalify.core import Core
from pykwalify.errors import SchemaError  # noqa: F401 — re-exported for callers

_PKG_ROOT = Path(__file__).parent.parent
DEFAULT_META_DIR: Path = _PKG_ROOT / "edi_framework" / "meta"


def validate_lifecycle(path: "str | Path", meta_dir: "Path | None" = None) -> None:
    """
    Validate a lifecycle state machine YAML file against lifecycle_schema.yaml.

    Uses source_data (pre-loaded dict) instead of source_file so that
    pykwalify does not try to open the file with the Windows system encoding
    (cp1252), which fails on files containing non-ASCII characters such as
    the ge-sign (>=) used in the quantity-chain rule string.

    Args:
        path:     Path to a lifecycle/*.yaml file.
        meta_dir: Override for the edi_framework/meta/ directory.

    Raises:
        pykwalify.errors.SchemaError: if the file fails schema validation.
        FileNotFoundError: if the file or schema does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Lifecycle file not found: {path}")

    meta = meta_dir or DEFAULT_META_DIR
    schema_path = meta / "lifecycle_schema.yaml"
    if not schema_path.exists():
        raise FileNotFoundError(f"Meta-schema not found: {schema_path}")

    # Explicit UTF-8 to avoid Windows charmap errors on non-ASCII characters.
    with open(path, "r", encoding="utf-8") as fh:
        source_data = yaml.safe_load(fh)

    with open(schema_path, "r", encoding="utf-8") as fh:
        schema_data = yaml.safe_load(fh)

    c = Core(source_data=source_data, schema_data=schema_data)
    c.validate(raise_exception=True)
