"""extractor.py — PDF → FieldInventory via schema-constrained Claude extraction.

Unlike Andy's open-ended Path 1 prompt, this extractor:
  1. Targets only known 850 segments (ISA, GS, BEG, REF, DTM, N1/N3/N4,
     PO1, PO3, PID, CTT) with element-level granularity.
  2. Uses a schema-contract system prompt so the LLM fills in a pre-defined
     structure rather than inventing one.
  3. Returns a typed FieldInventory — no YAML involved at this stage.

Backend: anthropic (claude-opus-4-6) — requires ANTHROPIC_API_KEY env var.
Dependencies: anthropic, pdfplumber  (both already in requirements.txt)
No imports from certportal/, portals/, agents/, lifecycle_engine/.
"""
from __future__ import annotations

import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
import pdfplumber

from lab_850.schema import ElementSpec, FieldInventory, SegmentSpec

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The 850 segments we care about, in EDI order.
_TARGET_SEGMENTS = [
    "ISA", "GS",
    "BEG",
    "REF",
    "DTM",
    "N1", "N2", "N3", "N4",
    "PO1", "PO3",
    "PID",
    "PER",
    "CTT",
]

_SYSTEM_PROMPT = """\
You are an EDI X12 005010 mapping specialist.
Your task is to analyse a retailer's Trading Partner Guide (TPG) for the 850 Purchase Order \
transaction set and return a precise JSON object describing the field-level requirements.

Return ONLY a valid JSON object — no markdown fences, no commentary — with this exact structure:

{
  "spec_version": "<string, e.g. '005010'>",
  "bundle": "<'general_merchandise' or 'transportation'>",
  "confidence": "<'HIGH' | 'MEDIUM' | 'LOW'>",
  "confidence_notes": ["<string>", ...],
  "segments": {
    "<SEGMENT_ID>": {
      "required": <true|false>,
      "condition": "<string — leave empty if unconditionally required>",
      "loop": "<string — loop name if inside a loop, else empty>",
      "notes": "<string>",
      "elements": {
        "<ELEMENT_ID>": {
          "element_id": "<string, e.g. 'BEG03'>",
          "required": <true|false>,
          "description": "<string>",
          "qualifier_values": ["<string>", ...],
          "constraints": ["<string>", ...],
          "notes": "<string>"
        }
      }
    }
  },
  "business_rules": ["<string>", ...]
}

Focus on these segments ONLY: ISA, GS, BEG, REF, DTM, N1, N2, N3, N4, PO1, PO3, PID, PER, CTT.
For each segment:
  - List every element the retailer specifically mentions or mandates.
  - Include qualifier_values (e.g. BEG01 values "00" and "05") wherever the TPG names them.
  - Include constraints (e.g. "zero-suppressed", "max 22 chars", "CCYYMMDD").
  - Set confidence LOW if you had to infer because the TPG was ambiguous or incomplete.
If a segment is not described in the TPG, omit it entirely (do not include with empty elements).
"""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_from_pdf(
    pdf_path: str | Path,
    retailer_slug: str,
    retailer_name: str = "",
    api_key: str | None = None,
    model: str = "claude-opus-4-6",
) -> FieldInventory:
    """Extract an 850 FieldInventory from a TPG PDF.

    Args:
        pdf_path:      Local path to the PDF file.
        retailer_slug: Slug identifier for the retailer (e.g. "lowes").
        retailer_name: Human-readable retailer name (defaults to slug title-cased).
        api_key:       OpenAI API key. Falls back to OPENAI_API_KEY env var.
        model:         OpenAI model to use (default: gpt-4o).

    Returns:
        FieldInventory populated from the PDF.
    """
    pdf_path = Path(pdf_path)
    if not retailer_name:
        retailer_name = retailer_slug.replace("-", " ").replace("_", " ").title()

    print(f"  [extractor] Reading PDF: {pdf_path.name}")
    pdf_text = _extract_text(pdf_path)
    if not pdf_text.strip():
        raise ValueError(f"PDF text extraction returned empty content: {pdf_path}")
    print(f"  [extractor] Extracted {len(pdf_text):,} chars from {pdf_path.name}")

    print(f"  [extractor] Calling {model} for schema-constrained extraction…")
    raw_json = _call_llm(pdf_text, model=model, api_key=api_key)

    inventory = _build_inventory(
        raw=raw_json,
        retailer_slug=retailer_slug,
        retailer_name=retailer_name,
        source_pdf=pdf_path.name,
    )
    print(
        f"  [extractor] Done. {len(inventory.segments)} segments extracted. "
        f"Confidence: {inventory.confidence}"
    )
    return inventory


def extract_from_text(
    pdf_text: str,
    retailer_slug: str,
    retailer_name: str = "",
    api_key: str | None = None,
    model: str = "claude-opus-4-6",
    source_pdf: str = "inline",
) -> FieldInventory:
    """Extract from pre-extracted PDF text (useful for testing without a real PDF)."""
    if not retailer_name:
        retailer_name = retailer_slug.replace("-", " ").replace("_", " ").title()
    raw_json = _call_llm(pdf_text, model=model, api_key=api_key)
    return _build_inventory(
        raw=raw_json,
        retailer_slug=retailer_slug,
        retailer_name=retailer_name,
        source_pdf=source_pdf,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_text(pdf_path: Path) -> str:
    parts: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def _call_llm(
    pdf_text: str,
    model: str,
    api_key: str | None,
) -> dict[str, Any]:
    """Send the PDF text to Claude with schema-constrained prompt. Returns parsed JSON."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set and no api_key argument provided.")

    client = anthropic.Anthropic(api_key=key)

    # Truncate to ~100k chars to stay within context limits
    user_content = (
        "Here is the Trading Partner Guide content for the 850 Purchase Order:\n\n"
        + pdf_text[:100_000]
        + "\n\nExtract and return the JSON structure as specified."
    )

    with client.messages.stream(
        model=model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        response = stream.get_final_message()

    raw = next(
        (b.text for b in response.content if b.type == "text"), ""
    ).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Claude returned non-JSON response (first 200 chars): {raw[:200]!r}"
        ) from exc


def _build_inventory(
    raw: dict[str, Any],
    retailer_slug: str,
    retailer_name: str,
    source_pdf: str,
) -> FieldInventory:
    """Map the GPT-4o JSON response to a typed FieldInventory."""
    segments: dict[str, SegmentSpec] = {}

    for seg_id, seg_data in raw.get("segments", {}).items():
        elements: dict[str, ElementSpec] = {}
        for elem_id, elem_data in seg_data.get("elements", {}).items():
            elements[elem_id] = ElementSpec(
                element_id=elem_data.get("element_id", elem_id),
                required=bool(elem_data.get("required", False)),
                description=elem_data.get("description", ""),
                qualifier_values=list(elem_data.get("qualifier_values", [])),
                constraints=list(elem_data.get("constraints", [])),
                notes=elem_data.get("notes", ""),
            )
        segments[seg_id] = SegmentSpec(
            segment_id=seg_id,
            required=bool(seg_data.get("required", False)),
            condition=seg_data.get("condition", ""),
            loop=seg_data.get("loop", ""),
            elements=elements,
            notes=seg_data.get("notes", ""),
        )

    return FieldInventory(
        retailer_slug=retailer_slug,
        retailer_name=retailer_name,
        source_pdf=source_pdf,
        spec_version=raw.get("spec_version", "unknown"),
        extracted_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        bundle=raw.get("bundle", "general_merchandise"),
        segments=segments,
        business_rules=list(raw.get("business_rules", [])),
        confidence=raw.get("confidence", "MEDIUM"),
        confidence_notes=list(raw.get("confidence_notes", [])),
    )
