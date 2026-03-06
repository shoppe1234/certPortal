"""portals/meredith.py — Retailer Portal (port 8001).

Aesthetic: Clean enterprise SaaS. Light theme. Confident typography. Notion meets Linear.
Colors: #f8f9fc base, #1a1f36 text, #4f6ef7 primary, #e8ecf5 borders, #22c55e success.

INV-07: Never imports from agents/. DB reads only via certportal.core.
Agents triggered by writing workspace signals, never by calling agent functions.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from certportal.core.database import get_connection, get_pool
from certportal.core.gate_enforcer import GateOrderViolation, get_gate_status, transition_gate

BASE_DIR = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


app = FastAPI(
    title="certPortal Retailer (Meredith)",
    description="Retailer portal — spec setup, YAML wizard, supplier certification board.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok", "portal": "meredith", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Home / Dashboard
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, conn=Depends(get_connection)):
    # Retailer context: in production this would come from JWT. Sprint 1: first spec row.
    spec_row = await conn.fetchrow(
        "SELECT retailer_slug, spec_version, thesis_s3_key, created_at FROM retailer_specs LIMIT 1"
    )
    supplier_count = await conn.fetchval(
        "SELECT COUNT(*) FROM hitl_gate_status"
    ) or 0
    certified_count = await conn.fetchval(
        "SELECT COUNT(*) FROM hitl_gate_status WHERE gate_3 = 'CERTIFIED'"
    ) or 0

    return templates.TemplateResponse(
        "meredith_home.html",
        {
            "request": request,
            "portal_name": "meredith",
            "spec": dict(spec_row) if spec_row else None,
            "supplier_count": supplier_count,
            "certified_count": certified_count,
        },
    )


# ---------------------------------------------------------------------------
# Spec Setup
# ---------------------------------------------------------------------------


@app.get("/spec-setup", response_class=HTMLResponse)
async def spec_setup(request: Request, conn=Depends(get_connection)):
    specs = await conn.fetch(
        "SELECT retailer_slug, spec_version, thesis_s3_key, created_at FROM retailer_specs ORDER BY created_at DESC"
    )
    return templates.TemplateResponse(
        "meredith_spec_setup.html",
        {
            "request": request,
            "portal_name": "meredith",
            "specs": [dict(s) for s in specs],
        },
    )


@app.post("/spec-setup/upload")
async def trigger_spec_upload(request: Request):
    """Trigger Dwight agent via S3 workspace signal. Never calls agents/ directly (INV-07)."""
    body = await request.json()
    pdf_s3_key = body.get("pdf_s3_key")
    retailer_slug = body.get("retailer_slug")

    if not pdf_s3_key or not retailer_slug:
        raise HTTPException(status_code=400, detail="pdf_s3_key and retailer_slug required")

    # TODO: call agent via workspace signal
    # workspace = S3AgentWorkspace(retailer_slug)
    # workspace.upload("signals/dwight_trigger.json", json.dumps({
    #     "agent": "dwight", "pdf_s3_key": pdf_s3_key, "triggered_at": utcnow()
    # }))
    return JSONResponse(
        {
            "status": "queued",
            "message": "Dwight spec analysis queued via workspace signal.",
            "retailer_slug": retailer_slug,
            "pdf_s3_key": pdf_s3_key,
        }
    )


# ---------------------------------------------------------------------------
# YAML Wizard (3-path)
# ---------------------------------------------------------------------------


@app.get("/yaml-wizard", response_class=HTMLResponse)
async def yaml_wizard(request: Request, conn=Depends(get_connection)):
    specs = await conn.fetch(
        "SELECT retailer_slug, spec_version FROM retailer_specs ORDER BY created_at DESC"
    )
    return templates.TemplateResponse(
        "meredith_yaml_wizard.html",
        {
            "request": request,
            "portal_name": "meredith",
            "specs": [dict(s) for s in specs],
            "supported_bundles": {
                "general_merchandise": ["850", "855", "856", "810", "997"],
                "transportation": ["204", "990", "210", "214"],
            },
        },
    )


@app.post("/yaml-wizard/path1")
async def yaml_wizard_path1(request: Request):
    """Path 1: Trigger Andy PDF extraction via workspace signal."""
    body = await request.json()
    # TODO: call agent via workspace signal
    return JSONResponse({"status": "queued", "path": 1, "payload": body})


@app.post("/yaml-wizard/path2")
async def yaml_wizard_path2(request: Request):
    """Path 2: Trigger Andy YAML upload validation via workspace signal."""
    body = await request.json()
    # TODO: call agent via workspace signal
    return JSONResponse({"status": "queued", "path": 2, "payload": body})


@app.post("/yaml-wizard/path3")
async def yaml_wizard_path3(request: Request):
    """Path 3: Trigger Andy wizard form serialization via workspace signal."""
    body = await request.json()
    # TODO: call agent via workspace signal
    return JSONResponse({"status": "queued", "path": 3, "payload": body})


# ---------------------------------------------------------------------------
# Supplier Status Board
# ---------------------------------------------------------------------------


@app.get("/supplier-status", response_class=HTMLResponse)
async def supplier_status(request: Request, conn=Depends(get_connection)):
    rows = await conn.fetch(
        """
        SELECT
            h.supplier_slug,
            h.gate_1, h.gate_2, h.gate_3,
            h.last_updated,
            (SELECT COUNT(*) FROM test_occurrences t
             WHERE t.supplier_slug = h.supplier_slug AND t.status = 'PASS') AS pass_count,
            (SELECT COUNT(*) FROM test_occurrences t
             WHERE t.supplier_slug = h.supplier_slug AND t.status = 'FAIL') AS fail_count
        FROM hitl_gate_status h
        ORDER BY h.last_updated DESC
        """
    )
    return templates.TemplateResponse(
        "meredith_supplier_status.html",
        {
            "request": request,
            "portal_name": "meredith",
            "suppliers": [dict(r) for r in rows],
        },
    )


# ---------------------------------------------------------------------------
# HTMX partials
# ---------------------------------------------------------------------------


@app.get("/htmx/supplier-status/{supplier_id}", response_class=HTMLResponse)
async def supplier_status_partial(
    request: Request, supplier_id: str, conn=Depends(get_connection)
):
    row = await conn.fetchrow(
        """
        SELECT supplier_slug, gate_1, gate_2, gate_3, last_updated
        FROM hitl_gate_status
        WHERE supplier_slug = $1
        """,
        supplier_id,
    )
    if not row:
        return HTMLResponse(f"<tr><td colspan='5'>Supplier {supplier_id} not found</td></tr>")
    gate_status = dict(row)
    return templates.TemplateResponse(
        "_supplier_status_row.html",
        {"request": request, "supplier": gate_status},
    )


@app.get("/htmx/spec-steps/{retailer_slug}", response_class=HTMLResponse)
async def spec_steps_partial(
    request: Request, retailer_slug: str, conn=Depends(get_connection)
):
    spec = await conn.fetchrow(
        "SELECT * FROM retailer_specs WHERE retailer_slug = $1 ORDER BY created_at DESC LIMIT 1",
        retailer_slug,
    )
    return templates.TemplateResponse(
        "_spec_steps.html",
        {
            "request": request,
            "spec": dict(spec) if spec else None,
            "retailer_slug": retailer_slug,
        },
    )


# ---------------------------------------------------------------------------
# Gate management (retailer-facing)
# ---------------------------------------------------------------------------


@app.post("/suppliers/{supplier_id}/approve-gate/{gate}")
async def retailer_approve_gate(
    supplier_id: str, gate: int, conn=Depends(get_connection)
):
    """Retailer approves a supplier gate (calls gate_enforcer)."""
    if gate not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="gate must be 1, 2, or 3")
    try:
        await transition_gate(
            supplier_id=supplier_id,
            gate=gate,
            new_state="COMPLETE",
            updated_by="meredith_retailer",
            conn=conn,
        )
    except GateOrderViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse({"status": "ok", "supplier_id": supplier_id, "gate": gate})
