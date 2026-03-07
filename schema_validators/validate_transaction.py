"""
schema_validators/validate_transaction.py

Validates edi_framework/transactions/*.yaml files against
edi_framework/meta/transaction_schema.yaml using pykwalify.
"""
from pathlib import Path

from pykwalify.core import Core
from pykwalify.errors import SchemaError  # noqa: F401 — re-exported for callers

# Default location of meta-schema relative to this module's package root
_PKG_ROOT = Path(__file__).parent.parent
DEFAULT_META_DIR: Path = _PKG_ROOT / "edi_framework" / "meta"


def validate_transaction(path: "str | Path", meta_dir: "Path | None" = None) -> None:
    """
    Validate a transaction YAML file against transaction_schema.yaml.

    Args:
        path:     Path to a transactions/*.yaml file.
        meta_dir: Override for the edi_framework/meta/ directory.
                  Defaults to <repo_root>/edi_framework/meta/.

    Raises:
        pykwalify.errors.SchemaError: if the file fails schema validation.
        FileNotFoundError: if the file or schema does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Transaction file not found: {path}")

    meta = meta_dir or DEFAULT_META_DIR
    schema = meta / "transaction_schema.yaml"
    if not schema.exists():
        raise FileNotFoundError(f"Meta-schema not found: {schema}")

    c = Core(source_file=str(path), schema_files=[str(schema)])
    c.validate(raise_exception=True)
