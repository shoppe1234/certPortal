# certPortal — What It Does and How It Works

certPortal is an EDI certification platform. It helps retailers and suppliers set up, test, and certify their electronic data interchange (EDI) connections before going live.

Think of it like a driving test for EDI: before a supplier can start sending real purchase orders, invoices, and shipping notices to a retailer, they need to prove their systems can do it correctly. certPortal manages that entire process.

---

## What certPortal Does

- Lets retailers define their EDI requirements (which documents they need, what format, what rules)
- Walks suppliers through a guided onboarding wizard — from acknowledging specs to production go-live
- Automatically validates every test document against the retailer's rules
- Tracks each supplier through a five-gate certification process (A → B → 1 → 2 → 3)
- Lets suppliers request exceptions when a transaction doesn't apply to their business
- Lets retailers review, approve, or deny exception requests
- Provides a template library where admins curate reusable EDI configurations for retailers
- Generates fix suggestions when documents have errors
- Produces specification documents (Markdown, HTML, PDF) that describe the retailer's requirements
- Keeps a full audit trail of every validation, every gate transition, and every decision
- Offers a unified visual design with light/dark mode across all three portals

## What certPortal Does Not Do

- It does not process live/production EDI transactions
- It does not replace the supplier's EDI system — it tests the output of that system
- It does not handle purchase order fulfillment, shipping, or payment
- It does not allow self-registration — an admin must create every account

---

## The Three Portals

certPortal has three types of users, each with their own portal (web application). All three share a unified design system with portal-specific accent colors and a dark mode toggle.

| Role | Portal | Accent | What They Do |
|------|--------|--------|-------------|
| **Admin** | PAM (port 8000) | Pink, defaults dark | Manages the platform: creates accounts, reviews escalations, curates template library, certifies suppliers |
| **Retailer** | Meredith (port 8001) | Blue | Defines EDI requirements: sets up specs, reviews exception requests, adopts templates from PAM |
| **Supplier** | Chrissy (port 8002) | Amber | Completes onboarding: acknowledges specs, submits test documents, requests exceptions, earns certification |

### How They Relate to Each Other

```
┌─────────────────────────────────────────────────────────────────────┐
│  PAM (Admin)                                                        │
│  • Creates accounts for retailers + suppliers                       │
│  • Curates template library (lifecycle, scenario, preset templates)  │
│  • Reviews HITL escalations                                         │
│  • Certifies suppliers (Gate 3 → CERTIFIED)                         │
│  • Publishes templates → Kelly notifies retailers                    │
└────────────┬────────────────────────────────────────┬───────────────┘
             │ templates                               │ certification
             ▼                                         │
┌────────────────────────┐    S3 signals    ┌─────────────────────────┐
│  Meredith (Retailer)   │◄───────────────►│  Chrissy (Supplier)      │
│  • Defines lifecycle   │  exceptions,     │  • 6-step onboarding     │
│  • Customizes Layer 2  │  gate signals    │  • Submits test EDI docs │
│  • Reviews exceptions  │                  │  • Requests exceptions   │
│  • Adopts/forks        │                  │  • Reviews errors/patches│
│    templates from PAM  │                  │  • Earns certification   │
└────────────────────────┘                  └─────────────────────────┘
```

The admin sits above both. The retailer sets the bar. The supplier clears the bar. Portals never import from each other or from agents — all cross-portal communication happens via S3 signals.

The architecture diagram in `SketchesDiagrams/chrissy_onboarding_v3.html` shows the full cross-portal data flow, gate formulas, exception request lifecycle, and template cascade.

---

## The Template Library

PAM admins curate a library of reusable EDI configuration templates. This is a competitive advantage — certPortal offers pre-built, industry-specific templates that retailers can adopt instead of configuring from scratch.

### Template Categories

| Category | What It Contains | Example |
|----------|-----------------|---------|
| **Lifecycle** | Complete order-to-cash document flow definitions | Standard Retail: 850→855→856→810 |
| **Scenario Bundle** | Pre-defined sets of test scenarios | Grocery/FMCG: adds 860 change orders with stricter timing |
| **Layer 2 Preset** | Segment-level customization overlays | Drop Ship: 3PL routing, no 860/865 |

### How Templates Flow

```
PAM creates template → PAM publishes → Kelly notifies retailers
                                           ↓
                               Meredith sees in /template-library
                                           ↓
                              Retailer ADOPTs (links to original)
                                   or FORKs (clones for editing)
                                           ↓
                         Chrissy supplier sees no difference —
                         their test scenarios come from whatever
                         config the retailer chose
```

---

## Retailer Responsibilities

Retailers use the Meredith portal to define their EDI requirements. This is the foundation that suppliers will be tested against.

### Setting Up the Lifecycle

Every EDI relationship follows a lifecycle — a sequence of documents that must flow in a specific order. For example, a typical order-to-cash lifecycle looks like this:

```
Purchase Order (850) → PO Acknowledgment (855) → Ship Notice (856) → Invoice (810)
```

The retailer uses the **Lifecycle Wizard** to define this flow:

1. **Choose a mode** — Use a pre-built lifecycle as-is, copy one and modify it, or create one from scratch
2. **Select the X12 version** — The EDI standard version (e.g., 4010, 5010)
3. **Pick which transaction types to support** — Which documents (850, 855, 856, 860, 865, 810) are required
4. **Review or edit the state machine** — The rules about which documents can follow which, and what validations apply at each step

### Customizing the Spec (Layer 2)

On top of the base lifecycle, retailers add their own customizations using the **Layer 2 YAML Wizard**:

1. **Start from a preset** — Choose a starting template (Standard Retail, Minimal, or Blank) — or adopt one from the PAM template library
2. **Add segment-level overrides** — Customize which data elements are required, optional, or have specific allowed values
3. **Generate the unified spec** — The system merges the base lifecycle (Layer 1) with the retailer's customizations (Layer 2) into a complete specification
4. **Download artifacts** — The finished spec is available as a Markdown guide, branded HTML page, and PDF document

### Reviewing Exception Requests

When a supplier requests an exception for a test scenario, the request appears in the retailer's **Exception Queue** on Meredith:

- **Pending requests** show the supplier name, transaction type, reason code, and optional note
- The retailer can **Approve** (marks the transaction as EXEMPT — no longer required for Gate 2) or **Deny** (transaction stays REQUIRED)
- Approvals and denials trigger Kelly notification signals to the supplier

### Monitoring Suppliers

Retailers can view all their suppliers on the **Supplier Status Board**, which shows each supplier's current gate status, pass/fail counts, and last update time. Retailers can also approve gate transitions for their own suppliers.

---

## Supplier Onboarding — The 6-Step Wizard

Suppliers use the Chrissy portal's onboarding wizard to complete certification. The wizard guides them through six sequential steps, each gated by a prerequisite.

```
Step 1 ──► Step 2 ──► Step 3 ──► Step 4 ──► Step 5 ──► Step 6
Gate A     Gate B     Gate 1     Items      Gate 2     Gate 3
Specs      Contact    Connection  Data      Testing    Go-Live
```

### Step 1 — Review Specifications (Gate A)

The supplier downloads and reviews the retailer's EDI specification package. After reviewing, they check an acknowledgment box and click "Acknowledge & Continue." This sets Gate A to COMPLETE and unlocks Step 2.

If the retailer hasn't published specs yet, the supplier sees a holding message and cannot start.

### Step 2 — Company & Contact Information (Gate B)

The supplier provides their company name and a primary contact (name, email, phone). All four fields are required. Submitting this form sets Gate B to COMPLETE and unlocks Step 3.

This contact information is who the retailer will reach out to if there's a question about the supplier's EDI setup.

### Step 3 — Connection & Test EDI Identifiers (Gate 1)

The supplier selects their connection method (AS2, SFTP, or FTP) and enters their test EDI identifiers: vendor number, EDI qualifier, ISA ID, and GS ID. These are test-environment credentials — production IDs come later at go-live.

Submitting this form sets Gate 1 to COMPLETE, unlocks Step 4, and triggers a Kelly notification signal ("test environment ready").

### Step 4 — Item Data

The supplier enters vendor part numbers, descriptions, units of measure, and locations for their test items. This data ensures test purchase orders contain realistic data. A CSV upload option is available for bulk entry.

### Step 5 — Test Scenarios (Gate 2)

This is the core testing step. The supplier sees a list of all transaction types the retailer requires (850, 855, 856, 810, etc.). Each transaction shows a REQUIRED badge.

For each required transaction:
- The supplier submits test EDI documents
- The system validates them automatically (via Moses, the validation agent)
- If the transaction passes, it's marked CERTIFIED

**Exception requests:** If a transaction doesn't apply to the supplier's business, they can request an exception with a reason code:
- **Not Applicable** — the supplier doesn't use this transaction type
- **Handled Externally** — managed by a third party (e.g., 3PL handles ship notices)
- **Deferred** — the supplier will implement later
- **Retailer Waived** — the retailer agreed to skip this requirement

Exception requests go to the retailer's Exception Queue on Meredith. If approved, the transaction is marked EXEMPT and counts as satisfied for Gate 2.

**Gate 2 formula:** For every scenario marked REQUIRED by the retailer, the transaction must be either CERTIFIED (tested and passed) or EXEMPT (exception approved). Pending exception requests block Gate 2.

### Step 6 — Go-Live (Gate 3)

Testing is complete. The supplier enters their production EDI credentials (which may differ from test IDs) and confirms. This triggers Gate 3 = PENDING, awaiting PAM admin certification.

Once an admin certifies Gate 3:
- The supplier sees a certification badge on their dashboard
- Kelly sends a certification notification email
- The supplier is cleared to begin live EDI transactions with the retailer

---

## The Five-Gate Model

Certification happens through five sequential gates. Gates must be completed in order — you cannot skip ahead. Every gate is binary: either met or not met. There are no partial states.

```
Gate A ──► Gate B ──► Gate 1 ──► Gate 2 ──► Gate 3
│          │          │          │          │
│ Specs    │ Contact  │ Connect  │ Testing  │ Certify
│ ack'd    │ info     │ + IDs    │ complete │ (admin)
│          │          │          │          │
▼          ▼          ▼          ▼          ▼
PENDING    PENDING    PENDING    PENDING    PENDING
  or         or         or         or         or
COMPLETE   COMPLETE   COMPLETE   COMPLETE   CERTIFIED
```

| Gate | What It Proves | Who Advances It | Prerequisite |
|------|---------------|-----------------|--------------|
| **Gate A** | Supplier has reviewed the retailer's specs | Supplier (acknowledge) | None |
| **Gate B** | Supplier has provided valid contact info | Supplier (form submit) | Gate A |
| **Gate 1** | Test environment is configured | Supplier (connection setup) | Gate B |
| **Gate 2** | All required scenarios pass or are exempt | Automatic (formula check) | Gate 1 |
| **Gate 3** | Production-ready, admin-approved | Admin (PAM certification) | Gate 2 |

Gate enforcement is handled by `gate_enforcer.py` (INV-03), the single authority for gate progression. The enforcer validates the prerequisite chain before every transition.

### What Happens When Things Go Wrong

If a supplier's document fails validation at any gate:

1. The error details appear on the supplier's **Errors** page in Chrissy
2. The system's patch generator (Ryan) automatically creates fix suggestions
3. The supplier reviews the patches on the **Patches** page
4. The supplier applies the fix to their EDI system and marks the patch as "Applied"
5. Marking a patch as applied triggers automatic re-validation
6. If serious issues arise, the system can escalate to the admin's **HITL Queue** in PAM for human review

This cycle — submit, fail, review errors, apply fix, re-submit — continues until the supplier passes all validations for the current gate.

---

## Visual Design

All three portals share a unified design system (`certportal-core.css`) with portal-specific accent colors:

| Portal | Accent Color | Default Theme |
|--------|-------------|---------------|
| PAM | Pink (#ec4899) | Dark |
| Meredith | Blue (#4f6ef7) | Light |
| Chrissy | Amber (#f59e0b) | Light |

Every portal has a dark mode toggle in the navigation bar. The toggle persists across page navigation via localStorage and respects the OS `prefers-color-scheme` setting. PAM defaults to dark mode; the other two default to light.

The design system uses Chrissy's warm aesthetic as the base: Plus Jakarta Sans font, 12px border radius, rounded pill buttons, generous whitespace. Components include cards, tables, forms, badges, gate pills, progress indicators, wizard step indicators, and empty states — all responsive down to 375px mobile viewports.

---

## What to Expect During the Process

### For Retailers

| Phase | What You Do | What to Expect |
|-------|------------|----------------|
| **Setup** | Complete both wizards (Lifecycle + Layer 2), or adopt a template from PAM | Takes one session. You define the rules once; they apply to all your suppliers. |
| **Monitoring** | Check the Supplier Status Board periodically | You see which suppliers are progressing, which are stuck, and which are certified. |
| **Exception Review** | Review and approve/deny supplier exception requests | Binary decisions: approve marks the transaction EXEMPT, deny keeps it REQUIRED. |
| **Gate Approval** | Review supplier results and approve gates | You can approve Gate 1 and Gate 2 for your suppliers. Gate 3 (certification) requires admin approval. |
| **Ongoing** | Update specs if requirements change | Re-run the wizards to generate updated specifications and artifacts. |

### For Suppliers

| Phase | What You Do | What to Expect |
|-------|------------|----------------|
| **Steps 1–3 (Setup)** | Acknowledge specs, provide contact info, configure test connection | Quick — mostly form filling. Unlocks your test environment. |
| **Step 4 (Items)** | Enter test item data (vendor part numbers, descriptions) | One-time data entry or CSV upload. |
| **Step 5 (Testing)** | Submit test EDI documents for each required transaction type | This is the hardest step. Expect multiple rounds of submit-fix-resubmit. Request exceptions for transactions that don't apply. |
| **Step 6 (Go-Live)** | Enter production credentials and wait for admin certification | Once Gate 2 is complete, submit your production IDs. The admin reviews and certifies. |
| **After Certification** | Begin live EDI transactions | Your certification badge confirms you are cleared to exchange production EDI documents with the retailer. |

The typical timeline depends on how closely your EDI system already aligns with the retailer's requirements. Suppliers with well-configured EDI systems may clear all gates quickly. Suppliers with formatting or sequencing issues should expect several rounds of submit-fix-resubmit before passing.

---

## Reference Documents

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | Developer instructions: invariants, module index, migration list, CLI commands |
| `DECISIONS.md` | Architectural Decision Record: ADR-001 through ADR-042 |
| `TODO.md` | Remaining work: deferred items, infrastructure to-dos |
| `README.md` | Setup guide, agent CLI commands, test suite reference |
| `TECHNICAL_REQUIREMENTS.md` | Original Sprint 1 design spec (TRD v2.0) |
| `portalRefactor-2026-03-15.md` | Portal refactoring plan: onboarding, exceptions, templates, Playwright |
| `websiteRefactor-2026-03-15.md` | UI consolidation plan: unified CSS, dark mode, template migration |
| `playwrightRalph.md` | Ralph Loop execution guide: flow file diagnostics, template selector reference |
| `SketchesDiagrams/chrissy_onboarding_v3.html` | Cross-portal architecture diagram: gate formulas, exception flow, template cascade |
