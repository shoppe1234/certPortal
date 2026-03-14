# Meredith Retailer Wizard Refactoring — Implementation Prompt

> **Status:** APPROVED — all questions answered, ready for implementation
> **Date:** 2026-03-14
> **Scope:** Replace PDF upload with two-wizard architecture (Lifecycle + Layer 2 YAML)
> **Affects:** portals/meredith.py, templates/, static/, certportal/generators/ (new), edi_framework/, migrations/, playwrightcli/

---

## EXECUTIVE SUMMARY

Replace Meredith's PDF-upload-to-Dwight spec creation flow with a **two-wizard architecture**:

1. **Lifecycle Wizard** — Define which transactions compose a lifecycle and how they transition
2. **Layer 2 YAML Wizard** — Configure each transaction's qualifiers, business rules, and mappings

Both wizards are **independent** (accessible separately), but a lifecycle with at least one transaction is required "to go to market." Artifacts (MD/HTML/PDF) are generated **after Layer 2 configuration** because Layer 2 overrides (e.g., N104 qualifier values) must be embedded in the spec documents distributed to suppliers.

---

## ARCHITECTURAL DECISIONS (Approved)

| # | Decision | Rationale |
|---|----------|-----------|
| AD-1 | **TWO WIZARDS** (lifecycle + layer2), independent but connected | Lifecycle = which transactions; Layer 2 = how each transaction behaves |
| AD-2 | **NO HARDCODING** — all transaction structures sourced dynamically from pyx12 XML maps + Stedi JSON schemas | Competitive advantage: support any X12 version without code changes |
| AD-3 | X12 versions at launch: **4010, 4030, 5010** | Sourced from Python X12 libraries at runtime |
| AD-4 | **Synchronous in-portal Python** for spec generation (no agent signal) | Fast, no latency; generators are deterministic |
| AD-5 | **Multi-session wizard** with DB persistence (JSONB) | Multiple concurrent sessions per retailer allowed; strict/deterministic at finalization |
| AD-6 | **Bundle-level presets, expandable to element-level** | Progressive disclosure UX; Standard Retail preset derived from Lowe's YAMLs |
| AD-7 | **partner_registry.yaml** as new Layer 0 white-label foundation | Future partners add a registry entry, not code changes |
| AD-8 | **Artifacts include Layer 2 logic** — generated AFTER Layer 2 config, not after lifecycle alone | Suppliers receive specs with retailer-specific qualifiers/rules baked in |
| AD-9 | **Direct portal download** for artifacts (FastAPI serves files) | No S3 pre-signed URL complexity for end users |
| AD-10 | **pyx12 + Stedi dual support** via `x12_source.py` abstraction layer | Flexibility; best-of-both data sources |
| AD-11 | Dwight, Andy Path 1, lab_850, THESIS.md → **deferred to TODO.md** | Can be re-incorporated later |
| AD-12 | Lifecycle required to "go to market" — must contain 1 or more transactions | But Layer 2 wizard accessible independently for tweaking |

---

## CRITICAL CONSTRAINT: ARTIFACTS INCLUDE LAYER 2

This is a key architectural point. The artifact generation pipeline is:

```
Layer 1 (base X12 structure from pyx12/Stedi)
    +
Layer 2 (retailer-specific overrides from wizard)
    =
Final Spec Artifact (MD/HTML/PDF distributed to suppliers)
```

Example: If a retailer configures N104 to require qualifier "93" for inbound 850s in their Layer 2 YAML, the generated 850 spec PDF must show:

```
N1 — Name Loop
  N101: Entity Identifier Code (mandatory) — ST, BT, VN, SF
  N103: Identification Code Qualifier (mandatory) — 93 [REQUIRED BY RETAILER]
  N104: Identification Code (mandatory) — Store/location number
```

This means `spec_builder.py` must merge Layer 1 + Layer 2 before rendering artifacts.

---

## INVARIANTS — NEVER VIOLATE

All existing invariants (INV-01 through INV-07) remain in force. Additionally:

- **NO HARDCODING** of transaction types, segment lists, element definitions, or qualifier values in Python code
- `edi_framework/` remains **READ-ONLY at runtime** (NC-01)
- YAML is the brain (NC-02) — wizard state is JSONB in DB, final output is YAML
- `lifecycle_engine/` and `order_to_cash.yaml` are **UNTOUCHED** — lifecycle logic does not change
- `playwrightcli/` isolation (ADR-027) — no imports from main codebase
- Portal never imports agents (INV-07)

---

## TASK LIST 1: Meredith Wizard Refactoring

### Phase A: Foundation — X12 Source & Partner Registry

| # | Task | Files | Description |
|---|------|-------|-------------|
| A1 | Create partner registry | `edi_framework/partner_registry.yaml` | White-label registry listing available partners, X12 versions, transaction sets. Lowe's is the first entry. Future partners add entries here, not code. |
| A2 | Create X12 source abstraction | `certportal/generators/x12_source.py` | Dual-source loader: reads from pyx12 XML map files AND Stedi JSON schemas. Returns normalized segment/element definitions for any X12 version (4010/4030/5010). **NO HARDCODING.** |
| A3 | Create version registry | `certportal/generators/version_registry.py` | Enumerates available X12 versions and their transaction sets dynamically from x12_source. No static lists. |
| A4 | Install pyx12 dependency | `requirements.txt` | `pyx12` for XML map files covering all X12 versions |
| A5 | Create package init | `certportal/generators/__init__.py` | Package initialization |
| A6 | Migration: wizard_sessions | `migrations/007_wizard_sessions.sql` | Table: `id UUID PK, retailer_slug, wizard_type TEXT ('lifecycle'\|'layer2'), session_name TEXT, step_number INT, state_json JSONB, x12_version TEXT, created_at, updated_at, completed_at NULLABLE`. Multiple active sessions per retailer allowed. |
| A7 | Migration: retailer_specs v2 | `migrations/008_retailer_specs_v2.sql` | Add columns: `x12_version TEXT, transaction_types TEXT[], artifacts_s3_prefix TEXT, lifecycle_ref TEXT, layer2_configured BOOLEAN DEFAULT FALSE` |

### Phase B: Template & Preset System

| # | Task | Files | Description |
|---|------|-------|-------------|
| B1 | Create Layer 2 presets | `edi_framework/templates/layer2_presets.yaml` | Derive "Standard Retail" preset from existing Lowe's transaction YAMLs. Bundle-level: pre-fills qualifiers, business rules, mapping defaults. Additional presets: "Minimal" (required segments only), "Blank" (manual config). |
| B2 | Create template loader | `certportal/generators/template_loader.py` | Reads partner_registry.yaml + layer2_presets.yaml + edi_framework/lifecycle/*.yaml + transactions/*.yaml. Returns wizard pre-fill data for frontend. |
| B3 | Create lifecycle builder | `certportal/generators/lifecycle_builder.py` | Three modes: (1) use existing lifecycle as-is, (2) clone + customize (deep copy, rename, modify states/transitions), (3) create from scratch. Validates output against `meta/lifecycle_schema.yaml`. |
| B4 | Create Layer 2 builder | `certportal/generators/layer2_builder.py` | Takes transaction type + X12 version + bundle preset + user overrides → Layer 2 YAML. Merges preset defaults with user-specified qualifier values, business rules. Validates against `meta/transaction_schema.yaml`. |

### Phase C: Spec Generator (Artifacts)

| # | Task | Files | Description |
|---|------|-------|-------------|
| C1 | Create spec builder | `certportal/generators/spec_builder.py` | **Merges Layer 1 (from x12_source) + Layer 2 (from wizard config)** → unified spec. Then renders to MD/HTML/PDF. Retailer-specific qualifiers/rules appear inline in the spec document. |
| C2 | Create Markdown renderer | `certportal/generators/render_markdown.py` | Per-transaction companion guide: segment tables, element details with Layer 2 annotations, code lists, business rules. Reference: `sampleArtifacts/stedi/generator/render_markdown.py` |
| C3 | Create HTML renderer | `certportal/generators/render_html.py` | MD → branded HTML. Styled with Meredith theme (DM Sans, Indigo-600 primary, clean tables). Printable. |
| C4 | Create PDF renderer | `certportal/generators/render_pdf.py` | HTML → PDF via weasyprint (preferred) or fpdf2 fallback. |
| C5 | Create artifact writer | `certportal/generators/artifact_writer.py` | Writes to S3: `{retailer_slug}/specs/{x12_ver}/{tx_code}.{md\|html\|pdf}`. Updates retailer_specs DB row. |

### Phase D: Lifecycle Wizard Routes & Templates (Wizard 1)

| # | Task | Files | Description |
|---|------|-------|-------------|
| D1 | New route `GET /lifecycle-wizard` | `portals/meredith.py` | Lifecycle wizard landing. Lists active sessions (resume) or start new. |
| D2 | New route `POST /lifecycle-wizard/new` | `portals/meredith.py` | Create new wizard session in DB. Return session_id. |
| D3 | New route `GET /lifecycle-wizard/{session_id}` | `portals/meredith.py` | Load/resume wizard from DB state. Render at correct step. |
| D4 | New route `POST /lifecycle-wizard/{session_id}/save-step` | `portals/meredith.py` | Save current step to wizard_sessions.state_json. Return next step HTML (HTMX swap). |
| D5 | New route `POST /lifecycle-wizard/{session_id}/generate` | `portals/meredith.py` | Finalize: validate lifecycle YAML (strict/deterministic), write to S3, mark session completed_at. |
| D6 | New template `meredith_lifecycle_wizard.html` | `templates/` | Steps: Mode Select → X12 Version → Transactions → States & Transitions (for copy/create modes) → Review → Generate. Step indicator with progress bar. |
| D7 | New partial `_wizard_step_indicator.html` | `templates/` | Reusable step progress component (active/complete/pending circles + connector line). |
| D8 | New partial `_lifecycle_state_editor.html` | `templates/` | State/transition editor: add/edit/remove states, define triggers (document + direction), configure transitions. |

### Phase E: Layer 2 YAML Wizard Routes & Templates (Wizard 2)

| # | Task | Files | Description |
|---|------|-------|-------------|
| E1 | Refactor `GET /yaml-wizard` | `portals/meredith.py`, `meredith_yaml_wizard.html` | Replace 3-path tabs: (a) Layer 2 Wizard entry (primary), (b) Upload existing YAML (keeps Path 2). Remove Path 1 tab (PDF). |
| E2 | New route `POST /yaml-wizard/layer2/new` | `portals/meredith.py` | Create new Layer 2 wizard session. Accept transaction_type and x12_version. |
| E3 | New route `GET /yaml-wizard/layer2/{session_id}` | `portals/meredith.py` | Load/resume Layer 2 wizard. |
| E4 | New route `POST /yaml-wizard/layer2/{session_id}/save-step` | `portals/meredith.py` | Save step (preset selection, segment config, rules, mappings). |
| E5 | New route `POST /yaml-wizard/layer2/{session_id}/generate` | `portals/meredith.py` | Finalize: build Layer 2 YAML, validate, write to S3. Mark session complete. |
| E6 | New route `POST /yaml-wizard/layer2/{session_id}/generate-artifacts` | `portals/meredith.py` | After Layer 2 is finalized: merge Layer 1 + Layer 2 → generate MD/HTML/PDF artifacts. Write to S3. |
| E7 | New route `GET /artifacts/{retailer_slug}/{tx_code}.{ext}` | `portals/meredith.py` | Direct download endpoint. Serves artifact file from S3 via FastAPI StreamingResponse. |
| E8 | New template `meredith_layer2_wizard.html` | `templates/` | Steps: Preset → Segments (expandable) → Business Rules → Mappings → Review → Generate YAML → Generate Artifacts. Transaction tab bar for multi-tx config. |
| E9 | New partial `_segment_config.html` | `templates/` | Per-segment: element table with qualifier dropdowns (populated from x12_source), requirement toggles, constraint fields. Expand/collapse. Bundle preset pre-fills values. |
| E10 | New partial `_business_rules.html` | `templates/` | Toggle/configure: quantity chain, N1 qualifier transforms, FOB restrictions, etc. Derived from layer2_presets. |
| E11 | New partial `_artifact_card.html` | `templates/` | Card per transaction showing generated artifact with MD/HTML/PDF download buttons. |

### Phase F: Portal Updates

| # | Task | Files | Description |
|---|------|-------|-------------|
| F1 | Refactor `GET /spec-setup` | `portals/meredith.py`, `meredith_spec_setup.html` | Remove PDF upload accordion. New flow: entry points to Lifecycle Wizard and Layer 2 Wizard. Show artifact gallery if generated. |
| F2 | Deprecate `POST /spec-setup/upload` | `portals/meredith.py` | Return 410 Gone. Remove Dwight trigger signal. |
| F3 | Deprecate `POST /yaml-wizard/path1` | `portals/meredith.py` | Return 410 Gone. Andy Path 1 deferred. |
| F4 | Update `GET /` dashboard | `portals/meredith.py`, `meredith_home.html` | Update action cards: "EDI Configuration" hub with sub-links to Lifecycle Wizard, YAML Wizard, Artifact Gallery. |
| F5 | New route `GET /artifacts` | `portals/meredith.py` | Artifact gallery: lists all generated specs grouped by transaction, with download links. Shows Layer 2 status per transaction. |

### Phase G: CSS & JavaScript

| # | Task | Files | Description |
|---|------|-------|-------------|
| G1 | Wizard step indicator CSS | `static/css/meredith.css` | Progress circles (active/complete/pending), connector lines, step labels. Transitions on step change. |
| G2 | Wizard JS controller | `static/js/meredith_wizard.js` | Step navigation (next/back), HTMX integration for save-step, form validation, session name input. |
| G3 | Segment config JS | `static/js/segment_config.js` | Expand/collapse segments, dynamic qualifier dropdown population from X12 source API, live preview pane (optional). |
| G4 | Lifecycle editor JS | `static/js/lifecycle_editor.js` | State add/edit/remove, transition configuration, auto-generated transition diagram (ASCII or simple SVG). |

### Phase H: Deprecation & Documentation

| # | Task | Files | Description |
|---|------|-------|-------------|
| H1 | Add deferred items to TODO.md | `TODO.md` | Dwight re-incorporation, Andy Path 1, lab_850 seed integration, THESIS.md format, Admin template upload portal |
| H2 | Write ADR-032 | `DECISIONS.md` | "Two-wizard architecture replaces PDF upload for spec creation" |
| H3 | Write ADR-033 | `DECISIONS.md` | "Dynamic X12 sourcing from pyx12 + Stedi; no hardcoded transaction structures" |
| H4 | Write ADR-034 | `DECISIONS.md` | "partner_registry.yaml as Layer 0 white-label foundation" |
| H5 | Write ADR-035 | `DECISIONS.md` | "Artifacts generated after Layer 2 config; Layer 2 logic embedded in spec documents" |
| H6 | Write ADR-036 | `DECISIONS.md` | "Multi-session wizard persistence with JSONB state; strict validation at finalization only" |
| H7 | Update CLAUDE.md | `CLAUDE.md` | Document: generators module, two-wizard architecture, partner_registry, wizard_sessions, artifact pipeline |

---

## TASK LIST 2: playwrightcli Refactoring

| # | Task | Files | Description |
|---|------|-------|-------------|
| P1 | Mark `SIG-YAML1-*` checks as SKIP | `requirements_verifier.py` | Path 1 deprecated; 3 checks become SKIP with deprecation note |
| P2 | New flow: `lifecycle_wizard_flow.py` | `playwrightcli/flows/` | E2E: login → /lifecycle-wizard → new session → mode=use → version=4010 → select bundle → generate → verify lifecycle YAML in S3. Standalone (ADR-027). |
| P3 | New checks: `LC-WIZ-01..08` | `requirements_verifier.py` | 01: version dropdown renders dynamically. 02: transaction checkboxes populate from API. 03: mode selector (use/copy/create) works. 04: states editor renders (copy/create modes). 05: generate returns 200. 06: lifecycle YAML in S3. 07: wizard_sessions row created. 08: resume loads correct step. |
| P4 | New flow: `layer2_wizard_flow.py` | `playwrightcli/flows/` | E2E: /yaml-wizard → Layer 2 → new session → preset=Standard Retail → expand BEG segment → override BEG02 → generate YAML → generate artifacts → verify S3 + download. |
| P5 | New checks: `L2-WIZ-01..09` | `requirements_verifier.py` | 01: preset loads defaults. 02: segment expand shows elements. 03: overrides applied to YAML. 04: YAML validates against meta-schema. 05: artifacts generated (MD exists). 06: artifacts include Layer 2 annotations. 07: download endpoint returns file. 08: wizard_sessions row. 09: resume works. |
| P6 | New flow: `wizard_session_flow.py` | `playwrightcli/flows/` | E2E: start wizard → complete 2 steps → navigate away → return → resume → verify state restored → start second session → verify both exist. |
| P7 | New checks: `WIZ-SESS-01..04` | `requirements_verifier.py` | 01: session created in DB. 02: state JSON matches form data. 03: resume loads correct step. 04: multiple sessions listed. |
| P8 | Update `meredith_flow.py` | `playwrightcli/flows/meredith_flow.py` | Remove spec-setup PDF step. Remove Path 1 signal step. Add Layer 2 wizard entry verification. |
| P9 | Deprecation checks: `DEPR-01..02` | `requirements_verifier.py` | 01: POST /spec-setup/upload returns 410. 02: POST /yaml-wizard/path1 returns 410. |
| P10 | Update `seed.sql` | `playwrightcli/fixtures/seed.sql` | Add: wizard_sessions test data (1 complete, 1 in-progress), partner_registry validation data. |
| P11 | New fixture: `artifact_checker.py` | `playwrightcli/fixtures/` | Standalone S3 checker for MD/HTML/PDF artifacts. boto3 only (ADR-027). |
| P12 | Update dry-run output | `playwrightcli/cli.py` | Include lifecycle-wizard, layer2-wizard, wizard-session steps. |

---

## TASK LIST 3: Post-Development Testing

### Unit Tests (T1–T14)

| # | Test | Scope |
|---|------|-------|
| T1 | `x12_source.py` returns segments/elements for 4010/4030/5010 from pyx12 | pyx12 integration |
| T2 | `x12_source.py` returns segments/elements for 4010 from Stedi JSON | Stedi integration |
| T3 | `version_registry.py` enumerates 3 versions with transaction sets | Version enumeration |
| T4 | `template_loader.py` reads partner_registry + presets → returns correct pre-fill | Template loading |
| T5 | `lifecycle_builder.py` mode=use returns existing lifecycle unchanged | Use mode |
| T6 | `lifecycle_builder.py` mode=copy produces deep clone with new name | Copy mode |
| T7 | `lifecycle_builder.py` mode=create with custom states validates against meta-schema | Create mode |
| T8 | `layer2_builder.py` Standard Retail preset → valid Layer 2 YAML | Preset generation |
| T9 | `layer2_builder.py` preset + user overrides merges correctly (override wins) | Override merge |
| T10 | `spec_builder.py` merges Layer 1 + Layer 2 → MD contains Layer 2 annotations | Merge + render |
| T11 | `render_html.py` produces valid HTML5 from merged spec | HTML artifact |
| T12 | `render_pdf.py` produces non-zero-byte PDF | PDF artifact |
| T13 | `wizard_sessions` CRUD — create, update step, resume, complete, list multiples | DB persistence |
| T14 | Input validation rejects malformed wizard state at finalization | Strict finalization |

### Integration Tests (T15–T24)

| # | Test | Scope |
|---|------|-------|
| T15 | `POST /lifecycle-wizard/{id}/generate` → lifecycle YAML in S3 | Route → S3 |
| T16 | `POST /yaml-wizard/layer2/{id}/generate` → YAML validates against meta-schema | Route → validator |
| T17 | `POST /yaml-wizard/layer2/{id}/generate-artifacts` → MD/HTML/PDF in S3 | Route → artifacts |
| T18 | Generated YAML passes `schema_validators/validate_all.py` | Full validation |
| T19 | `GET /artifacts/{slug}/{tx}.pdf` returns valid PDF binary | Download route |
| T20 | Artifact PDF contains Layer 2 qualifier annotations | Content verification |
| T21 | `retailer_specs` DB row has correct x12_version, artifacts_s3_prefix | DB persistence |
| T22 | Andy Path 2 (upload) still works unchanged | Backward compat |
| T23 | Andy Path 3 still works with wizard-generated payload | Backward compat |
| T24 | Two wizard sessions for same retailer — both persist independently | Multi-session |

### E2E via playwrightcli (T25–T38)

| # | Test | Scope |
|---|------|-------|
| T25 | Lifecycle wizard: mode=use → 4010 → Order-to-Cash bundle → generate | Happy path |
| T26 | Lifecycle wizard: mode=copy → rename → remove state → generate | Copy/customize |
| T27 | Lifecycle wizard: mode=create → add 2 states → add transition → generate | Create new |
| T28 | Layer 2 wizard: Standard Retail preset → generate YAML → generate artifacts | Happy path |
| T29 | Layer 2 wizard: expand BEG → override BEG02 qualifiers → verify in YAML | Element override |
| T30 | Layer 2 wizard: upload existing YAML (Path 2 preserved) | Upload path |
| T31 | Artifact download: click PDF link → file downloads → non-zero-byte | Download |
| T32 | Artifact content: generated PDF mentions retailer-configured N104 qualifier | Layer 2 in artifact |
| T33 | Multi-session: start lifecycle → leave → start layer2 → resume lifecycle | Session independence |
| T34 | X12 5010: select 5010 → different segments rendered than 4010 | Version switching |
| T35 | Scope isolation: retailer A cannot see retailer B's sessions or artifacts | INV-06 |
| T36 | Deprecated routes: POST /spec-setup/upload returns 410 | Deprecation |
| T37 | Deprecated routes: POST /yaml-wizard/path1 returns 410 | Deprecation |
| T38 | **All existing passing checks still pass** (full regression) | Regression |

### Manual / Exploratory (T39–T44)

| # | Test | Scope |
|---|------|-------|
| T39 | Generated PDF readability and formatting quality | Visual QA |
| T40 | Layer 2 annotations appear in correct position within spec doc | Content QA |
| T41 | Wizard usability on mobile/tablet viewport | Responsive |
| T42 | All 6 transactions configured via Layer 2 → all 6 artifacts generated | Scale |
| T43 | White-label: add new partner to registry → wizard shows new partner | Extensibility |
| T44 | Wizard 1 → Wizard 2 handoff: smooth transition, correct pre-selection | UX flow |

---

## DIAGRAMS

### Full Architecture — Python Module Dependency

```
                    ┌──────────────────────────────────┐
                    │      MEREDITH PORTAL (8001)       │
                    │      portals/meredith.py          │
                    └──────────┬───────────────────────┘
                               │
              ┌────────────────┼─────────────────────┐
              │                │                      │
              ▼                ▼                      ▼
    /lifecycle-wizard   /yaml-wizard/layer2    /artifacts/{slug}
              │                │                      │
              │                │                      │
              ▼                ▼                      ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              certportal/generators/                          │
    │                                                             │
    │  ┌──────────────────┐       ┌──────────────────────┐       │
    │  │ version_registry │──────▶│    x12_source.py      │       │
    │  │ (4010,4030,5010) │       │                       │       │
    │  └──────────────────┘       │  ┌─────────────────┐  │       │
    │                             │  │ pyx12 XML maps   │  │       │
    │                             │  ├─────────────────┤  │       │
    │                             │  │ Stedi JSON       │  │       │
    │                             │  └─────────────────┘  │       │
    │                             └───────────┬──────────┘       │
    │                                          │                  │
    │         ┌────────────────────────────────┤                  │
    │         │                                │                  │
    │         ▼                                ▼                  │
    │  ┌─────────────────┐          ┌─────────────────────┐      │
    │  │lifecycle_builder │          │  layer2_builder.py   │      │
    │  │                  │          │                      │      │
    │  │ Modes:           │          │ Inputs:              │      │
    │  │  use / copy /    │          │  bundle preset +     │      │
    │  │  create          │          │  user overrides +    │      │
    │  │                  │          │  x12_source data     │      │
    │  │ Reads:           │          │                      │      │
    │  │  partner_registry│          │ Reads:               │      │
    │  │  existing yamls  │          │  layer2_presets.yaml  │      │
    │  │                  │          │  edi_framework/      │      │
    │  │ Output:          │          │                      │      │
    │  │  lifecycle.yaml  │          │ Output:              │      │
    │  └─────────────────┘          │  maps/{tx}.yaml      │      │
    │                                └──────────┬──────────┘      │
    │                                           │                  │
    │                                           ▼                  │
    │                               ┌────────────────────┐        │
    │                               │  spec_builder.py    │        │
    │  template_loader.py           │                     │        │
    │  (reads all yamls,            │ MERGE:              │        │
    │   returns pre-fill)           │  Layer 1 (x12_src)  │        │
    │                               │  + Layer 2 (wizard)  │        │
    │                               │  = Final Spec        │        │
    │                               │                     │        │
    │                               │ render_markdown.py   │        │
    │                               │ render_html.py       │        │
    │                               │ render_pdf.py        │        │
    │                               └──────────┬──────────┘        │
    │                                           │                  │
    │                               ┌───────────▼──────────┐      │
    │                               │ artifact_writer.py    │      │
    │                               │ → S3 + DB             │      │
    │                               └──────────────────────┘      │
    └─────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────┐
    │              edi_framework/ (READ-ONLY AT RUNTIME)           │
    │                                                             │
    │  partner_registry.yaml     ◄── NEW (Layer 0 white-label)   │
    │  templates/                                                 │
    │    layer2_presets.yaml      ◄── NEW (competitive advantage) │
    │  lowes_master.yaml         (existing, now referenced by     │
    │                              partner_registry)              │
    │  transactions/*.yaml       (Layer 1)                        │
    │  mappings/*.yaml           (turnaround rules)               │
    │  lifecycle/                                                  │
    │    order_to_cash.yaml      (UNCHANGED)                      │
    │  shared/*.yaml             (envelope, codelists, segments)  │
    │  meta/*.yaml               (Layer 0 pykwalify schemas)      │
    └─────────────────────────────────────────────────────────────┘
```

### Data Flow — End to End

```
  RETAILER USER (Browser)
       │
       │  Step 1: Lifecycle Wizard
       │  ┌─────────────────────────────────────────┐
       │  │ Mode: use/copy/create                    │
       │  │ X12 Version: 4010 (from version_registry)│
       │  │ Transactions: 850,855,856,810 (from x12) │
       │  │ States: auto or custom                    │
       │  └──────────────────┬──────────────────────┘
       │                     │ save each step → wizard_sessions DB
       │                     │ finalize → lifecycle.yaml → S3
       │                     ▼
       │  Step 2: Layer 2 Wizard (per transaction)
       │  ┌─────────────────────────────────────────┐
       │  │ Preset: Standard Retail (from Lowe's)    │
       │  │ Expand: BEG segment → override BEG02     │
       │  │ Rules: quantity chain ON, N1 chain ON     │
       │  │ Mappings: 850→855 turnaround defaults     │
       │  └──────────────────┬──────────────────────┘
       │                     │ save each step → wizard_sessions DB
       │                     │ finalize → maps/{tx}.yaml → S3
       │                     ▼
       │  Step 3: Generate Artifacts
       │  ┌─────────────────────────────────────────┐
       │  │ Layer 1 (x12_source: pyx12/Stedi)       │
       │  │  + Layer 2 (wizard overrides)            │
       │  │  = Merged Spec                           │
       │  │                                          │
       │  │ Output per transaction:                  │
       │  │   {retailer}/specs/4010/850.md            │
       │  │   {retailer}/specs/4010/850.html          │
       │  │   {retailer}/specs/4010/850.pdf           │
       │  │                                          │
       │  │ Layer 2 annotations baked into artifacts: │
       │  │   "N104: qualifier 93 [REQUIRED]"         │
       │  └──────────────────┬──────────────────────┘
       │                     │ artifacts → S3 + retailer_specs DB
       │                     ▼
       │  Step 4: Download / Distribute
       │  ┌─────────────────────────────────────────┐
       │  │ GET /artifacts/{slug}/850.pdf             │
       │  │ → FastAPI StreamingResponse from S3       │
       │  │                                          │
       │  │ Suppliers receive these specs with         │
       │  │ retailer-specific requirements baked in.  │
       │  └─────────────────────────────────────────┘
```

### Web UI — Lifecycle Wizard (Wizard 1)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Meredith · Lifecycle Wizard                     Session: "My OTC"  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ● Mode ─── ● Version ─── ● Transactions ─── ○ States ─── ○ Review│
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░░░░░░░░ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Define States & Transitions                                  │  │
│  │  (Cloned from: Lowe's Order-to-Cash v2.0)                    │  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │  po_originated                                     [✎]  │  │  │
│  │  │  Trigger: 850 inbound                                   │  │  │
│  │  │  → po_acknowledged (855)  → po_changed (860)            │  │  │
│  │  │  → shipped (856)          → invoiced (810)              │  │  │
│  │  ├─────────────────────────────────────────────────────────┤  │  │
│  │  │  po_acknowledged                                   [✎]  │  │  │
│  │  │  Trigger: 855 outbound                                  │  │  │
│  │  │  → shipped (856)  → po_changed (860)  → invoiced (810) │  │  │
│  │  ├─────────────────────────────────────────────────────────┤  │  │
│  │  │  shipped                                           [✎]  │  │  │
│  │  │  Trigger: 856 outbound                                  │  │  │
│  │  │  → invoiced (810)  → shipped (856 replacement)          │  │  │
│  │  ├─────────────────────────────────────────────────────────┤  │  │
│  │  │  invoiced (terminal)                               [✎]  │  │  │
│  │  │  Trigger: 810 outbound                                  │  │  │
│  │  ├─────────────────────────────────────────────────────────┤  │  │
│  │  │  [+ Add State]                                          │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                                                               │  │
│  │  Auto-generated diagram:                                      │  │
│  │  po_originated ──855──▶ po_acknowledged ──856──▶ shipped     │  │
│  │       │──860──▶ po_changed ──865──▶ po_change_accepted       │  │
│  │                                            └──856──▶ shipped │  │
│  │                                      shipped ──810──▶ invoiced│ │
│  │                                                               │  │
│  │  ┌──────────┐                           ┌──────────────┐     │  │
│  │  │  ← Back  │                           │    Next →     │     │  │
│  │  └──────────┘                           └──────────────┘     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Web UI — Layer 2 Wizard (Wizard 2)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Meredith · Layer 2 Config — 850 Purchase Order (4010)              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ● Preset ─── ● Segments ─── ○ Rules ─── ○ Mappings ─── ○ Artifacts│
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│                                                                     │
│  Transactions: [850 ●] [855] [856] [860] [865] [810]              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Segment Configuration (Standard Retail preset applied)       │  │
│  │                                                               │  │
│  │  ▼ BEG — Beginning Segment for Purchase Order                │  │
│  │  ┌─────────┬──────────┬─────────────────┬──────────────────┐  │  │
│  │  │ Element │ Required │ Qualifier       │ Constraint        │  │  │
│  │  ├─────────┼──────────┼─────────────────┼──────────────────┤  │  │
│  │  │ BEG01   │ ☑ Yes    │ [00         ▼]  │ Transaction Set   │  │  │
│  │  │         │          │  00 - Original   │ Purpose Code     │  │  │
│  │  │         │          │  05 - Replace    │                  │  │  │
│  │  │         │          │  01 - Cancel     │                  │  │  │
│  │  ├─────────┼──────────┼─────────────────┼──────────────────┤  │  │
│  │  │ BEG02   │ ☑ Yes    │ [SA,NS,SP  ▼]  │ PO Type Code     │  │  │
│  │  │ BEG03   │ ☑ Yes    │ (free text)     │ Max 9, zero-supp │  │  │
│  │  │ BEG05   │ ☑ Yes    │ (date)          │ CCYYMMDD         │  │  │
│  │  └─────────┴──────────┴─────────────────┴──────────────────┘  │  │
│  │                                                               │  │
│  │  ▶ CUR — Currency  (preset: USD)                 [Expand ▶]  │  │
│  │  ▶ REF — Reference ID  (preset: IA, WO)         [Expand ▶]  │  │
│  │  ▶ FOB — F.O.B.  (preset: CC, PP only)          [Expand ▶]  │  │
│  │  ▶ DTM — Date/Time  (preset: 002, 010)          [Expand ▶]  │  │
│  │  ▶ N1  — Name Loop  (preset: ST, BT, VN, 93→)  [Expand ▶]  │  │
│  │  ▶ PO1 — Baseline Item Data                     [Expand ▶]  │  │
│  │  ▶ CTT — Transaction Totals                     [Expand ▶]  │  │
│  │                                                               │  │
│  │  All segments populated from X12 4010 library.                │  │
│  │  Preset values shown. Click [Expand] to override.            │  │
│  │                                                               │  │
│  │  ┌──────────┐                           ┌──────────────┐     │  │
│  │  │  ← Back  │                           │    Next →     │     │  │
│  │  └──────────┘                           └──────────────┘     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Web UI — Artifact Gallery (Post-Generation)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Meredith · Spec Artifacts                                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  X12 Version: 4010  |  Lifecycle: My Custom OTC  |  6 transactions │
│                                                                     │
│  These specs include your Layer 2 configuration and are ready       │
│  to distribute to suppliers.                                        │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  850 Purchase Order                      Layer 2: ✓ Applied  │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐                         │   │
│  │  │ ↓ MD   │  │ ↓ HTML │  │ ↓ PDF  │     Generated: Mar 14  │   │
│  │  └────────┘  └────────┘  └────────┘                         │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  855 PO Acknowledgment                   Layer 2: ✓ Applied  │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐                         │   │
│  │  │ ↓ MD   │  │ ↓ HTML │  │ ↓ PDF  │     Generated: Mar 14  │   │
│  │  └────────┘  └────────┘  └────────┘                         │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  856 ASN                                  Layer 2: ○ Pending │   │
│  │  Layer 2 not yet configured. [Configure ▶]                   │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  ...                                                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────┐                                      │
│  │  Download All (.zip)      │                                      │
│  └──────────────────────────┘                                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## TODO.md ADDITIONS (Deferred Items)

```markdown
### Deferred — Wizard Refactoring

**Dwight Re-incorporation**
- Reconnect PDF analysis as optional/admin fallback for spec creation
- Dwight agent stays in codebase, just disconnected from Meredith wizard flow
- Files: `agents/dwight.py`, `portals/meredith.py`

**Andy Path 1 (PDF → YAML)**
- Re-enable when Dwight is re-incorporated
- Path 1 signal handler currently returns 410 Gone
- File: `agents/andy.py`, `portals/meredith.py`

**lab_850 Seed Integration**
- Re-enable as optional pre-fill source for Layer 2 wizard
- lab_850 generates wizard_payload JSON that can seed Layer 2 presets
- Files: `lab_850/seed_generator.py`, `certportal/generators/layer2_builder.py`

**THESIS.md Artifact Format**
- Re-enable when Dwight is re-incorporated
- May become one of the artifact formats alongside MD/HTML/PDF

**Admin Template Upload Portal (PAM)**
- Add PAM route for admins to upload pre-formatted Layer 2 templates
- Templates become available to all retailers in the Layer 2 wizard
- Competitive advantage: curated templates as a service offering
- Files: `portals/pam.py`, `edi_framework/templates/`
```

---

## IMPLEMENTATION ORDER (Recommended)

```
Phase A (Foundation)     ████████████  — x12_source, version_registry,
                                         partner_registry, migrations

Phase B (Templates)      ████████      — layer2_presets, template_loader,
                                         lifecycle_builder, layer2_builder

Phase C (Spec Generator) ████████      — spec_builder (Layer1+Layer2 merge),
                                         renderers (MD/HTML/PDF), artifact_writer

Phase D (Lifecycle Wiz)  ████████████  — routes, templates, JS, session mgmt

Phase E (Layer 2 Wiz)    ████████████  — routes, templates, segment config,
                                         business rules, artifact generation

Phase F (Portal Updates) ██████        — dashboard, spec-setup refactor,
                                         artifact gallery, deprecations

Phase G (CSS/JS)         ██████        — wizard indicators, segment config,
                                         lifecycle editor

Phase H (Documentation)  ████          — ADRs, CLAUDE.md, TODO.md

Phase P (Playwright)     ████████████  — new flows, new checks, seed updates,
                                         regression verification
```

Phases A–C are sequential (each depends on the prior).
Phases D and E can partially overlap (shared wizard session infrastructure).
Phase F depends on D+E.
Phase G can run in parallel with D+E.
Phase H runs last.
Phase P runs after each phase for incremental verification.
