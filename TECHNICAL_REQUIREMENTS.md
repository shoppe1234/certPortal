# certPortal — Technical Requirements
## EDI Integration + Claude Code Desktop Handoff

| Field | Value |
|---|---|
| **Document Version** | 2.0 — Final (post Q&A + certPortal audit) |
| **Date** | 2026-03-06 |
| **Status** | ✅ APPROVED FOR CODING |
| **certPortal Repo** | github.com/shoppe1234/certPortal (public) |
| **PyEDI-Core Branch** | github.com/shoppe1234/PyEDI-Core/tree/flatfile |
| **Primary Developer** | Solo — Claude Code Desktop |
| **Database** | PostgreSQL (`CERTPORTAL_DB_URL` env var) |
| **Sprint Scope** | Sprint 1: `lifecycle_engine/` + `schema_validators/` + 865 YAML |

> ⚠️ **SECURITY:** The read-only GitHub token shared during design review should be revoked and regenerated at `github.com/settings/tokens` before coding begins.

---

## Table of Contents

1. [Context & What Was Audited](#1-context--what-was-audited)
2. [Non-Negotiable Constraints](#2-non-negotiable-constraints)
3. [Target Repository Structure](#3-target-repository-structure)
4. [Immediate Prerequisite: 865 Transaction YAML](#4-immediate-prerequisite-865-transaction-yaml)
5. [PostgreSQL Database Schema](#5-postgresql-database-schema)
6. [lifecycle_engine/ — Full Module Specification](#6-lifecycle_engine---full-module-specification)
7. [PO Number Extraction Contract](#7-po-number-extraction-contract)
8. [Transaction-to-State Mapping](#8-transaction-to-state-mapping)
9. [schema_validators/ — Layer 0 Specification](#9-schema_validators---layer-0-specification)
10. [Build Order — Claude Code Desktop](#10-build-order---claude-code-desktop)
11. [Moses Integration — Verify Before Coding](#11-moses-integration---verify-before-coding)
12. [Definition of Done](#12-definition-of-done)
13. [Items to Verify in Claude Code Desktop](#13-items-to-verify-in-claude-code-desktop)

---

## 1. Context & What Was Audited

Three repositories were fully reviewed and are the source of truth for this document:

| Codebase | Location | State | Sprint Role |
|---|---|---|---|
| `edi_framework/` | Project YAML files | ✅ Complete — 6 txns, 6 maps, lifecycle | Read-only spec source |
| `PyEDI-Core` (flatfile) | shoppe1234/PyEDI-Core | ✅ Functional — X12/CSV/fixed-length, 68/68 tests | Parser engine library |
| `certPortal` | shoppe1234/certPortal | 🔶 Partially built — 9 agents, 3 portals, S3 backbone | Host repo |
| `lifecycle_engine/` | Does not exist | 🔴 Must be built — **Sprint 1 primary deliverable** | New module |
| `schema_validators/` | Does not exist | 🔴 Must be built — **Sprint 1 secondary deliverable** | New module |

### 1.1 certPortal Architecture (What Exists)

certPortal is a **9-agent deterministic AI pipeline platform** — not just an EDI app. Understanding this is critical before touching any file.

| Agent | Role | LLM | Relevance to Integration |
|---|---|---|---|
| Monica | Orchestrator + HITL Keeper | GPT-4o-mini | Receives lifecycle violations via S3 `PAM-STATUS.json` |
| Dwight | Spec Analyst (PDF → THESIS.md) | GPT-4o | No direct integration |
| Andy | YAML Mapper — 3 ingestion paths | GPT-4o-mini (Path 1 only) | Path 2 = uploaded YAML → validates against our meta-schemas |
| **Moses** | EDI Validator — FULLY DETERMINISTIC | **None** | ⭐ **PRIMARY integration point** — calls PyEDI-Core + lifecycle_engine |
| Kelly | Multi-Channel Communications | GPT-4o-mini | Notified on lifecycle violations via S3 |
| Ryan | Patch Generator | GPT-4o-mini | Reads `ValidationResult` from S3 — lifecycle state is context |

### 1.2 Andy's 3 Ingestion Paths

Andy provides retailer/supplier optionality for onboarding YAML specs. All three paths produce YAML that `schema_validators/` must validate:

- **Path 1 — PDF → YAML:** LLM-assisted (GPT-4o-mini). Validation is critical here since LLMs can hallucinate structure.
- **Path 2 — Uploaded YAML → validated + stored:** Fully deterministic. Our pykwalify meta-schemas are the **runtime gate** for this path.
- **Path 3 — Wizard form → YAML:** Fully deterministic with advisory lock.

> **KEY INSIGHT:** `schema_validators/` is not just a dev/CI tool — it is the **runtime gate for Andy's Path 2**. Every uploaded YAML goes through `validate_file()` before being stored. This makes it a Sprint 1 production dependency.

---

## 2. Non-Negotiable Constraints

### 2.1 certPortal Existing Invariants (Enforced in Code)

| INV | Rule | Impact on New Modules |
|---|---|---|
| **INV-01** | Agents never import each other — S3 is the only inter-agent channel | `pyedi_core/` and `lifecycle_engine/` are **libraries** not agents — OK to import from agents |
| **INV-02** | All ambiguity routes through Monica via `PAM-STATUS.json` on S3 | `lifecycle_engine` must write violations to S3 workspace **in addition** to Postgres |
| **INV-03** | Gate ordering enforced by `gate_enforcer.py` (raises `GateOrderViolation`) | Lifecycle state machine IS a gate — align with existing gate pattern |
| **INV-04** | No LangChain — explicit OpenAI client calls only | ✅ No LLMs in our new modules |
| **INV-05** | `MONICA-MEMORY.md` is append-only (never opened with `"w"`) | `lifecycle_events` table is also append-only — INSERT only, no UPDATE/DELETE |
| **INV-06** | S3 paths scoped to `{retailer_slug}/{supplier_slug}/` | `partner_id` maps to `retailer_slug`. Lowe's = `"lowes"` |
| **INV-07** | Portals never import from `agents/` | Portals also cannot import `lifecycle_engine/` or `pyedi_core/` directly |

### 2.2 New Constraints (Sprint 1)

| NC | Rule |
|---|---|
| **NC-01** | `edi_framework/` is **READ-ONLY at runtime**. No process may write, patch, or overwrite any YAML file. |
| **NC-02** | No hardcoded transaction logic in `.py` files. Business rules live in YAML. Python executes. |
| **NC-03** | The PO number is the primary key everywhere — every table, every log event, every S3 path, every error record. |
| **NC-04** | `pyedi_core/` must remain usable **standalone** without `lifecycle_engine/` installed. Integration hook uses `ImportError` guard. |
| **NC-05** | `strict_mode=false` during development, `strict_mode=true` in production. Controlled via `lifecycle_engine/config.yaml`. |

---

## 3. Target Repository Structure

Three new top-level directories are added to certPortal. **Existing directories are untouched.**

```
certPortal/
│
├── agents/                     ← EXISTING — do not modify
├── portals/                    ← EXISTING — do not modify
├── certportal/                 ← EXISTING shared core
├── static/                     ← EXISTING
├── templates/                  ← EXISTING
├── testing/                    ← EXISTING
│
├── edi_framework/              ← NEW: YAML EDI Specs (read-only at runtime)
│   ├── lowes_master.yaml
│   ├── shared/
│   │   ├── envelope.yaml
│   │   ├── codelists.yaml
│   │   └── common_segments.yaml
│   ├── transactions/
│   │   ├── 850_stock_po.yaml
│   │   ├── 855_po_ack.yaml
│   │   ├── 856_asn.yaml
│   │   ├── 860_po_change.yaml
│   │   ├── 865_po_change_ack.yaml   ← MUST BE CREATED (Step 2 — blocking)
│   │   └── 810_invoice.yaml
│   ├── mappings/               ← 6 turnaround mapping files
│   ├── lifecycle/
│   │   └── order_to_cash.yaml
│   └── meta/                   ← Layer 0 pykwalify schemas (Step 3)
│       ├── transaction_schema.yaml
│       ├── mapping_schema.yaml
│       └── lifecycle_schema.yaml
│
├── pyedi_core/                 ← NEW: PyEDI-Core flatfile parser (simple copy)
│   ├── config/
│   │   └── config.yaml         ← add `partner_id: lowes`
│   ├── rules/
│   ├── schemas/
│   ├── pyedi_core/
│   │   ├── core/
│   │   ├── drivers/
│   │   └── pipeline.py         ← ADD lifecycle_engine hook after WRITE stage
│   └── tests/
│
├── lifecycle_engine/           ← NEW: State Machine Runtime (primary Sprint 1)
│   ├── config.yaml
│   ├── engine.py
│   ├── state_store.py          ← Postgres via psycopg2
│   ├── validators.py
│   ├── loader.py
│   ├── exceptions.py
│   ├── interface.py            ← ONLY file pipeline.py imports
│   ├── s3_writer.py            ← writes violations to S3 for Monica (INV-02)
│   ├── migrations/
│   │   └── 001_lifecycle_tables.sql
│   └── tests/
│
└── schema_validators/          ← NEW: Layer 0 pykwalify YAML validators
    ├── validate_all.py         ← CLI entry point + Andy Path 2 runtime gate
    ├── validate_transaction.py
    ├── validate_mapping.py
    ├── validate_lifecycle.py
    ├── report.py
    └── tests/
```

---

## 4. Immediate Prerequisite: 865 Transaction YAML

> 🔴 **BLOCKING:** `865_po_change_ack.yaml` must be created before any other coding begins. It is referenced by `lowes_master.yaml` and `order_to_cash.yaml`. The lifecycle engine will fail to load without it.

**File path:** `edi_framework/transactions/865_po_change_ack.yaml`

**Key facts:**
- Lowe's reuses `ST01=860` for 865 (envelope quirk)
- Functional group = `PC`
- `BCA02` = `AT` (accept) or `RJ` (reject) — only two allowed values
- One 865 per 860 — header only, no line-level detail
- `BCA03` must echo `BCH03` from the originating 860
- `BCA05` date must be on or after `BCH05` (860 date)

**Minimum required YAML structure:**

```yaml
transaction:
  id: "865"
  name: "PO Change Acknowledgment (Seller Initiated)"
  functional_group: "PC"
  direction: outbound         # Vendor → Lowe's
  version: "004010"

  shared_refs:
    envelope:  shared/envelope.yaml
    common:    shared/common_segments.yaml
    codelists: shared/codelists.yaml

  envelope_overrides:
    GS:
      GS01: { fixed_value: "PC" }
    ST:
      ST01: { fixed_value: "860" }   # Lowe's reuses ST01=860 for 865

  heading:
    BCA:
      name: "Beginning Segment for PO Change Acknowledgment"
      position: 20
      usage: mandatory
      max_use: 1
      elements:
        BCA01: { name: "Transaction Set Purpose Code", type: ID,
                 fixed_value: "00", usage: mandatory }
        BCA02: { name: "Acknowledgment Type", type: ID,
                 allowed_codes: [AT, RJ], usage: mandatory,
                 note: "AT=Accept  RJ=Reject" }
        BCA03: { name: "Purchase Order Number", type: AN,
                 min_max: "1/22", usage: mandatory,
                 note: "Must match originating 850 BEG03 / 860 BCH03" }
        BCA04: { name: "Release Number", type: AN,
                 min_max: "1/30", usage: optional }
        BCA05: { name: "Date", type: DT,
                 min_max: "8/8", format: "CCYYMMDD", usage: mandatory }
        BCA12: { name: "Change Order Sequence Number", type: AN,
                 min_max: "1/8", usage: optional,
                 note: "Echo BCH06 from originating 860" }

  business_rules:
    - "BCA03 must match BCH03 from the originating 860"
    - "One 865 per 860 — no line-level detail, header only"
    - "If BCA02=RJ, vendor must communicate reason out-of-band"
    - "BCA05 date must be on or after BCH05 (860 date)"
```

**Verification:** `python schema_validators/validate_all.py --file edi_framework/transactions/865_po_change_ack.yaml`

---

## 5. PostgreSQL Database Schema

All lifecycle state is persisted to the existing certPortal Postgres instance via `CERTPORTAL_DB_URL`. Three new tables. Migration SQL is committed; the database is never committed.

**Migration file:** `lifecycle_engine/migrations/001_lifecycle_tables.sql`

### 5.1 Table: `po_lifecycle`

One row per purchase order number. The primary state record.

```sql
CREATE TABLE po_lifecycle (
    id                     INTEGER      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    po_number              TEXT         NOT NULL UNIQUE,
    partner_id             TEXT         NOT NULL,          -- 'lowes' for Lowe's
    current_state          TEXT         NOT NULL,          -- order_to_cash.yaml state name
    is_terminal            BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ordered_qty            NUMERIC,                        -- from 850 PO1
    changed_qty            NUMERIC,                        -- from 860 POC
    accepted_qty           NUMERIC,                        -- from 855 ACK
    shipped_qty            NUMERIC,                        -- from 856 SN1
    invoiced_qty           NUMERIC,                        -- from 810 IT1
    n1_qualifier_inbound   TEXT,                           -- expect '93'
    n1_qualifier_outbound  TEXT                            -- expect '94' or '92'
);

CREATE INDEX idx_po_lifecycle_partner ON po_lifecycle(partner_id);
CREATE INDEX idx_po_lifecycle_state   ON po_lifecycle(current_state);
```

### 5.2 Table: `lifecycle_events`

Full audit trail. **INSERT ONLY — never UPDATE or DELETE** (mirrors INV-05 append-only pattern).

```sql
CREATE TABLE lifecycle_events (
    id               INTEGER      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    po_number        TEXT         NOT NULL REFERENCES po_lifecycle(po_number),
    partner_id       TEXT         NOT NULL,
    event_type       TEXT         NOT NULL,    -- state name triggered
    transaction_set  TEXT         NOT NULL,    -- '850','860','855','865','856','810'
    direction        TEXT         NOT NULL,    -- 'inbound' or 'outbound'
    source_file      TEXT         NOT NULL,
    correlation_id   TEXT         NOT NULL,    -- from pyedi_core pipeline
    prior_state      TEXT         NOT NULL,
    new_state        TEXT         NOT NULL,
    qty_at_event     NUMERIC,
    payload_snapshot JSONB,                    -- key fields captured at this event
    processed_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_le_po      ON lifecycle_events(po_number);
CREATE INDEX idx_le_corrId  ON lifecycle_events(correlation_id);
CREATE INDEX idx_le_type    ON lifecycle_events(event_type);
```

### 5.3 Table: `lifecycle_violations`

Every failed transition or validation failure. Also written to S3 for Monica (INV-02).

```sql
CREATE TABLE lifecycle_violations (
    id               INTEGER      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    po_number        TEXT,                     -- NULL if PO# could not be extracted
    partner_id       TEXT,
    transaction_set  TEXT         NOT NULL,
    source_file      TEXT         NOT NULL,
    correlation_id   TEXT         NOT NULL,
    violation_type   TEXT         NOT NULL,
        -- 'invalid_transition' | 'quantity_chain' | 'missing_po'
        -- 'duplicate_terminal' | 'n1_qualifier'
    violation_detail TEXT         NOT NULL,
    current_state    TEXT,
    attempted_event  TEXT         NOT NULL,
    failed_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

---

## 6. `lifecycle_engine/` — Full Module Specification

### 6.1 `config.yaml`

```yaml
# lifecycle_engine/config.yaml
lifecycle_engine:
  framework_base_path: '../edi_framework'   # relative to lifecycle_engine/
  log_level: INFO
  singleton: true

  profiles:
    development:
      strict_mode: false    # log violations, do not fail pipeline
    production:
      strict_mode: true     # violations route file to failed/

  s3:
    violations_prefix: 'lifecycle/violations/'   # under retailer/supplier scope
```

### 6.2 `exceptions.py`

```python
class LifecycleError(Exception): ...
class LifecycleConfigError(LifecycleError): ...       # bad/missing YAML
class MissingPONumberError(LifecycleError): ...       # PO# not in payload
class UnexpectedFirstDocumentError(LifecycleError): ...
class InvalidTransitionError(LifecycleError): ...     # not in valid_transitions
class QuantityChainError(LifecycleError): ...         # waterfall violated
class N1QualifierError(LifecycleError): ...           # wrong N103
class TerminalStateViolationError(LifecycleError): ...
class POContinuityError(LifecycleError): ...          # PO# mismatch

class LifecycleViolationError(LifecycleError):
    """Wraps any violation with structured metadata for pyedi_core."""
    def __init__(self, violation_type: str, detail: str,
                 po_number: str | None, correlation_id: str): ...
```

### 6.3 `loader.py` — YAML Framework Loader

Loads and caches `order_to_cash.yaml` at startup. Re-reads on process restart only.

```python
class LifecycleLoader:
    def __init__(self, framework_base_path: str): ...
    def load(self) -> None: ...
    def get_state(self, state_name: str) -> dict: ...
    def get_valid_transitions(self, state_name: str) -> list[str]: ...
    def get_captures(self, state_name: str) -> list[dict]: ...
    def get_validations(self, state_name: str) -> list[dict]: ...
    def get_primary_key_config(self) -> dict: ...
    def get_quantity_chain_rule(self) -> dict: ...
    def get_n1_qualifier_map(self) -> dict: ...
    def is_terminal_state(self, state_name: str) -> bool: ...
```

### 6.4 `state_store.py` — Postgres Persistence

**Uses `psycopg2`. No ORM. All writes in explicit transactions.**

```python
class StateStore:
    def __init__(self, dsn: str): ...         # dsn = CERTPORTAL_DB_URL

    def get_po(self, po_number: str) -> dict | None: ...
    def upsert_po(self, po_number: str, partner_id: str,
                  new_state: str, is_terminal: bool,
                  qty_fields: dict) -> None: ...
    def append_event(self, event: dict) -> None: ...
    def get_events(self, po_number: str) -> list[dict]: ...
    def record_violation(self, violation: dict) -> None: ...
    def get_violations(self, po_number: str) -> list[dict]: ...
    def get_pos_in_state(self, state: str, partner_id: str) -> list[dict]: ...
    def get_stale_pos(self, older_than_hours: int) -> list[dict]: ...
```

**Implementation rules:**
- `upsert_po()` and `append_event()` must execute in a **single transaction**
- All datetimes as `TIMESTAMPTZ`
- Use connection pooling if certportal.core already provides a pool — check V3 in Section 13

### 6.5 `validators.py` — Business Rules

Each function is independently callable and independently testable.

```python
def validate_transition(current_state: str,
                        target_state: str,
                        valid_transitions: list[str]) -> None:
    """Raises InvalidTransitionError if target not in valid_transitions."""

def validate_quantity_chain(po_record: dict,
                            transaction_set: str,
                            incoming_qty: float) -> None:
    """Enforces: ordered >= changed >= accepted >= shipped >= invoiced.
    Raises QuantityChainError with specific step detail."""

def validate_n1_qualifier(transaction_set: str,
                          observed_qualifier: str,
                          n1_map: dict) -> None:
    """Raises N1QualifierError if N103 does not match expected."""

def validate_not_terminal(po_record: dict) -> None:
    """Raises TerminalStateViolationError if PO already in terminal state."""

def validate_po_number_continuity(po_number: str,
                                  transaction_set: str,
                                  payload: dict,
                                  primary_key_config: dict) -> None:
    """Raises POContinuityError if PO# mismatch detected."""
```

### 6.6 `engine.py` — LifecycleEngine

**`process_event()` execution sequence — strictly ordered:**

| Step | Action | On Failure |
|---|---|---|
| **1. EXTRACT** | Extract PO# from payload using `PO_PATH_MAP` | Raise `MissingPONumberError` |
| **2. LOAD STATE** | Query `StateStore` for current PO state | If none + wrong first doc → `UnexpectedFirstDocumentError` |
| **3. DETERMINE** | Map `(transaction_set, direction)` → target state via `TRANSACTION_STATE_MAP` | Log WARNING, skip lifecycle |
| **4. VALIDATE** | Run all 5 validators in `validators.py` | Raise `LifecycleViolationError` with `violation_type` |
| **5. CAPTURE** | Extract fields from state's `captures` list → `payload_snapshot` JSON | Log warning, continue |
| **6. PERSIST** | `upsert_po()` + `append_event()` in single Postgres transaction | Raise `LifecycleError` |
| **7. S3 WRITE** | On violation only: write to S3 under `retailer/supplier` scope for Monica | Log error, do not re-raise |
| **8. RETURN** | `LifecycleResult` dataclass with `success=True` | — |

```python
@dataclass
class LifecycleResult:
    success:        bool
    po_number:      str
    partner_id:     str
    prior_state:    str | None
    new_state:      str
    is_terminal:    bool
    correlation_id: str
    violations:     list[str]   # empty on success
```

### 6.7 `interface.py` — Public API

> **This is the ONLY file that `pipeline.py` imports from `lifecycle_engine/`.**

```python
def on_document_processed(
    transaction_set: str,       # '850','860','855','865','856','810'
    direction: str,             # 'inbound' or 'outbound'
    payload: dict,              # full parsed JSON from pyedi_core
    source_file: str,
    correlation_id: str,
    partner_id: str = 'lowes'
) -> dict:
    """
    Called by pyedi_core/pipeline.py after successful parse.
    Uses cached singleton LifecycleEngine.
    Returns LifecycleResult as dict.
    Raises LifecycleViolationError on violation.
    """
```

**Hook location in `pyedi_core/pipeline.py`** — add AFTER the existing WRITE stage:

```python
# After successful write to outbound/
try:
    from lifecycle_engine.interface import on_document_processed
    lifecycle_result = on_document_processed(
        transaction_set = transaction_type,
        direction       = direction,
        payload         = result_payload,
        source_file     = str(file_path),
        correlation_id  = correlation_id,
        partner_id      = config.get('partner_id', 'unknown')
    )
    logger.info('lifecycle_event',
                state=lifecycle_result['new_state'],
                po_number=lifecycle_result['po_number'])
except ImportError:
    pass  # lifecycle_engine not installed — standalone pyedi_core use OK (NC-04)
except LifecycleViolationError as e:
    error_handler.handle_error(e, stage='LIFECYCLE', ...)
    raise
```

### 6.8 `s3_writer.py` — S3 Violation Writer

> **Use the existing `S3AgentWorkspace` abstraction from `certportal.core`. Do NOT use raw boto3.**

```python
def write_violation_to_s3(
    violation: dict,
    retailer_slug: str,
    supplier_slug: str,
    workspace: S3AgentWorkspace
) -> None:
    """
    Writes violation record to:
    {retailer_slug}/{supplier_slug}/lifecycle/violations/{correlation_id}.json
    """
```

---

## 7. PO Number Extraction Contract

**Confirmed:** All six transactions normalize PO# to `payload.header.po_number` in PyEDI-Core's output. Path is configurable via `PO_PATH_MAP` in `interface.py`.

| Transaction | Direction | Source Element | JSON Path | Notes |
|---|---|---|---|---|
| 850 | inbound | BEG03 | `payload.header.po_number` | Originates the PO# |
| 860 | inbound | BCH03 | `payload.header.po_number` | Must match 850 BEG03 |
| 855 | outbound | BAK03 | `payload.header.po_number` | Dual path — see Section 8 |
| 865 | outbound | BCA03 | `payload.header.po_number` | Must match 860 BCH03 |
| 856 | outbound | PRF01 | `payload.header.po_number` | Links back to 850 BEG03 |
| 810 | outbound | BIG04 | `payload.header.po_number` | Terminal document |

**N1 Qualifier Map** (enforced by `validate_n1_qualifier()`):

| Transaction | Expected N103 | Meaning |
|---|---|---|
| 850, 860 | `93` | Assigned by organization originating the transaction |
| 855, 856 | `94` | Assigned by org that is ultimate destination |
| 810 | `92` | Assigned by Buyer or Buyer's Agent |

---

## 8. Transaction-to-State Mapping

`TRANSACTION_STATE_MAP` — hardcoded in `engine.py`, derived from `order_to_cash.yaml`:

```python
TRANSACTION_STATE_MAP = {
    ('850', 'inbound'):   'po_originated',
    ('860', 'inbound'):   'po_changed',
    ('855', 'outbound'):  None,   # determined dynamically — see notes below
    ('865', 'outbound'):  None,   # determined dynamically — see notes below
    ('856', 'outbound'):  'shipped',
    ('810', 'outbound'):  'invoiced',
}
```

**855 dual-path logic:**
- No prior PO record exists → `reverse_po_created`
- Prior record exists in `po_originated` → `po_acknowledged`
- Engine checks `StateStore.get_po()` first to determine path

**865 dual-path logic:**
- `BCA02 = AT` → `po_change_accepted`
- `BCA02 = RJ` → `po_change_rejected`
- Engine reads `payload.header.ack_type` (verify exact key against moses.py output)

**Quantity chain enforcement:**
```
ordered (850 PO1) >= changed (860 POC) >= accepted (855 ACK) >= shipped (856 SN1) >= invoiced (810 IT1)
```

---

## 9. `schema_validators/` — Layer 0 Specification

### 9.1 Purpose

Two distinct roles:
1. **Dev/CI gate** — validates all `edi_framework/` YAMLs on every push to `main`
2. **Andy Path 2 runtime gate** — every uploaded YAML goes through `validate_file()` before being stored (production dependency)

### 9.2 Meta-Schema Files — Create in `edi_framework/meta/`

**`transaction_schema.yaml`** — validates all `transactions/*.yaml`
- Required top-level keys: `transaction.id`, `.name`, `.functional_group`, `.direction`, `.version`, `.shared_refs`, `.heading`
- `direction` must be one of: `inbound`, `outbound`

**`mapping_schema.yaml`** — validates all `mappings/*.yaml`
- Required: `mapping.source_transaction`, `.target_transaction`, `.rules`
- Each rule must have: `field`, `source`, `target`, `rule`
- `rule` enum: `exact_copy | transform | preferred | not_echoed | conditional`

**`lifecycle_schema.yaml`** — validates `lifecycle/order_to_cash.yaml`
- Required: `lifecycle.name`, `.version`, `.primary_key`, `.states`
- Each state must have: `trigger.document`, `trigger.direction`, `valid_transitions`

### 9.3 CLI Usage

```bash
# Validate entire edi_framework/ (dev/CI use)
python schema_validators/validate_all.py --framework-path ./edi_framework

# Validate single file (Andy Path 2 runtime gate)
python schema_validators/validate_all.py --file ./uploaded_schema.yaml

# CI mode — exit code 1 on any failure
python schema_validators/validate_all.py --ci

# Library mode (called by Andy agent)
from schema_validators.validate_all import validate_file
result = validate_file(path, schema_type='transaction')  # raises on failure
```

### 9.4 Expected Clean Output

```
✅ transactions/850_stock_po.yaml        PASSED
✅ transactions/855_po_ack.yaml          PASSED
✅ transactions/856_asn.yaml             PASSED
✅ transactions/860_po_change.yaml       PASSED
✅ transactions/865_po_change_ack.yaml   PASSED
✅ transactions/810_invoice.yaml         PASSED
✅ mappings/850_to_810_turnaround.yaml   PASSED
✅ mappings/850_to_855_turnaround.yaml   PASSED
✅ mappings/850_to_856_turnaround.yaml   PASSED
✅ mappings/855_to_810_turnaround.yaml   PASSED
✅ mappings/856_to_810_turnaround.yaml   PASSED
✅ mappings/860_to_865_turnaround.yaml   PASSED
✅ lifecycle/order_to_cash.yaml          PASSED

Summary: 13 passed, 0 failed
EXIT CODE: 0
```

---

## 10. Build Order — Claude Code Desktop

> ⚠️ Follow this order strictly. Verify each step before proceeding.

| Step | Action | Verification |
|---|---|---|
| **1** | **READ** `agents/moses.py` + `DECISIONS.md` in Plan Mode — no code yet | `cat agents/moses.py` |
| **2** | Create `edi_framework/transactions/865_po_change_ack.yaml` | Run after Step 5 |
| **3** | Create `edi_framework/meta/` with 3 pykwalify schema files | `ls edi_framework/meta/` |
| **4** | `pip install pykwalify psycopg2-binary pyyaml` | `python -c 'import pykwalify, psycopg2, yaml; print("OK")'` |
| **5** | Build `schema_validators/` + `validate_all.py` | `python schema_validators/validate_all.py --ci` (exit 0) |
| **6** | Build `lifecycle_engine/exceptions.py` | `python -c 'from lifecycle_engine.exceptions import LifecycleViolationError; print("OK")'` |
| **7** | Build `lifecycle_engine/loader.py` | `python -c 'from lifecycle_engine.loader import LifecycleLoader; l=LifecycleLoader("./edi_framework"); l.load(); print(l.get_valid_transitions("po_originated"))'` |
| **8** | Run migration SQL against Postgres | `psql $CERTPORTAL_DB_URL -f lifecycle_engine/migrations/001_lifecycle_tables.sql` |
| **9** | Build `lifecycle_engine/state_store.py` | `python -c 'import os; from lifecycle_engine.state_store import StateStore; s=StateStore(os.environ["CERTPORTAL_DB_URL"]); print(s.get_po("TEST"))'` |
| **10** | Build `lifecycle_engine/validators.py` | `pytest lifecycle_engine/tests/test_validators.py -v` |
| **11** | Build `lifecycle_engine/s3_writer.py` | `python -c 'from lifecycle_engine.s3_writer import write_violation_to_s3; print("OK")'` |
| **12** | Build `lifecycle_engine/engine.py` | `pytest lifecycle_engine/tests/test_engine.py -v` |
| **13** | Build `lifecycle_engine/interface.py` | `python -c 'from lifecycle_engine.interface import on_document_processed; print("OK")'` |
| **14** | Add lifecycle hook to `pyedi_core/pipeline.py` | Run test `.x12` file; confirm `lifecycle_events` row in Postgres |
| **15** | Add `partner_id: lowes` to `pyedi_core/config/config.yaml` | `grep partner_id pyedi_core/config/config.yaml` |
| **16** | Full integration test: 850 → 855 → 856 → 810 happy path | `SELECT * FROM po_lifecycle; SELECT COUNT(*) FROM lifecycle_events;` |
| **17** | 860 → 865 change path test | `SELECT current_state FROM po_lifecycle WHERE po_number='TEST860';` |
| **18** | Violation tests: over-invoiced, N1 mismatch, invalid transition | `SELECT * FROM lifecycle_violations;` + check `failed/` dir |
| **19** | Coverage check | `pytest --cov=lifecycle_engine --cov-report=term-missing` (≥ 85%) |
| **20** | GitHub Actions CI workflow | `.github/workflows/edi_ci.yml` — runs on push to `main` |

---

## 11. Moses Integration — Verify Before Coding

> ⚠️ **Read `agents/moses.py` FIRST in Claude Code Desktop (Step 1). Moses is the primary caller of `lifecycle_engine`. The integration approach depends entirely on what Moses currently does.**

**Expected pattern after integration:**

```python
# agents/moses.py
from pyedi_core import Pipeline
# lifecycle_engine fires automatically via pipeline.py hook — Moses does not call it directly

result = Pipeline(config_path='./pyedi_core/config/config.yaml').run(
    file=edi_file_path,
    return_payload=True
)
# Moses continues to write ValidationResult to S3 as it currently does
# lifecycle_engine separately writes violations to S3 for Monica (INV-02)
```

**Integration scenarios:**

| Scenario | Action |
|---|---|
| Moses does NOT yet call `pyedi_core` | Add `Pipeline` call to Moses. Lifecycle hook fires automatically from `pipeline.py`. |
| Moses HAS its own EDI validation logic | Audit for overlap. `lifecycle_engine` owns state transitions. Moses keeps format validation. |
| Moses writes `ValidationResult` to S3 | `s3_writer.py` writes to a **separate S3 path**. Do not merge outputs. |
| Moses has tests in `testing/` | Add lifecycle integration test to `testing/certportal_jules_test.py`. |

---

## 12. Definition of Done

### `lifecycle_engine/` is done when:
- [ ] `865_po_change_ack.yaml` exists and passes schema validation
- [ ] Postgres migration runs clean on first execution
- [ ] Happy path: 850 → 855 → 856 → 810 creates correct rows in all 3 tables
- [ ] Change path: 860 → 865 (AT and RJ) works correctly
- [ ] Reverse PO path: 855 with no prior 850 → `reverse_po_created` state
- [ ] All 5 violation types raise correct exceptions + write to `lifecycle_violations` + S3
- [ ] Quantity chain catches over-invoiced scenario
- [ ] N1 qualifier mismatch caught and recorded
- [ ] Process restart test: state survives engine restart (Postgres persists)
- [ ] `pipeline.py` hook integrated with `ImportError` guard — `pyedi_core` works standalone
- [ ] `strict_mode=false` logs violations without failing pipeline
- [ ] `pytest --cov >= 85%` on all `lifecycle_engine/` modules

### `schema_validators/` is done when:
- [ ] 3 meta-schema YAML files exist in `edi_framework/meta/`
- [ ] All 14 `edi_framework/` files pass validation (13 existing + 865)
- [ ] `validate_all.py --ci` exits 0 on clean repo, exits 1 on any failure
- [ ] `validate_file()` library function works when called by Andy agent (Path 2)
- [ ] GitHub Actions workflow runs validators on every push to `main`

### Sprint 1 is done when:
- [ ] All above checkboxes pass
- [ ] Full integration test: real `.x12` file → `pyedi_core` pipeline → lifecycle engine → Postgres rows → S3 violation write
- [ ] `DECISIONS.md` updated with Sprint 1 decisions

---

## 13. Items to Verify in Claude Code Desktop

> Complete these in Step 1 (Plan Mode) before writing any code.

| # | Item | Where to Look | What You Need |
|---|---|---|---|
| **V1** | Does Moses already call `pyedi_core`? What is its current validation logic? | `agents/moses.py` | Determines if Moses needs updating or just the hook added |
| **V2** | Any Sprint 1 decisions in `DECISIONS.md` that contradict this TRD? | `DECISIONS.md` | Read all; update after Sprint 1 |
| **V3** | What shared utilities exist in `certportal.core`? Postgres connection pool? | `certportal/` directory | `StateStore` should reuse existing Postgres patterns |
| **V4** | Where does Andy store validated YAMLs after Path 2? | `agents/andy.py` | `validate_file()` must integrate with Andy's storage call |
| **V5** | What are the `S3AgentWorkspace` method signatures for S3 writes? | `certportal/core/` | `s3_writer.py` must use existing abstraction — not raw boto3 |
| **V6** | What does `gate_enforcer.py` look like? | `certportal/` or `agents/` | Lifecycle state machine should align with existing gate pattern (INV-03) |
| **V7** | Is `psycopg2` already in `requirements.txt`? Is `pykwalify`? | `requirements.txt` | Avoid duplicate dependency entries |

---

*certPortal EDI Integration Technical Requirements v2.0 — Approved for Claude Code Desktop — 2026-03-06*
