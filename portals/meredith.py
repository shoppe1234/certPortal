"""portals/meredith.py — Retailer Portal (port 8001).

Aesthetic: Clean enterprise SaaS. Light theme. Confident typography. Notion meets Linear.
Colors: #f8f9fc base, #1a1f36 text, #4f6ef7 primary, #e8ecf5 borders, #22c55e success.

INV-07: Never imports from agents/. DB reads only via certportal.core.
Agents triggered by writing workspace signals, never by calling agent functions.
Auth (ADR-014): JWT cookie or Bearer header. Role required: 'admin' or 'retailer'.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from certportal.core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    build_token_claims,
    create_access_token,
    get_current_user,
    require_role,
)
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
# App + protected router
# ---------------------------------------------------------------------------

app = FastAPI(
    title="certPortal Retailer (Meredith)",
    description="Retailer portal — spec setup, YAML wizard, supplier certification board.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# All routes in this router require retailer or admin role
router = APIRouter(dependencies=[Depends(require_role("admin", "retailer"))])


# ---------------------------------------------------------------------------
# 401 / 403 exception handlers — redirect browsers to /login
# ---------------------------------------------------------------------------

@app.exception_handler(status.HTTP_401_UNAUTHORIZED)
async def authn_redirect(request: Request, exc: HTTPException):
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(status_code=401, content={"detail": exc.detail})


@app.exception_handler(status.HTTP_403_FORBIDDEN)
async def authz_redirect(request: Request, exc: HTTPException):
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse(url="/login?error=forbidden", status_code=302)
    return JSONResponse(status_code=403, content={"detail": exc.detail})


# ---------------------------------------------------------------------------
# Open endpoints (no auth required)
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "portal": "meredith", "version": "1.0.0"}


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    error_html = f'<p style="color:#e53e3e;margin-bottom:1rem">{error}</p>' if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>certPortal Retailer — Login</title>
  <style>
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8f9fc;color:#1a1f36;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
    .card{{background:#fff;padding:2.5rem;border-radius:8px;width:360px;box-shadow:0 2px 12px rgba(0,0,0,.08);border:1px solid #e8ecf5}}
    h1{{color:#4f6ef7;font-size:1.4rem;margin:0 0 1.5rem}}
    label{{display:block;font-size:.8rem;color:#6b7280;margin-bottom:.3rem;font-weight:500}}
    input{{width:100%;box-sizing:border-box;padding:.6rem .75rem;background:#fff;border:1px solid #e8ecf5;border-radius:6px;color:#1a1f36;font-size:.9rem}}
    input:focus{{outline:none;border-color:#4f6ef7;box-shadow:0 0 0 3px rgba(79,110,247,.1)}}
    button{{width:100%;margin-top:1.2rem;padding:.75rem;background:#4f6ef7;color:#fff;border:none;border-radius:6px;font-weight:600;font-size:1rem;cursor:pointer}}
    button:hover{{background:#3b5bd9}}
    .sep{{margin-bottom:1rem}}
  </style>
</head>
<body>
<div class="card">
  <h1>certPortal · Retailer</h1>
  {error_html}
  <form method="post" action="/token">
    <div class="sep"><label>Username</label><input name="username" autocomplete="username" required></div>
    <div class="sep"><label>Password</label><input name="password" type="password" autocomplete="current-password" required></div>
    <button type="submit">Sign in</button>
  </form>
</div>
</body>
</html>""")


@app.post("/token")
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """Validate credentials, set httponly JWT cookie, redirect to dashboard."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        return RedirectResponse(url="/login?error=Invalid+username+or+password", status_code=302)
    if user.get("role") not in ("admin", "retailer"):
        return RedirectResponse(url="/login?error=Retailer+or+admin+role+required", status_code=302)

    token = create_access_token(build_token_claims(user))
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@app.post("/token/api")
async def api_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Return JWT as JSON (for programmatic / test use)."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(build_token_claims(user))
    return {"access_token": token, "token_type": "bearer"}


@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ---------------------------------------------------------------------------
# Protected: Home / Dashboard
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    retailer_slug = user.get("retailer_slug")

    # Admin users see all specs; retailer users see their own
    if retailer_slug:
        spec_row = await conn.fetchrow(
            "SELECT retailer_slug, spec_version, thesis_s3_key, created_at FROM retailer_specs WHERE retailer_slug = $1 ORDER BY created_at DESC LIMIT 1",
            retailer_slug,
        )
    else:
        spec_row = await conn.fetchrow(
            "SELECT retailer_slug, spec_version, thesis_s3_key, created_at FROM retailer_specs ORDER BY created_at DESC LIMIT 1"
        )

    supplier_count = await conn.fetchval("SELECT COUNT(*) FROM hitl_gate_status") or 0
    certified_count = await conn.fetchval(
        "SELECT COUNT(*) FROM hitl_gate_status WHERE gate_3 = 'CERTIFIED'"
    ) or 0

    return templates.TemplateResponse(
        "meredith_home.html",
        {
            "request": request,
            "portal_name": "meredith",
            "current_user": user,
            "spec": dict(spec_row) if spec_row else None,
            "supplier_count": supplier_count,
            "certified_count": certified_count,
        },
    )


# ---------------------------------------------------------------------------
# Protected: Spec Setup
# ---------------------------------------------------------------------------


@router.get("/spec-setup", response_class=HTMLResponse)
async def spec_setup(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    retailer_slug = user.get("retailer_slug")
    if retailer_slug:
        specs = await conn.fetch(
            "SELECT retailer_slug, spec_version, thesis_s3_key, created_at FROM retailer_specs WHERE retailer_slug = $1 ORDER BY created_at DESC",
            retailer_slug,
        )
    else:
        specs = await conn.fetch(
            "SELECT retailer_slug, spec_version, thesis_s3_key, created_at FROM retailer_specs ORDER BY created_at DESC"
        )
    return templates.TemplateResponse(
        "meredith_spec_setup.html",
        {
            "request": request,
            "portal_name": "meredith",
            "current_user": user,
            "specs": [dict(s) for s in specs],
        },
    )


@router.post("/spec-setup/upload")
async def trigger_spec_upload(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Trigger Dwight agent via S3 workspace signal. Never calls agents/ directly (INV-07)."""
    body = await request.json()
    pdf_s3_key = body.get("pdf_s3_key")
    retailer_slug = body.get("retailer_slug") or user.get("retailer_slug")

    if not pdf_s3_key or not retailer_slug:
        raise HTTPException(status_code=400, detail="pdf_s3_key and retailer_slug required")

    # TODO: call agent via workspace signal
    return JSONResponse(
        {
            "status": "queued",
            "message": "Dwight spec analysis queued via workspace signal.",
            "retailer_slug": retailer_slug,
            "pdf_s3_key": pdf_s3_key,
        }
    )


# ---------------------------------------------------------------------------
# Protected: YAML Wizard (3-path)
# ---------------------------------------------------------------------------


@router.get("/yaml-wizard", response_class=HTMLResponse)
async def yaml_wizard(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    retailer_slug = user.get("retailer_slug")
    if retailer_slug:
        specs = await conn.fetch(
            "SELECT retailer_slug, spec_version FROM retailer_specs WHERE retailer_slug = $1 ORDER BY created_at DESC",
            retailer_slug,
        )
    else:
        specs = await conn.fetch(
            "SELECT retailer_slug, spec_version FROM retailer_specs ORDER BY created_at DESC"
        )
    return templates.TemplateResponse(
        "meredith_yaml_wizard.html",
        {
            "request": request,
            "portal_name": "meredith",
            "current_user": user,
            "specs": [dict(s) for s in specs],
            "supported_bundles": {
                "general_merchandise": ["850", "855", "856", "810", "997"],
                "transportation": ["204", "990", "210", "214"],
            },
        },
    )


@router.post("/yaml-wizard/path1")
async def yaml_wizard_path1(request: Request, user: dict = Depends(get_current_user)):
    """Path 1: Trigger Andy PDF extraction via workspace signal."""
    body = await request.json()
    # TODO: call agent via workspace signal
    return JSONResponse({"status": "queued", "path": 1, "payload": body})


@router.post("/yaml-wizard/path2")
async def yaml_wizard_path2(request: Request, user: dict = Depends(get_current_user)):
    """Path 2: Trigger Andy YAML upload validation via workspace signal."""
    body = await request.json()
    # TODO: call agent via workspace signal
    return JSONResponse({"status": "queued", "path": 2, "payload": body})


@router.post("/yaml-wizard/path3")
async def yaml_wizard_path3(request: Request, user: dict = Depends(get_current_user)):
    """Path 3: Trigger Andy wizard form serialization via workspace signal."""
    body = await request.json()
    # TODO: call agent via workspace signal
    return JSONResponse({"status": "queued", "path": 3, "payload": body})


# ---------------------------------------------------------------------------
# Protected: Supplier Status Board
# ---------------------------------------------------------------------------


@router.get("/supplier-status", response_class=HTMLResponse)
async def supplier_status(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
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
            "current_user": user,
            "suppliers": [dict(r) for r in rows],
        },
    )


# ---------------------------------------------------------------------------
# Protected: HTMX partials
# ---------------------------------------------------------------------------


@router.get("/htmx/supplier-status/{supplier_id}", response_class=HTMLResponse)
async def supplier_status_partial(
    request: Request,
    supplier_id: str,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
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


@router.get("/htmx/spec-steps/{retailer_slug}", response_class=HTMLResponse)
async def spec_steps_partial(
    request: Request,
    retailer_slug: str,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
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
# Protected: Gate management (retailer-facing)
# ---------------------------------------------------------------------------


@router.post("/suppliers/{supplier_id}/approve-gate/{gate}")
async def retailer_approve_gate(
    supplier_id: str,
    gate: int,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Retailer approves a supplier gate (calls gate_enforcer)."""
    if gate not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="gate must be 1, 2, or 3")
    try:
        await transition_gate(
            supplier_id=supplier_id,
            gate=gate,
            new_state="COMPLETE",
            updated_by=user["sub"],
            conn=conn,
        )
    except GateOrderViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse({"status": "ok", "supplier_id": supplier_id, "gate": gate})


# Mount the protected router
app.include_router(router)
