"""
X12 Version Registry — Dynamic Version and Transaction Set Enumeration

Enumerates available X12 versions and their transaction sets by querying
x12_source (pyx12 + Stedi). No static transaction lists.

The registry also reads partner_registry.yaml to surface partner-specific
transaction sets alongside the raw X12 source data.

Architecture Decision: AD-2, AD-3, AD-7 from wizard refactoring prompt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from certportal.generators.x12_source import (
    list_pyx12_transactions,
    list_stedi_transactions,
    load_transaction,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Partner registry path
# ---------------------------------------------------------------------------

_EDI_FRAMEWORK_DIR = Path(__file__).resolve().parents[2] / "edi_framework"
_PARTNER_REGISTRY_PATH = _EDI_FRAMEWORK_DIR / "partner_registry.yaml"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TransactionSetInfo:
    """Information about a transaction set available for a given version."""
    transaction_set: str         # e.g. "850"
    name: str                    # e.g. "Purchase Order"
    source: str                  # "pyx12", "stedi", or "partner_registry"
    functional_group: str = ""   # e.g. "PO"
    direction: str = ""          # "inbound", "outbound", "both", or ""


@dataclass
class VersionInfo:
    """Information about an available X12 version."""
    version: str                 # e.g. "004010"
    display_name: str            # e.g. "4010 (ANSI X12)"
    transaction_sets: list[TransactionSetInfo] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_version(raw: str) -> str:
    """
    Normalize a version string to the 6-digit X12 version format.

    The X12 standard uses 6-digit versions like "004010", "005010".
    pyx12 uses 5-digit interchange control version numbers (icvn) like
    "00401" (= 004010) and "00501" (= 005010). The mapping is:
      icvn "00400" -> version "004000" (rarely used)
      icvn "00401" -> version "004010"
      icvn "00501" -> version "005010"

    We also handle short forms: "4010" -> "004010", "5010" -> "005010".

    Examples:
        "4010"   -> "004010"
        "004010" -> "004010"
        "00401"  -> "004010"
        "00501"  -> "005010"
        "5010"   -> "005010"
    """
    # Already 6 digits — return as-is
    if len(raw) == 6 and raw.isdigit():
        return raw

    # 4-digit short form: "4010" -> "004010"
    if len(raw) == 4 and raw.isdigit():
        return raw.zfill(6)

    # 5-digit pyx12 icvn: "00401" -> "004010", "00501" -> "005010"
    if len(raw) == 5 and raw.isdigit():
        return raw + "0"

    # Fallback: zero-pad to 6
    return raw.zfill(6)


def _load_partner_registry() -> dict:
    """Load partner_registry.yaml from edi_framework/."""
    if not _PARTNER_REGISTRY_PATH.is_file():
        logger.warning("partner_registry.yaml not found at %s", _PARTNER_REGISTRY_PATH)
        return {}
    try:
        with open(_PARTNER_REGISTRY_PATH, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("Failed to load partner_registry.yaml: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_available_versions() -> list[VersionInfo]:
    """
    Enumerate all X12 versions that have at least one loadable transaction set.

    Sources are combined:
      1. pyx12 XML maps (via x12_source.list_pyx12_transactions)
      2. Stedi JSON schemas (via x12_source.list_stedi_transactions)
      3. partner_registry.yaml (declares versions per partner)

    Returns a list of VersionInfo sorted by version string.
    """
    # Collect all (version, transaction_set) pairs from all sources
    version_map: dict[str, dict[str, TransactionSetInfo]] = {}

    # --- pyx12 ---
    for entry in list_pyx12_transactions():
        ver = _normalize_version(entry["version"])
        ts = entry["transaction_set"]
        if ver not in version_map:
            version_map[ver] = {}
        if ts not in version_map[ver]:
            version_map[ver][ts] = TransactionSetInfo(
                transaction_set=ts,
                name="",  # pyx12 maps.xml doesn't include display names
                source="pyx12",
                functional_group=entry.get("functional_group", ""),
            )

    # --- Stedi ---
    for entry in list_stedi_transactions():
        ver = _normalize_version(entry["version"])
        ts = entry["transaction_set"]
        if ver not in version_map:
            version_map[ver] = {}
        if ts not in version_map[ver]:
            version_map[ver][ts] = TransactionSetInfo(
                transaction_set=ts,
                name="",
                source="stedi",
            )

    # --- partner_registry ---
    registry = _load_partner_registry()
    for _slug, partner in registry.get("partners", {}).items():
        for ver_raw in partner.get("x12_versions", []):
            ver = _normalize_version(str(ver_raw))
            if ver not in version_map:
                version_map[ver] = {}
            for tx in partner.get("transaction_sets", []):
                ts = str(tx.get("id", ""))
                if ts and ts not in version_map[ver]:
                    version_map[ver][ts] = TransactionSetInfo(
                        transaction_set=ts,
                        name=tx.get("name", ""),
                        source="partner_registry",
                        functional_group=tx.get("functional_group", ""),
                        direction=tx.get("direction", ""),
                    )
                elif ts and ts in version_map[ver]:
                    # Enrich existing entry with partner-provided metadata
                    existing = version_map[ver][ts]
                    if not existing.name:
                        existing.name = tx.get("name", "")
                    if not existing.functional_group:
                        existing.functional_group = tx.get("functional_group", "")
                    if not existing.direction:
                        existing.direction = tx.get("direction", "")

    # Build VersionInfo list
    results = []
    for ver in sorted(version_map.keys()):
        short_ver = ver.lstrip("0") or "0"
        display = f"{short_ver} (ANSI X12)"
        tx_list = sorted(version_map[ver].values(), key=lambda t: t.transaction_set)
        results.append(VersionInfo(
            version=ver,
            display_name=display,
            transaction_sets=tx_list,
        ))

    return results


def get_version(version: str) -> Optional[VersionInfo]:
    """
    Get details for a specific X12 version.

    Args:
        version: X12 version string, e.g. "004010" or "4010"

    Returns:
        VersionInfo if the version has any available transactions, None otherwise.
    """
    normalized = _normalize_version(version)
    for vi in get_available_versions():
        if vi.version == normalized:
            return vi
    return None


def get_transaction_sets_for_version(version: str) -> list[TransactionSetInfo]:
    """
    Return all available transaction sets for a given X12 version.

    Args:
        version: X12 version string, e.g. "004010" or "4010"

    Returns:
        List of TransactionSetInfo, empty if version not found.
    """
    vi = get_version(version)
    if vi is None:
        return []
    return vi.transaction_sets


def get_partner_versions(partner_slug: str) -> list[VersionInfo]:
    """
    Get X12 versions declared by a specific partner in partner_registry.yaml.

    Returns only the versions and transaction sets that the partner declares,
    filtered from the full available set.
    """
    registry = _load_partner_registry()
    partner = registry.get("partners", {}).get(partner_slug)
    if partner is None:
        logger.warning("Partner '%s' not found in registry", partner_slug)
        return []

    partner_versions = {_normalize_version(str(v)) for v in partner.get("x12_versions", [])}
    partner_tx_ids = {str(tx.get("id", "")) for tx in partner.get("transaction_sets", [])}

    all_versions = get_available_versions()
    results = []
    for vi in all_versions:
        if vi.version in partner_versions:
            filtered_tx = [t for t in vi.transaction_sets if t.transaction_set in partner_tx_ids]
            if filtered_tx:
                results.append(VersionInfo(
                    version=vi.version,
                    display_name=vi.display_name,
                    transaction_sets=filtered_tx,
                ))

    return results


def is_transaction_loadable(transaction_set: str, version: str) -> bool:
    """
    Check whether a transaction set can be fully loaded (segments + elements).

    This goes beyond enumeration — it actually tries to load the definition
    from x12_source to verify the data is parseable.
    """
    result = load_transaction(transaction_set, version)
    return result is not None
