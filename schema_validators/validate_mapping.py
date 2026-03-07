"""
schema_validators/validate_mapping.py

Validates edi_framework/mappings/*.yaml files against
edi_framework/meta/mapping_schema.yaml using pykwalify.
"""
from pathlib import Path

from pykwalify.core import Core
from pykwalify.errors import SchemaError  # noqa: F401 — re-exported for callers

_PKG_ROOT = Path(__file__).parent.parent
DEFAULT_META_DIR: Path = _PKG_ROOT / "edi_framework" / "meta"


def validate_mapping(path: "str | Path", meta_dir: "Path | None" = None) -> None:
    """
    Validate a turnaround mapping YAML file against mapping_schema.yaml.

    Args:
        path:     Path to a mappings/*.yaml file.
        meta_dir: Override for the edi_framework/meta/ directory.

    Raises:
        pykwalify.errors.SchemaError: if the file fails schema validation.
        FileNotFoundError: if the file or schema does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Mapping file not found: {path}")

    meta = meta_dir or DEFAULT_META_DIR
    schema = meta / "mapping_schema.yaml"
    if not schema.exists():
        raise FileNotFoundError(f"Meta-schema not found: {schema}")

    c = Core(source_file=str(path), schema_files=[str(schema)])
    c.validate(raise_exception=True)
