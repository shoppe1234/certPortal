"""lab_850 — 850 Trading Partner Guide PDF analyser.

Standalone tool for extracting X12 850 field inventories from retailer PDFs,
comparing them across retailers, and generating deterministic Andy Path 3
wizard_payload seeds.

Isolation: no imports from certportal/, portals/, agents/, lifecycle_engine/.
Dependencies: openai, pdfplumber (stdlib + these two third-party packages only).

Entry point:
    python -m lab_850 --help
"""
from lab_850.schema import ElementSpec, FieldInventory, SegmentSpec

__all__ = ["ElementSpec", "FieldInventory", "SegmentSpec"]
