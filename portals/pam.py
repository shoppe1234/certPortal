"""portals/pam.py — Admin Portal (port 8000).

Aesthetic: Industrial command center. Dark theme. Monospace data. Bloomberg-meets-SaaS.
Colors: #0a0e1a base, #00ff88 active, #ffaa00 warning, #ff4455 error, #1e2d40 card surfaces.

INV-07: Never imports from agents/. DB reads only via certportal.core.
Auth (ADR-014): JWT cookie or Bearer header. Role required: 'admin'.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Request, status
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
    hash_password,
    require_role,
)
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
    await get_pool()
    yield


# ---------------------------------------------------------------------------
# App + protected router
# ---------------------------------------------------------------------------

app = FastAPI(
    title="certPortal Admin (Pam)",
    description="Admin command centre — retailers, suppliers, HITL, Monica memory.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# All routes in this router require admin role
router = APIRouter(dependencies=[Depends(require_role("admin"))])


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
    return {"status": "ok", "portal": "pam", "version": "1.0.0"}


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    error_html = f'<p style="color:#ff4455;margin-bottom:1rem">{error}</p>' if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>certPortal Admin — Login</title>
  <style>
    body{{font-family:monospace;background:#0a0e1a;color:#c9d1d9;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
    .card{{background:#1e2d40;padding:2.5rem;border-radius:8px;width:340px;box-shadow:0 4px 24px rgba(0,0,0,.4)}}
    h1{{color:#00ff88;font-size:1.4rem;margin:0 0 1.5rem}}
    label{{display:block;font-size:.8rem;color:#8b949e;margin-bottom:.3rem}}
    input{{width:100%;box-sizing:border-box;padding:.6rem;background:#0a0e1a;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;font-family:monospace;font-size:.9rem}}
    button{{width:100%;margin-top:1.2rem;padding:.75rem;background:#00ff88;color:#0a0e1a;border:none;border-radius:4px;font-weight:700;font-size:1rem;cursor:pointer;font-family:monospace}}
    .sep{{margin-bottom:1rem}}
  </style>
</head>
<body>
<div class="card">
  <h1>certPortal · Admin</h1>
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
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        return RedirectResponse(url="/login?error=Invalid+username+or+password", status_code=302)
    if user.get("role") != "admin":
        return RedirectResponse(url="/login?error=Admin+role+required+for+this+portal", status_code=302)

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
    user = await authenticate_user(form_data.username, form_data.password)
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
# Protected: Dashboard
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
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
            "current_user": user,
            "retailers": [r["retailer_slug"] for r in retailers],
            "suppliers": [s["supplier_slug"] for s in suppliers],
            "hitl_queue_count": hitl_count,
            "memory_entry_count": memory_count,
            "now": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )


# ---------------------------------------------------------------------------
# Protected: Retailers
# ---------------------------------------------------------------------------

@router.get("/retailers", response_class=HTMLResponse)
async def retailers(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    rows = await conn.fetch(
        "SELECT retailer_slug, spec_version, thesis_s3_key, created_at FROM retailer_specs ORDER BY created_at DESC"
    )
    return templates.TemplateResponse(
        "pam_retailers.html",
        {
            "request": request,
            "portal_name": "pam",
            "current_user": user,
            "retailers": [dict(r) for r in rows],
        },
    )


# ---------------------------------------------------------------------------
# Protected: Suppliers
# ---------------------------------------------------------------------------

@router.get("/suppliers", response_class=HTMLResponse)
async def suppliers(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    rows = await conn.fetch(
        "SELECT supplier_slug, gate_1, gate_2, gate_3, last_updated, last_updated_by FROM hitl_gate_status ORDER BY last_updated DESC"
    )
    return templates.TemplateResponse(
        "pam_suppliers.html",
        {
            "request": request,
            "portal_name": "pam",
            "current_user": user,
            "suppliers": [dict(r) for r in rows],
        },
    )


# ---------------------------------------------------------------------------
# Protected: HITL Queue
# ---------------------------------------------------------------------------

@router.get("/hitl-queue", response_class=HTMLResponse)
async def hitl_queue(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    rows = await conn.fetch(
        """
        SELECT queue_id, retailer_slug, supplier_slug, agent, summary,
               channel, status, queued_at
        FROM hitl_queue WHERE status = 'PENDING_APPROVAL' ORDER BY queued_at ASC
        """
    )
    return templates.TemplateResponse(
        "pam_hitl_queue.html",
        {
            "request": request,
            "portal_name": "pam",
            "current_user": user,
            "queue_items": [dict(r) for r in rows],
        },
    )


@router.post("/hitl-queue/{queue_id}/approve")
async def approve_hitl_item(
    queue_id: str,
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    row = await conn.fetchrow("SELECT * FROM hitl_queue WHERE queue_id = $1", queue_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Queue item {queue_id} not found")
    await conn.execute(
        "UPDATE hitl_queue SET status='APPROVED', resolved_at=now(), resolved_by=$1 WHERE queue_id=$2",
        user["sub"], queue_id,
    )
    return JSONResponse({"status": "approved", "queue_id": queue_id, "resolved_by": user["sub"]})


@router.post("/hitl-queue/{queue_id}/reject")
async def reject_hitl_item(
    queue_id: str,
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    await conn.execute(
        "UPDATE hitl_queue SET status='REJECTED', resolved_at=now(), resolved_by=$1 WHERE queue_id=$2",
        user["sub"], queue_id,
    )
    return JSONResponse({"status": "rejected", "queue_id": queue_id, "resolved_by": user["sub"]})


# ---------------------------------------------------------------------------
# Protected: Monica Memory
# ---------------------------------------------------------------------------

@router.get("/monica-memory", response_class=HTMLResponse)
async def monica_memory(
    request: Request,
    page: int = 1,
    limit: int = 50,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    offset = (page - 1) * limit
    rows = await conn.fetch(
        "SELECT timestamp, agent, direction, message, retailer_slug, supplier_slug FROM monica_memory ORDER BY timestamp DESC LIMIT $1 OFFSET $2",
        limit, offset,
    )
    total = await conn.fetchval("SELECT COUNT(*) FROM monica_memory") or 0
    return templates.TemplateResponse(
        "pam_monica_memory.html",
        {
            "request": request,
            "portal_name": "pam",
            "current_user": user,
            "entries": [dict(r) for r in rows],
            "page": page, "limit": limit, "total": total,
            "total_pages": (total + limit - 1) // limit,
        },
    )


# ---------------------------------------------------------------------------
# Protected: Gate management
# ---------------------------------------------------------------------------

@router.post("/suppliers/{supplier_id}/gate/{gate}/complete")
async def complete_gate(
    supplier_id: str,
    gate: int,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    if gate not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="gate must be 1, 2, or 3")
    try:
        await transition_gate(supplier_id=supplier_id, gate=gate, new_state="COMPLETE",
                              updated_by=user["sub"], conn=conn)
    except GateOrderViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse({"status": "ok", "supplier_id": supplier_id, "gate": gate, "new_state": "COMPLETE"})


@router.post("/suppliers/{supplier_id}/gate/3/certify")
async def certify_supplier(
    supplier_id: str,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    try:
        await transition_gate(supplier_id=supplier_id, gate=3, new_state="CERTIFIED",
                              updated_by=user["sub"], conn=conn)
    except GateOrderViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse({"status": "certified", "supplier_id": supplier_id})


# ---------------------------------------------------------------------------
# Protected: HTMX partials
# ---------------------------------------------------------------------------

@router.get("/htmx/supplier-gate/{supplier_id}", response_class=HTMLResponse)
async def supplier_gate_partial(
    request: Request,
    supplier_id: str,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    gate_status = await get_gate_status(supplier_id, conn)
    return templates.TemplateResponse(
        "_gate_status_row.html",
        {"request": request, "supplier_id": supplier_id, "gate_status": gate_status},
    )


@router.get("/htmx/hitl-count", response_class=HTMLResponse)
async def hitl_count_partial(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM hitl_queue WHERE status = 'PENDING_APPROVAL'"
    ) or 0
    return HTMLResponse(f'<span class="hitl-badge" data-count="{count}">{count}</span>')


# ---------------------------------------------------------------------------
# Protected: Register new user (admin only — sits on admin router)
# ---------------------------------------------------------------------------

_PAM_CARD_CSS = """
  body{font-family:monospace;background:#0a0e1a;color:#c9d1d9;display:flex;
       align-items:center;justify-content:center;min-height:100vh;margin:0}
  .card{background:#1e2d40;padding:2.5rem;border-radius:8px;width:480px;
        box-shadow:0 4px 24px rgba(0,0,0,.4)}
  h1{color:#00ff88;font-size:1.3rem;margin:0 0 1.5rem}
  label{display:block;font-size:.75rem;color:#8b949e;margin-bottom:.25rem;
        text-transform:uppercase;letter-spacing:.5px}
  input,select{width:100%;box-sizing:border-box;padding:.55rem .7rem;
               background:#0a0e1a;border:1px solid #30363d;border-radius:4px;
               color:#c9d1d9;font-family:monospace;font-size:.9rem;margin-bottom:.9rem}
  select option{background:#0a0e1a}
  button{width:100%;margin-top:.3rem;padding:.7rem;background:#00ff88;color:#0a0e1a;
         border:none;border-radius:4px;font-weight:700;font-size:.95rem;cursor:pointer;
         font-family:monospace}
  button:hover{background:#00cc6e}
  .msg{color:#00ff88;margin-bottom:1rem;font-size:.9rem}
  .err{color:#ff4455;margin-bottom:1rem;font-size:.9rem}
  .back{margin-top:1rem;font-size:.82rem}
  .back a{color:#00ff88;text-decoration:none}
"""


@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    user: dict = Depends(get_current_user),
    error: str = "",
    msg: str = "",
):
    """Render the user registration form (admin only)."""
    err_html = f'<p class="err">{error}</p>' if error else ""
    msg_html = f'<p class="msg">{msg}</p>' if msg else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>certPortal Admin — Register User</title>
<style>{_PAM_CARD_CSS}</style></head>
<body><div class="card">
  <h1>certPortal &middot; Register User</h1>
  {msg_html}{err_html}
  <form method="post" action="/register">
    <label>Username</label>
    <input name="username" autocomplete="off" required>
    <label>Password (min 8 characters)</label>
    <input name="password" type="password" autocomplete="new-password" required minlength="8">
    <label>Confirm Password</label>
    <input name="confirm_password" type="password" autocomplete="new-password" required>
    <label>Role</label>
    <select name="role" required>
      <option value="">&#8212; select role &#8212;</option>
      <option value="admin">admin</option>
      <option value="retailer">retailer</option>
      <option value="supplier">supplier</option>
    </select>
    <label>Retailer Slug (optional)</label>
    <input name="retailer_slug" placeholder="e.g. lowes">
    <label>Supplier Slug (optional)</label>
    <input name="supplier_slug" placeholder="e.g. acme">
    <button type="submit">Register User</button>
  </form>
  <p class="back"><a href="/">&#8592; Back to Dashboard</a></p>
</div></body></html>""")


@router.post("/register")
async def register_user(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
    role: Annotated[str, Form()],
    retailer_slug: Annotated[str, Form()] = "",
    supplier_slug: Annotated[str, Form()] = "",
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Create a new portal_users row (admin only)."""
    _allowed_roles = {"admin", "retailer", "supplier"}

    if not username.strip():
        return RedirectResponse(url="/register?error=Username+is+required", status_code=302)
    if password != confirm_password:
        return RedirectResponse(url="/register?error=Passwords+do+not+match", status_code=302)
    if len(password) < 8:
        return RedirectResponse(url="/register?error=Password+must+be+at+least+8+characters", status_code=302)
    if role not in _allowed_roles:
        return RedirectResponse(url="/register?error=Invalid+role+%28must+be+admin%2C+retailer%2C+or+supplier%29", status_code=302)

    new_hash = hash_password(password)
    try:
        await conn.execute(
            "INSERT INTO portal_users (username, hashed_password, role, retailer_slug, supplier_slug) "
            "VALUES ($1, $2, $3, $4, $5)",
            username.strip(),
            new_hash,
            role,
            retailer_slug.strip() or None,
            supplier_slug.strip() or None,
        )
    except asyncpg.UniqueViolationError:
        return RedirectResponse(url="/register?error=Username+already+taken", status_code=302)

    return RedirectResponse(
        url=f"/register?msg=User+%27{username.strip()}%27+registered+successfully",
        status_code=302,
    )


# ---------------------------------------------------------------------------
# Protected: Change password (any authenticated admin user)
# ---------------------------------------------------------------------------


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(
    request: Request,
    user: dict = Depends(get_current_user),
    error: str = "",
    msg: str = "",
):
    """Render the change-password form."""
    err_html = f'<p class="err">{error}</p>' if error else ""
    msg_html = f'<p class="msg">{msg}</p>' if msg else ""
    username = user.get("sub", "")
    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>certPortal Admin — Change Password</title>
<style>{_PAM_CARD_CSS}</style></head>
<body><div class="card">
  <h1>certPortal &middot; Change Password</h1>
  <p style="color:#6a8aa8;font-size:.85rem;margin-bottom:1.2rem">Signed in as <strong style="color:#c8d8e8">{username}</strong></p>
  {msg_html}{err_html}
  <form method="post" action="/change-password">
    <label>Current Password</label>
    <input name="current_password" type="password" autocomplete="current-password" required>
    <label>New Password (min 8 characters)</label>
    <input name="new_password" type="password" autocomplete="new-password" required minlength="8">
    <label>Confirm New Password</label>
    <input name="confirm_password" type="password" autocomplete="new-password" required>
    <button type="submit">Change Password</button>
  </form>
  <p class="back"><a href="/">&#8592; Back to Dashboard</a></p>
</div></body></html>""")


@router.post("/change-password")
async def change_password(
    request: Request,
    current_password: Annotated[str, Form()],
    new_password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Verify current password and update to a new bcrypt hash."""
    if new_password != confirm_password:
        return RedirectResponse(
            url="/change-password?error=New+passwords+do+not+match", status_code=302
        )
    if len(new_password) < 8:
        return RedirectResponse(
            url="/change-password?error=New+password+must+be+at+least+8+characters",
            status_code=302,
        )

    # Verify current credentials — uses DB or _DEV_USERS fallback
    verified = await authenticate_user(user["sub"], current_password)
    if verified is None:
        return RedirectResponse(
            url="/change-password?error=Current+password+is+incorrect", status_code=302
        )

    new_hash = hash_password(new_password)
    result = await conn.execute(
        "UPDATE portal_users SET hashed_password = $1, updated_at = NOW() "
        "WHERE username = $2 AND is_active = TRUE",
        new_hash,
        user["sub"],
    )
    if result == "UPDATE 0":
        return RedirectResponse(
            url="/change-password?error=Password+update+failed+%28dev-only+account+not+in+DB%3F%29",
            status_code=302,
        )

    return RedirectResponse(
        url="/change-password?msg=Password+changed+successfully", status_code=302
    )


# Mount the protected router
app.include_router(router)
