"""portals/chrissy.py — Supplier Portal (port 8002).

Aesthetic: Friendly, task-completion focused. Warm light theme. Generous whitespace.
Colors: #fffbf7 base, #2d2926 text, #f59e0b primary, #d1fae5 success, #fef3c7 warning.

INV-07: Never imports from agents/. DB reads only via certportal.core.
Auth (ADR-014): JWT cookie or Bearer header. Role required: 'admin' or 'supplier'.
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
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
    compute_current_step,
    get_gate_status,
    get_onboarding_profile,
    transition_gate,
)
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
    title="certPortal Supplier (Chrissy)",
    description="Supplier portal — scenarios, errors, Ryan's patches, certification badge.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# All routes in this router require supplier or admin role
router = APIRouter(dependencies=[Depends(require_role("admin", "supplier"))])


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
    return {"status": "ok", "portal": "chrissy", "version": "1.0.0"}


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    error_html = f'<p class="auth-err">{error}</p>' if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <title>certPortal Supplier — Login</title>
  <link rel="stylesheet" href="/static/css/certportal-core.css">
  <link rel="stylesheet" href="/static/css/portal-chrissy.css">
  <link rel="stylesheet" href="/static/css/auth-standalone.css">
</head>
<body class="auth-body">
<div class="auth-card">
  <h1 class="auth-title">certPortal · Supplier</h1>
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
    if user.get("role") not in ("admin", "supplier"):
        return RedirectResponse(url="/login?error=Supplier+or+admin+role+required", status_code=302)

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

_CHRISSY_AUTH_HEAD = (
    '  <link rel="stylesheet" href="/static/css/certportal-core.css">\n'
    '  <link rel="stylesheet" href="/static/css/portal-chrissy.css">\n'
    '  <link rel="stylesheet" href="/static/css/auth-standalone.css">'
)


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_form(error: str = ""):
    """Render the forgot-password form (username field, supplier theme)."""
    err_html = f'<p class="auth-err">{error}</p>' if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<title>certPortal Supplier - Forgot Password</title>
{_CHRISSY_AUTH_HEAD}</head>
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
        send_reset_email(row["email"], reset_link, "Supplier")
    return RedirectResponse(url="/login?msg=reset_sent", status_code=302)


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_form(token: str, error: str = ""):
    """Show the new-password form if the token is valid (peek - does NOT mark used)."""
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
<title>certPortal Supplier - Reset Password</title>
{_CHRISSY_AUTH_HEAD}</head>
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
# Protected: Home
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    # Supplier context from JWT claims; admin users fall back to first row
    supplier_slug = user.get("supplier_slug") or "demo"

    row = await conn.fetchrow(
        "SELECT supplier_id AS supplier_slug, gate_1, gate_2, gate_3, last_updated FROM hitl_gate_status WHERE supplier_id = $1",
        supplier_slug,
    )
    supplier = (
        dict(row)
        if row
        else {
            "supplier_slug": supplier_slug,
            "gate_1": "PENDING",
            "gate_2": "PENDING",
            "gate_3": "PENDING",
        }
    )

    total_tests = await conn.fetchval(
        "SELECT COUNT(*) FROM test_occurrences WHERE supplier_slug = $1",
        supplier_slug,
    ) or 0
    passed_tests = await conn.fetchval(
        "SELECT COUNT(*) FROM test_occurrences WHERE supplier_slug = $1 AND status = 'PASS'",
        supplier_slug,
    ) or 0

    return templates.TemplateResponse(
        "chrissy_home.html",
        {
            "request": request,
            "portal_name": "chrissy",
            "current_user": user,
            "supplier": supplier,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "progress_pct": round((passed_tests / total_tests * 100) if total_tests > 0 else 0),
        },
    )


# ---------------------------------------------------------------------------
# Protected: Scenarios
# ---------------------------------------------------------------------------


@router.get("/scenarios", response_class=HTMLResponse)
async def scenarios(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    supplier_slug = user.get("supplier_slug")
    if supplier_slug:
        rows = await conn.fetch(
            """
            SELECT supplier_slug, retailer_slug, transaction_type, channel,
                   status, validated_at
            FROM test_occurrences
            WHERE supplier_slug = $1
            ORDER BY validated_at DESC
            LIMIT 100
            """,
            supplier_slug,
        )
    else:
        # Admin: show all
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
            "current_user": user,
            "scenarios": [dict(r) for r in rows],
        },
    )


# ---------------------------------------------------------------------------
# Protected: Errors
# ---------------------------------------------------------------------------


@router.get("/errors", response_class=HTMLResponse)
async def errors(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Show validation errors with Ryan's patch suggestions."""
    supplier_slug = user.get("supplier_slug") or "demo"

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
            "current_user": user,
            "supplier_slug": supplier_slug,
            "error_groups": error_groups,
        },
    )


# ---------------------------------------------------------------------------
# Protected: Patches (Ryan's suggestions)
# ---------------------------------------------------------------------------


@router.get("/patches", response_class=HTMLResponse)
async def patches(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    supplier_slug = user.get("supplier_slug") or "demo"
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
            "current_user": user,
            "supplier_slug": supplier_slug,
            "patches": [dict(r) for r in rows],
        },
    )


@router.post("/patches/{patch_id}/mark-applied")
async def mark_patch_applied(
    patch_id: int,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Supplier marks a patch as applied. Triggers Moses revalidation via S3 signal (INV-07)."""
    row = await conn.fetchrow("SELECT * FROM patch_suggestions WHERE id = $1", patch_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")

    await conn.execute(
        "UPDATE patch_suggestions SET applied = TRUE WHERE id = $1",
        patch_id,
    )

    # Write Moses revalidation signal (ADR-019, INV-01, INV-07)
    ts = int(time.time())
    workspace = S3AgentWorkspace(row["retailer_slug"], row["supplier_slug"])
    workspace.upload(
        f"signals/moses_revalidate_{patch_id}_{ts}.json",
        json.dumps({
            "trigger": "patch_applied",
            "patch_id": patch_id,
            "supplier_slug": row["supplier_slug"],
            "retailer_slug": row["retailer_slug"],
        }),
    )

    return JSONResponse({"status": "applied", "patch_id": patch_id})


@router.post("/patches/{patch_id}/reject")
async def reject_patch(
    patch_id: int,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Supplier rejects a patch suggestion. Sets rejected=TRUE; no downstream signal (ADR-019)."""
    result = await conn.execute(
        "UPDATE patch_suggestions SET rejected = TRUE WHERE id = $1",
        patch_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")
    return JSONResponse({"status": "rejected", "patch_id": patch_id})


@router.get("/patches/{patch_id}/content", response_class=HTMLResponse)
async def patch_content(
    patch_id: int,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Return patch .md content inline as HTML (ADR-019)."""
    row = await conn.fetchrow("SELECT * FROM patch_suggestions WHERE id = $1", patch_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")
    workspace = S3AgentWorkspace(row["retailer_slug"], row["supplier_slug"])
    md = workspace.download(row["patch_s3_key"]).decode("utf-8")
    safe_md = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return HTMLResponse(
        f"<pre style='white-space:pre-wrap;font-family:var(--font-mono,monospace);padding:1rem'>{safe_md}</pre>"
    )


# ---------------------------------------------------------------------------
# Protected: Certification badge
# ---------------------------------------------------------------------------


@router.get("/certification", response_class=HTMLResponse)
async def certification(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    supplier_slug = user.get("supplier_slug") or "demo"
    gate_status = await get_gate_status(supplier_slug, conn)
    certified = gate_status.get("gate_3") == "CERTIFIED"
    return templates.TemplateResponse(
        "chrissy_home.html",
        {
            "request": request,
            "portal_name": "chrissy",
            "current_user": user,
            "supplier": {"supplier_slug": supplier_slug, **gate_status},
            "certified": certified,
            "total_tests": 0,
            "passed_tests": 0,
            "progress_pct": 100 if certified else 0,
        },
    )


# ---------------------------------------------------------------------------
# Protected: HTMX partials
# ---------------------------------------------------------------------------


@router.get("/htmx/scenario-status/{scenario_id}", response_class=HTMLResponse)
async def scenario_status_partial(
    request: Request,
    scenario_id: str,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    supplier_slug = user.get("supplier_slug") or "demo"
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


@router.get("/htmx/patch-list/{supplier_slug}", response_class=HTMLResponse)
async def patch_list_partial(
    request: Request,
    supplier_slug: str,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
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


# ---------------------------------------------------------------------------
# Protected: Change password (any authenticated supplier/admin user)
# ---------------------------------------------------------------------------



@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(
    request: Request,
    user: dict = Depends(get_current_user),
    error: str = "",
    msg: str = "",
):
    """Render the change-password form (supplier theme)."""
    err_html = f'<p class="auth-err">{error}</p>' if error else ""
    msg_html = f'<p class="auth-msg">{msg}</p>' if msg else ""
    username = user.get("sub", "")
    return HTMLResponse(f"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<title>certPortal Supplier — Change Password</title>
{_CHRISSY_AUTH_HEAD}</head>
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
# Protected: Onboarding Wizard (6-step flow)
# ---------------------------------------------------------------------------


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Render the onboarding wizard; determine current step from gate state."""
    supplier_slug = user.get("supplier_slug") or "demo"
    retailer_slug = user.get("retailer_slug") or "lowes"

    current_step = await compute_current_step(supplier_slug, conn)
    gates = await get_gate_status(supplier_slug, conn)
    profile = await get_onboarding_profile(supplier_slug, conn)
    if profile is None:
        # Auto-create onboarding profile on first visit
        await conn.execute(
            "INSERT INTO supplier_onboarding (supplier_slug, retailer_slug) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            supplier_slug, retailer_slug,
        )
        profile = {"supplier_slug": supplier_slug, "retailer_slug": retailer_slug,
                    "specs_acknowledged": False, "items_complete": False}

    # Fetch exception requests for step 5
    exceptions = [dict(r) for r in await conn.fetch(
        "SELECT * FROM exception_requests WHERE supplier_slug = $1 AND retailer_slug = $2 ORDER BY requested_at DESC",
        supplier_slug, retailer_slug,
    )]

    # Fetch test occurrences for step 5 scenario list
    scenarios = [dict(r) for r in await conn.fetch(
        "SELECT * FROM test_occurrences WHERE supplier_slug = $1 ORDER BY validated_at DESC",
        supplier_slug,
    )]

    return templates.TemplateResponse(
        "chrissy_onboarding.html",
        {
            "request": request,
            "portal_name": "chrissy",
            "current_user": user,
            "current_step": current_step,
            "gates": gates,
            "profile": profile,
            "exceptions": exceptions,
            "scenarios": scenarios,
            "supplier_slug": supplier_slug,
            "retailer_slug": retailer_slug,
        },
    )


@router.post("/onboarding/step1")
async def onboarding_step1(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Acknowledge specs → set specs_acknowledged=TRUE, advance Gate A."""
    supplier_slug = user.get("supplier_slug") or "demo"
    await conn.execute(
        "UPDATE supplier_onboarding SET specs_acknowledged = TRUE, updated_at = NOW() WHERE supplier_slug = $1",
        supplier_slug,
    )
    await transition_gate(supplier_slug, "a", "COMPLETE", user["sub"], conn)
    return RedirectResponse(url="/onboarding", status_code=302)


@router.post("/onboarding/step2")
async def onboarding_step2(
    request: Request,
    company_name: str = Form(...),
    contact_name: str = Form(...),
    contact_email: str = Form(...),
    contact_phone: str = Form(...),
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Save company + contact fields, advance Gate B."""
    supplier_slug = user.get("supplier_slug") or "demo"
    if not all([company_name.strip(), contact_name.strip(), contact_email.strip(), contact_phone.strip()]):
        return RedirectResponse(url="/onboarding?error=All+contact+fields+are+required", status_code=302)

    await conn.execute(
        """UPDATE supplier_onboarding
           SET company_name=$2, contact_name=$3, contact_email=$4, contact_phone=$5, updated_at=NOW()
           WHERE supplier_slug=$1""",
        supplier_slug, company_name.strip(), contact_name.strip(),
        contact_email.strip(), contact_phone.strip(),
    )
    await transition_gate(supplier_slug, "b", "COMPLETE", user["sub"], conn)
    return RedirectResponse(url="/onboarding", status_code=302)


@router.post("/onboarding/step3")
async def onboarding_step3(
    request: Request,
    connection_method: str = Form(...),
    test_vendor_number: str = Form(...),
    test_isa_id: str = Form(...),
    test_gs_id: str = Form(...),
    test_edi_qualifier: str = Form(""),
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Save connection method + test EDI IDs, advance Gate 1."""
    supplier_slug = user.get("supplier_slug") or "demo"
    retailer_slug = user.get("retailer_slug") or "lowes"

    await conn.execute(
        """UPDATE supplier_onboarding
           SET connection_method=$2, test_vendor_number=$3, test_edi_qualifier=$4,
               test_isa_id=$5, test_gs_id=$6, updated_at=NOW()
           WHERE supplier_slug=$1""",
        supplier_slug, connection_method, test_vendor_number,
        test_edi_qualifier, test_isa_id, test_gs_id,
    )
    await transition_gate(supplier_slug, 1, "COMPLETE", user["sub"], conn)

    # Write gate1_complete signal for Kelly (INV-07: S3 only, no agent import)
    ts = int(time.time())
    workspace = S3AgentWorkspace(retailer_slug, supplier_slug)
    workspace.upload(
        f"signals/gate1_complete_{supplier_slug}_{ts}.json",
        json.dumps({
            "event_type": "gate1_complete",
            "supplier_slug": supplier_slug,
            "retailer_slug": retailer_slug,
            "timestamp": ts,
            "message": f"Test environment ready for {supplier_slug}",
        }),
    )
    return RedirectResponse(url="/onboarding", status_code=302)


@router.post("/onboarding/step4")
async def onboarding_step4(
    request: Request,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Save item data. Expects JSON body with items array."""
    supplier_slug = user.get("supplier_slug") or "demo"
    form = await request.form()
    items_raw = form.get("items_json", "[]")
    try:
        items = json.loads(items_raw)
    except json.JSONDecodeError:
        items = []

    items_complete = len(items) > 0 and all(
        item.get("vendor_part_number") for item in items
    )

    await conn.execute(
        """UPDATE supplier_onboarding
           SET items_json=$2::jsonb, items_complete=$3, updated_at=NOW()
           WHERE supplier_slug=$1""",
        supplier_slug, json.dumps(items), items_complete,
    )
    return RedirectResponse(url="/onboarding", status_code=302)


@router.post("/onboarding/step6")
async def onboarding_step6(
    request: Request,
    prod_vendor_number: str = Form(...),
    prod_isa_id: str = Form(...),
    prod_gs_id: str = Form(...),
    prod_edi_qualifier: str = Form(""),
    prod_connection_method: str = Form(""),
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Save production IDs + confirmation, set Gate 3 = PENDING (awaiting PAM approval)."""
    supplier_slug = user.get("supplier_slug") or "demo"

    await conn.execute(
        """UPDATE supplier_onboarding
           SET prod_vendor_number=$2, prod_edi_qualifier=$3, prod_isa_id=$4,
               prod_gs_id=$5, prod_connection_method=$6, prod_confirmed=TRUE, updated_at=NOW()
           WHERE supplier_slug=$1""",
        supplier_slug, prod_vendor_number, prod_edi_qualifier,
        prod_isa_id, prod_gs_id, prod_connection_method,
    )
    # Gate 3 stays PENDING — PAM admin certifies it
    return RedirectResponse(url="/onboarding", status_code=302)


# ---------------------------------------------------------------------------
# Protected: Exception Requests
# ---------------------------------------------------------------------------


@router.post("/scenarios/{scenario_id}/request-exception")
async def request_exception(
    request: Request,
    scenario_id: str,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Create an exception request for a test scenario."""
    supplier_slug = user.get("supplier_slug") or "demo"
    retailer_slug = user.get("retailer_slug") or "lowes"
    form = await request.form()
    reason_code = form.get("reason_code", "NOT_APPLICABLE")
    note = form.get("note", "")
    transaction_type = form.get("transaction_type", "850")

    await conn.execute(
        """INSERT INTO exception_requests
           (supplier_slug, retailer_slug, scenario_id, transaction_type, reason_code, note)
           VALUES ($1, $2, $3, $4, $5, $6)
           ON CONFLICT (supplier_slug, retailer_slug, scenario_id, transaction_type, status) DO NOTHING""",
        supplier_slug, retailer_slug, scenario_id, transaction_type,
        reason_code, note or None,
    )

    # Write exception_requested signal for Kelly (INV-07)
    ts = int(time.time())
    workspace = S3AgentWorkspace(retailer_slug, supplier_slug)
    workspace.upload(
        f"signals/exception_requested_{scenario_id}_{ts}.json",
        json.dumps({
            "event_type": "exception_requested",
            "supplier_slug": supplier_slug,
            "retailer_slug": retailer_slug,
            "scenario_id": scenario_id,
            "transaction_type": transaction_type,
            "reason_code": reason_code,
            "timestamp": ts,
        }),
    )

    # Return HTMX partial or redirect
    if request.headers.get("hx-request"):
        return HTMLResponse(
            f'<span class="badge badge-pending">PENDING</span>'
            f'<small>Exception requested</small>'
        )
    return RedirectResponse(url="/onboarding", status_code=302)


@router.post("/scenarios/{scenario_id}/withdraw-exception")
async def withdraw_exception(
    request: Request,
    scenario_id: str,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """Withdraw a PENDING exception request."""
    supplier_slug = user.get("supplier_slug") or "demo"
    retailer_slug = user.get("retailer_slug") or "lowes"

    result = await conn.execute(
        """DELETE FROM exception_requests
           WHERE supplier_slug=$1 AND retailer_slug=$2 AND scenario_id=$3 AND status='PENDING'""",
        supplier_slug, retailer_slug, scenario_id,
    )
    if request.headers.get("hx-request"):
        return HTMLResponse('<span class="badge badge-withdrawn">Withdrawn</span>')
    return RedirectResponse(url="/onboarding", status_code=302)


@router.get("/htmx/exception-status/{exc_id}", response_class=HTMLResponse)
async def exception_status_partial(
    request: Request,
    exc_id: int,
    conn=Depends(get_connection),
    user: dict = Depends(get_current_user),
):
    """HTMX partial: live status of an exception request."""
    row = await conn.fetchrow(
        "SELECT status, reason_code, resolved_at FROM exception_requests WHERE id = $1",
        exc_id,
    )
    if not row:
        return HTMLResponse('<span class="badge">Not found</span>')
    status_class = {"PENDING": "badge-pending", "APPROVED": "badge-complete", "DENIED": "badge-denied"}.get(
        row["status"], "badge-pending"
    )
    return HTMLResponse(f'<span class="badge {status_class}">{row["status"]}</span>')


# Mount the protected router
app.include_router(router)
