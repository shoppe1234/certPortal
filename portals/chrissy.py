"""portals/chrissy.py — Supplier Portal (port 8002).

Aesthetic: Friendly, task-completion focused. Warm light theme. Generous whitespace.
Colors: #fffbf7 base, #2d2926 text, #f59e0b primary, #d1fae5 success, #fef3c7 warning.

INV-07: Never imports from agents/. DB reads only via certportal.core.
Auth (ADR-014): JWT cookie or Bearer header. Role required: 'admin' or 'supplier'.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
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
    error_html = f'<p style="color:#dc2626;margin-bottom:1rem">{error}</p>' if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>certPortal Supplier — Login</title>
  <style>
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#fffbf7;color:#2d2926;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
    .card{{background:#fff;padding:2.5rem;border-radius:8px;width:360px;box-shadow:0 2px 12px rgba(0,0,0,.06);border:1px solid #fef3c7}}
    h1{{color:#f59e0b;font-size:1.4rem;margin:0 0 1.5rem}}
    label{{display:block;font-size:.8rem;color:#6b7280;margin-bottom:.3rem;font-weight:500}}
    input{{width:100%;box-sizing:border-box;padding:.6rem .75rem;background:#fff;border:1px solid #e5e7eb;border-radius:6px;color:#2d2926;font-size:.9rem}}
    input:focus{{outline:none;border-color:#f59e0b;box-shadow:0 0 0 3px rgba(245,158,11,.15)}}
    button{{width:100%;margin-top:1.2rem;padding:.75rem;background:#f59e0b;color:#fff;border:none;border-radius:6px;font-weight:600;font-size:1rem;cursor:pointer}}
    button:hover{{background:#d97706}}
    .sep{{margin-bottom:1rem}}
  </style>
</head>
<body>
<div class="card">
  <h1>certPortal · Supplier</h1>
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
    if user.get("role") not in ("admin", "supplier"):
        return RedirectResponse(url="/login?error=Supplier+or+admin+role+required", status_code=302)

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
        "SELECT supplier_slug, gate_1, gate_2, gate_3, last_updated FROM hitl_gate_status WHERE supplier_slug = $1",
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
    """Supplier marks a patch as applied. Does not call any agent."""
    result = await conn.execute(
        "UPDATE patch_suggestions SET applied = TRUE WHERE id = $1",
        patch_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")
    return JSONResponse({"status": "applied", "patch_id": patch_id})


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

_CHRISSY_CARD_CSS = """
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       background:#fffbf7;color:#2d2926;display:flex;align-items:center;
       justify-content:center;min-height:100vh;margin:0}
  .card{background:#fff;padding:2.5rem;border-radius:8px;width:420px;
        box-shadow:0 2px 12px rgba(0,0,0,.06);border:1px solid #fef3c7}
  h1{color:#f59e0b;font-size:1.3rem;margin:0 0 1.5rem}
  label{display:block;font-size:.8rem;color:#6b7280;margin-bottom:.25rem;font-weight:500}
  input{width:100%;box-sizing:border-box;padding:.6rem .75rem;background:#fff;
        border:1px solid #e5e7eb;border-radius:6px;color:#2d2926;font-size:.9rem;
        margin-bottom:.9rem}
  input:focus{outline:none;border-color:#f59e0b;box-shadow:0 0 0 3px rgba(245,158,11,.15)}
  button{width:100%;margin-top:.3rem;padding:.7rem;background:#f59e0b;color:#fff;
         border:none;border-radius:6px;font-weight:600;font-size:.95rem;cursor:pointer}
  button:hover{background:#d97706}
  .msg{color:#16a34a;margin-bottom:1rem;font-size:.9rem}
  .err{color:#dc2626;margin-bottom:1rem;font-size:.9rem}
  .back{margin-top:1rem;font-size:.82rem}
  .back a{color:#f59e0b;text-decoration:none}
"""


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(
    request: Request,
    user: dict = Depends(get_current_user),
    error: str = "",
    msg: str = "",
):
    """Render the change-password form (supplier theme)."""
    err_html = f'<p class="err">{error}</p>' if error else ""
    msg_html = f'<p class="msg">{msg}</p>' if msg else ""
    username = user.get("sub", "")
    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>certPortal Supplier — Change Password</title>
<style>{_CHRISSY_CARD_CSS}</style></head>
<body><div class="card">
  <h1>certPortal &middot; Change Password</h1>
  <p style="color:#6b7280;font-size:.85rem;margin-bottom:1.2rem">Signed in as <strong style="color:#2d2926">{username}</strong></p>
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
