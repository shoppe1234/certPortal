"""portals/pam.py — Admin Portal (port 8000).

Aesthetic: Industrial command center. Dark theme. Monospace data. Bloomberg-meets-SaaS.
Colors: #0a0e1a base, #00ff88 active, #ffaa00 warning, #ff4455 error, #1e2d40 card surfaces.

INV-07: Never imports from agents/. DB reads only via certportal.core.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from certportal.core.database import get_connection, get_pool
from certportal.core.gate_enforcer import (
    GateOrderViolation,
    get_gate_status,
    transition_gate,
)
from certportal.core.models import HITLGateStatus

BASE_DIR = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()  # Warm up the connection pool
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


app = FastAPI(
    title="certPortal Admin (Pam)",
    description="Admin command centre — retailers, suppliers, HITL, Monica memory.",
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
    return {"status": "ok", "portal": "pam", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, conn=Depends(get_connection)):
    # Retailer × supplier certification matrix
    retailers = await conn.fetch(
        "SELECT DISTINCT retailer_slug FROM retailer_specs ORDER BY retailer_slug"
    )
    suppliers = await conn.fetch(
        "SELECT DISTINCT supplier_slug FROM hitl_gate_status ORDER BY supplier_slug"
    )
    hitl_count = await conn.fetchval(
        "SELECT COUNT(*) FROM hitl_queue WHERE status = 'PENDING_APPROVAL'"
    ) or 0
    memory_count = await conn.fetchval("SELECT COUNT(*) FROM monica_memory") or 0

    return templates.TemplateResponse(
        "pam_dashboard.html",
        {
            "request": request,
            "portal_name": "pam",
            "retailers": [r["retailer_slug"] for r in retailers],
            "suppliers": [s["supplier_slug"] for s in suppliers],
            "hitl_queue_count": hitl_count,
            "memory_entry_count": memory_count,
            "now": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )


# ---------------------------------------------------------------------------
# Retailers
# ---------------------------------------------------------------------------


@app.get("/retailers", response_class=HTMLResponse)
async def retailers(request: Request, conn=Depends(get_connection)):
    rows = await conn.fetch(
        """
        SELECT retailer_slug, spec_version, thesis_s3_key, created_at
        FROM retailer_specs
        ORDER BY created_at DESC
        """
    )
    return templates.TemplateResponse(
        "pam_retailers.html",
        {
            "request": request,
            "portal_name": "pam",
            "retailers": [dict(r) for r in rows],
        },
    )


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


@app.get("/suppliers", response_class=HTMLResponse)
async def suppliers(request: Request, conn=Depends(get_connection)):
    rows = await conn.fetch(
        """
        SELECT supplier_slug, gate_1, gate_2, gate_3, last_updated, last_updated_by
        FROM hitl_gate_status
        ORDER BY last_updated DESC
        """
    )
    return templates.TemplateResponse(
        "pam_suppliers.html",
        {
            "request": request,
            "portal_name": "pam",
            "suppliers": [dict(r) for r in rows],
        },
    )


# ---------------------------------------------------------------------------
# HITL Queue
# ---------------------------------------------------------------------------


@app.get("/hitl-queue", response_class=HTMLResponse)
async def hitl_queue(request: Request, conn=Depends(get_connection)):
    rows = await conn.fetch(
        """
        SELECT queue_id, retailer_slug, supplier_slug, agent, summary,
               channel, status, queued_at
        FROM hitl_queue
        WHERE status = 'PENDING_APPROVAL'
        ORDER BY queued_at ASC
        """
    )
    return templates.TemplateResponse(
        "pam_hitl_queue.html",
        {
            "request": request,
            "portal_name": "pam",
            "queue_items": [dict(r) for r in rows],
        },
    )


@app.post("/hitl-queue/{queue_id}/approve")
async def approve_hitl_item(
    queue_id: str, request: Request, conn=Depends(get_connection)
):
    """Approve a HITL queue item. Portals never call agents — approval updates DB only."""
    row = await conn.fetchrow(
        "SELECT * FROM hitl_queue WHERE queue_id = $1", queue_id
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Queue item {queue_id} not found")

    await conn.execute(
        """
        UPDATE hitl_queue
        SET status = 'APPROVED', resolved_at = now(), resolved_by = 'pam_admin'
        WHERE queue_id = $1
        """,
        queue_id,
    )
    # TODO: call agent via workspace signal — write approval signal to S3
    return JSONResponse({"status": "approved", "queue_id": queue_id})


@app.post("/hitl-queue/{queue_id}/reject")
async def reject_hitl_item(
    queue_id: str, request: Request, conn=Depends(get_connection)
):
    """Reject a HITL queue item."""
    await conn.execute(
        """
        UPDATE hitl_queue
        SET status = 'REJECTED', resolved_at = now(), resolved_by = 'pam_admin'
        WHERE queue_id = $1
        """,
        queue_id,
    )
    return JSONResponse({"status": "rejected", "queue_id": queue_id})


# ---------------------------------------------------------------------------
# Monica Memory Log Viewer
# ---------------------------------------------------------------------------


@app.get("/monica-memory", response_class=HTMLResponse)
async def monica_memory(
    request: Request,
    page: int = 1,
    limit: int = 50,
    conn=Depends(get_connection),
):
    offset = (page - 1) * limit
    rows = await conn.fetch(
        """
        SELECT timestamp, agent, direction, message, retailer_slug, supplier_slug
        FROM monica_memory
        ORDER BY timestamp DESC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    total = await conn.fetchval("SELECT COUNT(*) FROM monica_memory") or 0

    return templates.TemplateResponse(
        "pam_monica_memory.html",
        {
            "request": request,
            "portal_name": "pam",
            "entries": [dict(r) for r in rows],
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        },
    )


# ---------------------------------------------------------------------------
# Gate management
# ---------------------------------------------------------------------------


@app.post("/suppliers/{supplier_id}/gate/{gate}/complete")
async def complete_gate(
    supplier_id: str,
    gate: int,
    conn=Depends(get_connection),
):
    """Transition a supplier gate to COMPLETE. Enforces ordering via gate_enforcer."""
    if gate not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="gate must be 1, 2, or 3")
    try:
        await transition_gate(
            supplier_id=supplier_id,
            gate=gate,
            new_state="COMPLETE",
            updated_by="pam_admin",
            conn=conn,
        )
    except GateOrderViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse(
        {"status": "ok", "supplier_id": supplier_id, "gate": gate, "new_state": "COMPLETE"}
    )


@app.post("/suppliers/{supplier_id}/gate/3/certify")
async def certify_supplier(supplier_id: str, conn=Depends(get_connection)):
    """Issue certification (Gate 3 → CERTIFIED)."""
    try:
        await transition_gate(
            supplier_id=supplier_id,
            gate=3,
            new_state="CERTIFIED",
            updated_by="pam_admin",
            conn=conn,
        )
    except GateOrderViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse({"status": "certified", "supplier_id": supplier_id})


# ---------------------------------------------------------------------------
# HTMX partials
# ---------------------------------------------------------------------------


@app.get("/htmx/supplier-gate/{supplier_id}", response_class=HTMLResponse)
async def supplier_gate_partial(
    request: Request, supplier_id: str, conn=Depends(get_connection)
):
    gate_status = await get_gate_status(supplier_id, conn)
    return templates.TemplateResponse(
        "_gate_status_row.html",
        {"request": request, "supplier_id": supplier_id, "gate_status": gate_status},
    )


@app.get("/htmx/hitl-count", response_class=HTMLResponse)
async def hitl_count_partial(request: Request, conn=Depends(get_connection)):
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM hitl_queue WHERE status = 'PENDING_APPROVAL'"
    ) or 0
    return HTMLResponse(f'<span class="hitl-badge" data-count="{count}">{count}</span>')
