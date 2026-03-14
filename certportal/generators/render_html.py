"""
HTML Renderer — Converts Markdown companion guide to branded HTML.

Uses Python's `markdown` library for MD -> HTML conversion, then wraps
in a styled HTML template with the Meredith portal theme (DM Sans font,
Indigo-600 primary, clean tables, print-friendly).

Architecture Decision: AD-9 from wizard refactoring prompt.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Meredith theme CSS (inline for self-contained HTML documents)
# ---------------------------------------------------------------------------

_MEREDITH_CSS = """\
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,400;0,500;0,700;1,400&display=swap');

:root {
    --indigo-50: #eef2ff;
    --indigo-100: #e0e7ff;
    --indigo-200: #c7d2fe;
    --indigo-600: #4f46e5;
    --indigo-700: #4338ca;
    --indigo-800: #3730a3;
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-300: #d1d5db;
    --gray-500: #6b7280;
    --gray-600: #4b5563;
    --gray-700: #374151;
    --gray-800: #1f2937;
    --gray-900: #111827;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 10pt;
    line-height: 1.6;
    color: var(--gray-800);
    max-width: 1100px;
    margin: 0 auto;
    padding: 40px 32px;
    background: #ffffff;
}

h1 {
    font-size: 22pt;
    font-weight: 700;
    color: var(--indigo-800);
    border-bottom: 3px solid var(--indigo-600);
    padding-bottom: 12px;
    margin-bottom: 16px;
    margin-top: 0;
}

h2 {
    font-size: 16pt;
    font-weight: 700;
    color: var(--indigo-700);
    border-bottom: 2px solid var(--indigo-200);
    padding-bottom: 8px;
    margin-top: 32px;
    margin-bottom: 16px;
}

h3 {
    font-size: 13pt;
    font-weight: 700;
    color: var(--gray-800);
    margin-top: 24px;
    margin-bottom: 10px;
}

h4 {
    font-size: 11pt;
    font-weight: 500;
    color: var(--gray-700);
    margin-top: 16px;
    margin-bottom: 8px;
}

p {
    margin-bottom: 10px;
}

strong {
    font-weight: 700;
}

em {
    font-style: italic;
}

code {
    background: var(--gray-100);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 9pt;
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

hr {
    border: none;
    border-top: 1px solid var(--gray-200);
    margin: 20px 0;
}

/* Tables */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0 20px 0;
    font-size: 9pt;
}

th {
    background: var(--indigo-600);
    color: #ffffff;
    font-weight: 700;
    text-align: left;
    padding: 8px 10px;
    border: 1px solid var(--indigo-700);
}

td {
    padding: 6px 10px;
    border: 1px solid var(--gray-200);
    text-align: left;
    vertical-align: top;
}

tr:nth-child(even) {
    background: var(--gray-50);
}

tr:hover {
    background: var(--indigo-50);
}

/* Lists */
ul, ol {
    margin: 8px 0 12px 24px;
}

li {
    margin: 4px 0;
}

/* Blockquotes (used for conditions) */
blockquote {
    border-left: 4px solid var(--indigo-600);
    background: var(--indigo-50);
    padding: 10px 16px;
    margin: 12px 0;
    font-style: italic;
    color: var(--gray-700);
}

/* Retailer annotations */
strong:has(+ strong) {
    color: var(--indigo-600);
}

/* Print styles */
@media print {
    body {
        padding: 20px;
        max-width: none;
        font-size: 9pt;
    }

    h1 { font-size: 18pt; }
    h2 { font-size: 14pt; page-break-before: auto; }
    h3 { font-size: 12pt; }

    table { font-size: 8pt; page-break-inside: avoid; }
    th { background: #4f46e5 !important; color: #ffffff !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    tr:nth-child(even) { background: #f9fafb !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }

    blockquote {
        border-left-color: #4f46e5;
        background: #eef2ff !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }

    a { text-decoration: none; color: var(--gray-800); }
}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_html(
    markdown_content: str,
    retailer_name: str | None = None,
) -> str:
    """
    Convert Markdown companion guide to branded HTML.

    Args:
        markdown_content: Markdown string (from render_markdown).
        retailer_name: Optional retailer name for the page title.

    Returns:
        Complete HTML document string with inline Meredith-themed styles.
    """
    try:
        import markdown as md_lib
    except ImportError:
        logger.error(
            "The 'markdown' library is not installed. "
            "Install it with: pip install markdown"
        )
        # Return a minimal HTML wrapper without markdown conversion
        escaped = (
            markdown_content
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>Companion Guide</title></head>"
            f"<body><pre>{escaped}</pre></body></html>"
        )

    # Convert Markdown to HTML body
    html_body = md_lib.markdown(
        markdown_content,
        extensions=["tables", "toc", "fenced_code"],
    )

    # Build page title
    title = "EDI Companion Guide"
    if retailer_name:
        title = f"{retailer_name} — {title}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_escape_html(title)}</title>
    <style>
{_MEREDITH_CSS}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""


def _escape_html(text: str) -> str:
    """Escape HTML special characters in text."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
