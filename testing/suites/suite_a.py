"""
testing/suites/suite_a.py — Portal Auth Tests (ADR-014).

Tests certportal.core.auth: token creation/decoding, get_current_user dependency,
require_role factory, authenticate_user, and _DEV_USERS structure.

No live DB, S3, or network required — all auth logic is pure in-process.

Architecture coverage:
  ADR-014 — JWT HS256 via python-jose, httponly cookie + Bearer header dual-accept
  certportal.core.auth — create_access_token, decode_token, get_current_user,
                         require_role, authenticate_user, build_token_claims
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
        decode_token,
        get_current_user,
        require_role,
        authenticate_user,
        build_token_claims,
        _DEV_USERS,
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
# Test 09: authenticate_user — valid and invalid credentials
# ---------------------------------------------------------------------------

def _test_09_authenticate_user() -> None:
    """authenticate_user returns user dict on valid creds, None on bad password."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    # Valid credentials
    user = authenticate_user("pam_admin", "certportal_admin")
    assert user is not None, "Expected user dict for valid credentials, got None"
    assert user["sub"] == "pam_admin"
    assert user["role"] == "admin"

    # Wrong password
    bad = authenticate_user("pam_admin", "wrong_password")
    assert bad is None, f"Expected None for wrong password, got: {bad}"

    # Non-existent user
    nonexistent = authenticate_user("nobody", "certportal_admin")
    assert nonexistent is None, f"Expected None for unknown user, got: {nonexistent}"


# ---------------------------------------------------------------------------
# Test 10: _DEV_USERS structure — 3 users with required keys
# ---------------------------------------------------------------------------

def _test_10_dev_users_structure() -> None:
    """_DEV_USERS has exactly 3 users (admin, retailer, supplier) with required keys."""
    assert _AUTH_OK, f"auth import failed: {_IMPORT_ERRORS}"

    required_keys = {"password", "role", "retailer_slug", "supplier_slug"}
    expected_roles = {"admin", "retailer", "supplier"}

    assert len(_DEV_USERS) == 3, \
        f"Expected 3 dev users, got {len(_DEV_USERS)}: {list(_DEV_USERS.keys())}"

    actual_roles = {v["role"] for v in _DEV_USERS.values()}
    assert actual_roles == expected_roles, \
        f"Expected roles {expected_roles}, got {actual_roles}"

    for username, user in _DEV_USERS.items():
        missing = required_keys - set(user.keys())
        assert not missing, f"User '{username}' missing keys: {missing}"
        assert user["password"], f"User '{username}' has empty password"
        assert user["role"] in expected_roles, f"User '{username}' has invalid role: {user['role']!r}"


# ---------------------------------------------------------------------------
# Suite entry point
# ---------------------------------------------------------------------------

def run() -> list[dict]:
    """Run all 10 auth tests. No live DB, S3, or OpenAI required."""
    tests = [
        ("suite_a_test_01", "Auth: create_access_token + decode_token round-trip",          _test_01_token_round_trip),
        ("suite_a_test_02", "Auth: get_current_user resolves from Bearer header",            _test_02_get_current_user_bearer_header),
        ("suite_a_test_03", "Auth: get_current_user resolves from cookie",                   _test_03_get_current_user_cookie),
        ("suite_a_test_04", "Auth: Bearer header takes priority over cookie",                _test_04_get_current_user_bearer_priority),
        ("suite_a_test_05", "Auth: no token raises HTTP 401",                               _test_05_get_current_user_no_token_raises_401),
        ("suite_a_test_06", "Auth: expired token raises HTTP 401",                          _test_06_decode_token_expired_raises_401),
        ("suite_a_test_07", "Auth: require_role matching role passes",                      _test_07_require_role_pass),
        ("suite_a_test_08", "Auth: require_role wrong role raises HTTP 403",                _test_08_require_role_fail),
        ("suite_a_test_09", "Auth: authenticate_user valid/invalid credentials",            _test_09_authenticate_user),
        ("suite_a_test_10", "Auth: _DEV_USERS has 3 users with required structure",         _test_10_dev_users_structure),
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
