"""certportal/core/auth.py — JWT authentication for all three portals.

Used by portals/pam.py, portals/meredith.py, portals/chrissy.py.
INV-07 compliant: portals import from certportal.core, never from agents/.

Token format (JWT HS256):
  sub:            user slug
  role:           'admin' | 'retailer' | 'supplier'
  retailer_slug:  bound retailer (all non-admin users)
  supplier_slug:  bound supplier (supplier role only)
  exp:            expiry timestamp (UTC)

Auth flow:
  POST /token  → validate credentials, set httponly cookie + return token JSON
  GET  /login  → render HTML login form
  POST /logout → clear access_token cookie, redirect to /login
  All other routes → FastAPI dependency get_current_user() checks cookie or Bearer header.

Sprint 1: credentials stored in _DEV_USERS (plaintext). Not for production.
Sprint 2: replace _DEV_USERS with DB users table + bcrypt password hashing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError, jwt

from certportal.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8-hour session (full working day)

# ---------------------------------------------------------------------------
# Sprint 1 dev credentials
# Sprint 2: replace with DB users table + bcrypt (hash with passlib.bcrypt)
# ---------------------------------------------------------------------------

_DEV_USERS: dict[str, dict[str, Any]] = {
    "pam_admin": {
        "password": "certportal_admin",
        "role": "admin",
        "retailer_slug": None,
        "supplier_slug": None,
    },
    "lowes_retailer": {
        "password": "certportal_retailer",
        "role": "retailer",
        "retailer_slug": "lowes",
        "supplier_slug": None,
    },
    "acme_supplier": {
        "password": "certportal_supplier",
        "role": "supplier",
        "retailer_slug": "lowes",
        "supplier_slug": "acme",
    },
}


# ---------------------------------------------------------------------------
# Token creation / decoding
# ---------------------------------------------------------------------------

def create_access_token(
    data: dict[str, Any],
    expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
) -> str:
    """Encode a JWT access token with the given claims + expiry."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload["exp"] = expire
    return jwt.encode(payload, settings.certportal_jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT token.

    Raises:
        HTTPException 401 — invalid signature, expired, or malformed token.
    """
    try:
        payload = jwt.decode(
            token, settings.certportal_jwt_secret, algorithms=[ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# FastAPI dependency — resolves the authenticated user from request
# ---------------------------------------------------------------------------

async def get_current_user(
    authorization: str | None = Header(default=None),
    access_token: str | None = Cookie(default=None),
) -> dict[str, Any]:
    """Resolve the current user from JWT.

    Accepts token from (in priority order):
      1. Authorization: Bearer <token>  header  — for API / programmatic access
      2. access_token cookie             — for browser sessions after /token login

    Returns the decoded JWT payload dict (contains sub, role, retailer_slug, etc.)
    Raises HTTP 401 if no valid token is found.
    """
    token: str | None = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — provide a Bearer token or log in via /login",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return decode_token(token)


# ---------------------------------------------------------------------------
# Role enforcement dependency factory
# ---------------------------------------------------------------------------

def require_role(*allowed_roles: str):
    """Dependency factory that enforces the caller has one of the allowed roles.

    Usage in a router:
        router = APIRouter(dependencies=[Depends(require_role("admin"))])

    Usage on a single route:
        @app.post("/approve")
        async def approve(user=Depends(require_role("admin", "retailer"))):
            ...

    Raises HTTP 403 if the authenticated user's role is not in allowed_roles.
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{user.get('role')}' is not permitted here. "
                    f"Required: {list(allowed_roles)}"
                ),
            )
        return user

    return _check


# ---------------------------------------------------------------------------
# Credential validation (Sprint 1: plaintext lookup)
# ---------------------------------------------------------------------------

def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    """Validate username + password against _DEV_USERS.

    Returns the user record dict on success, None on failure.
    Sprint 2: replace with DB query + bcrypt.checkpw().
    """
    user = _DEV_USERS.get(username)
    if user is None:
        return None
    if user["password"] != password:  # Sprint 2: bcrypt.checkpw(password, user["hashed_pw"])
        return None
    return {"sub": username, **user}


def build_token_claims(user_record: dict[str, Any]) -> dict[str, Any]:
    """Build JWT payload from an authenticated user record."""
    return {
        "sub": user_record["sub"],
        "role": user_record["role"],
        "retailer_slug": user_record.get("retailer_slug"),
        "supplier_slug": user_record.get("supplier_slug"),
    }
