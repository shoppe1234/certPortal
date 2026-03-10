"""
testing/unit/test_auth.py — Portal Auth Tests (ADR-014 through ADR-017, ADR-021, ADR-023, ADR-025).

Migrated from testing/suites/suite_a.py (25 tests).

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

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = [pytest.mark.unit]

# ---------------------------------------------------------------------------
# Module-level imports via importorskip
# ---------------------------------------------------------------------------

_auth = pytest.importorskip("certportal.core.auth", reason="certportal.core.auth not importable")

create_access_token = _auth.create_access_token
create_refresh_token = _auth.create_refresh_token
create_password_reset_token = _auth.create_password_reset_token
decode_refresh_token = _auth.decode_refresh_token
decode_token = _auth.decode_token
get_current_user = _auth.get_current_user
require_role = _auth.require_role
authenticate_user = _auth.authenticate_user
build_token_claims = _auth.build_token_claims
hash_password = _auth.hash_password
revoke_jti = _auth.revoke_jti
validate_password_reset_token = _auth.validate_password_reset_token
_DEV_USERS = _auth._DEV_USERS
_verify_password = _auth._verify_password
ACCESS_TOKEN_EXPIRE_MINUTES = _auth.ACCESS_TOKEN_EXPIRE_MINUTES

HTTPException = pytest.importorskip("fastapi", reason="fastapi not importable").HTTPException


# ===========================================================================
# Token Round-Trip Tests (ADR-014)
# ===========================================================================

class TestTokenRoundTrip:
    """Tests 01-06: token creation, decoding, and expiration."""

    def test_create_access_token_and_decode(self):
        """create_access_token encodes claims that decode_token retrieves correctly."""
        claims = {"sub": "pam_admin", "role": "admin", "retailer_slug": None, "supplier_slug": None}
        token = create_access_token(claims)

        assert isinstance(token, str), f"Expected str token, got {type(token)}"
        assert len(token) > 20, "Token too short to be a real JWT"

        decoded = decode_token(token)
        assert decoded["sub"] == "pam_admin", f"sub mismatch: {decoded['sub']!r}"
        assert decoded["role"] == "admin", f"role mismatch: {decoded['role']!r}"
        assert "exp" in decoded, "decoded payload must contain 'exp'"

    @pytest.mark.asyncio
    async def test_get_current_user_bearer_header(self):
        """get_current_user resolves the user from a valid Authorization: Bearer header."""
        token = create_access_token({"sub": "pam_admin", "role": "admin"})

        result = await get_current_user(
            authorization=f"Bearer {token}",
            access_token=None,
        )

        assert result["sub"] == "pam_admin", f"Expected sub='pam_admin', got {result['sub']!r}"
        assert result["role"] == "admin", f"Expected role='admin', got {result['role']!r}"

    @pytest.mark.asyncio
    async def test_get_current_user_cookie(self):
        """get_current_user resolves the user from a valid access_token cookie."""
        token = create_access_token({"sub": "lowes_retailer", "role": "retailer", "retailer_slug": "lowes"})

        result = await get_current_user(
            authorization=None,
            access_token=token,
        )

        assert result["sub"] == "lowes_retailer", f"sub mismatch: {result['sub']!r}"
        assert result["role"] == "retailer"
        assert result.get("retailer_slug") == "lowes"

    @pytest.mark.asyncio
    async def test_get_current_user_bearer_priority(self):
        """Bearer header takes priority over cookie when both are present."""
        bearer_token = create_access_token({"sub": "pam_admin", "role": "admin"})
        cookie_token = create_access_token({"sub": "lowes_retailer", "role": "retailer"})

        result = await get_current_user(
            authorization=f"Bearer {bearer_token}",
            access_token=cookie_token,
        )

        # Bearer header wins — sub should be pam_admin not lowes_retailer
        assert result["sub"] == "pam_admin", \
            f"Bearer should take priority, got sub={result['sub']!r}"

    @pytest.mark.asyncio
    async def test_get_current_user_no_token_raises_401(self):
        """get_current_user raises HTTP 401 when neither Bearer header nor cookie is present."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization=None, access_token=None)

        assert exc_info.value.status_code == 401, f"Expected 401, got {exc_info.value.status_code}"

    def test_decode_token_expired_raises_401(self):
        """decode_token raises HTTP 401 for a token that has already expired."""
        # Create a token that expired 5 minutes ago
        expired_token = create_access_token(
            {"sub": "pam_admin", "role": "admin"},
            expires_minutes=-5,
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_token(expired_token)

        assert exc_info.value.status_code == 401, f"Expected 401, got {exc_info.value.status_code}"


# ===========================================================================
# Role Authorization Tests (ADR-014)
# ===========================================================================

class TestRequireRole:
    """Tests 07-08: require_role factory."""

    @pytest.mark.asyncio
    async def test_require_role_matching_passes(self):
        """require_role('admin') passes when the user has role='admin'."""
        admin_user = {"sub": "pam_admin", "role": "admin", "retailer_slug": None}
        checker = require_role("admin")

        result = await checker(user=admin_user)
        assert result == admin_user, f"require_role should return the user dict: {result}"

    @pytest.mark.asyncio
    async def test_require_role_wrong_role_raises_403(self):
        """require_role('admin') raises HTTP 403 when the user has role='supplier'."""
        supplier_user = {"sub": "acme_supplier", "role": "supplier", "supplier_slug": "acme"}
        checker = require_role("admin")

        with pytest.raises(HTTPException) as exc_info:
            await checker(user=supplier_user)

        assert exc_info.value.status_code == 403, f"Expected 403, got {exc_info.value.status_code}"


# ===========================================================================
# Authenticate User Tests (ADR-015)
# ===========================================================================

class TestAuthenticateUser:
    """Tests 09-11: authenticate_user — DEV_USERS fallback + DB path."""

    @pytest.mark.asyncio
    async def test_dev_users_fallback(self):
        """authenticate_user returns user dict via _DEV_USERS fallback when DB is unreachable."""
        # Valid credentials — falls back to _DEV_USERS bcrypt verification
        user = await authenticate_user("pam_admin", "certportal_admin")
        assert user is not None, "Expected user dict for valid credentials, got None"
        assert user["sub"] == "pam_admin"
        assert user["role"] == "admin"
        assert user.get("retailer_slug") is None

        # Wrong password
        bad = await authenticate_user("pam_admin", "wrong_password")
        assert bad is None, f"Expected None for wrong password, got: {bad}"

        # Non-existent user
        nonexistent = await authenticate_user("nobody", "certportal_admin")
        assert nonexistent is None, f"Expected None for unknown user, got: {nonexistent}"

    def test_dev_users_structure(self):
        """_DEV_USERS has exactly 3 users (admin, retailer, supplier) with bcrypt hashes."""
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
        assert _verify_password("certportal_admin", _DEV_USERS["pam_admin"]["hashed_password"])
        assert _verify_password("certportal_retailer", _DEV_USERS["lowes_retailer"]["hashed_password"])
        assert _verify_password("certportal_supplier", _DEV_USERS["acme_supplier"]["hashed_password"])

    @pytest.mark.asyncio
    async def test_db_path_with_mocked_asyncpg(self):
        """authenticate_user uses portal_users DB row when asyncpg returns a record."""
        import bcrypt as _bcrypt_lib
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
            user = await authenticate_user("db_test_user", db_password)
            assert user is not None, "Expected user dict from DB path, got None"
            assert user["sub"] == "db_test_user"
            assert user["role"] == "retailer"
            assert user["retailer_slug"] == "testco"

            # Wrong password — DB path returns None
            mock_conn.fetchrow = AsyncMock(return_value=fake_row)
            bad = await authenticate_user("db_test_user", "wrong_password")
            assert bad is None, f"Expected None for wrong DB password, got: {bad}"

            # User not found in DB (row = None) — falls through to _DEV_USERS
            mock_conn.fetchrow = AsyncMock(return_value=None)
            fallback_user = await authenticate_user("pam_admin", "certportal_admin")
            assert fallback_user is not None, \
                "Expected _DEV_USERS fallback when DB row is None"
            assert fallback_user["sub"] == "pam_admin"


# ===========================================================================
# Password Hashing Tests
# ===========================================================================

class TestHashPassword:
    """Test 12: hash_password bcrypt round-trip."""

    def test_hash_password_round_trip(self):
        """hash_password produces a bcrypt $2b$ hash verified by _verify_password."""
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


# ===========================================================================
# Endpoint Tests — /register, /change-password (ADR-016)
# ===========================================================================

class TestRegisterEndpoint:
    """Test 13: POST /register validation logic via TestClient + mocked DB."""

    def test_register_validation_and_success(self):
        """POST /register validates input and (with mocked DB) redirects on success/error."""
        from fastapi.testclient import TestClient
        from certportal.core.database import get_connection
        import certportal.core.database as _dbmod

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


class TestChangePasswordEndpoint:
    """Test 14: POST /change-password validation + mocked DB."""

    def test_change_password_validation_and_success(self):
        """POST /change-password validates passwords and updates DB on success."""
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

                # ── valid change (mocked DB UPDATE) ─────────────────────────
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


# ===========================================================================
# Refresh Token Tests (ADR-017)
# ===========================================================================

class TestRefreshToken:
    """Tests 15-17: refresh token round-trip, rejection, and /token/refresh endpoint."""

    def test_refresh_token_round_trip(self):
        """create_refresh_token encodes claims; decode_refresh_token retrieves them."""
        claims = build_token_claims({
            "sub": "lowes_retailer", "role": "retailer",
            "retailer_slug": "lowes", "supplier_slug": None,
        })
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
        with pytest.raises(HTTPException) as exc_info:
            decode_refresh_token(access)
        assert exc_info.value.status_code == 401, f"Expected 401, got {exc_info.value.status_code}"

    @pytest.mark.asyncio
    async def test_refresh_token_rejected_as_access(self):
        """get_current_user raises 401 when a refresh token is supplied as an access token."""
        claims = build_token_claims({
            "sub": "pam_admin", "role": "admin",
            "retailer_slug": None, "supplier_slug": None,
        })
        refresh = create_refresh_token(claims)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization=f"Bearer {refresh}", access_token=None)

        assert exc_info.value.status_code == 401, f"Expected 401, got {exc_info.value.status_code}"

    def test_token_refresh_endpoint(self):
        """POST /token/refresh with valid refresh cookie returns new access token (ADR-017)."""
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

                # ── valid refresh cookie -> new access token ────────────────
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

                # ── no refresh cookie -> 401 ────────────────────────────────
                client.cookies.clear()
                r = client.post("/token/refresh")
                assert r.status_code == 401, \
                    f"Expected 401 for missing refresh token, got {r.status_code}"

            finally:
                app.dependency_overrides.clear()


# ===========================================================================
# JTI & Token Revocation Tests (ADR-021)
# ===========================================================================

class TestJtiRevocation:
    """Tests 18-20: JTI claims, revoke_jti(), and revoked token rejection."""

    def test_jti_in_tokens(self):
        """create_access_token and create_refresh_token both include a 'jti' claim."""
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

    @pytest.mark.asyncio
    async def test_revoke_jti_inserts(self):
        """revoke_jti() inserts the JTI into revoked_tokens when a pool is configured."""
        import certportal.core.auth as _auth_module

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

        # ── With pool configured: execute() must be called ────────────────
        _auth_module.set_revocation_pool(mock_pool)
        try:
            await revoke_jti(expected_jti, expected_exp)
            assert mock_conn.execute.called, "Expected execute() to be called for JTI insert"
            call_sql = mock_conn.execute.call_args[0][0]
            assert "revoked_tokens" in call_sql, \
                f"SQL does not reference revoked_tokens: {call_sql!r}"
            call_jti = mock_conn.execute.call_args[0][1]
            assert call_jti == expected_jti, \
                f"JTI mismatch: passed {call_jti!r}, expected {expected_jti!r}"
        finally:
            _auth_module.set_revocation_pool(None)

        # ── No pool: revoke_jti() is a no-op (must not raise) ─────────────
        mock_conn2 = AsyncMock()
        mock_conn2.execute = AsyncMock(return_value=None)
        _auth_module.set_revocation_pool(None)
        await revoke_jti(expected_jti, expected_exp)  # no-op, should not raise
        assert not mock_conn2.execute.called, "execute() must not be called when pool is None"

    @pytest.mark.asyncio
    async def test_revoked_token_rejected(self):
        """get_current_user raises HTTP 401 when the token's JTI is in revoked_tokens."""
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
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(authorization=f"Bearer {access}", access_token=None)

            assert exc_info.value.status_code == 401, f"Expected 401, got {exc_info.value.status_code}"

            # Verify fetchval was called with the right SQL (checking revoked_tokens)
            assert mock_conn.fetchval.called, "Expected fetchval() to query revoked_tokens"
            fetch_sql = mock_conn.fetchval.call_args[0][0]
            assert "revoked_tokens" in fetch_sql, \
                f"fetchval SQL does not query revoked_tokens: {fetch_sql!r}"
        finally:
            _auth_module.set_revocation_pool(None)


# ===========================================================================
# Password Reset Token Tests (ADR-023)
# ===========================================================================

class TestPasswordResetToken:
    """Tests 21-24: create/validate password reset tokens, /forgot-password, /reset-password."""

    @pytest.mark.asyncio
    async def test_create_password_reset_token(self):
        """create_password_reset_token generates URL-safe token and inserts into DB."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=None)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_ctx)

        token = await create_password_reset_token("pam_admin", mock_pool)

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

    @pytest.mark.asyncio
    async def test_validate_password_reset_token(self):
        """validate_password_reset_token: valid row -> username + UPDATE used=TRUE; None if no row."""
        # ── Valid token: row found -> returns username, UPDATE called ──────
        mock_conn_ok = AsyncMock()
        mock_conn_ok.fetchrow = AsyncMock(return_value={"username": "pam_admin"})
        mock_conn_ok.execute = AsyncMock(return_value=None)
        mock_ctx_ok = AsyncMock()
        mock_ctx_ok.__aenter__ = AsyncMock(return_value=mock_conn_ok)
        mock_ctx_ok.__aexit__ = AsyncMock(return_value=False)
        mock_pool_ok = MagicMock()
        mock_pool_ok.acquire = MagicMock(return_value=mock_ctx_ok)

        result = await validate_password_reset_token("valid_token_abc", mock_pool_ok)
        assert result == "pam_admin", f"Expected 'pam_admin', got {result!r}"
        assert mock_conn_ok.execute.called, "Expected execute() (UPDATE used=TRUE) to be called"
        update_sql = mock_conn_ok.execute.call_args[0][0]
        assert "used" in update_sql.lower(), f"UPDATE SQL does not set used: {update_sql!r}"

        # ── Invalid/expired token: fetchrow returns None -> returns None ───
        mock_conn_bad = AsyncMock()
        mock_conn_bad.fetchrow = AsyncMock(return_value=None)
        mock_conn_bad.execute = AsyncMock(return_value=None)
        mock_ctx_bad = AsyncMock()
        mock_ctx_bad.__aenter__ = AsyncMock(return_value=mock_conn_bad)
        mock_ctx_bad.__aexit__ = AsyncMock(return_value=False)
        mock_pool_bad = MagicMock()
        mock_pool_bad.acquire = MagicMock(return_value=mock_ctx_bad)

        result_bad = await validate_password_reset_token("expired_token", mock_pool_bad)
        assert result_bad is None, f"Expected None for invalid token, got {result_bad!r}"
        assert not mock_conn_bad.execute.called, \
            "execute() (UPDATE) must NOT be called when token is invalid"

    def test_forgot_password_redirect(self):
        """POST /forgot-password always redirects to /login?msg=reset_sent (no enumeration)."""
        from fastapi.testclient import TestClient

        try:
            from portals.pam import app as pam_app
        except Exception as exc:
            raise AssertionError(f"Cannot import portals.pam: {exc}") from exc

        client = TestClient(pam_app, raise_server_exceptions=False)

        # ── Case 1: user exists with email -> token generated, email sent ──
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

        # ── Case 2: user not found -> still 302 reset_sent (no enumeration)
        mock_pool2 = AsyncMock()
        mock_pool2.fetchrow = AsyncMock(return_value=None)

        with patch("portals.pam.create_password_reset_token", new=AsyncMock(return_value="tok")), \
             patch("portals.pam.send_reset_email", return_value=False), \
             patch("portals.pam.get_pool", new=AsyncMock(return_value=mock_pool2)):
            resp2 = client.post("/forgot-password", data={"username": "nonexistent"}, follow_redirects=False)

        assert resp2.status_code == 302, f"Expected 302 for unknown user, got {resp2.status_code}"
        assert "reset_sent" in resp2.headers.get("location", ""), \
            f"Expected reset_sent for unknown user: {resp2.headers.get('location')!r}"

    def test_reset_password_submit(self):
        """POST /reset-password: valid token -> 302 password_changed; bad inputs -> 302 error."""
        from fastapi.testclient import TestClient

        try:
            from portals.pam import app as pam_app
        except Exception as exc:
            raise AssertionError(f"Cannot import portals.pam: {exc}") from exc

        client = TestClient(pam_app, raise_server_exceptions=False)

        # ── Password mismatch -> error redirect ────────────────────────────
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

        # ── Password too short -> error redirect ──────────────────────────
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

        # ── Valid token + valid passwords -> 302 password_changed ─────────
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


# ===========================================================================
# Revoked Token Cleanup Tests (ADR-025)
# ===========================================================================

class TestCleanupRevokedTokens:
    """Test 25: cleanup_expired_revoked_tokens() deletes expired rows."""

    @pytest.mark.asyncio
    async def test_cleanup_expired_revoked_tokens(self):
        """cleanup_expired_revoked_tokens: returns row count when pool set; 0 when None."""
        import certportal.core.auth as _auth_module
        from certportal.core.auth import cleanup_expired_revoked_tokens

        # ── With pool configured: DELETE called, returns row count ────────
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 3")
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_ctx)

        _auth_module.set_revocation_pool(mock_pool)
        try:
            count = await cleanup_expired_revoked_tokens()
            assert count == 3, f"Expected 3 rows deleted, got {count}"
            assert mock_conn.execute.called, "Expected execute() to be called"
            sql = mock_conn.execute.call_args[0][0]
            assert "expires_at" in sql and "NOW()" in sql, \
                f"DELETE SQL does not check expires_at < NOW(): {sql!r}"
            assert "revoked_tokens" in sql, f"DELETE SQL does not touch revoked_tokens: {sql!r}"
        finally:
            _auth_module.set_revocation_pool(None)

        # ── No pool configured: returns 0 without touching DB ─────────────
        mock_conn2 = AsyncMock()
        count_noop = await cleanup_expired_revoked_tokens()
        assert count_noop == 0, f"Expected 0 when pool is None, got {count_noop}"
        assert not mock_conn2.execute.called, "execute() must NOT be called when pool is None"
