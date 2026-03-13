"""comparator.py — Cross-retailer 850 field comparison.

Takes a list of FieldInventory objects (one per retailer) and produces:
  1. A segment presence matrix  — which retailers use which segments
  2. A qualifier divergence report — where retailers use different qualifier values
  3. A common-core summary — elements every retailer mandates (safe to pre-fill)
  4. A Markdown report string

No external dependencies — stdlib only.
"""
from __future__ import annotations

from collections import defaultdict
from io import StringIO
from typing import Sequence

from lab_850.schema import ElementSpec, FieldInventory


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compare(inventories: Sequence[FieldInventory]) -> "ComparisonReport":
    """Build a ComparisonReport from multiple FieldInventory objects."""
    if not inventories:
        raise ValueError("At least one FieldInventory is required.")
    return ComparisonReport(list(inventories))


# ---------------------------------------------------------------------------
# Report class
# ---------------------------------------------------------------------------


class ComparisonReport:
    """Cross-retailer comparison report.

    Attributes:
        inventories:     The input FieldInventory list.
        segment_matrix:  {segment_id: {retailer_slug: bool}}
        qualifier_diff:  {(segment_id, element_id): {retailer_slug: [qualifier_values]}}
        common_core:     {segment_id: {element_id: ElementSpec}} — universal required elements
    """

    def __init__(self, inventories: list[FieldInventory]) -> None:
        self.inventories = inventories
        self._retailer_slugs = [inv.retailer_slug for inv in inventories]

        self.segment_matrix: dict[str, dict[str, bool]] = self._build_segment_matrix()
        self.qualifier_diff: dict[
            tuple[str, str], dict[str, list[str]]
        ] = self._build_qualifier_diff()
        self.common_core: dict[str, dict[str, ElementSpec]] = self._build_common_core()

    # ------------------------------------------------------------------
    # Markdown export
    # ------------------------------------------------------------------

    def to_markdown(self) -> str:
        buf = StringIO()
        w = buf.write

        retailers = self._retailer_slugs
        n = len(self.inventories)

        w("# 850 Cross-Retailer Comparison Report\n\n")
        w(f"**Retailers analysed ({n}):** {', '.join(retailers)}\n\n")

        # --- Segment presence matrix ---
        w("## Segment Presence Matrix\n\n")
        header = "| Segment | " + " | ".join(retailers) + " |\n"
        w(header)
        w("|" + "---------|" * (n + 1) + "\n")
        all_segs = sorted(self.segment_matrix.keys())
        for seg in all_segs:
            row_cells = [
                "✓" if self.segment_matrix[seg].get(r, False) else "–"
                for r in retailers
            ]
            w(f"| `{seg}` | " + " | ".join(row_cells) + " |\n")
        w("\n")

        # --- Common core ---
        w("## Common Core (required by all retailers)\n\n")
        if not self.common_core:
            w("_No elements are mandatory across all analysed retailers._\n\n")
        else:
            for seg_id, elements in sorted(self.common_core.items()):
                w(f"### {seg_id}\n\n")
                for elem_id, spec in sorted(elements.items()):
                    qualifier_str = (
                        ", ".join(f"`{q}`" for q in spec.qualifier_values)
                        if spec.qualifier_values
                        else "—"
                    )
                    w(f"- **{elem_id}** — {spec.description or '(no description)'}  \n")
                    w(f"  Qualifiers: {qualifier_str}  \n")
                    if spec.constraints:
                        w(f"  Constraints: {'; '.join(spec.constraints)}  \n")
                    if spec.notes:
                        w(f"  Notes: {spec.notes}  \n")
                w("\n")

        # --- Qualifier divergence ---
        w("## Qualifier Divergence (retailers differ)\n\n")
        divergences = {
            k: v
            for k, v in self.qualifier_diff.items()
            if len({tuple(sorted(vals)) for vals in v.values()}) > 1
        }
        if not divergences:
            w("_All retailers agree on qualifier values for every shared element._\n\n")
        else:
            for (seg_id, elem_id), by_retailer in sorted(divergences.items()):
                w(f"### `{seg_id}.{elem_id}`\n\n")
                for retailer, vals in sorted(by_retailer.items()):
                    vals_str = ", ".join(f"`{v}`" for v in vals) if vals else "_(none)_"
                    w(f"- **{retailer}**: {vals_str}\n")
                w("\n")

        # --- Business rules per retailer ---
        w("## Business Rules by Retailer\n\n")
        for inv in self.inventories:
            w(f"### {inv.retailer_name} (`{inv.retailer_slug}`)\n\n")
            if inv.business_rules:
                for rule in inv.business_rules:
                    w(f"- {rule}\n")
            else:
                w("_No business rules extracted._\n")
            w("\n")

        # --- Confidence summary ---
        w("## Extraction Confidence\n\n")
        for inv in self.inventories:
            flag = " ⚠" if inv.confidence != "HIGH" else ""
            w(f"- **{inv.retailer_name}**: {inv.confidence}{flag}\n")
            for note in inv.confidence_notes:
                w(f"  - {note}\n")
        w("\n")

        return buf.getvalue()

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _build_segment_matrix(self) -> dict[str, dict[str, bool]]:
        matrix: dict[str, dict[str, bool]] = defaultdict(dict)
        for inv in self.inventories:
            for seg_id in inv.segments:
                matrix[seg_id][inv.retailer_slug] = True
        return dict(matrix)

    def _build_qualifier_diff(
        self,
    ) -> dict[tuple[str, str], dict[str, list[str]]]:
        diff: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(dict)
        for inv in self.inventories:
            for seg_id, seg_spec in inv.segments.items():
                for elem_id, elem_spec in seg_spec.elements.items():
                    if elem_spec.qualifier_values:
                        diff[(seg_id, elem_id)][inv.retailer_slug] = (
                            elem_spec.qualifier_values
                        )
        return dict(diff)

    def _build_common_core(self) -> dict[str, dict[str, ElementSpec]]:
        """Elements that are required=True in every retailer's inventory."""
        n = len(self.inventories)
        # count[(seg_id, elem_id)] = how many retailers have this as required
        required_count: dict[tuple[str, str], int] = defaultdict(int)
        # Store a representative ElementSpec (from the last retailer seen — for display)
        representative: dict[tuple[str, str], ElementSpec] = {}

        for inv in self.inventories:
            for seg_id, seg_spec in inv.segments.items():
                for elem_id, elem_spec in seg_spec.elements.items():
                    if elem_spec.required:
                        required_count[(seg_id, elem_id)] += 1
                        representative[(seg_id, elem_id)] = elem_spec

        core: dict[str, dict[str, ElementSpec]] = defaultdict(dict)
        for (seg_id, elem_id), count in required_count.items():
            if count == n:
                core[seg_id][elem_id] = representative[(seg_id, elem_id)]

        return dict(core)
