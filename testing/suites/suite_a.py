"""
testing/suites/suite_a.py — Portal Auth Tests (ADR-014 through ADR-017, ADR-021, ADR-023, ADR-025).

Tests certportal.core.auth: token creation/decoding, get_current_user dependency,
require_role factory, authenticate_user (DB path + _DEV_USERS fallback),
_DEV_USERS bcrypt hash structure, refresh token round-trip, JWT revocation,
password reset token lifecycle, and revoked_tokens cleanup.

No live DB, S3, or network required — DB calls are mocked throughout.

Architecture coverage:
  ADR-014 — JWT HS256 via python-jose, httponly cookie + Bearer header dual-accept
  ADR-015 — DB-backed auth (portal_users table + bcrypt), _DEV_USERS fallback
  ADR-016 — /register (admin) and /change-password (all portals) endpoints
  ADR-017 — Stateless JWT refresh tokens (30-day expiry, type-claim separation)
  ADR-021 — JWT revocation: JTI claim, revoked_tokens table, get_current_user check
  ADR-023 — Email password reset: create/validate token, /forgot-password, /reset-password
  ADR-025 — Revoked tokens expiry cleanup: cleanup_expired_revoked_tokens()
"""
from __future__ import annotations

import asyncio
import traceback
from enum import Enum
from typing import Callable


class TestStatus(Enum):
    SKIP = "SKIP"
    PASS = "PASS"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

_AUTH_OK = False
_IMPORT_ERRORS: list[str] = []

try:
    from certportal.core.auth import (  # type: ignore[import]
        create_access_token,
        create_refresh_token,
        create_password_reset_token,
        decode_refresh_token,
        decode_token,
        get_current_user,
        require_role,
        authenticate_user,
        build_token_claims,
        hash_password,
        revoke_jti,
        validate_password_reset_token,
        _DEV_USERS,
        _verify_password,
        ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    from fastapi import HTTPException
    _AUTH_OK = True
except Exception as _e:  # noqa: BLE001
    _IMPORT_ERRORS.append(f"certportal.core.auth: {_e}")


# ---------------------------------------------------------------------------
# Async runner
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine synchronously inside a test function."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def _run_test(name: str, fn: Callable[[], None]) -> dict:
    try:
        fn()
        return {"test": name, "status": TestStatus.PASS, "reason": ""}
    except AssertionError as e:
        return {"test": name, "status": TestStatus.FAIL, "reason": f"AssertionError: {e}"}
    except Exception as e:
        return {
            "test": name,
            "status": TestStatus.FAIL,
            "reason": f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}",
        }


# ---------------------------------------------------------------------------
# Test 01: create_access_token + decode_token round-trip
# ---------------------------------------------------------------------------

def _test_01_token_round_trip() -> None:
    """create_access_token encodes claims that decode_token retrieves correctly."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    claims = {"sub": "pam_admin", "role": "admin", "retailer_slug": None, "supplier_slug": None}
    token = create_access_token(claims)

    assert isinstance(token, str), f"Expected str token, got {type(token)}"
    assert len(token) > 20, "Token too short to be a real JWT"

    decoded = decode_token(token)
    assert decoded["sub"] == "pam_admin", f"sub mismatch: {decoded['sub']!r}"
    assert decoded["role"] == "admin", f"role mismatch: {decoded['role']!r}"
    assert "exp" in decoded, "decoded payload must contain 'exp'"


# ---------------------------------------------------------------------------
# Test 02: get_current_user accepts Bearer header
# ---------------------------------------------------------------------------

def _test_02_get_current_user_bearer_header() -> None:
    """get_current_user resolves the user from a valid Authorization: Bearer header."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    token = create_access_token({"sub": "pam_admin", "role": "admin"})

    result = _run_async(get_current_user(
        authorization=f"Bearer {token}",
        access_token=None,
    ))

    assert result["sub"] == "pam_admin", f"Expected sub='pam_admin', got {result['sub']!r}"
    assert result["role"] == "admin", f"Expected role='admin', got {result['role']!r}"


# ---------------------------------------------------------------------------
# Test 03: get_current_user accepts cookie
# ---------------------------------------------------------------------------

def _test_03_get_current_user_cookie() -> None:
    """get_current_user resolves the user from a valid access_token cookie."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    token = create_access_token({"sub": "lowes_retailer", "role": "retailer", "retailer_slug": "lowes"})

    result = _run_async(get_current_user(
        authorization=None,
        access_token=token,
    ))

    assert result["sub"] == "lowes_retailer", f"sub mismatch: {result['sub']!r}"
    assert result["role"] == "retailer"
    assert result.get("retailer_slug") == "lowes"


# ---------------------------------------------------------------------------
# Test 04: get_current_user prefers Bearer over cookie
# ---------------------------------------------------------------------------

def _test_04_get_current_user_bearer_priority() -> None:
    """Bearer header takes priority over cookie when both are present."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    bearer_token = create_access_token({"sub": "pam_admin", "role": "admin"})
    cookie_token = create_access_token({"sub": "lowes_retailer", "role": "retailer"})

    result = _run_async(get_current_user(
        authorization=f"Bearer {bearer_token}",
        access_token=cookie_token,
    ))

    # Bearer header wins — sub should be pam_admin not lowes_retailer
    assert result["sub"] == "pam_admin", \
        f"Bearer should take priority, got sub={result['sub']!r}"


# ---------------------------------------------------------------------------
# Test 05: get_current_user raises 401 when no token provided
# ---------------------------------------------------------------------------

def _test_05_get_current_user_no_token_raises_401() -> None:
    """get_current_user raises HTTP 401 when neither Bearer header nor cookie is present."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    raised = False
    status_code = None
    try:
        _run_async(get_current_user(authorization=None, access_token=None))
    except HTTPException as exc:
        raised = True
        status_code = exc.status_code

    assert raised, "Expected HTTPException when no token is provided"
    assert status_code == 401, f"Expected 401, got {status_code}"


# ---------------------------------------------------------------------------
# Test 06: decode_token raises 401 for expired token
# ---------------------------------------------------------------------------

def _test_06_decode_token_expired_raises_401() -> None:
    """decode_token raises HTTP 401 for a token that has already expired."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    # Create a token that expired 5 minutes ago
    expired_token = create_access_token(
        {"sub": "pam_admin", "role": "admin"},
        expires_minutes=-5,
    )

    raised = False
    status_code = None
    try:
        decode_token(expired_token)
    except HTTPException as exc:
        raised = True
        status_code = exc.status_code

    assert raised, "Expected HTTPException for expired token"
    assert status_code == 401, f"Expected 401, got {status_code}"


# ---------------------------------------------------------------------------
# Test 07: require_role — matching role passes
# ---------------------------------------------------------------------------

def _test_07_require_role_pass() -> None:
    """require_role('admin') passes when the user has role='admin'."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    admin_user = {"sub": "pam_admin", "role": "admin", "retailer_slug": None}
    checker = require_role("admin")

    # Call _check directly, bypassing FastAPI DI
    result = _run_async(checker(user=admin_user))
    assert result == admin_user, f"require_role should return the user dict: {result}"


# ---------------------------------------------------------------------------
# Test 08: require_role — wrong role raises 403
# ---------------------------------------------------------------------------

def _test_08_require_role_fail() -> None:
    """require_role('admin') raises HTTP 403 when the user has role='supplier'."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    supplier_user = {"sub": "acme_supplier", "role": "supplier", "supplier_slug": "acme"}
    checker = require_role("admin")

    raised = False
    status_code = None
    try:
        _run_async(checker(user=supplier_user))
    except HTTPException as exc:
        raised = True
        status_code = exc.status_code

    assert raised, "Expected HTTPException for wrong role"
    assert status_code == 403, f"Expected 403, got {status_code}"


# ---------------------------------------------------------------------------
# Test 09: authenticate_user — _DEV_USERS fallback path (no live DB)
# ---------------------------------------------------------------------------

def _test_09_authenticate_user_dev_fallback() -> None:
    """authenticate_user returns user dict via _DEV_USERS fallback when DB is unreachable.

    In CI / dev without a running Postgres, the DB connection attempt raises
    an exception; authenticate_user catches it and falls back to _DEV_USERS
    bcrypt verification — so valid creds return a user record and invalid creds
    return None, with no live DB required.
    """
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    # Valid credentials — falls back to _DEV_USERS bcrypt verification
    user = _run_async(authenticate_user("pam_admin", "certportal_admin"))
    assert user is not None, "Expected user dict for valid credentials, got None"
    assert user["sub"] == "pam_admin"
    assert user["role"] == "admin"
    assert user.get("retailer_slug") is None

    # Wrong password
    bad = _run_async(authenticate_user("pam_admin", "wrong_password"))
    assert bad is None, f"Expected None for wrong password, got: {bad}"

    # Non-existent user
    nonexistent = _run_async(authenticate_user("nobody", "certportal_admin"))
    assert nonexistent is None, f"Expected None for unknown user, got: {nonexistent}"


# ---------------------------------------------------------------------------
# Test 10: _DEV_USERS structure — 3 users with bcrypt hashed passwords
# ---------------------------------------------------------------------------

def _test_10_dev_users_structure() -> None:
    """_DEV_USERS has exactly 3 users (admin, retailer, supplier) with bcrypt hashes."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    required_keys = {"hashed_password", "role", "retailer_slug", "supplier_slug"}
    expected_roles = {"admin", "retailer", "supplier"}

    assert len(_DEV_USERS) == 3, \
        f"Expected 3 dev users, got {len(_DEV_USERS)}: {list(_DEV_USERS.keys())}"

    actual_roles = {v["role"] for v in _DEV_USERS.values()}
    assert actual_roles == expected_roles, \
        f"Expected roles {expected_roles}, got {actual_roles}"

    for username, user in _DEV_USERS.items():
        missing = required_keys - set(user.keys())
        assert not missing, f"User '{username}' missing keys: {missing}"

        # Hashed password must be a bcrypt hash (starts with $2b$)
        hp = user["hashed_password"]
        assert hp.startswith("$2b$"), \
            f"User '{username}' hashed_password is not a bcrypt hash: {hp[:20]!r}"

        assert user["role"] in expected_roles, \
            f"User '{username}' has invalid role: {user['role']!r}"

    # Verify _verify_password works against the stored hashes
    assert _verify_password("certportal_admin",    _DEV_USERS["pam_admin"]["hashed_password"])
    assert _verify_password("certportal_retailer", _DEV_USERS["lowes_retailer"]["hashed_password"])
    assert _verify_password("certportal_supplier", _DEV_USERS["acme_supplier"]["hashed_password"])


# ---------------------------------------------------------------------------
# Test 11: authenticate_user — DB path with mocked asyncpg
# ---------------------------------------------------------------------------

def _test_11_authenticate_user_db_path() -> None:
    """authenticate_user uses portal_users DB row when asyncpg returns a record.

    asyncpg.connect is patched to return a mock connection whose fetchrow()
    returns a realistic fake record — verifying that the DB code path executes
    and that bcrypt verification is applied to the row's hashed_password.
    """
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    import bcrypt as _bcrypt_lib  # same lib used by auth.py
    from unittest.mock import AsyncMock, patch
    import certportal.core.auth as _auth_mod

    # Build a fake DB record with a known password
    db_password = "db_secure_password"
    db_hash = _bcrypt_lib.hashpw(db_password.encode(), _bcrypt_lib.gensalt(rounds=4)).decode()

    fake_row = {
        "username": "db_test_user",
        "hashed_password": db_hash,
        "role": "retailer",
        "retailer_slug": "testco",
        "supplier_slug": None,
    }

    # Mock asyncpg.connect to return a mock connection
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_row)
    mock_conn.close = AsyncMock()

    with patch.object(_auth_mod.asyncpg, "connect", AsyncMock(return_value=mock_conn)):
        # Valid DB credentials
        user = _run_async(authenticate_user("db_test_user", db_password))
        assert user is not None, "Expected user dict from DB path, got None"
        assert user["sub"] == "db_test_user"
        assert user["role"] == "retailer"
        assert user["retailer_slug"] == "testco"

        # Wrong password — DB path returns None (no _DEV_USERS fallback for existing DB user)
        mock_conn.fetchrow = AsyncMock(return_value=fake_row)
        bad = _run_async(authenticate_user("db_test_user", "wrong_password"))
        assert bad is None, f"Expected None for wrong DB password, got: {bad}"

        # User not found in DB (row = None) — falls through to _DEV_USERS
        mock_conn.fetchrow = AsyncMock(return_value=None)
        # "pam_admin" is in _DEV_USERS, so it should still authenticate via fallback
        fallback_user = _run_async(authenticate_user("pam_admin", "certportal_admin"))
        assert fallback_user is not None, \
            "Expected _DEV_USERS fallback when DB row is None"
        assert fallback_user["sub"] == "pam_admin"


# ---------------------------------------------------------------------------
# Test 12: hash_password — bcrypt round-trip
# ---------------------------------------------------------------------------

def _test_12_hash_password_round_trip() -> None:
    """hash_password produces a bcrypt $2b$ hash verified by _verify_password."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    plain = "Sprint3SecurePass!"
    h = hash_password(plain)

    assert isinstance(h, str), f"Expected str hash, got {type(h)}"
    assert h.startswith("$2b$"), f"hash must start with '$2b$', got: {h[:10]!r}"
    assert len(h) >= 60, f"bcrypt hash should be >=60 chars, got {len(h)}"

    # Correct password verifies
    assert _verify_password(plain, h), "hash should verify against the original password"

    # Wrong passwords must not verify
    assert not _verify_password("wrong", h), "wrong password must not verify"
    assert not _verify_password("", h), "empty password must not verify"
    assert not _verify_password(plain + " ", h), "padded password must not verify"

    # Two calls produce different salts
    h2 = hash_password(plain)
    assert h != h2, "bcrypt should generate a unique salt each call"
    assert _verify_password(plain, h2), "second hash should also verify"


# ---------------------------------------------------------------------------
# Test 13: /register endpoint — validation logic via TestClient + mocked DB
# ---------------------------------------------------------------------------

def _test_13_register_endpoint() -> None:
    """POST /register validates input and (with mocked DB) redirects on success/error.

    Checks:
      - Password mismatch  → error redirect
      - Password too short → error redirect
      - Invalid role       → error redirect
      - Valid form data    → success redirect (mocked conn.execute)
    """
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    from unittest.mock import AsyncMock, MagicMock, patch
    from fastapi.testclient import TestClient
    from certportal.core.database import get_connection

    # Build an admin JWT for authorization
    admin_token = create_access_token({
        "sub": "pam_admin", "role": "admin",
        "retailer_slug": None, "supplier_slug": None,
    })
    auth_header = {"Authorization": f"Bearer {admin_token}"}

    # Mock DB dependency: conn.execute returns INSERT success
    async def _mock_conn():
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
        yield mock_conn

    # Patch the asyncpg pool so the lifespan doesn't try to connect
    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    import certportal.core.database as _dbmod
    with patch.object(_dbmod, "_pool", mock_pool):
        from portals.pam import app
        app.dependency_overrides[get_connection] = _mock_conn
        try:
            client = TestClient(app, raise_server_exceptions=True)

            # ── passwords do not match ──────────────────────────────────
            r = client.post("/register", data={
                "username": "testuser", "password": "SecurePass1",
                "confirm_password": "DifferentPass1", "role": "retailer",
                "retailer_slug": "", "supplier_slug": "",
            }, headers=auth_header, follow_redirects=False)
            assert r.status_code == 302, f"expected 302, got {r.status_code}"
            assert "error=" in r.headers.get("location", ""), \
                f"expected error in redirect, got: {r.headers.get('location')}"
            assert "match" in r.headers["location"].lower() or \
                   "Passwords" in r.headers["location"], \
                f"redirect should mention password mismatch: {r.headers['location']}"

            # ── password too short ──────────────────────────────────────
            r = client.post("/register", data={
                "username": "testuser", "password": "short",
                "confirm_password": "short", "role": "retailer",
                "retailer_slug": "", "supplier_slug": "",
            }, headers=auth_header, follow_redirects=False)
            assert r.status_code == 302
            assert "error=" in r.headers.get("location", "")

            # ── invalid role ────────────────────────────────────────────
            r = client.post("/register", data={
                "username": "testuser", "password": "SecurePass1",
                "confirm_password": "SecurePass1", "role": "superuser",
                "retailer_slug": "", "supplier_slug": "",
            }, headers=auth_header, follow_redirects=False)
            assert r.status_code == 302
            assert "error=" in r.headers.get("location", "")

            # ── valid registration (mocked DB) ──────────────────────────
            r = client.post("/register", data={
                "username": "new_retailer", "password": "SecurePass123",
                "confirm_password": "SecurePass123", "role": "retailer",
                "retailer_slug": "lowes", "supplier_slug": "",
            }, headers=auth_header, follow_redirects=False)
            assert r.status_code == 302, f"expected 302, got {r.status_code}: {r.text[:200]}"
            loc = r.headers.get("location", "")
            assert "msg=" in loc, f"expected success msg in redirect, got: {loc}"

        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 14: /change-password endpoint — validation + mocked DB
# ---------------------------------------------------------------------------

def _test_14_change_password_endpoint() -> None:
    """POST /change-password validates passwords and updates DB on success.

    Checks:
      - Password mismatch        → error redirect
      - New password too short   → error redirect
      - Wrong current password   → error redirect (authenticate_user returns None)
      - Valid change (mocked)    → success redirect
    """
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    from unittest.mock import AsyncMock, MagicMock, patch
    from fastapi.testclient import TestClient
    from certportal.core.database import get_connection
    import certportal.core.auth as _auth_mod
    import certportal.core.database as _dbmod

    admin_token = create_access_token({
        "sub": "pam_admin", "role": "admin",
        "retailer_slug": None, "supplier_slug": None,
    })
    auth_header = {"Authorization": f"Bearer {admin_token}"}

    async def _mock_conn():
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        yield mock_conn

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    with patch.object(_dbmod, "_pool", mock_pool):
        from portals.pam import app
        app.dependency_overrides[get_connection] = _mock_conn
        try:
            client = TestClient(app, raise_server_exceptions=True)

            # ── new passwords do not match ──────────────────────────────
            r = client.post("/change-password", data={
                "current_password": "certportal_admin",
                "new_password": "NewSecurePass1",
                "confirm_password": "NewSecurePass2",
            }, headers=auth_header, follow_redirects=False)
            assert r.status_code == 302
            assert "error=" in r.headers.get("location", "")

            # ── new password too short ──────────────────────────────────
            r = client.post("/change-password", data={
                "current_password": "certportal_admin",
                "new_password": "short",
                "confirm_password": "short",
            }, headers=auth_header, follow_redirects=False)
            assert r.status_code == 302
            assert "error=" in r.headers.get("location", "")

            # ── wrong current password ──────────────────────────────────
            # Patch authenticate_user to return None (wrong password)
            with patch.object(_auth_mod, "authenticate_user", AsyncMock(return_value=None)):
                r = client.post("/change-password", data={
                    "current_password": "wrong_password",
                    "new_password": "NewSecurePass1",
                    "confirm_password": "NewSecurePass1",
                }, headers=auth_header, follow_redirects=False)
                assert r.status_code == 302
                loc = r.headers.get("location", "")
                assert "error=" in loc, f"expected error in redirect, got: {loc}"
                assert "incorrect" in loc.lower() or "Current" in loc, \
                    f"redirect should mention wrong current password: {loc}"

            # ── valid change (mocked DB UPDATE returns UPDATE 1) ────────
            # Patch authenticate_user to succeed (correct current password)
            fake_user = {
                "sub": "pam_admin", "role": "admin",
                "retailer_slug": None, "supplier_slug": None,
            }
            with patch.object(_auth_mod, "authenticate_user", AsyncMock(return_value=fake_user)):
                r = client.post("/change-password", data={
                    "current_password": "certportal_admin",
                    "new_password": "NewSecurePass1!",
                    "confirm_password": "NewSecurePass1!",
                }, headers=auth_header, follow_redirects=False)
                assert r.status_code == 302, f"expected 302, got {r.status_code}: {r.text[:200]}"
                loc = r.headers.get("location", "")
                assert "msg=" in loc, f"expected success msg in redirect, got: {loc}"

        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 15: create_refresh_token + decode_refresh_token round-trip
# ---------------------------------------------------------------------------

def _test_15_refresh_token_round_trip() -> None:
    """create_refresh_token encodes claims; decode_refresh_token retrieves them.

    Verifies:
      - type claim is 'refresh' in the encoded token
      - payload round-trips sub, role, retailer_slug
      - decode_refresh_token raises 401 if given a plain access token
    """
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    claims = build_token_claims({
        "sub": "lowes_retailer", "role": "retailer",
        "retailer_slug": "lowes", "supplier_slug": None,
    })
    # build_token_claims tags type='access'; create_refresh_token overrides to 'refresh'
    refresh = create_refresh_token(claims)
    assert isinstance(refresh, str) and len(refresh) > 20, "Expected JWT string"

    decoded = decode_refresh_token(refresh)
    assert decoded["sub"] == "lowes_retailer", f"sub mismatch: {decoded['sub']!r}"
    assert decoded["role"] == "retailer", f"role mismatch: {decoded['role']!r}"
    assert decoded["type"] == "refresh", f"type must be 'refresh', got {decoded['type']!r}"
    assert decoded.get("retailer_slug") == "lowes"
    assert "exp" in decoded

    # decode_refresh_token must reject a regular access token
    access = create_access_token(claims)
    raised = False
    try:
        decode_refresh_token(access)
    except HTTPException as exc:
        raised = True
        assert exc.status_code == 401, f"Expected 401, got {exc.status_code}"
    assert raised, "decode_refresh_token should raise 401 for an access token"


# ---------------------------------------------------------------------------
# Test 16: get_current_user rejects refresh token used as access token
# ---------------------------------------------------------------------------

def _test_16_refresh_token_rejected_as_access() -> None:
    """get_current_user raises 401 when a refresh token is supplied as an access token.

    ADR-017: type='refresh' tokens are explicitly blocked by get_current_user().
    Tokens without a 'type' claim remain valid for backward compatibility.
    """
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    claims = build_token_claims({
        "sub": "pam_admin", "role": "admin",
        "retailer_slug": None, "supplier_slug": None,
    })
    refresh = create_refresh_token(claims)

    raised = False
    status_code = None
    try:
        _run_async(get_current_user(authorization=f"Bearer {refresh}", access_token=None))
    except HTTPException as exc:
        raised = True
        status_code = exc.status_code

    assert raised, "Expected HTTPException when refresh token used as access token"
    assert status_code == 401, f"Expected 401, got {status_code}"


# ---------------------------------------------------------------------------
# Test 17: POST /token/refresh via TestClient -> new access token returned
# ---------------------------------------------------------------------------

def _test_17_token_refresh_endpoint() -> None:
    """POST /token/refresh with valid refresh cookie returns new access token (ADR-017).

    Verifies:
      - 200 JSON response with access_token + token_type='bearer'
      - Returned access token decodes correctly with preserved sub + role
      - access_token cookie is set on the response
      - Missing refresh_token cookie returns 401
    """
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    from unittest.mock import AsyncMock, MagicMock, patch
    from fastapi.testclient import TestClient
    import certportal.core.database as _dbmod

    claims = build_token_claims({
        "sub": "pam_admin", "role": "admin",
        "retailer_slug": None, "supplier_slug": None,
    })
    valid_refresh = create_refresh_token(claims)

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    with patch.object(_dbmod, "_pool", mock_pool):
        from portals.pam import app
        try:
            client = TestClient(app, raise_server_exceptions=True)

            # ── valid refresh cookie -> new access token ────────────────────
            client.cookies.set("refresh_token", valid_refresh)
            r = client.post("/token/refresh")
            assert r.status_code == 200, \
                f"Expected 200, got {r.status_code}: {r.text[:200]}"
            body = r.json()
            assert "access_token" in body, f"Expected access_token in body: {body}"
            assert body.get("token_type") == "bearer"

            # Returned access token must decode correctly
            new_access = body["access_token"]
            decoded = decode_token(new_access)
            assert decoded["sub"] == "pam_admin", f"sub mismatch: {decoded.get('sub')!r}"
            assert decoded.get("type") == "access", \
                f"type must be 'access', got {decoded.get('type')!r}"

            # access_token cookie must be set on the response
            assert "access_token" in r.cookies, \
                "access_token cookie missing from /token/refresh response"

            # ── no refresh cookie -> 401 ────────────────────────────────────
            client.cookies.clear()
            r = client.post("/token/refresh")
            assert r.status_code == 401, \
                f"Expected 401 for missing refresh token, got {r.status_code}"

        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 18: JTI claim present in both token types (ADR-021)
# ---------------------------------------------------------------------------

def _test_18_jti_in_tokens() -> None:
    """create_access_token and create_refresh_token both include a 'jti' claim (ADR-021).

    Verifies:
      - 'jti' key is present in decoded access token payload
      - 'jti' key is present in decoded refresh token payload
      - Each jti is a 32-char hex string (secrets.token_hex(16))
      - Two successive tokens have different jtis (uniqueness)
    """
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    claims = build_token_claims({
        "sub": "pam_admin", "role": "admin",
        "retailer_slug": None, "supplier_slug": None,
    })

    # Access token
    access = create_access_token(claims)
    a_payload = decode_token(access)
    assert "jti" in a_payload, f"'jti' missing from access token payload: {a_payload.keys()}"
    assert isinstance(a_payload["jti"], str) and len(a_payload["jti"]) == 32, \
        f"jti must be 32-char hex, got {a_payload['jti']!r}"

    # Refresh token
    refresh = create_refresh_token(claims)
    r_payload = decode_token(refresh)
    assert "jti" in r_payload, f"'jti' missing from refresh token payload: {r_payload.keys()}"
    assert isinstance(r_payload["jti"], str) and len(r_payload["jti"]) == 32, \
        f"jti must be 32-char hex, got {r_payload['jti']!r}"

    # Uniqueness: two access tokens should have different jtis
    access2 = create_access_token(claims)
    a2_payload = decode_token(access2)
    assert a_payload["jti"] != a2_payload["jti"], "Successive tokens should have unique jtis"


# ---------------------------------------------------------------------------
# Test 19: revoke_jti() inserts JTI into revoked_tokens (ADR-021)
# ---------------------------------------------------------------------------

def _test_19_revoke_jti_inserts() -> None:
    """revoke_jti() inserts the JTI into revoked_tokens when a pool is configured.

    Verifies:
      - execute() called with INSERT INTO revoked_tokens ... containing correct jti
      - revoke_jti() is a no-op when pool is None (no execute() call)
    """
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    from unittest.mock import AsyncMock, MagicMock
    import certportal.core.auth as _auth_module
    from certportal.core.auth import revoke_jti

    claims = build_token_claims({
        "sub": "pam_admin", "role": "admin",
        "retailer_slug": None, "supplier_slug": None,
    })
    access = create_access_token(claims)
    a_payload = decode_token(access)
    expected_jti = a_payload["jti"]
    expected_exp = a_payload["exp"]

    # Build mock pool
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=None)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_ctx)

    # ── With pool configured: execute() must be called ────────────────────
    _auth_module.set_revocation_pool(mock_pool)
    try:
        _run_async(revoke_jti(expected_jti, expected_exp))
        assert mock_conn.execute.called, "Expected execute() to be called for JTI insert"
        call_sql = mock_conn.execute.call_args[0][0]
        assert "revoked_tokens" in call_sql, \
            f"SQL does not reference revoked_tokens: {call_sql!r}"
        call_jti = mock_conn.execute.call_args[0][1]
        assert call_jti == expected_jti, \
            f"JTI mismatch: passed {call_jti!r}, expected {expected_jti!r}"
    finally:
        _auth_module.set_revocation_pool(None)

    # ── No pool: revoke_jti() is a no-op (must not raise) ─────────────────
    mock_conn2 = AsyncMock()
    mock_conn2.execute = AsyncMock(return_value=None)
    _auth_module.set_revocation_pool(None)
    _run_async(revoke_jti(expected_jti, expected_exp))   # no-op, should not raise
    assert not mock_conn2.execute.called, "execute() must not be called when pool is None"


# ---------------------------------------------------------------------------
# Test 20: get_current_user raises HTTP 401 for revoked token (ADR-021)
# ---------------------------------------------------------------------------

def _test_20_revoked_token_rejected() -> None:
    """get_current_user raises HTTP 401 when the token's JTI is in revoked_tokens.

    ADR-021: revocation check fires when _revocation_pool is configured.
    """
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    from unittest.mock import AsyncMock, MagicMock
    import certportal.core.auth as _auth_module

    claims = build_token_claims({
        "sub": "pam_admin", "role": "admin",
        "retailer_slug": None, "supplier_slug": None,
    })
    access = create_access_token(claims)

    # Mock pool whose fetchval() returns 1 (token found → revoked)
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_ctx)

    _auth_module.set_revocation_pool(mock_pool)
    try:
        raised = False
        status_code = None
        try:
            _run_async(get_current_user(authorization=f"Bearer {access}", access_token=None))
        except HTTPException as exc:
            raised = True
            status_code = exc.status_code

        assert raised, "Expected HTTPException for revoked token"
        assert status_code == 401, f"Expected 401, got {status_code}"

        # Verify fetchval was called with the right SQL (checking revoked_tokens)
        assert mock_conn.fetchval.called, "Expected fetchval() to query revoked_tokens"
        fetch_sql = mock_conn.fetchval.call_args[0][0]
        assert "revoked_tokens" in fetch_sql, \
            f"fetchval SQL does not query revoked_tokens: {fetch_sql!r}"
    finally:
        _auth_module.set_revocation_pool(None)


# ---------------------------------------------------------------------------
# Test 21: create_password_reset_token inserts row + returns URL-safe token (ADR-023)
# ---------------------------------------------------------------------------

def _test_21_create_password_reset_token() -> None:
    """create_password_reset_token generates URL-safe token and inserts into DB."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    from unittest.mock import AsyncMock, MagicMock

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=None)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_ctx)

    token = _run_async(create_password_reset_token("pam_admin", mock_pool))

    # token_urlsafe(32) produces 43 URL-safe characters
    assert isinstance(token, str), "Expected str token"
    assert len(token) >= 43, f"Expected >=43 chars, got {len(token)}: {token!r}"

    # execute() must be called with INSERT INTO password_reset_tokens
    assert mock_conn.execute.called, "Expected execute() to be called"
    call_sql = mock_conn.execute.call_args[0][0]
    assert "password_reset_tokens" in call_sql, \
        f"SQL does not reference password_reset_tokens: {call_sql!r}"
    call_token = mock_conn.execute.call_args[0][1]
    assert call_token == token, f"Token in SQL ({call_token!r}) != returned token ({token!r})"


# ---------------------------------------------------------------------------
# Test 22: validate_password_reset_token marks used + returns username (ADR-023)
# ---------------------------------------------------------------------------

def _test_22_validate_password_reset_token() -> None:
    """validate_password_reset_token: valid row -> username + UPDATE used=TRUE; None if no row."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    from unittest.mock import AsyncMock, MagicMock

    # ── Valid token: row found -> returns username, UPDATE called ──────────
    mock_conn_ok = AsyncMock()
    mock_conn_ok.fetchrow = AsyncMock(return_value={"username": "pam_admin"})
    mock_conn_ok.execute = AsyncMock(return_value=None)
    mock_ctx_ok = AsyncMock()
    mock_ctx_ok.__aenter__ = AsyncMock(return_value=mock_conn_ok)
    mock_ctx_ok.__aexit__ = AsyncMock(return_value=False)
    mock_pool_ok = MagicMock()
    mock_pool_ok.acquire = MagicMock(return_value=mock_ctx_ok)

    result = _run_async(validate_password_reset_token("valid_token_abc", mock_pool_ok))
    assert result == "pam_admin", f"Expected 'pam_admin', got {result!r}"
    assert mock_conn_ok.execute.called, "Expected execute() (UPDATE used=TRUE) to be called"
    update_sql = mock_conn_ok.execute.call_args[0][0]
    assert "used" in update_sql.lower(), f"UPDATE SQL does not set used: {update_sql!r}"

    # ── Invalid/expired token: fetchrow returns None -> returns None ───────
    mock_conn_bad = AsyncMock()
    mock_conn_bad.fetchrow = AsyncMock(return_value=None)
    mock_conn_bad.execute = AsyncMock(return_value=None)
    mock_ctx_bad = AsyncMock()
    mock_ctx_bad.__aenter__ = AsyncMock(return_value=mock_conn_bad)
    mock_ctx_bad.__aexit__ = AsyncMock(return_value=False)
    mock_pool_bad = MagicMock()
    mock_pool_bad.acquire = MagicMock(return_value=mock_ctx_bad)

    result_bad = _run_async(validate_password_reset_token("expired_token", mock_pool_bad))
    assert result_bad is None, f"Expected None for invalid token, got {result_bad!r}"
    assert not mock_conn_bad.execute.called, \
        "execute() (UPDATE) must NOT be called when token is invalid"


# ---------------------------------------------------------------------------
# Test 23: POST /forgot-password always redirects 302 reset_sent (ADR-023)
# ---------------------------------------------------------------------------

def _test_23_forgot_password_redirect() -> None:
    """POST /forgot-password always redirects to /login?msg=reset_sent (no enumeration)."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    from unittest.mock import AsyncMock, MagicMock, patch
    from fastapi.testclient import TestClient

    # Import pam app (uses TestClient for portal route testing)
    try:
        from portals.pam import app as pam_app  # type: ignore[import]
    except Exception as exc:
        raise AssertionError(f"Cannot import portals.pam: {exc}") from exc

    client = TestClient(pam_app, raise_server_exceptions=False)

    # ── Case 1: user exists with email -> token generated, email sent ──────
    mock_row = {"email": "pam@example.com"}
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value=mock_row)

    with patch("portals.pam.create_password_reset_token", new=AsyncMock(return_value="faketoken123")), \
         patch("portals.pam.send_reset_email", return_value=True), \
         patch("portals.pam.get_pool", new=AsyncMock(return_value=mock_pool)):
        resp = client.post("/forgot-password", data={"username": "pam_admin"}, follow_redirects=False)

    assert resp.status_code == 302, f"Expected 302, got {resp.status_code}"
    assert "reset_sent" in resp.headers.get("location", ""), \
        f"Expected reset_sent in Location: {resp.headers.get('location')!r}"

    # ── Case 2: user not found -> still 302 reset_sent (no enumeration) ───
    mock_pool2 = AsyncMock()
    mock_pool2.fetchrow = AsyncMock(return_value=None)

    with patch("portals.pam.create_password_reset_token", new=AsyncMock(return_value="tok")), \
         patch("portals.pam.send_reset_email", return_value=False), \
         patch("portals.pam.get_pool", new=AsyncMock(return_value=mock_pool2)):
        resp2 = client.post("/forgot-password", data={"username": "nonexistent"}, follow_redirects=False)

    assert resp2.status_code == 302, f"Expected 302 for unknown user, got {resp2.status_code}"
    assert "reset_sent" in resp2.headers.get("location", ""), \
        f"Expected reset_sent for unknown user: {resp2.headers.get('location')!r}"


# ---------------------------------------------------------------------------
# Test 24: POST /reset-password validates and updates password (ADR-023)
# ---------------------------------------------------------------------------

def _test_24_reset_password_submit() -> None:
    """POST /reset-password: valid token -> 302 password_changed; bad inputs -> 302 error."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    from unittest.mock import AsyncMock, patch
    from fastapi.testclient import TestClient

    try:
        from portals.pam import app as pam_app  # type: ignore[import]
    except Exception as exc:
        raise AssertionError(f"Cannot import portals.pam: {exc}") from exc

    client = TestClient(pam_app, raise_server_exceptions=False)

    # ── Password mismatch -> error redirect ────────────────────────────────
    with patch("portals.pam.validate_password_reset_token", new=AsyncMock(return_value="pam_admin")):
        resp_mm = client.post(
            "/reset-password",
            data={"token": "tok", "new_password": "pass1234", "confirm_password": "different"},
            follow_redirects=False,
        )
    assert resp_mm.status_code == 302
    assert "mismatch" in resp_mm.headers.get("location", "").lower() or \
           "error" in resp_mm.headers.get("location", "").lower(), \
        f"Expected error redirect for mismatch: {resp_mm.headers.get('location')!r}"

    # ── Password too short -> error redirect ──────────────────────────────
    with patch("portals.pam.validate_password_reset_token", new=AsyncMock(return_value="pam_admin")):
        resp_short = client.post(
            "/reset-password",
            data={"token": "tok", "new_password": "short", "confirm_password": "short"},
            follow_redirects=False,
        )
    assert resp_short.status_code == 302
    assert "error" in resp_short.headers.get("location", "").lower() or \
           "too_short" in resp_short.headers.get("location", "").lower(), \
        f"Expected error for short password: {resp_short.headers.get('location')!r}"

    # ── Valid token + valid passwords -> 302 password_changed ─────────────
    mock_pool = AsyncMock()
    mock_pool.execute = AsyncMock(return_value=None)

    with patch("portals.pam.validate_password_reset_token", new=AsyncMock(return_value="pam_admin")), \
         patch("portals.pam.get_pool", new=AsyncMock(return_value=mock_pool)):
        resp_ok = client.post(
            "/reset-password",
            data={"token": "goodtok", "new_password": "newpass8!", "confirm_password": "newpass8!"},
            follow_redirects=False,
        )
    assert resp_ok.status_code == 302, f"Expected 302, got {resp_ok.status_code}"
    assert "password_changed" in resp_ok.headers.get("location", ""), \
        f"Expected password_changed in Location: {resp_ok.headers.get('location')!r}"
    assert mock_pool.execute.called, "Expected pool.execute() to UPDATE portal_users"
    update_sql = mock_pool.execute.call_args[0][0]
    assert "portal_users" in update_sql, f"UPDATE SQL does not touch portal_users: {update_sql!r}"


# ---------------------------------------------------------------------------
# Test 25: cleanup_expired_revoked_tokens() deletes expired rows (ADR-025)
# ---------------------------------------------------------------------------

def _test_25_cleanup_expired_revoked_tokens() -> None:
    """cleanup_expired_revoked_tokens: returns row count when pool set; 0 when None."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    from unittest.mock import AsyncMock, MagicMock
    import certportal.core.auth as _auth_module
    from certportal.core.auth import cleanup_expired_revoked_tokens  # type: ignore[import]

    # ── With pool configured: DELETE called, returns row count ────────────
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="DELETE 3")
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_ctx)

    _auth_module.set_revocation_pool(mock_pool)
    try:
        count = _run_async(cleanup_expired_revoked_tokens())
        assert count == 3, f"Expected 3 rows deleted, got {count}"
        assert mock_conn.execute.called, "Expected execute() to be called"
        sql = mock_conn.execute.call_args[0][0]
        assert "expires_at" in sql and "NOW()" in sql, \
            f"DELETE SQL does not check expires_at < NOW(): {sql!r}"
        assert "revoked_tokens" in sql, f"DELETE SQL does not touch revoked_tokens: {sql!r}"
    finally:
        _auth_module.set_revocation_pool(None)

    # ── No pool configured: returns 0 without touching DB ─────────────────
    mock_conn2 = AsyncMock()
    count_noop = _run_async(cleanup_expired_revoked_tokens())
    assert count_noop == 0, f"Expected 0 when pool is None, got {count_noop}"
    assert not mock_conn2.execute.called, "execute() must NOT be called when pool is None"


# ---------------------------------------------------------------------------
# Suite entry point
# ---------------------------------------------------------------------------

def run() -> list[dict]:
    """Run all 25 auth tests. No live DB, S3, or OpenAI required."""
    tests = [
        ("suite_a_test_01", "Auth: create_access_token + decode_token round-trip",            _test_01_token_round_trip),
        ("suite_a_test_02", "Auth: get_current_user resolves from Bearer header",              _test_02_get_current_user_bearer_header),
        ("suite_a_test_03", "Auth: get_current_user resolves from cookie",                     _test_03_get_current_user_cookie),
        ("suite_a_test_04", "Auth: Bearer header takes priority over cookie",                  _test_04_get_current_user_bearer_priority),
        ("suite_a_test_05", "Auth: no token raises HTTP 401",                                 _test_05_get_current_user_no_token_raises_401),
        ("suite_a_test_06", "Auth: expired token raises HTTP 401",                            _test_06_decode_token_expired_raises_401),
        ("suite_a_test_07", "Auth: require_role matching role passes",                        _test_07_require_role_pass),
        ("suite_a_test_08", "Auth: require_role wrong role raises HTTP 403",                  _test_08_require_role_fail),
        ("suite_a_test_09", "Auth: authenticate_user valid/invalid via _DEV_USERS fallback",  _test_09_authenticate_user_dev_fallback),
        ("suite_a_test_10", "Auth: _DEV_USERS has 3 users with bcrypt hashes",               _test_10_dev_users_structure),
        ("suite_a_test_11", "Auth: authenticate_user DB path (mocked asyncpg)",              _test_11_authenticate_user_db_path),
        ("suite_a_test_12", "Auth: hash_password produces valid bcrypt round-trip",          _test_12_hash_password_round_trip),
        ("suite_a_test_13", "Auth: /register validates input, redirects on success",         _test_13_register_endpoint),
        ("suite_a_test_14", "Auth: /change-password validates and updates on success",       _test_14_change_password_endpoint),
        ("suite_a_test_15", "Auth: create_refresh_token + decode_refresh_token round-trip",  _test_15_refresh_token_round_trip),
        ("suite_a_test_16", "Auth: refresh token rejected by get_current_user (ADR-017)",    _test_16_refresh_token_rejected_as_access),
        ("suite_a_test_17", "Auth: POST /token/refresh returns new access token",            _test_17_token_refresh_endpoint),
        ("suite_a_test_18", "Auth: JTI claim present in access and refresh tokens (ADR-021)", _test_18_jti_in_tokens),
        ("suite_a_test_19", "Auth: revoke_jti() inserts JTI into revoked_tokens (ADR-021)",  _test_19_revoke_jti_inserts),
        ("suite_a_test_20", "Auth: get_current_user rejects revoked token -- 401 (ADR-021)", _test_20_revoked_token_rejected),
        ("suite_a_test_21", "Auth: create_password_reset_token inserts row + returns token (ADR-023)", _test_21_create_password_reset_token),
        ("suite_a_test_22", "Auth: validate_password_reset_token marks used + returns username (ADR-023)", _test_22_validate_password_reset_token),
        ("suite_a_test_23", "Auth: POST /forgot-password always redirects to reset_sent (ADR-023)", _test_23_forgot_password_redirect),
        ("suite_a_test_24", "Auth: POST /reset-password validates and updates password (ADR-023)", _test_24_reset_password_submit),
        ("suite_a_test_25", "Auth: cleanup_expired_revoked_tokens deletes expired JTIs (ADR-025)", _test_25_cleanup_expired_revoked_tokens),
    ]

    results = []
    for test_id, description, fn in tests:
        r = _run_test(test_id, fn)
        r["description"] = description
        results.append(r)
        status_str = r["status"].value
        reason_str = f" -- {r['reason'][:120]}" if r["reason"] else ""
        print(f"  [{status_str:4s}] {test_id}: {description}{reason_str}")

    return results
