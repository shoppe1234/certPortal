"""
Spec Builder — Merges Layer 1 (base X12 structure) + Layer 2 (retailer overrides)
into a unified spec, then delegates to renderers for artifact generation.

Layer 1 data comes from x12_source (pyx12/Stedi).
Layer 2 data comes from the wizard's finalized config (a dict).

Artifacts (MD/HTML/PDF) are generated AFTER Layer 2 config so that
retailer-specific qualifiers and business rules appear inline in the spec
documents distributed to suppliers.

Architecture Decision: AD-8 from wizard refactoring prompt.
Constraint: NC-02 — YAML is the brain; no hardcoded transaction logic in .py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from certportal.generators.x12_source import (
    ElementDef,
    LoopDef,
    SegmentDef,
    TransactionDef,
    load_transaction,
)
from certportal.generators.template_loader import load_transaction_yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Merged spec data structures
# ---------------------------------------------------------------------------

@dataclass
class MergedElement:
    """An element with both Layer 1 base info and Layer 2 annotations."""
    ref: str
    element_id: str
    name: str
    requirement: str         # M, O, C
    data_type: str
    min_length: int = 0
    max_length: int = 0
    usage: str = ""
    codes: list[dict] = field(default_factory=list)
    # Layer 2 annotations
    layer2_qualifier: str = ""
    layer2_allowed_codes: list[str] = field(default_factory=list)
    layer2_note: str = ""
    layer2_format: str = ""
    layer2_constraints: dict = field(default_factory=dict)
    layer2_computed: str = ""
    layer2_codelist_ref: str = ""
    is_retailer_required: bool = False


@dataclass
class MergedSegment:
    """A segment with Layer 1 structure and Layer 2 overrides applied."""
    id: str
    name: str
    position: str
    requirement: str
    max_use: int = 1
    notes: str = ""
    elements: list[MergedElement] = field(default_factory=list)
    # Layer 2 annotations
    layer2_overrides: dict = field(default_factory=dict)
    layer2_instances: list[dict] = field(default_factory=list)
    layer2_condition: str = ""
    layer2_turnaround: dict = field(default_factory=dict)


@dataclass
class MergedLoop:
    """A loop with merged segments."""
    id: str
    name: str
    segments: list[MergedSegment] = field(default_factory=list)
    loops: list["MergedLoop"] = field(default_factory=list)


@dataclass
class MergedSpec:
    """Complete merged specification for a single transaction type."""
    transaction_type: str
    transaction_name: str
    x12_version: str
    retailer_name: str = ""
    loops: list[MergedLoop] = field(default_factory=list)
    business_rules: list[dict] = field(default_factory=list)
    mapping_notes: list[str] = field(default_factory=list)
    generated_at: str = ""
    source: str = ""  # "pyx12", "stedi", or "yaml_fallback"


# ---------------------------------------------------------------------------
# Internal helpers — Layer 2 annotation application
# ---------------------------------------------------------------------------

def _apply_layer2_to_element(
    element: ElementDef,
    l2_elements: dict,
    l2_overrides: dict,
) -> MergedElement:
    """
    Create a MergedElement from a Layer 1 ElementDef and Layer 2 config.

    l2_elements: dict from Layer 2 segments -> {seg} -> elements -> {elem_ref}
    l2_overrides: dict from Layer 2 segments -> {seg} -> overrides -> {elem_ref}
    """
    ref = element.ref
    l2_elem = l2_elements.get(ref, {})
    l2_ovr = l2_overrides.get(ref, {})

    # Merge Layer 2 values
    qualifier = l2_elem.get("qualifier", "") or l2_ovr.get("qualifier", "") or l2_ovr.get("fixed_value", "")
    allowed = l2_elem.get("allowed_codes", []) or l2_ovr.get("allowed_codes", [])
    note = l2_elem.get("note", "") or l2_ovr.get("note", "")
    fmt = l2_elem.get("format", "")
    constraints = l2_elem.get("constraints", {})
    computed = l2_elem.get("computed", "")
    codelist_ref = l2_elem.get("codelist_ref", "")

    # An element is "retailer required" if Layer 2 sets a specific qualifier
    # or the Layer 2 override exists
    is_retailer_required = bool(qualifier) or bool(l2_ovr)

    return MergedElement(
        ref=element.ref,
        element_id=element.element_id,
        name=element.name,
        requirement=element.requirement,
        data_type=element.data_type,
        min_length=element.min_length,
        max_length=element.max_length,
        usage=element.usage,
        codes=element.codes,
        layer2_qualifier=qualifier,
        layer2_allowed_codes=allowed if isinstance(allowed, list) else [allowed],
        layer2_note=note,
        layer2_format=fmt,
        layer2_constraints=constraints,
        layer2_computed=computed,
        layer2_codelist_ref=codelist_ref,
        is_retailer_required=is_retailer_required,
    )


def _find_layer2_segment(seg_id: str, l2_segments: dict) -> dict:
    """
    Find Layer 2 config for a segment, handling suffix variations.

    Layer 2 may use segment IDs like "N1_loop", "DTM_shipment", etc.
    We try: exact match, then prefix match (e.g., "DTM" matches "DTM_shipment").
    """
    if seg_id in l2_segments:
        return l2_segments[seg_id]

    # Try suffix variations
    for l2_key, l2_val in l2_segments.items():
        base = l2_key.split("_")[0] if "_" in l2_key else l2_key
        if base == seg_id:
            return l2_val

    return {}


def _merge_segment(
    segment: SegmentDef,
    l2_segments: dict,
) -> MergedSegment:
    """Merge a Layer 1 SegmentDef with Layer 2 config."""
    l2_seg = _find_layer2_segment(segment.id, l2_segments)

    l2_elements = l2_seg.get("elements", {}) if isinstance(l2_seg, dict) else {}
    l2_overrides = l2_seg.get("overrides", {}) if isinstance(l2_seg, dict) else {}
    l2_instances = l2_seg.get("instances", []) if isinstance(l2_seg, dict) else []
    l2_condition = l2_seg.get("condition", "") if isinstance(l2_seg, dict) else ""
    l2_turnaround = l2_seg.get("turnaround", {}) if isinstance(l2_seg, dict) else {}

    merged_elements = [
        _apply_layer2_to_element(elem, l2_elements, l2_overrides)
        for elem in segment.elements
    ]

    return MergedSegment(
        id=segment.id,
        name=segment.name,
        position=segment.position,
        requirement=segment.requirement,
        max_use=segment.max_use,
        notes=segment.notes,
        elements=merged_elements,
        layer2_overrides=l2_overrides,
        layer2_instances=l2_instances,
        layer2_condition=l2_condition,
        layer2_turnaround=l2_turnaround,
    )


def _merge_loop(loop: LoopDef, l2_segments: dict) -> MergedLoop:
    """Recursively merge a Layer 1 LoopDef with Layer 2 segment configs."""
    merged_segments = [
        _merge_segment(seg, l2_segments) for seg in loop.segments
    ]
    merged_child_loops = [
        _merge_loop(child, l2_segments) for child in loop.loops
    ]
    return MergedLoop(
        id=loop.id,
        name=loop.name,
        segments=merged_segments,
        loops=merged_child_loops,
    )


# ---------------------------------------------------------------------------
# Fallback: build TransactionDef from edi_framework YAML
# ---------------------------------------------------------------------------

def _load_from_yaml_fallback(
    transaction_type: str, x12_version: str
) -> Optional[TransactionDef]:
    """
    Build a minimal TransactionDef from edi_framework/transactions/*.yaml.

    Used when neither pyx12 nor Stedi has the transaction.
    """
    tx_data = load_transaction_yaml(transaction_type)
    if not tx_data:
        return None

    tx = tx_data.get("transaction", {})
    tx_name = tx.get("name", f"Transaction {transaction_type}")

    # Build a flat loop structure from heading + detail
    heading_segs = []
    for seg_name, seg_config in (tx.get("heading") or {}).items():
        if not isinstance(seg_config, dict):
            continue
        heading_segs.append(SegmentDef(
            id=seg_name,
            name=seg_config.get("name", seg_name),
            position="",
            requirement="M" if seg_config.get("required", False) else "O",
        ))

    detail_segs = []
    for seg_name, seg_config in (tx.get("detail") or {}).items():
        if not isinstance(seg_config, dict):
            continue
        detail_segs.append(SegmentDef(
            id=seg_name,
            name=seg_config.get("name", seg_name),
            position="",
            requirement="M" if seg_config.get("required", False) else "O",
        ))

    loops = []
    if heading_segs:
        loops.append(LoopDef(id="HEADING", name="Heading", segments=heading_segs))
    if detail_segs:
        loops.append(LoopDef(id="DETAIL", name="Detail", segments=detail_segs))

    return TransactionDef(
        transaction_set=transaction_type,
        name=tx_name,
        version=x12_version,
        loops=loops,
        source="yaml_fallback",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_spec(
    transaction_type: str,
    x12_version: str,
    layer2_config: Optional[dict] = None,
    retailer_name: str = "",
) -> MergedSpec:
    """
    Merge Layer 1 (base X12 structure) + Layer 2 (retailer overrides)
    into a unified MergedSpec.

    Args:
        transaction_type: X12 transaction set code (e.g. "850").
        x12_version: X12 version (e.g. "004010").
        layer2_config: Optional dict of Layer 2 overrides. Expected structure:
            {
                "segments": { "BEG": { "elements": {...}, "overrides": {...} }, ... },
                "business_rules": [...],
                "mapping_refs": [...]
            }
            If None, only Layer 1 data is used.
        retailer_name: Display name for the retailer (appears in generated docs).

    Returns:
        MergedSpec containing all merged segment/element data plus annotations.
    """
    # Load Layer 1 from x12_source (pyx12 -> Stedi -> YAML fallback)
    tx_def = load_transaction(transaction_type, x12_version)
    if tx_def is None:
        tx_def = _load_from_yaml_fallback(transaction_type, x12_version)
    if tx_def is None:
        logger.error(
            "No X12 definition found for %s/%s from any source",
            transaction_type, x12_version,
        )
        return MergedSpec(
            transaction_type=transaction_type,
            transaction_name=f"Transaction {transaction_type}",
            x12_version=x12_version,
            retailer_name=retailer_name,
            generated_at=datetime.now(timezone.utc).isoformat(),
            source="none",
        )

    # Extract Layer 2 segments dict
    l2_segments = {}
    l2_business_rules = []
    l2_mapping_refs = []

    if layer2_config and isinstance(layer2_config, dict):
        l2_segments = layer2_config.get("segments", {})
        l2_business_rules = layer2_config.get("business_rules", [])
        l2_mapping_refs = layer2_config.get("mapping_refs", [])

    # Merge loops
    merged_loops = [_merge_loop(loop, l2_segments) for loop in tx_def.loops]

    # Build mapping notes from refs
    mapping_notes = []
    for ref in l2_mapping_refs:
        if isinstance(ref, str):
            mapping_notes.append(ref)
        elif isinstance(ref, dict):
            mapping_notes.append(ref.get("ref", str(ref)))

    return MergedSpec(
        transaction_type=tx_def.transaction_set,
        transaction_name=tx_def.name,
        x12_version=tx_def.version,
        retailer_name=retailer_name,
        loops=merged_loops,
        business_rules=l2_business_rules if isinstance(l2_business_rules, list) else [],
        mapping_notes=mapping_notes,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source=tx_def.source,
    )


def generate_artifacts(
    merged_spec: MergedSpec,
    output_formats: tuple[str, ...] = ("md", "html", "pdf"),
) -> dict[str, bytes]:
    """
    Render a MergedSpec to all requested output formats.

    Args:
        merged_spec: The merged spec to render.
        output_formats: Tuple of format strings: "md", "html", "pdf".

    Returns:
        Dict mapping format extension to content bytes.
        Only includes formats that were successfully generated.
    """
    artifacts: dict[str, bytes] = {}

    md_content = ""
    if "md" in output_formats or "html" in output_formats or "pdf" in output_formats:
        from certportal.generators.render_markdown import render_markdown
        md_content = render_markdown(merged_spec)
        if "md" in output_formats:
            artifacts["md"] = md_content.encode("utf-8")

    html_content = ""
    if ("html" in output_formats or "pdf" in output_formats) and md_content:
        from certportal.generators.render_html import render_html
        html_content = render_html(md_content, retailer_name=merged_spec.retailer_name)
        if "html" in output_formats:
            artifacts["html"] = html_content.encode("utf-8")

    if "pdf" in output_formats and html_content:
        from certportal.generators.render_pdf import render_pdf, is_pdf_available
        if is_pdf_available():
            pdf_bytes = render_pdf(html_content)
            if pdf_bytes:
                artifacts["pdf"] = pdf_bytes
        else:
            logger.warning(
                "PDF generation requested but no PDF renderer available. "
                "Install weasyprint or fpdf2."
            )

    return artifacts


def generate_all_artifacts(
    transaction_types: list[str],
    x12_version: str,
    layer2_configs: Optional[dict[str, dict]] = None,
    retailer_name: str = "",
    output_formats: tuple[str, ...] = ("md", "html", "pdf"),
) -> dict[str, dict[str, bytes]]:
    """
    Generate artifacts for multiple transaction types in batch.

    Args:
        transaction_types: List of X12 transaction set codes (e.g. ["850", "855"]).
        x12_version: X12 version (e.g. "004010").
        layer2_configs: Optional dict mapping transaction_type -> layer2_config.
            Example: {"850": {"segments": {...}}, "855": {"segments": {...}}}
        retailer_name: Display name for the retailer.
        output_formats: Tuple of format strings.

    Returns:
        Dict mapping transaction_type -> dict of format -> bytes.
        Example: {"850": {"md": b"...", "html": b"...", "pdf": b"..."}}
    """
    all_artifacts: dict[str, dict[str, bytes]] = {}

    for tx_type in transaction_types:
        l2_config = None
        if layer2_configs and tx_type in layer2_configs:
            l2_config = layer2_configs[tx_type]

        merged = build_spec(tx_type, x12_version, l2_config, retailer_name)
        artifacts = generate_artifacts(merged, output_formats)
        all_artifacts[tx_type] = artifacts

        logger.info(
            "Generated artifacts for %s/%s: %s",
            tx_type, x12_version, list(artifacts.keys()),
        )

    return all_artifacts
