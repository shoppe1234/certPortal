"""Migrated from testing/suites/suite_h.py — Sprint 4 + Sprint 5 Integration Tests."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = [pytest.mark.unit]


class TestMeredithWorkspaceSignals:
    """Group 1 — Meredith workspace signals (ADR-018)."""

    def test_h01_dwight_trigger_signal(self):
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

        upload_calls = []

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

        assert len(upload_calls) == 1
        retailer, supplier, key, content = upload_calls[0]
        assert retailer == "lowes"
        assert supplier == "system"
        assert key.startswith("signals/dwight_trigger_")
        payload = json.loads(content)
        assert payload["type"] == "dwight_spec_analysis"
        assert payload["pdf_s3_key"] == "specs/lowes_2024.pdf"

    def test_h02_andy_path1_trigger_signal(self):
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

        upload_calls = []

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

        assert len(upload_calls) == 1
        _, supplier, key, content = upload_calls[0]
        assert supplier == "system"
        assert key.startswith("signals/andy_path1_trigger_")
        payload = json.loads(content)
        assert payload["type"] == "andy_yaml_path1"

    def test_h03_andy_path2_path3_signals(self):
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

        upload_calls = []

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
                r2 = client.post("/yaml-wizard/path2",
                    json={"retailer_slug": "lowes", "yaml_s3_key": "maps/850.yaml"},
                    headers={"Authorization": f"Bearer {token}"})
                r3 = client.post("/yaml-wizard/path3",
                    json={"retailer_slug": "lowes", "field": "value"},
                    headers={"Authorization": f"Bearer {token}"})
                assert r2.status_code == 200 and r3.status_code == 200
            finally:
                app.dependency_overrides.clear()

        assert len(upload_calls) == 2
        _, _, key2, content2 = upload_calls[0]
        assert key2.startswith("signals/andy_path2_trigger_")
        p2 = json.loads(content2)
        assert p2["type"] == "andy_yaml_path2"
        _, _, key3, content3 = upload_calls[1]
        assert key3.startswith("signals/andy_path3_trigger_")
        p3 = json.loads(content3)
        assert p3["type"] == "andy_yaml_path3"


class TestChrissyPatch:
    """Group 2 — Chrissy patch apply/reject/content (ADR-019)."""

    def test_h04_mark_applied_writes_moses_signal(self):
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

        upload_calls = []

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
                r = client.post("/patches/42/mark-applied",
                                headers={"Authorization": f"Bearer {token}"})
                assert r.status_code == 200
                assert r.json()["status"] == "applied"
            finally:
                app.dependency_overrides.clear()

        assert len(upload_calls) == 1
        key, content = upload_calls[0]
        assert key.startswith("signals/moses_revalidate_42_")
        payload = json.loads(content)
        assert payload["trigger"] == "patch_applied"
        assert payload["patch_id"] == 42

    def test_h05_reject_patch_sets_rejected_true(self):
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

        upload_calls = []

        class FakeWorkspace:
            def __init__(self, retailer_slug, supplier_slug): pass
            def upload(self, key, content): upload_calls.append(key)

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
                r = client.post("/patches/99/reject",
                                headers={"Authorization": f"Bearer {token}"})
                assert r.status_code == 200
                assert r.json()["status"] == "rejected"
            finally:
                app.dependency_overrides.clear()

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert "rejected" in call_args[0].lower() and "true" in call_args[0].lower()
        assert len(upload_calls) == 0

    def test_h06_patch_content_returns_markdown(self):
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
            def __init__(self, retailer_slug, supplier_slug): pass
            def download(self, key): return PATCH_CONTENT.encode("utf-8")

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
                r = client.get("/patches/7/content",
                               headers={"Authorization": f"Bearer {token}"})
                assert r.status_code == 200
                assert "text/html" in r.headers.get("content-type", "")
                assert "Fix ISA" in r.text
                assert "<pre" in r.text
            finally:
                app.dependency_overrides.clear()


class TestPamHitlApprove:
    """Group 3 — Pam HITL approve/reject S3 signals (ADR-020)."""

    def test_h07_approve_writes_kelly_signal(self):
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

        upload_calls = []

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
                r = client.post("/hitl-queue/q-001/approve",
                                headers={"Authorization": f"Bearer {token}"})
                assert r.status_code == 200
                assert r.json()["status"] == "approved"
            finally:
                app.dependency_overrides.clear()

        assert len(upload_calls) == 1
        retailer, supplier, key, content = upload_calls[0]
        assert retailer == "lowes" and supplier == "acme"
        assert key == "signals/kelly_approved_q-001.json"
        payload = json.loads(content)
        assert payload["queue_id"] == "q-001"
        assert payload["approved_by"] == "pam_admin"
        assert payload["draft"] == "Hello Acme team!"

    def test_h08_approve_reject_db_status_updates(self):
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

        execute_calls = []
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
                mock_conn.fetchrow = AsyncMock(return_value=None)
                r = client.post("/hitl-queue/q-002/reject",
                                headers={"Authorization": f"Bearer {token}"})
                assert r.status_code == 200
            finally:
                app.dependency_overrides.clear()

        approve_sqls = [s for s in execute_calls if "APPROVED" in s]
        reject_sqls = [s for s in execute_calls if "REJECTED" in s]
        assert approve_sqls, f"Expected SQL with APPROVED, got: {execute_calls}"
        assert reject_sqls, f"Expected SQL with REJECTED, got: {execute_calls}"

    def test_h09_reject_does_not_write_signal(self):
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

        upload_calls = []

        class FakeWorkspace:
            def __init__(self, *args): pass
            def upload(self, key, content): upload_calls.append(key)

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

        assert len(upload_calls) == 0


class TestKellyDispatch:
    """Group 4 — Kelly channel dispatch (ADR-020)."""

    def test_h10_email_dispatch_calls_smtp(self):
        import agents.kelly as _kelly

        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "587",
            "SMTP_USER": "kelly@example.com", "SMTP_PASSWORD": "secret",
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
            assert call_args[0] == "smtp.example.com"
            mock_smtp_instance.starttls.assert_called_once()
            mock_smtp_instance.login.assert_called_once_with("kelly@example.com", "secret")
            mock_smtp_instance.sendmail.assert_called_once()

    def test_h11_google_chat_dispatch_calls_requests(self):
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
            assert "chat.googleapis.com" in url_called
            kwargs = mock_post.call_args[1]
            headers = kwargs.get("headers", {})
            assert "Bearer fake-oauth-token" in headers.get("Authorization", "")

    def test_h12_missing_env_dispatch_does_not_raise(self):
        import agents.kelly as _kelly

        with patch.dict("os.environ", {}, clear=True):
            try:
                _kelly._dispatch_message("email", "", "Test draft", "acme", "lowes")
                _kelly._dispatch_message("google_chat", "thread123", "Test draft", "acme", "lowes")
                _kelly._dispatch_message("ms_teams", "", "Test draft", "acme", "lowes")
            except Exception as exc:
                pytest.fail(f"_dispatch_message raised {type(exc).__name__}: {exc}")


class TestMonicaEscalation:
    """Group 5 — Monica escalation -> HITL queue (ADR-022)."""

    def test_h13_escalation_queued_to_hitl(self):
        import agents.monica as _monica

        feedback_content = (
            b"2026-03-07T10:00:00Z SENTIMENT_ESCALATION thread_id=thread-xyz supplier=acme\n"
            b"2026-03-07T11:00:00Z INFO Normal log line\n"
        )

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

        assert mock_cur.execute.called
        execute_calls_sql = [str(c[0][0]) for c in mock_cur.execute.call_args_list]
        hitl_inserts = [s for s in execute_calls_sql if "hitl_queue" in s]
        assert hitl_inserts

        insert_args = mock_cur.execute.call_args_list[-1][0]
        insert_params = insert_args[1] if len(insert_args) > 1 else ()
        assert "KELLY" in insert_params
        assert "email" in insert_params
        assert "PENDING_APPROVAL" in insert_params

        actions = result.get("actions_taken", [])
        assert any("escalation_queued" in a for a in actions)
        assert any("thread-xyz" in a for a in actions)

    def test_h14_no_escalation_no_hitl_write(self):
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

        assert not mock_connect.called
        actions = result.get("actions_taken", [])
        assert not any("kelly_escalations_detected" in a for a in actions)
        assert not any("escalation_queued" in a for a in actions)
