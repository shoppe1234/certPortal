# certportal/generators — Wizard artifact generation pipeline
#
# This package provides:
#   x12_source        - Dual pyx12/Stedi X12 definition loader
#   version_registry  - Dynamic X12 version and transaction set enumeration
#   template_loader   - Reads partner registry, presets, lifecycles for wizard pre-fill
#   lifecycle_builder - Build lifecycle YAML (use/copy/create modes with validation)
#   layer2_builder    - Merge preset defaults + user overrides into Layer 2 YAML
#
# Phase C will add: spec_builder, render_markdown, render_html, render_pdf, artifact_writer
