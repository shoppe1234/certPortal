-- testing/fixtures/sql/seed_patch_suggestions.sql
-- Seeds two patch suggestions for CHR-04 (apply / reject tests).
-- Patch content (.yaml) is stored in S3; these rows reference the S3 key.
-- Safe to re-run — existing rows are not overwritten.

INSERT INTO patch_suggestions (
    supplier_slug, retailer_slug, error_code, segment, element,
    summary, patch_s3_key, applied
)
VALUES
    (
        'acme', 'lowes', 'E001', 'BEG', 'BEG03',
        'Truncate PO number to 22 characters maximum',
        'lowes/acme/patches/patch_beg03_001.yaml',
        FALSE
    ),
    (
        'acme', 'lowes', 'E002', 'ISA', 'ISA13',
        'Replace ISA13 with sequential 9-digit numeric control number',
        'lowes/acme/patches/patch_isa13_001.yaml',
        FALSE
    );
