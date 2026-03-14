# certportal/generators — Wizard artifact generation pipeline
#
# This package provides:
#   x12_source        - Dual pyx12/Stedi X12 definition loader
#   version_registry  - Dynamic X12 version and transaction set enumeration
#   template_loader   - Reads partner registry, presets, lifecycles for wizard pre-fill
#   lifecycle_builder - Build lifecycle YAML (use/copy/create modes with validation)
#   layer2_builder    - Merge preset defaults + user overrides into Layer 2 YAML
#   spec_builder      - Merge Layer 1 + Layer 2 into unified spec; generate artifacts
#   render_markdown   - Per-transaction companion guide in Markdown
#   render_html       - Branded HTML with Meredith theme (DM Sans, Indigo-600)
#   render_pdf        - PDF via weasyprint (preferred) or fpdf2 (fallback)
#   artifact_writer   - Write artifacts to S3 + update retailer_specs DB
