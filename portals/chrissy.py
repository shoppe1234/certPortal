"""portals/chrissy.py — Supplier Portal (port 8002).

Aesthetic: Friendly, task-completion focused. Warm light theme. Generous whitespace.
Colors: #fffbf7 base, #2d2926 text, #f59e0b primary, #d1fae5 success, #fef3c7 warning.

INV-07: Never imports from agents/. DB reads only via certportal.core.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from certportal.core.database import get_connection, get_pool
from certportal.core.gate_enforcer import get_gate_status

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
    title="certPortal Supplier (Chrissy)",
    description="Supplier portal — scenarios, errors, Ryan's patches, certification badge.",
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
    return {"status": "ok", "portal": "chrissy", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, conn=Depends(get_connection)):
    # Sprint 1: no auth — show first supplier found
    row = await conn.fetchrow(
        "SELECT supplier_slug, gate_1, gate_2, gate_3, last_updated FROM hitl_gate_status LIMIT 1"
    )
    supplier = dict(row) if row else {"supplier_slug": "demo", "gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"}

    total_tests = await conn.fetchval(
        "SELECT COUNT(*) FROM test_occurrences WHERE supplier_slug = $1",
        supplier.get("supplier_slug", "demo"),
    ) or 0
    passed_tests = await conn.fetchval(
        "SELECT COUNT(*) FROM test_occurrences WHERE supplier_slug = $1 AND status = 'PASS'",
        supplier.get("supplier_slug", "demo"),
    ) or 0

    return templates.TemplateResponse(
        "chrissy_home.html",
        {
            "request": request,
            "portal_name": "chrissy",
            "supplier": supplier,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "progress_pct": round((passed_tests / total_tests * 100) if total_tests > 0 else 0),
        },
    )


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@app.get("/scenarios", response_class=HTMLResponse)
async def scenarios(request: Request, conn=Depends(get_connection)):
    # Sprint 1: no auth — show all test occurrences
    rows = await conn.fetch(
        """
        SELECT supplier_slug, retailer_slug, transaction_type, channel,
               status, validated_at
        FROM test_occurrences
        ORDER BY validated_at DESC
        LIMIT 100
        """
    )
    return templates.TemplateResponse(
        "chrissy_scenarios.html",
        {
            "request": request,
            "portal_name": "chrissy",
            "scenarios": [dict(r) for r in rows],
        },
    )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


@app.get("/errors", response_class=HTMLResponse)
async def errors(
    request: Request,
    supplier_slug: str = "demo",
    conn=Depends(get_connection),
):
    """Show validation errors with Ryan's patch suggestions."""
    # Fetch recent failed test occurrences
    rows = await conn.fetch(
        """
        SELECT result_json, validated_at, transaction_type
        FROM test_occurrences
        WHERE supplier_slug = $1 AND status IN ('FAIL', 'PARTIAL')
        ORDER BY validated_at DESC
        LIMIT 20
        """,
        supplier_slug,
    )

    error_groups: list[dict] = []
    for row in rows:
        import json
        result = json.loads(row["result_json"])
        patches = await conn.fetch(
            "SELECT * FROM patch_suggestions WHERE supplier_slug = $1 ORDER BY created_at DESC LIMIT 10",
            supplier_slug,
        )
        error_groups.append(
            {
                "transaction_type": row["transaction_type"],
                "validated_at": row["validated_at"],
                "errors": result.get("errors", []),
                "patches": [dict(p) for p in patches],
            }
        )

    return templates.TemplateResponse(
        "chrissy_errors.html",
        {
            "request": request,
            "portal_name": "chrissy",
            "supplier_slug": supplier_slug,
            "error_groups": error_groups,
        },
    )


# ---------------------------------------------------------------------------
# Patches (Ryan's suggestions)
# ---------------------------------------------------------------------------


@app.get("/patches", response_class=HTMLResponse)
async def patches(
    request: Request,
    supplier_slug: str = "demo",
    conn=Depends(get_connection),
):
    rows = await conn.fetch(
        """
        SELECT id, error_code, segment, element, summary,
               patch_s3_key, applied, created_at
        FROM patch_suggestions
        WHERE supplier_slug = $1
        ORDER BY created_at DESC
        """,
        supplier_slug,
    )
    return templates.TemplateResponse(
        "chrissy_patches.html",
        {
            "request": request,
            "portal_name": "chrissy",
            "supplier_slug": supplier_slug,
            "patches": [dict(r) for r in rows],
        },
    )


@app.post("/patches/{patch_id}/mark-applied")
async def mark_patch_applied(patch_id: int, conn=Depends(get_connection)):
    """Supplier marks a patch as applied. Does not call any agent."""
    result = await conn.execute(
        "UPDATE patch_suggestions SET applied = TRUE WHERE id = $1",
        patch_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")
    return JSONResponse({"status": "applied", "patch_id": patch_id})


# ---------------------------------------------------------------------------
# Certification badge
# ---------------------------------------------------------------------------


@app.get("/certification", response_class=HTMLResponse)
async def certification(
    request: Request,
    supplier_slug: str = "demo",
    conn=Depends(get_connection),
):
    gate_status = await get_gate_status(supplier_slug, conn)
    certified = gate_status.get("gate_3") == "CERTIFIED"
    return templates.TemplateResponse(
        "chrissy_home.html",
        {
            "request": request,
            "portal_name": "chrissy",
            "supplier": {"supplier_slug": supplier_slug, **gate_status},
            "certified": certified,
            "total_tests": 0,
            "passed_tests": 0,
            "progress_pct": 100 if certified else 0,
        },
    )


# ---------------------------------------------------------------------------
# HTMX partials
# ---------------------------------------------------------------------------


@app.get("/htmx/scenario-status/{scenario_id}", response_class=HTMLResponse)
async def scenario_status_partial(
    request: Request,
    scenario_id: str,
    supplier_slug: str = "demo",
    conn=Depends(get_connection),
):
    row = await conn.fetchrow(
        """
        SELECT status, validated_at, transaction_type
        FROM test_occurrences
        WHERE supplier_slug = $1
        ORDER BY validated_at DESC LIMIT 1
        """,
        supplier_slug,
    )
    return templates.TemplateResponse(
        "_scenario_status.html",
        {
            "request": request,
            "scenario_id": scenario_id,
            "result": dict(row) if row else None,
        },
    )


@app.get("/htmx/patch-list/{supplier_slug}", response_class=HTMLResponse)
async def patch_list_partial(
    request: Request, supplier_slug: str, conn=Depends(get_connection)
):
    rows = await conn.fetch(
        """
        SELECT id, error_code, segment, summary, applied, created_at
        FROM patch_suggestions
        WHERE supplier_slug = $1
        ORDER BY created_at DESC LIMIT 20
        """,
        supplier_slug,
    )
    return templates.TemplateResponse(
        "_patch_list.html",
        {"request": request, "patches": [dict(r) for r in rows]},
    )
