"""portals/pam.py — Admin Portal (port 8000).

Aesthetic: Industrial command center. Dark theme. Monospace data. Bloomberg-meets-SaaS.
Colors: #0a0e1a base, #00ff88 active, #ffaa00 warning, #ff4455 error, #1e2d40 card surfaces.

INV-07: Never imports from agents/. DB reads only via certportal.core.
Auth (ADR-014): JWT cookie or Bearer header. Role required: 'admin'.
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Cookie, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from certportal.core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    authenticate_user,
    build_token_claims,
    cleanup_expired_revoked_tokens,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    require_role,
    revoke_jti,
    set_revocation_pool,
    validate_password_reset_token,
)
from certportal.core.email_utils import send_reset_email
from certportal.core.database import get_connection, get_pool
from certportal.core.gate_enforcer import (
    GateOrderViolation,
    get_gate_status,
    transition_gate,
)
from certportal.core.models import HITLGateStatus
from certportal.core.workspace import S3AgentWorkspace

BASE_DIR = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await get_pool()
    set_revocation_pool(pool)   # ADR-021: register pool for JWT revocation checks

    async def _cleanup_loop():
        """Hourly background task: purge expired JTIs from revoked_tokens (ADR-025)."""
        await cleanup_expired_revoked_tokens()  # immediate first pass on startup
        while True:
            await asyncio.sleep(3600)
            await cleanup_expired_revoked_tokens()

    task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        task.cancel()
        set_revocation_pool(None)


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
    error_html = f'<p class="auth-err">{error}</p>' if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <title>certPortal Admin — Login</title>
  <link rel="stylesheet" href="/static/css/certportal-core.css">
  <link rel="stylesheet" href="/static/css/portal-pam.css">
  <link rel="stylesheet" href="/static/css/auth-standalone.css">
</head>
<body class="auth-body">
<div class="auth-card">
  <h1 class="auth-title">certPortal · Admin</h1>
  {error_html}
  <form method="post" action="/token">
    <div class="auth-sep"><label class="auth-label">Username</label><input class="auth-input" name="username" autocomplete="username" required></div>
    <div class="auth-sep"><label class="auth-label">Password</label><input class="auth-input" name="password" type="password" autocomplete="current-password" required></div>
    <button class="auth-btn" type="submit">Sign in</button>
  </form>
  <p class="auth-forgot"><a href="/forgot-password">Forgot password?</a></p>
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

    claims = build_token_claims(user)
    token = create_access_token(claims)
    refresh_token = create_refresh_token(claims)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    return response


@app.post("/token/refresh")
async def refresh_access_token(
    refresh_token: str | None = Cookie(default=None),
):
    """Issue a new access token from a valid refresh token (ADR-017)."""
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    claims = decode_refresh_token(refresh_token)
    user_record = {
        "sub": claims["sub"],
        "role": claims["role"],
        "retailer_slug": claims.get("retailer_slug"),
        "supplier_slug": claims.get("supplier_slug"),
    }
    access_token = create_access_token(build_token_claims(user_record))
    response = JSONResponse({"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key="access_token",
        value=access_token,
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
async def logout(access_token: str | None = Cookie(default=None)):
    """Clear auth cookies and revoke the token's JTI in revoked_tokens (ADR-021)."""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")   # also clear refresh (fix Sprint 4 gap)
    if access_token:
        try:
            payload = decode_token(access_token)
            await revoke_jti(payload.get("jti"), payload.get("exp"))
        except Exception:
            pass  # expired/malformed token — clear cookies regardless
    return response


# ---------------------------------------------------------------------------
# Open endpoints: Password reset (ADR-023)
# ---------------------------------------------------------------------------

_PAM_AUTH_HEAD = (
    '  <link rel="stylesheet" href="/static/css/certportal-core.css">\n'
    '  <link rel="stylesheet" href="/static/css/portal-pam.css">\n'
    '  <link rel="stylesheet" href="/static/css/auth-standalone.css">'
)


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_form(error: str = ""):
    """Render the forgot-password form (username field)."""
    err_html = f'<p class="auth-err">{error}</p>' if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<title>certPortal Admin — Forgot Password</title>
{_PAM_AUTH_HEAD}</head>
<body class="auth-body"><div class="auth-card">
  <h1 class="auth-title">certPortal &middot; Forgot Password</h1>
  {err_html}
  <p class="auth-subtitle">
    Enter your username and we will email a reset link if an address is on file.
  </p>
  <form method="post" action="/forgot-password">
    <label class="auth-label">Username</label>
    <input class="auth-input" name="username" autocomplete="username" required>
    <button class="auth-btn" type="submit">Send Reset Link</button>
  </form>
  <p class="auth-back"><a href="/login">&#8592; Back to login</a></p>
</div></body></html>""")


@app.post("/forgot-password")
async def forgot_password_submit(request: Request, username: str = Form(...)):
    """Generate a reset token and email it. Always redirects to reset_sent (no enumeration)."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT email FROM portal_users WHERE username=$1 AND is_active=TRUE", username
    )
    if row and row["email"]:
        token = await create_password_reset_token(username, pool)
        reset_link = f"{request.base_url}reset-password?token={token}"
        send_reset_email(row["email"], reset_link, "Admin")
    return RedirectResponse(url="/login?msg=reset_sent", status_code=302)


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_form(token: str, error: str = ""):
    """Show the new-password form if the token is valid (peek — does NOT mark used)."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT 1 FROM password_reset_tokens "
        "WHERE token=$1 AND expires_at > NOW() AND used=FALSE",
        token,
    )
    if row is None:
        return RedirectResponse(url="/forgot-password?error=Reset+link+is+invalid+or+expired", status_code=302)
    err_html = f'<p class="auth-err">{error}</p>' if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<title>certPortal Admin — Reset Password</title>
{_PAM_AUTH_HEAD}</head>
<body class="auth-body"><div class="auth-card">
  <h1 class="auth-title">certPortal &middot; Reset Password</h1>
  {err_html}
  <form method="post" action="/reset-password">
    <input type="hidden" name="token" value="{token}">
    <label class="auth-label">New Password (min 8 characters)</label>
    <input class="auth-input" name="new_password" type="password" autocomplete="new-password" required minlength="8">
    <label class="auth-label">Confirm New Password</label>
    <input class="auth-input" name="confirm_password" type="password" autocomplete="new-password" required>
    <button class="auth-btn" type="submit">Set New Password</button>
  </form>
</div></body></html>""")


@app.post("/reset-password")
async def reset_password_submit(
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    """Validate token, update password, mark token used."""
    if new_password != confirm_password:
        return RedirectResponse(
            url=f"/reset-password?token={token}&error=Passwords+do+not+match",
            status_code=302,
        )
    if len(new_password) < 8:
        return RedirectResponse(
            url=f"/reset-password?token={token}&error=Password+must+be+at+least+8+characters",
            status_code=302,
        )
    pool = await get_pool()
    username = await validate_password_reset_token(token, pool)
    if username is None:
        return RedirectResponse(
            url="/forgot-password?error=Reset+link+is+invalid+or+expired",
            status_code=302,
        )
    new_hash = hash_password(new_password)
    await pool.execute(
        "UPDATE portal_users SET hashed_password=$1, updated_at=NOW() WHERE username=$2",
        new_hash,
        username,
    )
    return RedirectResponse(url="/login?msg=password_changed", status_code=302)


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
        "SELECT DISTINCT supplier_id AS supplier_slug FROM hitl_gate_status ORDER BY supplier_id"
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
        "SELECT supplier_id AS supplier_slug, gate_1, gate_2, gate_3, last_updated, last_updated_by FROM hitl_gate_status ORDER BY last_updated DESC"
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

    # INV-01 / INV-07: Pam never calls kelly.run() directly — write S3 dispatch signal (ADR-020)
    workspace = S3AgentWorkspace(row["retailer_slug"], row["supplier_slug"])
    workspace.upload(
        f"signals/kelly_approved_{queue_id}.json",
        json.dumps({
            "queue_id": queue_id,
            "draft": row["draft"],
            "channel": row["channel"],
            "thread_id": row["thread_id"],
            "approved_by": user["sub"],
            "retailer_slug": row["retailer_slug"],
            "supplier_slug": row["supplier_slug"],
            "approved_at": int(time.time()),
        }),
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



@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    user: dict = Depends(get_current_user),
    error: str = "",
    msg: str = "",
):
    """Render the user registration form (admin only)."""
    err_html = f'<p class="auth-err">{error}</p>' if error else ""
    msg_html = f'<p class="auth-msg">{msg}</p>' if msg else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<title>certPortal Admin — Register User</title>
{_PAM_AUTH_HEAD}</head>
<body class="auth-body"><div class="auth-card auth-card--wide">
  <h1 class="auth-title">certPortal &middot; Register User</h1>
  {msg_html}{err_html}
  <form method="post" action="/register">
    <label class="auth-label">Username</label>
    <input class="auth-input" name="username" autocomplete="off" required>
    <label class="auth-label">Password (min 8 characters)</label>
    <input class="auth-input" name="password" type="password" autocomplete="new-password" required minlength="8">
    <label class="auth-label">Confirm Password</label>
    <input class="auth-input" name="confirm_password" type="password" autocomplete="new-password" required>
    <label class="auth-label">Role</label>
    <select class="auth-select" name="role" required>
      <option value="">&#8212; select role &#8212;</option>
      <option value="admin">admin</option>
      <option value="retailer">retailer</option>
      <option value="supplier">supplier</option>
    </select>
    <label class="auth-label">Retailer Slug (optional)</label>
    <input class="auth-input" name="retailer_slug" placeholder="e.g. lowes">
    <label class="auth-label">Supplier Slug (optional)</label>
    <input class="auth-input" name="supplier_slug" placeholder="e.g. acme">
    <button class="auth-btn" type="submit">Register User</button>
  </form>
  <p class="auth-back"><a href="/">&#8592; Back to Dashboard</a></p>
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
    err_html = f'<p class="auth-err">{error}</p>' if error else ""
    msg_html = f'<p class="auth-msg">{msg}</p>' if msg else ""
    username = user.get("sub", "")
    return HTMLResponse(f"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<title>certPortal Admin — Change Password</title>
{_PAM_AUTH_HEAD}</head>
<body class="auth-body"><div class="auth-card auth-card--wide">
  <h1 class="auth-title">certPortal &middot; Change Password</h1>
  <p class="auth-subtitle">Signed in as <strong>{username}</strong></p>
  {msg_html}{err_html}
  <form method="post" action="/change-password">
    <label class="auth-label">Current Password</label>
    <input class="auth-input" name="current_password" type="password" autocomplete="current-password" required>
    <label class="auth-label">New Password (min 8 characters)</label>
    <input class="auth-input" name="new_password" type="password" autocomplete="new-password" required minlength="8">
    <label class="auth-label">Confirm New Password</label>
    <input class="auth-input" name="confirm_password" type="password" autocomplete="new-password" required>
    <button class="auth-btn" type="submit">Change Password</button>
  </form>
  <p class="auth-back"><a href="/">&#8592; Back to Dashboard</a></p>
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


# ---------------------------------------------------------------------------
# Protected: Template Library Management (admin-only)
# ---------------------------------------------------------------------------


@router.get("/templates", response_class=HTMLResponse)
async def template_list(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """List all templates (published + drafts)."""
    rows = await conn.fetch(
        "SELECT * FROM pam_templates ORDER BY updated_at DESC",
    )
    return templates.TemplateResponse(
        "pam_templates.html",
        {
            "request": request,
            "portal_name": "pam",
            "current_user": user,
            "pam_templates": [dict(r) for r in rows],
        },
    )


@router.get("/templates/new", response_class=HTMLResponse)
async def template_new(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Template creation form."""
    return templates.TemplateResponse(
        "pam_template_editor.html",
        {
            "request": request,
            "portal_name": "pam",
            "current_user": user,
            "tpl": None,
            "mode": "create",
        },
    )


@router.post("/templates")
async def template_create(
    request: Request,
    template_slug: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    category: str = Form(...),
    industry: str = Form(""),
    x12_version: str = Form("4010"),
    content_yaml: str = Form(...),
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Create new template."""
    await conn.execute(
        """INSERT INTO pam_templates
           (template_slug, name, description, category, industry, x12_version, content_yaml, created_by)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
        template_slug, name, description or None, category,
        industry or None, x12_version, content_yaml, user["sub"],
    )
    return RedirectResponse(url="/templates", status_code=302)


@router.get("/templates/{template_id}", response_class=HTMLResponse)
async def template_detail(
    request: Request,
    template_id: int,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """View/edit template."""
    row = await conn.fetchrow("SELECT * FROM pam_templates WHERE id = $1", template_id)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return templates.TemplateResponse(
        "pam_template_editor.html",
        {
            "request": request,
            "portal_name": "pam",
            "current_user": user,
            "tpl": dict(row),
            "mode": "edit",
        },
    )


@router.post("/templates/{template_id}/update")
async def template_update(
    request: Request,
    template_id: int,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Update template content."""
    form = await request.form()
    name = form.get("name", "")
    description = form.get("description", "")
    category = form.get("category", "lifecycle")
    industry = form.get("industry", "")
    x12_version = form.get("x12_version", "4010")
    content_yaml = form.get("content_yaml", "")

    await conn.execute(
        """UPDATE pam_templates
           SET name=$2, description=$3, category=$4, industry=$5,
               x12_version=$6, content_yaml=$7, updated_at=NOW()
           WHERE id=$1""",
        template_id, name, description or None, category,
        industry or None, x12_version, content_yaml,
    )
    return RedirectResponse(url=f"/templates/{template_id}", status_code=302)


@router.post("/templates/{template_id}/publish")
async def template_publish(
    template_id: int,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Publish template (set is_published=TRUE)."""
    result = await conn.execute(
        "UPDATE pam_templates SET is_published=TRUE, updated_at=NOW() WHERE id=$1",
        template_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Template not found")

    # Write template_published signal for Kelly (INV-07)
    import time as _time, json as _json
    ts = int(_time.time())
    from certportal.core.workspace import S3AgentWorkspace
    workspace = S3AgentWorkspace("_system", "templates")
    workspace.upload(
        f"signals/template_published_{template_id}_{ts}.json",
        _json.dumps({
            "event_type": "template_published",
            "template_id": template_id,
            "published_by": user["sub"],
            "timestamp": ts,
        }),
    )

    return RedirectResponse(url="/templates", status_code=302)


@router.post("/templates/{template_id}/unpublish")
async def template_unpublish(
    template_id: int,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Unpublish template (set is_published=FALSE)."""
    result = await conn.execute(
        "UPDATE pam_templates SET is_published=FALSE, updated_at=NOW() WHERE id=$1",
        template_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Template not found")
    return RedirectResponse(url="/templates", status_code=302)


@router.post("/templates/{template_id}/version")
async def template_version(
    template_id: int,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Increment version number."""
    result = await conn.execute(
        "UPDATE pam_templates SET version = version + 1, updated_at=NOW() WHERE id=$1",
        template_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Template not found")
    return RedirectResponse(url=f"/templates/{template_id}", status_code=302)


# Mount the protected router
app.include_router(router)
