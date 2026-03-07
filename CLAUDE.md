# certPortal — Claude Code Instructions

## BEFORE WRITING ANY CODE
Read these files first — in this order:
1. agents/moses.py          ← understand current EDI validation logic
2. DECISIONS.md             ← all Sprint 1 architectural decisions
3. TECHNICAL_REQUIREMENTS.md ← full TRD v2.0

## Architecture Invariants — NEVER VIOLATE
- INV-01: Agents never import each other. S3 is the only inter-agent channel.
- INV-02: All violations route through Monica via PAM-STATUS.json on S3.
- INV-03: Gate ordering enforced by gate_enforcer.py.
- INV-04: No LangChain. Explicit OpenAI calls only.
- INV-05: MONICA-MEMORY.md is append-only. Never open with "w".
- INV-06: S3 paths scoped to {retailer_slug}/{supplier_slug}/.
- INV-07: Portals never import from agents/.

## New Constraints (Sprint 1)
- NC-01: edi_framework/ is READ-ONLY at runtime. Never write to it.
- NC-02: No hardcoded transaction logic in .py files. YAML is the brain.
- NC-03: PO number is the primary key in every table, log, and S3 path.
- NC-04: pyedi_core/ must work standalone without lifecycle_engine/ installed.
- NC-05: strict_mode=false dev, strict_mode=true production.

## Build Order — Follow Exactly (TRD Section 10)
Step 1:  Read moses.py + DECISIONS.md (Plan Mode)
Step 2:  Create edi_framework/transactions/865_po_change_ack.yaml
Step 3:  Create edi_framework/meta/ pykwalify schemas (3 files)
Step 4:  Build schema_validators/ + validate_all.py
Step 5:  Build lifecycle_engine/exceptions.py
Step 6:  Build lifecycle_engine/loader.py
Step 7:  Run Postgres migration (migrations/001_lifecycle_tables.sql)
Step 8:  Build lifecycle_engine/state_store.py (psycopg2, no ORM)
Step 9:  Build lifecycle_engine/validators.py
Step 10: Build lifecycle_engine/s3_writer.py
Step 11: Build lifecycle_engine/engine.py
Step 12: Build lifecycle_engine/interface.py
Step 13: Hook interface.py into pyedi_core/pipeline.py (with ImportError guard)
Step 14: Add partner_id field read to pipeline.py config
Step 15: Full integration test

## Full Technical Specification
Read TECHNICAL_REQUIREMENTS.md for complete specs on lifecycle_engine/,
schema_validators/, Postgres schema, build order, and Moses integration.

## Database
- CERTPORTAL_DB_URL = Postgres
- Use psycopg2. No SQLAlchemy. No ORM.
- All writes in explicit transactions with BEGIN/COMMIT/ROLLBACK.
- lifecycle_events table: INSERT ONLY. Never UPDATE or DELETE.

## S3 Workspace
- Use existing S3AgentWorkspace abstraction from certportal.core
- Do NOT use raw boto3 directly
- All paths scoped to {retailer_slug}/{supplier_slug}/

## Testing Targets
- pytest --cov >= 85% on all lifecycle_engine/ modules
- validate_all.py --ci must exit 0 before Sprint 1 is done

## Key File Locations
- edi_framework/lifecycle/order_to_cash.yaml  ← state machine definition
- edi_framework/lowes_master.yaml             ← transaction registry
- pyedi_core/config/config.yaml              ← parser runtime config
- lifecycle_engine/config.yaml               ← engine config (create this)
