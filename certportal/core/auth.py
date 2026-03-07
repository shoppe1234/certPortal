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

Password storage:
  Passwords are bcrypt-hashed (rounds=12) using the bcrypt library directly.
  DB: portal_users table, queried via asyncpg (see migrations/002_users_table.sql).
  Fallback: _DEV_USERS in-memory dict used when DB is unavailable (dev/CI only).

Sprint 1: _DEV_USERS with bcrypt-hashed dev passwords.
Sprint 2 (this file): async authenticate_user() queries portal_users table first.
Sprint 3: /register, /change-password, refresh tokens.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import bcrypt as _bcrypt_lib
from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError, jwt

from certportal.core.config import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8-hour session (full working day)

# ---------------------------------------------------------------------------
# Dev user registry
#
# Passwords are bcrypt-hashed (rounds=12). Plaintext reference:
#   pam_admin       → certportal_admin
#   lowes_retailer  → certportal_retailer
#   acme_supplier   → certportal_supplier
#
# Seeded into portal_users by migrations/002_users_table.sql.
# _DEV_USERS is the in-process fallback used when DB is unreachable (dev/CI).
# ---------------------------------------------------------------------------

_DEV_USERS: dict[str, dict[str, Any]] = {
    "pam_admin": {
        "hashed_password": "$2b$12$zm9vZ9thChmd45pNMC35lOh4MFdDmcuYrFiehnlYv.mnTMhD4GNU6",
        "role": "admin",
        "retailer_slug": None,
        "supplier_slug": None,
    },
    "lowes_retailer": {
        "hashed_password": "$2b$12$GFviKss9RDxqxa1wmxt8dO9Quy/tf9eWmbzck6Uh.SrAmywWWjSgW",
        "role": "retailer",
        "retailer_slug": "lowes",
        "supplier_slug": None,
    },
    "acme_supplier": {
        "hashed_password": "$2b$12$WWdvIWgYMYgKw/Ju1Sc7YuD665.oOkA31RDKArlzTR9VmiaMHOTZS",
        "role": "supplier",
        "retailer_slug": "lowes",
        "supplier_slug": "acme",
    },
}


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def _verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the bcrypt-hashed value."""
    return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (rounds=12).

    Used by /change-password endpoint (Sprint 3) and migration seeding.
    """
    return _bcrypt_lib.hashpw(plain.encode("utf-8"), _bcrypt_lib.gensalt(rounds=12)).decode("utf-8")


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
# DB helper — fetch a user row from portal_users via asyncpg
# ---------------------------------------------------------------------------

async def _db_fetch_user(username: str) -> dict[str, Any] | None:
    """Query portal_users for a single active user row.

    Returns a dict with keys: username, hashed_password, role, retailer_slug,
    supplier_slug — or None if the user is not found or is inactive.

    Raises any asyncpg / network exception to the caller (authenticate_user
    catches them and falls back to _DEV_USERS).
    """
    conn: asyncpg.Connection = await asyncpg.connect(settings.certportal_db_url)
    try:
        row = await conn.fetchrow(
            "SELECT username, hashed_password, role, retailer_slug, supplier_slug "
            "FROM portal_users "
            "WHERE username = $1 AND is_active = TRUE",
            username,
        )
    finally:
        await conn.close()

    if row is None:
        return None
    return dict(row)


# ---------------------------------------------------------------------------
# Credential validation — DB first, _DEV_USERS fallback
# ---------------------------------------------------------------------------

async def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    """Validate username + password.

    Priority:
      1. Query portal_users table via asyncpg (DB must be up + migrated).
         - If user found in DB:  verify password → return record or None (no fallback).
         - If user NOT in DB:    fall through to _DEV_USERS.
      2. _DEV_USERS in-process dict (dev / CI fallback when DB is unreachable).

    Returns the user record dict on success:
        {"sub": username, "role": ..., "retailer_slug": ..., "supplier_slug": ...}
    Returns None if credentials are invalid.

    Never raises — DB errors are caught and logged; fallback is used.
    """
    # ------------------------------------------------------------------
    # 1. DB authentication
    # ------------------------------------------------------------------
    db_row: dict[str, Any] | None = None
    db_available = False

    try:
        db_row = await _db_fetch_user(username)
        db_available = True
    except Exception as exc:
        logger.warning(
            "authenticate_user: DB unavailable (%s: %s), falling back to _DEV_USERS",
            type(exc).__name__,
            exc,
        )

    if db_available:
        if db_row is None:
            # User not found in DB — fall through to _DEV_USERS
            pass
        else:
            # User exists in DB — verify password; do NOT fall back on wrong password
            if _verify_password(password, db_row["hashed_password"]):
                return {
                    "sub": db_row["username"],
                    "role": db_row["role"],
                    "retailer_slug": db_row["retailer_slug"],
                    "supplier_slug": db_row["supplier_slug"],
                }
            return None  # Wrong password — no _DEV_USERS backdoor

    # ------------------------------------------------------------------
    # 2. _DEV_USERS fallback (DB not reachable OR user not found in DB)
    # ------------------------------------------------------------------
    dev_user = _DEV_USERS.get(username)
    if dev_user is None:
        return None
    if not _verify_password(password, dev_user["hashed_password"]):
        return None
    return {
        "sub": username,
        "role": dev_user["role"],
        "retailer_slug": dev_user.get("retailer_slug"),
        "supplier_slug": dev_user.get("supplier_slug"),
    }


def build_token_claims(user_record: dict[str, Any]) -> dict[str, Any]:
    """Build JWT payload from an authenticated user record."""
    return {
        "sub": user_record["sub"],
        "role": user_record["role"],
        "retailer_slug": user_record.get("retailer_slug"),
        "supplier_slug": user_record.get("supplier_slug"),
    }
