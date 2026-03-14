"""
X12 Source Abstraction Layer — Dual pyx12/Stedi Definition Loader

Reads X12 transaction structure definitions from two sources:
  1. pyx12 XML map files (primary, when available for a given transaction)
  2. Stedi-style JSON schemas (fallback, from local files)

Returns normalized segment/element definitions regardless of source.
NO HARDCODING of transaction types, segments, or elements.

Architecture Decision: AD-2, AD-10 from wizard refactoring prompt.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalized data structures (source-agnostic)
# ---------------------------------------------------------------------------

@dataclass
class ElementDef:
    """Normalized X12 data element definition."""
    ref: str                          # e.g. "BEG01"
    element_id: str                   # e.g. "353" (data element number)
    name: str                         # e.g. "Transaction Set Purpose Code"
    requirement: str                  # M=mandatory, O=optional, C=conditional
    data_type: str                    # ID, AN, DT, N0, N2, R, etc.
    min_length: int = 0
    max_length: int = 0
    usage: str = ""                   # free-text usage note
    codes: list[dict] = field(default_factory=list)  # [{"code": "00", "description": "Original"}, ...]


@dataclass
class SegmentDef:
    """Normalized X12 segment definition."""
    id: str                           # e.g. "BEG"
    name: str                         # e.g. "Beginning Segment for Purchase Order"
    position: str                     # e.g. "020"
    requirement: str                  # M=mandatory, O=optional
    max_use: int = 1
    notes: str = ""
    elements: list[ElementDef] = field(default_factory=list)


@dataclass
class LoopDef:
    """Normalized X12 loop definition."""
    id: str                           # e.g. "HEADING", "N1_LOOP"
    name: str
    segments: list[SegmentDef] = field(default_factory=list)
    loops: list["LoopDef"] = field(default_factory=list)


@dataclass
class TransactionDef:
    """Complete normalized X12 transaction definition."""
    transaction_set: str              # e.g. "850"
    name: str                         # e.g. "Purchase Order"
    version: str                      # e.g. "004010"
    description: str = ""
    loops: list[LoopDef] = field(default_factory=list)
    source: str = ""                  # "pyx12" or "stedi"


# ---------------------------------------------------------------------------
# Stedi JSON schema paths
# ---------------------------------------------------------------------------

# Default location: sampleArtifacts/stedi/schemas/ relative to project root.
# Override with STEDI_SCHEMAS_DIR env var.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_STEDI_DIR = _PROJECT_ROOT / "sampleArtifacts" / "stedi" / "schemas"


def _stedi_schemas_dir() -> Path:
    """Return the directory containing Stedi JSON schema files."""
    env_dir = os.environ.get("STEDI_SCHEMAS_DIR")
    if env_dir:
        return Path(env_dir)
    return _DEFAULT_STEDI_DIR


# ---------------------------------------------------------------------------
# pyx12 XML map loader
# ---------------------------------------------------------------------------

def _pyx12_available() -> bool:
    """Check whether pyx12 is installed and importable."""
    try:
        import pyx12  # noqa: F401
        return True
    except ImportError:
        return False


def _pyx12_map_dir() -> Optional[Path]:
    """Return the pyx12 map directory, or None if unavailable."""
    try:
        import pyx12
        candidate = Path(pyx12.__file__).parent / "map"
        if candidate.is_dir():
            return candidate
    except ImportError:
        pass
    return None


def _find_pyx12_map(transaction_set: str, version: str) -> Optional[Path]:
    """
    Find a pyx12 XML map file for a given transaction set and X12 version.

    pyx12 map filenames follow the pattern: {ts}.{ver}.{impl}.xml
    e.g. 997.4010.xml, 835.5010.X221.A1.xml

    The version in filenames is the short form: "4010" not "004010".
    """
    map_dir = _pyx12_map_dir()
    if not map_dir:
        return None

    # Normalize version: "004010" -> "4010"
    short_ver = version.lstrip("0") if version.startswith("00") else version

    # Look for any XML file starting with "{ts}.{ver}"
    prefix = f"{transaction_set}.{short_ver}"
    candidates = sorted(map_dir.glob(f"{prefix}*.xml"))

    if candidates:
        # Prefer the first match (usually the base map)
        return candidates[0]
    return None


def _parse_pyx12_elements(segment_node) -> list[ElementDef]:
    """Parse <element> children from a pyx12 segment XML node."""
    import xml.etree.ElementTree as ET  # noqa: F811
    elements = []
    for elem in segment_node.findall("element"):
        ref = elem.get("xid", "")
        codes = []
        valid_codes = elem.find("valid_codes")
        if valid_codes is not None:
            for code_node in valid_codes.findall("code"):
                codes.append({
                    "code": code_node.text.strip() if code_node.text else "",
                    "description": ""
                })

        data_ele_node = elem.find("data_ele")
        element_id = data_ele_node.text.strip() if data_ele_node is not None and data_ele_node.text else ""

        name_node = elem.find("name")
        name = name_node.text.strip() if name_node is not None and name_node.text else ""

        usage_node = elem.find("usage")
        usage = usage_node.text.strip() if usage_node is not None and usage_node.text else ""

        # Map pyx12 usage codes: R=required, S=situational, N=not used
        req_map = {"R": "M", "S": "O", "N": "N"}
        requirement = req_map.get(usage, "O")

        elements.append(ElementDef(
            ref=ref,
            element_id=element_id,
            name=name,
            requirement=requirement,
            data_type="",      # pyx12 stores data type in dataele.xml, not inline
            min_length=0,
            max_length=0,
            usage="",
            codes=codes,
        ))
    return elements


def _parse_pyx12_loop(loop_node) -> LoopDef:
    """Recursively parse a pyx12 <loop> XML node into a LoopDef."""
    loop_id = loop_node.get("xid", "UNKNOWN")
    name_node = loop_node.find("name")
    name = name_node.text.strip() if name_node is not None and name_node.text else loop_id

    segments = []
    for seg in loop_node.findall("segment"):
        seg_id = seg.get("xid", "")
        seg_name_node = seg.find("name")
        seg_name = seg_name_node.text.strip() if seg_name_node is not None and seg_name_node.text else seg_id

        pos_node = seg.find("pos")
        pos = pos_node.text.strip() if pos_node is not None and pos_node.text else "000"

        usage_node = seg.find("usage")
        usage = usage_node.text.strip() if usage_node is not None and usage_node.text else "R"
        req_map = {"R": "M", "S": "O", "N": "N"}

        max_use_node = seg.find("max_use")
        max_use = 1
        if max_use_node is not None and max_use_node.text:
            try:
                max_use = int(max_use_node.text)
            except ValueError:
                max_use = 999  # ">1" in pyx12 means unbounded

        elements = _parse_pyx12_elements(seg)

        segments.append(SegmentDef(
            id=seg_id,
            name=seg_name,
            position=pos,
            requirement=req_map.get(usage, "O"),
            max_use=max_use,
            notes="",
            elements=elements,
        ))

    child_loops = []
    for child in loop_node.findall("loop"):
        child_loops.append(_parse_pyx12_loop(child))

    return LoopDef(id=loop_id, name=name, segments=segments, loops=child_loops)


def _load_from_pyx12(transaction_set: str, version: str) -> Optional[TransactionDef]:
    """
    Load a transaction definition from pyx12 XML map files.

    Returns None if pyx12 is not installed or the map is not available.
    """
    map_path = _find_pyx12_map(transaction_set, version)
    if map_path is None:
        return None

    import xml.etree.ElementTree as ET
    try:
        tree = ET.parse(str(map_path))
        root = tree.getroot()
    except (ET.ParseError, OSError) as exc:
        logger.warning("Failed to parse pyx12 map %s: %s", map_path, exc)
        return None

    # Root is <transaction xid="...">
    tx_id = root.get("xid", transaction_set)
    name_node = root.find("name")
    tx_name = name_node.text.strip() if name_node is not None and name_node.text else f"Transaction {tx_id}"

    loops = []
    for loop_node in root.findall("loop"):
        loops.append(_parse_pyx12_loop(loop_node))

    return TransactionDef(
        transaction_set=tx_id,
        name=tx_name,
        version=version,
        description="",
        loops=loops,
        source="pyx12",
    )


# ---------------------------------------------------------------------------
# Stedi JSON schema loader
# ---------------------------------------------------------------------------

def _find_stedi_schema(transaction_set: str, version: str) -> Optional[Path]:
    """
    Find a Stedi JSON schema file for a given transaction set and version.

    Naming convention: x12_{ts}_{short_ver}.json
    e.g. x12_850_4010.json
    """
    schemas_dir = _stedi_schemas_dir()
    if not schemas_dir.is_dir():
        return None

    # Normalize version: "004010" -> "4010"
    short_ver = version.lstrip("0") if version.startswith("00") else version

    candidate = schemas_dir / f"x12_{transaction_set}_{short_ver}.json"
    if candidate.is_file():
        return candidate
    return None


def _parse_stedi_elements(elements_json: list[dict]) -> list[ElementDef]:
    """Parse elements from Stedi JSON format."""
    elements = []
    for elem in elements_json:
        codes = []
        for code_entry in elem.get("codes", []):
            if isinstance(code_entry, dict):
                codes.append({
                    "code": code_entry.get("code", ""),
                    "description": code_entry.get("description", ""),
                })
            elif isinstance(code_entry, str):
                codes.append({"code": code_entry, "description": ""})

        elements.append(ElementDef(
            ref=elem.get("ref", ""),
            element_id=str(elem.get("element_id", "")),
            name=elem.get("name", ""),
            requirement=elem.get("requirement", "O"),
            data_type=elem.get("data_type", ""),
            min_length=elem.get("min_length", 0),
            max_length=elem.get("max_length", 0),
            usage=elem.get("usage", ""),
            codes=codes,
        ))
    return elements


def _parse_stedi_loops(loops_json: list[dict]) -> list[LoopDef]:
    """Recursively parse loops from Stedi JSON format."""
    loops = []
    for loop_data in loops_json:
        segments = []
        for seg in loop_data.get("segments", []):
            elements = _parse_stedi_elements(seg.get("elements", []))
            segments.append(SegmentDef(
                id=seg.get("id", ""),
                name=seg.get("name", ""),
                position=str(seg.get("position", "000")),
                requirement=seg.get("requirement", "O"),
                max_use=seg.get("max_use", 1),
                notes=seg.get("notes", ""),
                elements=elements,
            ))

        child_loops = _parse_stedi_loops(loop_data.get("loops", []))

        loops.append(LoopDef(
            id=loop_data.get("id", ""),
            name=loop_data.get("name", ""),
            segments=segments,
            loops=child_loops,
        ))
    return loops


def _load_from_stedi(transaction_set: str, version: str) -> Optional[TransactionDef]:
    """
    Load a transaction definition from a Stedi JSON schema file.

    Returns None if no schema file is found for the requested transaction/version.
    """
    schema_path = _find_stedi_schema(transaction_set, version)
    if schema_path is None:
        return None

    try:
        with open(schema_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load Stedi schema %s: %s", schema_path, exc)
        return None

    tx_info = data.get("transaction_set", {})
    loops = _parse_stedi_loops(data.get("loops", []))

    return TransactionDef(
        transaction_set=tx_info.get("id", transaction_set),
        name=tx_info.get("name", f"Transaction {transaction_set}"),
        version=tx_info.get("version", version),
        description=tx_info.get("description", ""),
        loops=loops,
        source="stedi",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_transaction(transaction_set: str, version: str) -> Optional[TransactionDef]:
    """
    Load a normalized X12 transaction definition.

    Resolution order:
      1. pyx12 XML map (if pyx12 is installed and has the map)
      2. Stedi JSON schema (local file fallback)

    Args:
        transaction_set: X12 transaction set code, e.g. "850", "855", "997"
        version: X12 version, e.g. "004010", "005010"

    Returns:
        TransactionDef if found from any source, None otherwise.
    """
    # Try pyx12 first
    if _pyx12_available():
        result = _load_from_pyx12(transaction_set, version)
        if result is not None:
            logger.info(
                "Loaded %s/%s from pyx12 XML map", transaction_set, version
            )
            return result

    # Fall back to Stedi JSON
    result = _load_from_stedi(transaction_set, version)
    if result is not None:
        logger.info(
            "Loaded %s/%s from Stedi JSON schema", transaction_set, version
        )
        return result

    logger.warning(
        "No X12 definition found for %s/%s from any source",
        transaction_set, version,
    )
    return None


def get_segments(transaction_set: str, version: str) -> list[SegmentDef]:
    """
    Return a flat list of all segments for a transaction, across all loops.

    Convenience method for UIs that need a segment list without loop nesting.
    """
    tx = load_transaction(transaction_set, version)
    if tx is None:
        return []

    segments: list[SegmentDef] = []
    _collect_segments(tx.loops, segments)
    return segments


def _collect_segments(loops: list[LoopDef], out: list[SegmentDef]) -> None:
    """Recursively collect segments from nested loops."""
    for loop in loops:
        out.extend(loop.segments)
        _collect_segments(loop.loops, out)


def list_available_sources() -> dict[str, bool]:
    """
    Report which X12 definition sources are available.

    Returns a dict like: {"pyx12": True, "stedi": True}
    """
    return {
        "pyx12": _pyx12_available() and _pyx12_map_dir() is not None,
        "stedi": _stedi_schemas_dir().is_dir(),
    }


def list_pyx12_transactions() -> list[dict]:
    """
    Enumerate all transaction sets available from pyx12 XML maps.

    Returns a list of dicts with keys: transaction_set, version, map_file.
    """
    map_dir = _pyx12_map_dir()
    if map_dir is None:
        return []

    import xml.etree.ElementTree as ET
    maps_xml = map_dir / "maps.xml"
    if not maps_xml.is_file():
        return []

    try:
        tree = ET.parse(str(maps_xml))
        root = tree.getroot()
    except (ET.ParseError, OSError):
        return []

    results = []
    for version_node in root.findall("version"):
        icvn = version_node.get("icvn", "")
        for map_node in version_node.findall("map"):
            abbr = map_node.get("abbr", "")
            fic = map_node.get("fic", "")
            map_file = (map_node.text or "").strip()
            if abbr and map_file and fic != "FA":
                # Extract leading transaction set number from abbreviation.
                # Abbreviations like "835W1" or "837Q3" -> "835", "837".
                # Skip "X12" (control segments, not real transactions).
                m = re.match(r"^(\d{3})", abbr)
                if m:
                    ts = m.group(1)
                    results.append({
                        "transaction_set": ts,
                        "version": icvn,
                        "abbreviation": abbr,
                        "functional_group": fic,
                        "map_file": map_file,
                    })
    return results


def list_stedi_transactions() -> list[dict]:
    """
    Enumerate all transaction sets available from Stedi JSON schemas.

    Returns a list of dicts with keys: transaction_set, version, schema_file.
    """
    schemas_dir = _stedi_schemas_dir()
    if not schemas_dir.is_dir():
        return []

    results = []
    for path in sorted(schemas_dir.glob("x12_*.json")):
        # Parse filename: x12_{ts}_{ver}.json
        parts = path.stem.split("_")
        if len(parts) >= 3:
            ts = parts[1]
            ver = parts[2]
            results.append({
                "transaction_set": ts,
                "version": ver,
                "schema_file": path.name,
            })
    return results
