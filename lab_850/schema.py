"""schema.py — Dataclasses for 850 Trading Partner Guide extraction.

FieldInventory is the canonical output of extractor.py.
It is consumed by comparator.py and seed_generator.py.

No external dependencies — stdlib only.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ElementSpec:
    """A single element within an X12 segment."""

    element_id: str          # e.g. "BEG03"
    required: bool
    description: str = ""
    qualifier_values: list[str] = field(default_factory=list)  # e.g. ["00","05"]
    constraints: list[str] = field(default_factory=list)        # e.g. ["max 22 chars"]
    notes: str = ""


@dataclass
class SegmentSpec:
    """An X12 segment as described in a retailer's TPG."""

    segment_id: str           # e.g. "BEG"
    required: bool
    condition: str = ""       # e.g. "Required when cross-dock order"
    loop: str = ""            # e.g. "N1 loop"
    elements: dict[str, ElementSpec] = field(default_factory=dict)
    notes: str = ""


@dataclass
class FieldInventory:
    """Complete 850 field-level inventory for one retailer.

    Produced by extractor.py.  Consumed by comparator.py and seed_generator.py.
    """

    retailer_slug: str
    retailer_name: str
    source_pdf: str           # filename (not full path)
    spec_version: str         # e.g. "005010"
    extracted_at: str         # ISO-8601 UTC
    bundle: str               # "general_merchandise" | "transportation"
    segments: dict[str, SegmentSpec] = field(default_factory=dict)
    business_rules: list[str] = field(default_factory=list)
    confidence: str = "MEDIUM"          # HIGH | MEDIUM | LOW
    confidence_notes: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FieldInventory":
        """Reconstruct from a dict (e.g. loaded from a saved JSON file)."""
        segments: dict[str, SegmentSpec] = {}
        for seg_id, seg_data in d.get("segments", {}).items():
            elements: dict[str, ElementSpec] = {}
            for elem_id, elem_data in seg_data.get("elements", {}).items():
                elements[elem_id] = ElementSpec(**elem_data)
            seg_copy = {k: v for k, v in seg_data.items() if k != "elements"}
            segments[seg_id] = SegmentSpec(**seg_copy, elements=elements)

        inv_copy = {k: v for k, v in d.items() if k != "segments"}
        return cls(**inv_copy, segments=segments)

    @classmethod
    def from_json(cls, json_str: str) -> "FieldInventory":
        return cls.from_dict(json.loads(json_str))
