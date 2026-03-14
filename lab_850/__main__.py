"""__main__.py — CLI for lab_850.

Usage examples:

  # Extract a single retailer PDF
  python -m lab_850 --pdf lab_850/pdfs/lowes.pdf --retailer lowes

  # Extract all PDFs in a directory (retailer slug = stem of filename)
  python -m lab_850 --pdfs lab_850/pdfs/

  # Extract + cross-retailer comparison report
  python -m lab_850 --pdfs lab_850/pdfs/ --compare

  # Extract + generate Andy Path 3 seed JSON
  python -m lab_850 --pdf lab_850/pdfs/lowes.pdf --retailer lowes --seed

  # Extract + compare + generate merged seed (elements common to all retailers)
  python -m lab_850 --pdfs lab_850/pdfs/ --compare --seed

  # Save output to a specific directory (default: lab_850/reports/)
  python -m lab_850 --pdfs lab_850/pdfs/ --compare --out ./my_reports/

  # Dry-run: print what PDFs would be processed, no API calls
  python -m lab_850 --pdfs lab_850/pdfs/ --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    """Convert a PDF filename stem to a clean retailer slug.

    Lowercases, strips version-like suffixes (v4010, 005010, etc.),
    collapses any run of non-alphanumeric characters to a single underscore,
    and strips leading/trailing underscores.

    Examples:
      "Lowe's Merch Stock 850 Purchase Order v4010" -> "lowes_merch_stock"
      "United Hardware DIB 850 4010 (1)"            -> "united_hardware_dib"
      "United Hardware DIB 850 4010"                -> "united_hardware_dib"
    """
    s = name.lower()
    s = s.replace("'", "").replace("`", "")     # drop apostrophes before general pass
    # Strip common EDI suffixes: transaction set numbers, version numbers
    s = re.sub(r"\b(850|855|856|810|997|860|865)\b", "", s)
    s = re.sub(r"\bv?\d{4,6}\b", "", s)        # v4010, 005010, 4010
    s = re.sub(r"\(?\d+\)?$", "", s)            # trailing (1), 1, etc.
    s = re.sub(r"purchase\s*order", "", s)       # redundant for 850s
    s = re.sub(r"[^a-z0-9]+", "_", s)           # non-alphanumeric -> _
    s = s.strip("_")
    return s or "retailer"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m lab_850",
        description="850 TPG PDF analyser — extract field inventories, compare retailers, "
                    "generate Andy Path 3 seed payloads.",
    )

    # Input
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--pdf",
        metavar="PATH",
        help="Single PDF file to extract.",
    )
    input_group.add_argument(
        "--pdfs",
        metavar="DIR",
        help="Directory of PDF files (one per retailer). "
             "Retailer slug is derived from the filename stem.",
    )

    # Retailer slug — only used with --pdf
    parser.add_argument(
        "--retailer",
        metavar="SLUG",
        help="Retailer slug for --pdf mode (e.g. 'lowes'). "
             "In --pdfs mode the filename stem is used automatically.",
    )
    parser.add_argument(
        "--retailer-name",
        metavar="NAME",
        help="Human-readable retailer name (optional, defaults to slug title-cased).",
        default="",
    )

    # Actions
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Generate a cross-retailer Markdown comparison report.",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Generate Andy Path 3 wizard_payload JSON seed(s).",
    )

    # Output
    parser.add_argument(
        "--out",
        metavar="DIR",
        default="lab_850/reports",
        help="Output directory for reports and seeds (default: lab_850/reports/).",
    )

    # Model
    parser.add_argument(
        "--model",
        default="claude-opus-4-6",
        help="Claude model to use for extraction (default: claude-opus-4-6).",
    )

    # Flags
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be processed without making any API calls.",
    )
    parser.add_argument(
        "--load",
        metavar="DIR",
        help="Skip extraction — load previously saved FieldInventory JSON files "
             "from DIR instead.  Useful for --compare and --seed without re-running GPT.",
    )

    args = parser.parse_args(argv)

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------
    if args.pdf and not args.retailer:
        parser.error("--retailer is required when using --pdf")

    out_dir = Path(args.out)

    # Collect (pdf_path, retailer_slug, retailer_name) tuples
    if args.pdf:
        targets = [(Path(args.pdf), args.retailer, args.retailer_name)]
    else:
        pdfs_dir = Path(args.pdfs)
        if not pdfs_dir.is_dir():
            print(f"ERROR: --pdfs directory not found: {pdfs_dir}", file=sys.stderr)
            sys.exit(1)
        pdf_files = sorted(pdfs_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"ERROR: No PDF files found in {pdfs_dir}", file=sys.stderr)
            sys.exit(1)
        targets = [
            (p, _slugify(p.stem), "")
            for p in pdf_files
        ]
        # Warn on duplicate slugs (two PDFs mapping to the same slug would overwrite)
        seen_slugs: dict[str, str] = {}
        for pdf_path, slug, _ in targets:
            if slug in seen_slugs:
                print(
                    f"WARNING: '{pdf_path.name}' and '{seen_slugs[slug]}' both map to "
                    f"slug '{slug}'. The second will overwrite the first.\n"
                    f"  Rename one PDF or use --pdf --retailer to process them separately.",
                    file=sys.stderr,
                )
            seen_slugs[slug] = pdf_path.name

    # ------------------------------------------------------------------
    # Dry-run
    # ------------------------------------------------------------------
    if args.dry_run:
        print(f"\n[dry-run] Would process {len(targets)} PDF(s):\n")
        for pdf_path, slug, name in targets:
            print(f"  {pdf_path.name:40s}  ->  retailer_slug={slug!r}")
        print(f"\n[dry-run] Output directory: {out_dir.resolve()}")
        if args.compare:
            print("[dry-run] Would generate: comparison.md")
        if args.seed:
            for _, slug, _ in targets:
                print(f"[dry-run] Would generate: seed_{slug}.json")
            if len(targets) > 1:
                print("[dry-run] Would generate: seed_merged.json")
        return

    # ------------------------------------------------------------------
    # Lazy imports (keep startup fast for --dry-run)
    # ------------------------------------------------------------------
    from lab_850.extractor import extract_from_pdf
    from lab_850.schema import FieldInventory

    # ------------------------------------------------------------------
    # Extract or load inventories
    # ------------------------------------------------------------------
    inventories: list[FieldInventory] = []

    if args.load:
        load_dir = Path(args.load)
        print(f"\nLoading inventories from {load_dir}…\n")
        json_files = sorted(load_dir.glob("inventory_*.json"))
        if not json_files:
            print(f"ERROR: No inventory_*.json files found in {load_dir}", file=sys.stderr)
            sys.exit(1)
        for jf in json_files:
            inv = FieldInventory.from_json(jf.read_text(encoding="utf-8"))
            inventories.append(inv)
            print(f"  Loaded: {jf.name}  ({inv.retailer_slug})")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nExtracting {len(targets)} PDF(s)…\n")
        for pdf_path, slug, name in targets:
            print(f"[{slug}] {pdf_path.name}")
            try:
                inv = extract_from_pdf(
                    pdf_path=pdf_path,
                    retailer_slug=slug,
                    retailer_name=name,
                    model=args.model,
                )
            except Exception as exc:
                print(f"  ERROR: {exc}", file=sys.stderr)
                continue

            inventories.append(inv)

            # Always save the raw FieldInventory JSON
            inv_path = out_dir / f"inventory_{slug}.json"
            inv_path.write_text(inv.to_json(), encoding="utf-8")
            print(f"  Saved: {inv_path.relative_to(Path.cwd()) if inv_path.is_relative_to(Path.cwd()) else inv_path}\n")

    if not inventories:
        print("No inventories produced. Exiting.", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Comparison report
    # ------------------------------------------------------------------
    if args.compare:
        from lab_850.comparator import compare

        print("Generating comparison report…")
        report = compare(inventories)
        md_path = out_dir / "comparison.md"
        md_path.write_text(report.to_markdown(), encoding="utf-8")
        print(f"  Saved: {md_path}\n")

    # ------------------------------------------------------------------
    # Seed generation
    # ------------------------------------------------------------------
    if args.seed:
        from lab_850.seed_generator import generate_seed_json, generate_merged_seed

        print("Generating seed JSON(s)…")
        for inv in inventories:
            seed_path = out_dir / f"seed_{inv.retailer_slug}.json"
            seed_path.write_text(generate_seed_json(inv), encoding="utf-8")
            print(f"  Saved: {seed_path}")

        if len(inventories) > 1:
            merged = generate_merged_seed(inventories, require_all=True)
            merged_path = out_dir / "seed_merged.json"
            merged_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
            print(f"  Saved: {merged_path} (intersection of all retailers)")

        print()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"Done. {len(inventories)} inventory(ies) in {out_dir}/")


if __name__ == "__main__":
    main()
