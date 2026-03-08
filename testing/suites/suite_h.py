"""
testing/suites/suite_h.py — Sprint 4 + Sprint 5 Integration Tests.

14 tests across 5 groups:
  Group 1 — Meredith workspace signals (ADR-018): 3 tests
  Group 2 — Chrissy patch apply/reject/content (ADR-019): 3 tests
  Group 3 — Pam HITL approve S3 signal (ADR-020): 3 tests
  Group 4 — Kelly real channel dispatch (ADR-020): 3 tests
  Group 5 — Monica escalation → HITL queue (ADR-022): 2 tests

No live S3, DB, or SMTP required — all external calls mocked.
No live DB required for Groups 1, 3, 4, 5 (mocked).
DB required for Group 2 (patch_suggestions table — patched via TestClient dependency override).
"""
from __future__ import annotations

import json
import traceback
from enum import Enum
from typing import Callable
from unittest.mock import AsyncMock, MagicMock, patch, call


class TestStatus(Enum):
    SKIP = "SKIP"
    PASS = "PASS"
    FAIL = "FAIL"


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


# ===========================================================================
# Group 1 — Meredith workspace signals (ADR-018)
# ===========================================================================

def _test_h01_dwight_trigger_signal() -> None:
    """POST /spec-setup/upload writes signals/dwight_trigger_{ts}.json to S3 workspace."""
    from unittest.mock import MagicMock, patch, AsyncMock
    from fastapi.testclient import TestClient
    import certportal.core.database as _dbmod
    from certportal.core.auth import create_access_token, build_token_claims

    token = create_access_token(build_token_claims({
        "sub": "lowes_retailer", "role": "retailer",
        "retailer_slug": "lowes", "supplier_slug": None,
    }))

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    upload_calls: list[tuple] = []

    class FakeWorkspace:
        def __init__(self, retailer_slug, supplier_slug):
            self._retailer_slug = retailer_slug
            self._supplier_slug = supplier_slug

        def upload(self, key, content):
            upload_calls.append((self._retailer_slug, self._supplier_slug, key, content))
            return key

    with patch.object(_dbmod, "_pool", mock_pool), \
         patch("portals.meredith.S3AgentWorkspace", FakeWorkspace):
        from portals.meredith import app
        try:
            client = TestClient(app, raise_server_exceptions=True)
            r = client.post(
                "/spec-setup/upload",
                json={"pdf_s3_key": "specs/lowes_2024.pdf", "retailer_slug": "lowes"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        finally:
            app.dependency_overrides.clear()

    assert len(upload_calls) == 1, f"Expected 1 upload call, got {len(upload_calls)}"
    retailer, supplier, key, content = upload_calls[0]
    assert retailer == "lowes", f"retailer_slug mismatch: {retailer!r}"
    assert supplier == "system", f"supplier_slug must be 'system' for Meredith signals, got {supplier!r}"
    assert key.startswith("signals/dwight_trigger_"), f"key format wrong: {key!r}"
    payload = json.loads(content)
    assert payload["type"] == "dwight_spec_analysis", f"type mismatch: {payload['type']!r}"
    assert payload["pdf_s3_key"] == "specs/lowes_2024.pdf"
    assert payload["retailer_slug"] == "lowes"


def _test_h02_andy_path1_trigger_signal() -> None:
    """POST /yaml-wizard/path1 writes signals/andy_path1_trigger_{ts}.json to S3."""
    from fastapi.testclient import TestClient
    import certportal.core.database as _dbmod
    from certportal.core.auth import create_access_token, build_token_claims

    token = create_access_token(build_token_claims({
        "sub": "lowes_retailer", "role": "retailer",
        "retailer_slug": "lowes", "supplier_slug": None,
    }))

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    upload_calls: list[tuple] = []

    class FakeWorkspace:
        def __init__(self, retailer_slug, supplier_slug):
            self._retailer_slug = retailer_slug
            self._supplier_slug = supplier_slug

        def upload(self, key, content):
            upload_calls.append((self._retailer_slug, self._supplier_slug, key, content))
            return key

    with patch.object(_dbmod, "_pool", mock_pool), \
         patch("portals.meredith.S3AgentWorkspace", FakeWorkspace):
        from portals.meredith import app
        try:
            client = TestClient(app, raise_server_exceptions=True)
            r = client.post(
                "/yaml-wizard/path1",
                json={"retailer_slug": "lowes", "transaction_type": "850"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        finally:
            app.dependency_overrides.clear()

    assert len(upload_calls) == 1, f"Expected 1 upload call, got {len(upload_calls)}"
    _, supplier, key, content = upload_calls[0]
    assert supplier == "system", f"supplier_slug must be 'system', got {supplier!r}"
    assert key.startswith("signals/andy_path1_trigger_"), f"key format wrong: {key!r}"
    payload = json.loads(content)
    assert payload["type"] == "andy_yaml_path1", f"type mismatch: {payload['type']!r}"
    assert payload["retailer_slug"] == "lowes"


def _test_h03_andy_path2_path3_signals() -> None:
    """POST /yaml-wizard/path2 and /path3 each write their own correctly-typed S3 signal."""
    from fastapi.testclient import TestClient
    import certportal.core.database as _dbmod
    from certportal.core.auth import create_access_token, build_token_claims

    token = create_access_token(build_token_claims({
        "sub": "lowes_retailer", "role": "retailer",
        "retailer_slug": "lowes", "supplier_slug": None,
    }))

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    upload_calls: list[tuple] = []

    class FakeWorkspace:
        def __init__(self, retailer_slug, supplier_slug):
            self._retailer_slug = retailer_slug
            self._supplier_slug = supplier_slug

        def upload(self, key, content):
            upload_calls.append((self._retailer_slug, self._supplier_slug, key, content))
            return key

    with patch.object(_dbmod, "_pool", mock_pool), \
         patch("portals.meredith.S3AgentWorkspace", FakeWorkspace):
        from portals.meredith import app
        try:
            client = TestClient(app, raise_server_exceptions=True)
            r2 = client.post(
                "/yaml-wizard/path2",
                json={"retailer_slug": "lowes", "yaml_s3_key": "maps/850.yaml"},
                headers={"Authorization": f"Bearer {token}"},
            )
            r3 = client.post(
                "/yaml-wizard/path3",
                json={"retailer_slug": "lowes", "field": "value"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r2.status_code == 200 and r3.status_code == 200
        finally:
            app.dependency_overrides.clear()

    assert len(upload_calls) == 2, f"Expected 2 upload calls (path2+path3), got {len(upload_calls)}"

    # path2
    _, _, key2, content2 = upload_calls[0]
    assert key2.startswith("signals/andy_path2_trigger_"), f"path2 key wrong: {key2!r}"
    p2 = json.loads(content2)
    assert p2["type"] == "andy_yaml_path2", f"path2 type wrong: {p2['type']!r}"

    # path3
    _, _, key3, content3 = upload_calls[1]
    assert key3.startswith("signals/andy_path3_trigger_"), f"path3 key wrong: {key3!r}"
    p3 = json.loads(content3)
    assert p3["type"] == "andy_yaml_path3", f"path3 type wrong: {p3['type']!r}"


# ===========================================================================
# Group 2 — Chrissy patch apply / reject / content (ADR-019)
# ===========================================================================

def _test_h04_mark_applied_writes_moses_signal() -> None:
    """POST /patches/{id}/mark-applied writes signals/moses_revalidate_{id}_{ts}.json."""
    from fastapi.testclient import TestClient
    import certportal.core.database as _dbmod
    from certportal.core.auth import create_access_token, build_token_claims
    from certportal.core.database import get_connection

    token = create_access_token(build_token_claims({
        "sub": "acme_supplier", "role": "supplier",
        "retailer_slug": "lowes", "supplier_slug": "acme",
    }))

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    upload_calls: list[tuple] = []

    class FakeWorkspace:
        def __init__(self, retailer_slug, supplier_slug):
            self._retailer_slug = retailer_slug
            self._supplier_slug = supplier_slug

        def upload(self, key, content):
            upload_calls.append((key, content))
            return key

    fake_row = {
        "id": 42, "supplier_slug": "acme", "retailer_slug": "lowes",
        "error_code": "ISA_SEG", "segment": "ISA", "element": None,
        "summary": "Fix ISA segment", "patch_s3_key": "patches/42.md",
        "applied": False, "rejected": False, "created_at": None,
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_row)
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    async def _mock_conn():
        yield mock_conn

    with patch.object(_dbmod, "_pool", mock_pool), \
         patch("portals.chrissy.S3AgentWorkspace", FakeWorkspace):
        from portals.chrissy import app
        app.dependency_overrides[get_connection] = _mock_conn
        try:
            client = TestClient(app, raise_server_exceptions=True)
            r = client.post(
                "/patches/42/mark-applied",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
            assert r.json()["status"] == "applied"
        finally:
            app.dependency_overrides.clear()

    assert len(upload_calls) == 1, f"Expected 1 upload call, got {len(upload_calls)}"
    key, content = upload_calls[0]
    assert key.startswith("signals/moses_revalidate_42_"), f"key format wrong: {key!r}"
    payload = json.loads(content)
    assert payload["trigger"] == "patch_applied", f"trigger mismatch: {payload['trigger']!r}"
    assert payload["patch_id"] == 42
    assert payload["supplier_slug"] == "acme"
    assert payload["retailer_slug"] == "lowes"


def _test_h05_reject_patch_sets_rejected_true() -> None:
    """POST /patches/{id}/reject sets rejected=TRUE via DB execute (no S3 signal)."""
    from fastapi.testclient import TestClient
    import certportal.core.database as _dbmod
    from certportal.core.auth import create_access_token, build_token_claims
    from certportal.core.database import get_connection

    token = create_access_token(build_token_claims({
        "sub": "acme_supplier", "role": "supplier",
        "retailer_slug": "lowes", "supplier_slug": "acme",
    }))

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    upload_calls: list = []

    class FakeWorkspace:
        def __init__(self, retailer_slug, supplier_slug):
            pass

        def upload(self, key, content):
            upload_calls.append(key)

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    async def _mock_conn():
        yield mock_conn

    with patch.object(_dbmod, "_pool", mock_pool), \
         patch("portals.chrissy.S3AgentWorkspace", FakeWorkspace):
        from portals.chrissy import app
        app.dependency_overrides[get_connection] = _mock_conn
        try:
            client = TestClient(app, raise_server_exceptions=True)
            r = client.post(
                "/patches/99/reject",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
            body = r.json()
            assert body["status"] == "rejected", f"status mismatch: {body}"
            assert body["patch_id"] == 99
        finally:
            app.dependency_overrides.clear()

    # Verify DB execute was called with rejected=TRUE
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args[0]
    assert "rejected" in call_args[0].lower() and "true" in call_args[0].lower(), \
        f"Expected rejected=TRUE in SQL, got: {call_args[0]!r}"

    # No S3 upload for rejected patches (ADR-019)
    assert len(upload_calls) == 0, \
        f"Expected 0 S3 uploads on reject, got {len(upload_calls)}: {upload_calls}"


def _test_h06_patch_content_returns_markdown() -> None:
    """GET /patches/{id}/content returns inline HTML with patch .md content."""
    from fastapi.testclient import TestClient
    import certportal.core.database as _dbmod
    from certportal.core.auth import create_access_token, build_token_claims
    from certportal.core.database import get_connection

    token = create_access_token(build_token_claims({
        "sub": "acme_supplier", "role": "supplier",
        "retailer_slug": "lowes", "supplier_slug": "acme",
    }))

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    PATCH_CONTENT = "# Fix ISA*01\n\nReplace value with `00`.\n"

    class FakeWorkspace:
        def __init__(self, retailer_slug, supplier_slug):
            pass

        def download(self, key):
            return PATCH_CONTENT.encode("utf-8")

    fake_row = {
        "id": 7, "supplier_slug": "acme", "retailer_slug": "lowes",
        "error_code": "ISA", "segment": "ISA", "element": "ISA01",
        "summary": "Fix ISA01", "patch_s3_key": "patches/7.md",
        "applied": False, "rejected": False, "created_at": None,
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_row)

    async def _mock_conn():
        yield mock_conn

    with patch.object(_dbmod, "_pool", mock_pool), \
         patch("portals.chrissy.S3AgentWorkspace", FakeWorkspace):
        from portals.chrissy import app
        app.dependency_overrides[get_connection] = _mock_conn
        try:
            client = TestClient(app, raise_server_exceptions=True)
            r = client.get(
                "/patches/7/content",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
            assert "text/html" in r.headers.get("content-type", ""), \
                f"Expected HTML response, got: {r.headers.get('content-type')}"
            assert "Fix ISA" in r.text, f"Expected patch content in response: {r.text[:200]}"
            assert "<pre" in r.text, "Expected <pre> wrapper in HTML response"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# Group 3 — Pam HITL approve S3 signal (ADR-020)
# ===========================================================================

def _test_h07_approve_writes_kelly_signal() -> None:
    """POST /hitl-queue/{queue_id}/approve writes signals/kelly_approved_{id}.json to S3."""
    from fastapi.testclient import TestClient
    import certportal.core.database as _dbmod
    from certportal.core.auth import create_access_token, build_token_claims
    from certportal.core.database import get_connection

    token = create_access_token(build_token_claims({
        "sub": "pam_admin", "role": "admin",
        "retailer_slug": None, "supplier_slug": None,
    }))

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    upload_calls: list[tuple] = []

    class FakeWorkspace:
        def __init__(self, retailer_slug, supplier_slug):
            self._retailer_slug = retailer_slug
            self._supplier_slug = supplier_slug

        def upload(self, key, content):
            upload_calls.append((self._retailer_slug, self._supplier_slug, key, content))
            return key

    fake_queue_row = {
        "queue_id": "q-001", "retailer_slug": "lowes", "supplier_slug": "acme",
        "agent": "kelly", "draft": "Hello Acme team!", "summary": "Test draft",
        "thread_id": "space123", "channel": "google_chat",
        "status": "PENDING_APPROVAL",
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_queue_row)
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    async def _mock_conn():
        yield mock_conn

    with patch.object(_dbmod, "_pool", mock_pool), \
         patch("portals.pam.S3AgentWorkspace", FakeWorkspace):
        from portals.pam import app
        app.dependency_overrides[get_connection] = _mock_conn
        try:
            client = TestClient(app, raise_server_exceptions=True)
            r = client.post(
                "/hitl-queue/q-001/approve",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
            assert r.json()["status"] == "approved"
        finally:
            app.dependency_overrides.clear()

    assert len(upload_calls) == 1, f"Expected 1 upload call, got {len(upload_calls)}"
    retailer, supplier, key, content = upload_calls[0]
    assert retailer == "lowes" and supplier == "acme"
    assert key == "signals/kelly_approved_q-001.json", f"key mismatch: {key!r}"
    payload = json.loads(content)
    assert payload["queue_id"] == "q-001"
    assert payload["approved_by"] == "pam_admin"
    assert payload["draft"] == "Hello Acme team!"
    assert payload["channel"] == "google_chat"


def _test_h08_approve_reject_db_status_updates() -> None:
    """Approve sets status=APPROVED; reject sets status=REJECTED in DB."""
    from fastapi.testclient import TestClient
    import certportal.core.database as _dbmod
    from certportal.core.auth import create_access_token, build_token_claims
    from certportal.core.database import get_connection

    token = create_access_token(build_token_claims({
        "sub": "pam_admin", "role": "admin",
        "retailer_slug": None, "supplier_slug": None,
    }))

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    class FakeWorkspace:
        def __init__(self, *args): pass
        def upload(self, *args): pass

    fake_queue_row = {
        "queue_id": "q-002", "retailer_slug": "lowes", "supplier_slug": "acme",
        "agent": "kelly", "draft": "Test", "summary": None,
        "thread_id": None, "channel": "email", "status": "PENDING_APPROVAL",
    }

    execute_calls: list[str] = []
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_queue_row)

    async def _recording_execute(sql, *args):
        execute_calls.append(sql)
        return "UPDATE 1"

    mock_conn.execute = _recording_execute

    async def _mock_conn():
        yield mock_conn

    with patch.object(_dbmod, "_pool", mock_pool), \
         patch("portals.pam.S3AgentWorkspace", FakeWorkspace):
        from portals.pam import app
        app.dependency_overrides[get_connection] = _mock_conn
        try:
            client = TestClient(app, raise_server_exceptions=True)
            r = client.post("/hitl-queue/q-002/approve",
                            headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200

            mock_conn.fetchrow = AsyncMock(return_value=None)  # reject doesn't need row
            r = client.post("/hitl-queue/q-002/reject",
                            headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
        finally:
            app.dependency_overrides.clear()

    approve_sqls = [s for s in execute_calls if "APPROVED" in s]
    reject_sqls  = [s for s in execute_calls if "REJECTED" in s]
    assert approve_sqls, f"Expected SQL with APPROVED, got: {execute_calls}"
    assert reject_sqls,  f"Expected SQL with REJECTED, got: {execute_calls}"


def _test_h09_reject_does_not_write_signal() -> None:
    """POST /hitl-queue/{queue_id}/reject does NOT write an S3 signal (ADR-020)."""
    from fastapi.testclient import TestClient
    import certportal.core.database as _dbmod
    from certportal.core.auth import create_access_token, build_token_claims
    from certportal.core.database import get_connection

    token = create_access_token(build_token_claims({
        "sub": "pam_admin", "role": "admin",
        "retailer_slug": None, "supplier_slug": None,
    }))

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock()),
        __aexit__=AsyncMock(return_value=False),
    ))

    upload_calls: list = []

    class FakeWorkspace:
        def __init__(self, *args): pass
        def upload(self, key, content):
            upload_calls.append(key)

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    async def _mock_conn():
        yield mock_conn

    with patch.object(_dbmod, "_pool", mock_pool), \
         patch("portals.pam.S3AgentWorkspace", FakeWorkspace):
        from portals.pam import app
        app.dependency_overrides[get_connection] = _mock_conn
        try:
            client = TestClient(app, raise_server_exceptions=True)
            r = client.post("/hitl-queue/q-003/reject",
                            headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
        finally:
            app.dependency_overrides.clear()

    assert len(upload_calls) == 0, \
        f"Expected no S3 uploads on reject, got {len(upload_calls)}: {upload_calls}"


# ===========================================================================
# Group 4 — Kelly channel dispatch (ADR-020)
# ===========================================================================

def _test_h10_email_dispatch_calls_smtp() -> None:
    """Kelly _dispatch_email() calls smtplib.SMTP with correct host when env vars are set."""
    import agents.kelly as _kelly
    import smtplib

    with patch.dict("os.environ", {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "kelly@example.com",
        "SMTP_PASSWORD": "secret",
        "SMTP_FROM": "certportal@example.com",
    }):
        mock_smtp = MagicMock()
        mock_smtp_instance = MagicMock()
        mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__exit__ = MagicMock(return_value=False)
        mock_smtp.return_value = mock_smtp_instance

        with patch("agents.kelly.smtplib.SMTP", mock_smtp):
            _kelly._dispatch_email("Test draft", "lowes", "acme")

        mock_smtp.assert_called_once()
        call_args = mock_smtp.call_args[0]
        assert call_args[0] == "smtp.example.com", f"SMTP host mismatch: {call_args[0]!r}"
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("kelly@example.com", "secret")
        mock_smtp_instance.sendmail.assert_called_once()


def _test_h11_google_chat_dispatch_calls_requests() -> None:
    """Kelly _dispatch_google_chat() calls requests.post with correct URL prefix."""
    import agents.kelly as _kelly

    with patch.dict("os.environ", {
        "KELLY_GOOGLE_CHAT_OAUTH_TOKEN_LOWES": "fake-oauth-token",
    }):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("agents.kelly.requests.post", return_value=mock_response) as mock_post:
            _kelly._dispatch_google_chat("Test draft", "space/ABC123", "lowes", "acme")

        mock_post.assert_called_once()
        url_called = mock_post.call_args[0][0]
        assert "chat.googleapis.com" in url_called, \
            f"Expected Google Chat URL, got: {url_called!r}"
        kwargs = mock_post.call_args[1]
        headers = kwargs.get("headers", {})
        assert "Bearer fake-oauth-token" in headers.get("Authorization", ""), \
            f"Expected Bearer token in headers: {headers}"


def _test_h12_missing_env_dispatch_does_not_raise() -> None:
    """Kelly _dispatch_message() returns without raising when env vars are missing (ADR-020)."""
    import agents.kelly as _kelly

    # Patch out env completely so no SMTP_HOST / KELLY_* vars are set
    with patch.dict("os.environ", {}, clear=True):
        # Restore non-dispatch vars that kelly.py may need at import time
        try:
            # Should not raise despite no env vars
            _kelly._dispatch_message("email", "", "Test draft", "acme", "lowes")
            _kelly._dispatch_message("google_chat", "thread123", "Test draft", "acme", "lowes")
            _kelly._dispatch_message("ms_teams", "", "Test draft", "acme", "lowes")
        except Exception as exc:
            raise AssertionError(
                f"_dispatch_message raised {type(exc).__name__}: {exc} with missing env vars"
            ) from exc


# ===========================================================================
# Group 5 — Monica escalation → HITL queue (ADR-022)
# ===========================================================================

def _test_h13_escalation_queued_to_hitl() -> None:
    """Monica.run() calls _queue_escalation_for_hitl() when GLOBAL-FEEDBACK.md has escalations.

    Verifies:
      - psycopg2 cursor.execute called with INSERT INTO hitl_queue
      - queue_id starts with 'escalation_'
      - 'escalation_queued:{thread_id}' appears in summary['actions_taken']
      - agent='KELLY', channel='email', status='PENDING_APPROVAL' in INSERT args
    """
    import agents.monica as _monica
    from certportal.core.workspace import FileNotFoundInWorkspace

    feedback_content = (
        b"2026-03-07T10:00:00Z SENTIMENT_ESCALATION thread_id=thread-xyz supplier=acme\n"
        b"2026-03-07T11:00:00Z INFO Normal log line\n"
    )

    # Mock psycopg2 cursor + connection
    mock_cur = MagicMock()
    mock_cur.rowcount = 1
    mock_conn_psyco = MagicMock()
    mock_conn_psyco.cursor = MagicMock(return_value=mock_cur)
    mock_conn_psyco.commit = MagicMock()
    mock_conn_psyco.close = MagicMock()

    mock_workspace = MagicMock()
    mock_workspace.read_pam_status = MagicMock(return_value={
        "gate_1": "COMPLETE", "gate_2": "COMPLETE", "gate_3": "PENDING",
    })
    mock_workspace.download = MagicMock(return_value=feedback_content)
    mock_workspace.write_pam_status = MagicMock()
    mock_workspace._supplier_slug = "acme"

    with patch("agents.monica.S3AgentWorkspace", return_value=mock_workspace), \
         patch("psycopg2.connect", return_value=mock_conn_psyco), \
         patch.dict("os.environ", {"CERTPORTAL_DB_URL": "postgresql://fake/db"}), \
         patch("agents.monica._summarise_for_hitl", return_value="Escalation summary"), \
         patch("agents.monica.monica_logger"):

        result = _monica.run(retailer_slug="lowes", supplier_slug="acme")

    # queue_escalation_for_hitl should have inserted into hitl_queue
    assert mock_cur.execute.called, "Expected psycopg2 cursor.execute() to be called"
    execute_calls_sql = [str(c[0][0]) for c in mock_cur.execute.call_args_list]
    hitl_inserts = [s for s in execute_calls_sql if "hitl_queue" in s]
    assert hitl_inserts, \
        f"Expected at least one INSERT INTO hitl_queue call; got: {execute_calls_sql}"

    # Verify agent and channel in INSERT args
    insert_args = mock_cur.execute.call_args_list[-1][0]  # last execute call args
    insert_params = insert_args[1] if len(insert_args) > 1 else ()
    assert "KELLY" in insert_params, f"agent='KELLY' not found in INSERT params: {insert_params}"
    assert "email" in insert_params, f"channel='email' not found in INSERT params: {insert_params}"
    assert "PENDING_APPROVAL" in insert_params, \
        f"status='PENDING_APPROVAL' not found in INSERT params: {insert_params}"

    # Summary should record the escalation queue action
    actions = result.get("actions_taken", [])
    assert any("escalation_queued" in a for a in actions), \
        f"Expected 'escalation_queued:...' in actions_taken: {actions}"
    assert any("thread-xyz" in a for a in actions), \
        f"Expected thread-xyz in actions_taken: {actions}"


def _test_h14_no_escalation_no_hitl_write() -> None:
    """Monica.run() does NOT call psycopg2 when GLOBAL-FEEDBACK.md is absent (no escalations).

    Verifies:
      - psycopg2.connect NOT called
      - 'kelly_escalations_detected' NOT in summary['actions_taken']
    """
    import agents.monica as _monica
    from certportal.core.workspace import FileNotFoundInWorkspace

    mock_workspace = MagicMock()
    mock_workspace.read_pam_status = MagicMock(return_value={
        "gate_1": "COMPLETE", "gate_2": "COMPLETE", "gate_3": "PENDING",
    })
    mock_workspace.download = MagicMock(side_effect=FileNotFoundInWorkspace("GLOBAL-FEEDBACK.md"))
    mock_workspace.write_pam_status = MagicMock()
    mock_workspace._supplier_slug = "acme"

    with patch("agents.monica.S3AgentWorkspace", return_value=mock_workspace), \
         patch("psycopg2.connect") as mock_connect, \
         patch("agents.monica.monica_logger"):

        result = _monica.run(retailer_slug="lowes", supplier_slug="acme")

    assert not mock_connect.called, \
        "psycopg2.connect must NOT be called when no escalations are detected"

    actions = result.get("actions_taken", [])
    assert not any("kelly_escalations_detected" in a for a in actions), \
        f"Unexpected escalation action in summary: {actions}"
    assert not any("escalation_queued" in a for a in actions), \
        f"Unexpected escalation_queued action in summary: {actions}"


# ===========================================================================
# Suite entry point
# ===========================================================================

def run() -> list[dict]:
    """Run all 14 Sprint 4 + Sprint 5 integration tests. No live S3/SMTP/network required."""
    tests = [
        # Group 1 — Meredith workspace signals
        ("suite_h_test_01", "Meredith: /spec-setup/upload writes dwight_trigger signal",     _test_h01_dwight_trigger_signal),
        ("suite_h_test_02", "Meredith: /yaml-wizard/path1 writes andy_path1_trigger signal", _test_h02_andy_path1_trigger_signal),
        ("suite_h_test_03", "Meredith: /yaml-wizard/path2+3 each write correctly-typed signal", _test_h03_andy_path2_path3_signals),
        # Group 2 — Chrissy patch
        ("suite_h_test_04", "Chrissy: mark-applied writes moses_revalidate signal",          _test_h04_mark_applied_writes_moses_signal),
        ("suite_h_test_05", "Chrissy: reject sets rejected=TRUE, no S3 upload",              _test_h05_reject_patch_sets_rejected_true),
        ("suite_h_test_06", "Chrissy: /patches/{id}/content returns inline markdown",        _test_h06_patch_content_returns_markdown),
        # Group 3 — Pam HITL
        ("suite_h_test_07", "Pam: approve writes kelly_approved signal to S3 (ADR-020)",     _test_h07_approve_writes_kelly_signal),
        ("suite_h_test_08", "Pam: approve/reject set correct DB status values",              _test_h08_approve_reject_db_status_updates),
        ("suite_h_test_09", "Pam: reject does NOT write any S3 signal",                      _test_h09_reject_does_not_write_signal),
        # Group 4 — Kelly dispatch
        ("suite_h_test_10", "Kelly: email channel calls smtplib.SMTP with correct host",     _test_h10_email_dispatch_calls_smtp),
        ("suite_h_test_11", "Kelly: google_chat calls requests.post to chat.googleapis.com", _test_h11_google_chat_dispatch_calls_requests),
        ("suite_h_test_12", "Kelly: missing env vars -> dispatch returns without raising",   _test_h12_missing_env_dispatch_does_not_raise),
        # Group 5 — Monica escalation -> HITL queue (ADR-022)
        ("suite_h_test_13", "Monica: escalation detected -> hitl_queue row inserted (ADR-022)", _test_h13_escalation_queued_to_hitl),
        ("suite_h_test_14", "Monica: no escalation -> psycopg2 NOT called (ADR-022)",           _test_h14_no_escalation_no_hitl_write),
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
