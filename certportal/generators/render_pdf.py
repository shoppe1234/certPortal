"""
PDF Renderer — Converts HTML companion guide to PDF.

Attempts weasyprint first (highest quality), falls back to fpdf2
if weasyprint is unavailable (weasyprint has system-level dependencies
that may not be present everywhere).

Both libraries are optional — the module gracefully degrades.

Architecture Decision: AD-9 from wizard refactoring prompt.
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Availability checks
# ---------------------------------------------------------------------------

def _weasyprint_available() -> bool:
    """Check if weasyprint is installed and importable."""
    try:
        import weasyprint  # noqa: F401
        return True
    except ImportError:
        return False
    except OSError:
        # weasyprint may fail if system libraries (cairo, pango) are missing
        logger.warning("weasyprint found but system libraries unavailable")
        return False


def _fpdf2_available() -> bool:
    """Check if fpdf2 is installed and importable."""
    try:
        from fpdf import FPDF  # noqa: F401
        return True
    except ImportError:
        return False


def is_pdf_available() -> bool:
    """
    Check if any PDF renderer is installed.

    Returns:
        True if at least one PDF renderer (weasyprint or fpdf2) is available.
    """
    return _weasyprint_available() or _fpdf2_available()


# ---------------------------------------------------------------------------
# weasyprint renderer
# ---------------------------------------------------------------------------

def _render_with_weasyprint(html_content: str) -> bytes | None:
    """Render HTML to PDF using weasyprint."""
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_content).write_pdf()
        return pdf_bytes
    except ImportError:
        return None
    except Exception as exc:
        logger.warning("weasyprint PDF generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# fpdf2 renderer (pure Python fallback)
# ---------------------------------------------------------------------------

def _strip_html_tags(html: str) -> str:
    """Remove HTML tags, returning plain text."""
    clean = re.sub(r"<[^>]+>", "", html)
    # Decode common HTML entities
    clean = clean.replace("&amp;", "&")
    clean = clean.replace("&lt;", "<")
    clean = clean.replace("&gt;", ">")
    clean = clean.replace("&quot;", '"')
    clean = clean.replace("&#39;", "'")
    clean = clean.replace("&nbsp;", " ")
    return clean


def _render_with_fpdf2(html_content: str) -> bytes | None:
    """
    Render HTML to PDF using fpdf2.

    This is a simplified renderer — it strips HTML and renders the text
    with basic formatting (headers, tables detected by pipe chars).
    For full-fidelity rendering, use weasyprint.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        return None

    try:
        # Extract plain text from HTML
        text = _strip_html_tags(html_content)
        # Normalize unicode for core PDF fonts
        replacements = {
            "\u2013": "-", "\u2014": "--", "\u2018": "'", "\u2019": "'",
            "\u201c": '"', "\u201d": '"', "\u2022": "*", "\u00a0": " ",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = text.encode("latin-1", errors="replace").decode("latin-1")

        class GuidePDF(FPDF):
            def header(self):
                self.set_font("Helvetica", "B", 8)
                self.set_text_color(100, 100, 100)
                self.cell(0, 6, "EDI Companion Guide", align="C")
                self.ln(2)
                self.set_draw_color(79, 70, 229)  # Indigo-600
                self.line(
                    self.l_margin, self.get_y(),
                    self.w - self.r_margin, self.get_y()
                )
                self.ln(4)

            def footer(self):
                self.set_y(-12)
                self.set_font("Helvetica", "I", 7)
                self.set_text_color(130, 130, 130)
                self.cell(0, 5, f"Page {self.page_no()}", align="C")

        pdf = GuidePDF(orientation="P", unit="mm", format="Letter")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_margins(20, 20, 20)
        pdf.add_page()

        lines = text.split("\n")
        i = 0
        in_table = False
        table_rows: list[list[str]] = []

        def flush_table():
            nonlocal table_rows, in_table
            if not table_rows:
                in_table = False
                return
            usable = pdf.w - pdf.l_margin - pdf.r_margin
            n_cols = max(len(r) for r in table_rows) if table_rows else 1
            col_w = usable / n_cols

            for row_idx, row in enumerate(table_rows):
                if row_idx == 0:
                    pdf.set_font("Helvetica", "B", 6.5)
                    pdf.set_fill_color(79, 70, 229)  # Indigo-600
                    pdf.set_text_color(255, 255, 255)
                    fill = True
                else:
                    pdf.set_font("Helvetica", "", 6.5)
                    pdf.set_text_color(0, 0, 0)
                    if row_idx % 2 == 0:
                        pdf.set_fill_color(249, 250, 251)  # Gray-50
                        fill = True
                    else:
                        fill = False

                for ci, cell in enumerate(row):
                    pdf.cell(col_w, 5, cell[:40], border=1, fill=fill)
                for _ in range(n_cols - len(row)):
                    pdf.cell(col_w, 5, "", border=1, fill=fill)
                pdf.ln()

            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)
            table_rows = []
            in_table = False

        def safe_mc(text_val, h=5, style="", size=8, color=(0, 0, 0)):
            try:
                pdf.set_x(pdf.l_margin)
                pdf.set_font("Helvetica", style, size)
                pdf.set_text_color(*color)
                w = pdf.w - pdf.l_margin - pdf.r_margin
                pdf.multi_cell(w, h, text_val[:500], align="L")
            except Exception:
                pass

        while i < len(lines):
            line = lines[i]

            # Table detection
            if "|" in line and line.strip().startswith("|"):
                parts = [c.strip() for c in line.strip().strip("|").split("|")]
                if all(
                    set(p.replace("-", "").replace(":", "")) == set()
                    for p in parts if p
                ):
                    i += 1
                    in_table = True
                    continue
                table_rows.append(parts)
                in_table = True
                i += 1
                continue
            else:
                if in_table or table_rows:
                    flush_table()

            stripped = line.strip()

            if stripped.startswith("# "):
                safe_mc(stripped[2:], h=8, style="B", size=14, color=(55, 48, 163))
                pdf.set_draw_color(79, 70, 229)
                pdf.line(
                    pdf.l_margin, pdf.get_y(),
                    pdf.w - pdf.r_margin, pdf.get_y()
                )
                pdf.ln(4)
            elif stripped.startswith("## "):
                safe_mc(stripped[3:], h=7, style="B", size=11, color=(67, 56, 202))
                pdf.set_draw_color(199, 210, 254)
                pdf.line(
                    pdf.l_margin, pdf.get_y(),
                    pdf.w - pdf.r_margin, pdf.get_y()
                )
                pdf.ln(3)
            elif stripped.startswith("### "):
                safe_mc(stripped[4:], h=6, style="B", size=10, color=(31, 41, 55))
                pdf.ln(2)
            elif stripped.startswith("#### "):
                safe_mc(stripped[5:], h=5.5, style="B", size=9, color=(55, 65, 81))
                pdf.ln(1)
            elif stripped.startswith("---"):
                pdf.set_draw_color(229, 231, 235)
                pdf.line(
                    pdf.l_margin, pdf.get_y(),
                    pdf.w - pdf.r_margin, pdf.get_y()
                )
                pdf.ln(3)
            elif stripped.startswith("- "):
                # Remove bold markers for display
                clean = stripped[2:].replace("**", "")
                safe_mc("  " + clean)
            elif stripped == "":
                pdf.ln(2)
            else:
                clean = stripped.replace("**", "").replace("*", "")
                safe_mc(clean)

            i += 1

        if table_rows:
            flush_table()

        # Write to bytes via temp file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        pdf.output(tmp_path)
        pdf_bytes = Path(tmp_path).read_bytes()
        Path(tmp_path).unlink(missing_ok=True)
        return pdf_bytes

    except Exception as exc:
        logger.warning("fpdf2 PDF generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_pdf(html_content: str) -> bytes | None:
    """
    Convert HTML companion guide to PDF.

    Tries weasyprint first (high fidelity), falls back to fpdf2 (pure Python).

    Args:
        html_content: Complete HTML document string (from render_html).

    Returns:
        PDF file content as bytes, or None if no PDF renderer is available.
    """
    # Try weasyprint first
    if _weasyprint_available():
        result = _render_with_weasyprint(html_content)
        if result:
            logger.info("PDF generated via weasyprint (%d bytes)", len(result))
            return result

    # Fall back to fpdf2
    if _fpdf2_available():
        result = _render_with_fpdf2(html_content)
        if result:
            logger.info("PDF generated via fpdf2 (%d bytes)", len(result))
            return result

    logger.warning("No PDF renderer available. Install weasyprint or fpdf2.")
    return None
