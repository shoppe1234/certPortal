# certPortal

Cloud-native, multi-tenant EDI certification platform. Sprint 1.

## Architecture

**9-agent deterministic Python pipeline** (agents named after *The Office* characters):

| Agent | Role | LLM |
|---|---|---|
| Monica | Orchestrator + HITL Keeper | GPT-4o-mini (HITL summaries) |
| Dwight | Spec Analyst (PDF → THESIS.md) | GPT-4o |
| Andy | YAML Mapper (3-path ingestion) | GPT-4o-mini (Path 1 only) |
| Moses | Payload Analyst (EDI validation) | None — fully deterministic |
| Kelly | Multi-Channel Communications | GPT-4o-mini |
| Ryan | Patch Generator | GPT-4o-mini |

**3 portals** (FastAPI + Jinja2 + HTMX):

| Portal | Audience | Port | Theme |
|---|---|---|---|
| Pam | certPortal Admins | 8000 | Dark command center |
| Meredith | Retailer EDI Managers | 8001 | Clean enterprise SaaS |
| Chrissy | Supplier EDI Coordinators | 8002 | Warm, task-focused |

## Setup

```bash
# 1. Create .env from template
cp .env.template .env
# Fill in OVH_S3_KEY, OVH_S3_SECRET, CERTPORTAL_DB_URL, OPENAI_API_KEY, etc.

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install package (makes certportal.core importable)
pip install -e .

# 4. Run portals (each in its own terminal or via Procfile)
uvicorn portals.pam:app --port 8000
uvicorn portals.meredith:app --port 8001
uvicorn portals.chrissy:app --port 8002
```

## Running agents (CLI)

```bash
# Dwight — process a retailer PDF spec
python -m agents.dwight --retailer elior --pdf-key tpg/elior-guide.pdf

# Moses — validate a supplier's EDI file
python -m agents.moses --retailer elior --supplier acme --edi-key raw/850.edi --tx 850 --channel gs1

# Monica — orchestrate one pipeline run
python -m agents.monica --retailer elior --supplier acme

# Kelly — generate a communication
python -m agents.kelly --retailer elior --supplier acme --channel email --thread-id t001 --trigger validation_fail

# Ryan — generate patches (reads ValidationResult from S3)
python -m agents.ryan --retailer elior --supplier acme --result-key results/850_20260305T120000.json
```

## Running tests

```bash
python testing/certportal_jules_test.py
```

## Architectural invariants

See `DECISIONS.md` for all Sprint 1 decisions.

Key invariants (enforced in code):
- **INV-01**: Agents never import each other (S3 workspace is the only inter-agent channel)
- **INV-02**: All agent ambiguity routes through Monica via PAM-STATUS.json flags
- **INV-03**: Gate ordering enforced by `gate_enforcer.py` (raises `GateOrderViolation`)
- **INV-04**: No LangChain — explicit OpenAI client calls only
- **INV-05**: `MONICA-MEMORY.md` is append-only (never opened with `"w"`)
- **INV-06**: `S3AgentWorkspace` scopes all paths to `{retailer_slug}/{supplier_slug}/`
- **INV-07**: Portals never import from `agents/`
