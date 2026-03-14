"""
Markdown Renderer — Per-transaction companion guide with Layer 2 annotations.

Renders a MergedSpec (from spec_builder) into a structured Markdown document
suitable for distribution to suppliers. Layer 2 overrides appear inline with
markers like [RETAILER REQUIRED] and specific qualifier values.

Reference: sampleArtifacts/stedi/generator/render_markdown.py

Architecture Decision: AD-8 from wizard refactoring prompt.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from certportal.generators.spec_builder import (
    MergedElement,
    MergedLoop,
    MergedSegment,
    MergedSpec,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _requirement_label(req: str) -> str:
    """Convert requirement code to display label."""
    return {
        "M": "Mandatory",
        "O": "Optional",
        "C": "Conditional",
        "N": "Not Used",
    }.get(req, req)


def _usage_label(req: str) -> str:
    """Convert requirement code to usage label for tables."""
    return {
        "M": "Must Use",
        "O": "Used",
        "C": "Situational",
        "N": "Not Used",
    }.get(req, req)


def _escape_pipe(text: str) -> str:
    """Escape pipe characters for Markdown tables."""
    return text.replace("|", "\\|")


def _render_element_qualifier(elem: MergedElement) -> str:
    """Build the qualifier/value column content for an element."""
    parts = []

    if elem.layer2_qualifier:
        parts.append(f"**{elem.layer2_qualifier}**")

    if elem.layer2_allowed_codes:
        codes = [c for c in elem.layer2_allowed_codes if c]
        if codes:
            parts.append(", ".join(str(c) for c in codes))

    if elem.layer2_format:
        parts.append(elem.layer2_format)

    if elem.layer2_computed:
        parts.append(f"*{elem.layer2_computed}*")

    return " ".join(parts) if parts else ""


def _render_element_notes(elem: MergedElement) -> str:
    """Build the retailer notes column for an element."""
    parts = []

    if elem.is_retailer_required:
        parts.append("**[RETAILER REQUIRED]**")

    if elem.layer2_note:
        parts.append(elem.layer2_note)

    if elem.layer2_constraints:
        for key, val in elem.layer2_constraints.items():
            parts.append(f"{key}: {val}")

    if elem.layer2_codelist_ref:
        parts.append(f"(see codelist: {elem.layer2_codelist_ref})")

    return " ".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_header(spec: MergedSpec) -> str:
    """Render the document header."""
    lines = []
    lines.append(
        f"# X12 {spec.x12_version} {spec.transaction_type} "
        f"{spec.transaction_name} — Companion Guide\n"
    )

    gen_date = spec.generated_at or datetime.now(timezone.utc).isoformat()
    meta_parts = [f"**Generated:** {gen_date[:10]}"]
    if spec.retailer_name:
        meta_parts.append(f"**Retailer:** {spec.retailer_name}")
    meta_parts.append(f"**Source:** {spec.source}")
    lines.append("  |  ".join(meta_parts) + "\n")

    lines.append("---\n")
    return "\n".join(lines)


def _render_overview_table(spec: MergedSpec) -> str:
    """Render the Transaction Set Overview table."""
    lines = []
    lines.append("## Transaction Set Overview\n")

    for loop in spec.loops:
        if not loop.segments and not loop.loops:
            continue

        lines.append(f"### {loop.name}\n")
        lines.append("| Pos | Seg ID | Segment Name | Req | Max Use | Usage |")
        lines.append("|-----|--------|--------------|-----|---------|-------|")

        for seg in loop.segments:
            pos = _escape_pipe(seg.position)
            sid = _escape_pipe(seg.id)
            sname = _escape_pipe(seg.name)
            req = seg.requirement
            max_use = str(seg.max_use)
            usage = _usage_label(req)
            lines.append(f"| {pos} | {sid} | {sname} | {req} | {max_use} | {usage} |")

        # Nested loops
        for child_loop in loop.loops:
            for seg in child_loop.segments:
                pos = _escape_pipe(seg.position)
                sid = _escape_pipe(seg.id)
                sname = _escape_pipe(f"{seg.name} ({child_loop.name})")
                req = seg.requirement
                max_use = str(seg.max_use)
                usage = _usage_label(req)
                lines.append(f"| {pos} | {sid} | {sname} | {req} | {max_use} | {usage} |")

        lines.append("")

    return "\n".join(lines)


def _render_segment_detail(seg: MergedSegment) -> str:
    """Render detailed section for a single segment."""
    lines = []

    lines.append(f"### {seg.id} — {seg.name}\n")
    lines.append(
        f"**Requirement:** {_requirement_label(seg.requirement)}  |  "
        f"**Max Use:** {seg.max_use}\n"
    )

    if seg.notes:
        lines.append(f"**Purpose:** {seg.notes}\n")

    if seg.layer2_condition:
        lines.append(f"> **Condition:** {seg.layer2_condition}\n")

    # Layer 2 instances (e.g., N1 loop instances)
    if seg.layer2_instances:
        lines.append("**Instances:**\n")
        for inst in seg.layer2_instances:
            qualifier = inst.get("qualifier_N101", inst.get("qualifier", ""))
            desc = inst.get("description", "")
            req = "Required" if inst.get("required", False) else "Optional"
            lines.append(f"- **{qualifier}** — {desc} ({req})")
        lines.append("")

    # Layer 2 overrides at segment level
    if seg.layer2_overrides:
        lines.append("**Retailer Overrides:**\n")
        for ovr_key, ovr_val in seg.layer2_overrides.items():
            if isinstance(ovr_val, dict):
                qual = ovr_val.get("qualifier", "")
                note = ovr_val.get("note", "")
                allowed = ovr_val.get("allowed_codes", [])
                parts = [f"**{ovr_key}**:"]
                if qual:
                    parts.append(f"qualifier = **{qual}**")
                if allowed:
                    parts.append(f"allowed = {', '.join(str(c) for c in allowed)}")
                if note:
                    parts.append(f"— {note}")
                lines.append(f"- {' '.join(parts)}")
        lines.append("")

    # Element table
    if seg.elements:
        lines.append(
            "| Element | Name | Type | Min/Max | Usage | "
            "Qualifier/Value | Retailer Notes |"
        )
        lines.append(
            "|---------|------|------|---------|-------|"
            "-----------------|----------------|"
        )

        for elem in seg.elements:
            ref = _escape_pipe(elem.ref)
            name = _escape_pipe(elem.name)
            dtype = _escape_pipe(elem.data_type)
            minmax = f"{elem.min_length}/{elem.max_length}"
            usage = _usage_label(elem.requirement)
            qualifier = _escape_pipe(_render_element_qualifier(elem))
            notes = _escape_pipe(_render_element_notes(elem))
            lines.append(
                f"| {ref} | {name} | {dtype} | {minmax} | {usage} | "
                f"{qualifier} | {notes} |"
            )

        lines.append("")

    # Element detail with code lists
    for elem in seg.elements:
        if elem.codes or elem.layer2_qualifier or elem.layer2_allowed_codes:
            lines.append(f"#### {elem.ref} — {elem.name}\n")
            lines.append(f"- **Requirement:** {_requirement_label(elem.requirement)}")
            if elem.data_type:
                lines.append(f"- **Type:** {elem.data_type}")
            lines.append(f"- **Min/Max Length:** {elem.min_length}/{elem.max_length}")
            if elem.usage:
                lines.append(f"- **Usage Notes:** {elem.usage}")
            if elem.layer2_qualifier:
                lines.append(
                    f"- **Retailer Qualifier:** {elem.layer2_qualifier} "
                    f"**[REQUIRED BY RETAILER]**"
                )
            if elem.layer2_note:
                lines.append(f"- **Retailer Note:** {elem.layer2_note}")

            if elem.codes:
                lines.append(f"\n**Code List for {elem.ref}:**\n")
                lines.append("| Code | Description |")
                lines.append("|------|-------------|")
                for code_entry in elem.codes:
                    code = _escape_pipe(str(code_entry.get("code", "")))
                    desc = _escape_pipe(str(code_entry.get("description", "")))
                    lines.append(f"| {code} | {desc} |")
                lines.append("")

    # Turnaround info
    if seg.layer2_turnaround:
        lines.append("**Turnaround Rules:**\n")
        echo_entire = seg.layer2_turnaround.get("echo_entire_segment", False)
        if echo_entire:
            lines.append("- Echo entire segment to response transaction")
        echoes_to = seg.layer2_turnaround.get("echoes_to", [])
        for target in echoes_to:
            tx = target.get("transaction", "")
            target_seg = target.get("segment", "")
            target_elem = target.get("element", "")
            parts = [f"Echoes to: {tx}"]
            if target_seg:
                parts.append(f"segment {target_seg}")
            if target_elem:
                parts.append(f"element {target_elem}")
            lines.append(f"- {' '.join(parts)}")
        lines.append("")

    lines.append("---\n")
    return "\n".join(lines)


def _render_all_segments(spec: MergedSpec) -> str:
    """Render all segment detail sections."""
    lines = []
    lines.append("## Segment Detail\n")

    for loop in spec.loops:
        if loop.segments:
            lines.append(f"### Loop: {loop.name}\n")
            for seg in loop.segments:
                lines.append(_render_segment_detail(seg))

        # Nested loops
        for child_loop in loop.loops:
            if child_loop.segments:
                lines.append(f"### Loop: {child_loop.name}\n")
                for seg in child_loop.segments:
                    lines.append(_render_segment_detail(seg))

    return "\n".join(lines)


def _render_business_rules(spec: MergedSpec) -> str:
    """Render the business rules section."""
    if not spec.business_rules:
        return ""

    lines = []
    lines.append("## Business Rules\n")

    for rule in spec.business_rules:
        if isinstance(rule, dict):
            rule_id = rule.get("id", "")
            name = rule.get("name", rule_id)
            desc = rule.get("description", "")
            enforcement = rule.get("enforcement", "")

            lines.append(f"### {name}")
            if rule_id:
                lines.append(f"*Rule ID: {rule_id}*\n")
            lines.append(desc)
            if enforcement:
                lines.append(f"\n**Enforcement:** {enforcement}")

            # Additional rule details
            rule_map = rule.get("map", {})
            if rule_map:
                lines.append("\n| Transaction | Value |")
                lines.append("|-------------|-------|")
                for tx, val in rule_map.items():
                    lines.append(f"| {tx} | {val} |")

            allowed = rule.get("allowed", [])
            if allowed:
                lines.append(f"\n**Allowed values:** {', '.join(str(a) for a in allowed)}")

            lines.append("")
        elif isinstance(rule, str):
            lines.append(f"- {rule}")

    lines.append("")
    return "\n".join(lines)


def _render_mapping_notes(spec: MergedSpec) -> str:
    """Render the mapping notes section."""
    if not spec.mapping_notes:
        return ""

    lines = []
    lines.append("## Mapping Notes\n")
    lines.append(
        "The following mapping files define turnaround rules for this transaction:\n"
    )

    for ref in spec.mapping_notes:
        lines.append(f"- `{ref}`")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_markdown(merged_spec: MergedSpec) -> str:
    """
    Render a MergedSpec as a complete Markdown companion guide.

    Args:
        merged_spec: The merged spec (Layer 1 + Layer 2) to render.

    Returns:
        Complete Markdown document as a string.
    """
    parts = []

    parts.append(_render_header(merged_spec))
    parts.append(_render_overview_table(merged_spec))
    parts.append(_render_all_segments(merged_spec))
    parts.append(_render_business_rules(merged_spec))
    parts.append(_render_mapping_notes(merged_spec))

    # Revision history placeholder
    parts.append("## Revision History\n")
    parts.append("| Version | Date | Description |")
    parts.append("|---------|------|-------------|")
    gen_date = (merged_spec.generated_at or "")[:10]
    parts.append(f"| 1.0 | {gen_date} | Initial release |\n")

    return "\n".join(parts)
