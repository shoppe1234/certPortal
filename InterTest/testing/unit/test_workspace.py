"""Migrated from testing/suites/suite_d.py — Workspace Scope Tests (INV-06 + INV-05)."""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = [pytest.mark.unit]

ws_mod = pytest.importorskip("certportal.core.workspace")
S3AgentWorkspace = ws_mod.S3AgentWorkspace
WorkspaceScopeViolation = ws_mod.WorkspaceScopeViolation
FileNotFoundInWorkspace = ws_mod.FileNotFoundInWorkspace

botocore_exc = pytest.importorskip("botocore.exceptions")
ClientError = botocore_exc.ClientError


def _make_ws(retailer="lowes", supplier="acme"):
    with patch("certportal.core.workspace.boto3.client"):
        ws = S3AgentWorkspace(retailer, supplier)
    return ws


def _make_body(content: bytes):
    body = MagicMock()
    body.read.return_value = content
    return body


def _no_such_key():
    return ClientError({"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject")


class TestScopedKey:

    def test_01_correct_prefix(self):
        ws = _make_ws("lowes", "acme-corp")
        key = ws._scoped_key("maps/850.yaml")
        assert key == "lowes/acme-corp/maps/850.yaml"

    def test_02_rejects_dotdot(self):
        ws = _make_ws()
        with pytest.raises(WorkspaceScopeViolation):
            ws._scoped_key("../other-supplier/secret.json")

    def test_03_rejects_absolute_path(self):
        ws = _make_ws()
        with pytest.raises(WorkspaceScopeViolation):
            ws._scoped_key("/etc/passwd")


class TestUploadDownload:

    def test_04_upload_puts_to_correct_key(self):
        ws = _make_ws("lowes", "acme")
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        ws._client = mock_client
        returned = ws.upload("maps/850.yaml", b"YAML content")
        expected_key = "lowes/acme/maps/850.yaml"
        assert returned == expected_key
        mock_client.put_object.assert_called_once()
        kwargs = mock_client.put_object.call_args.kwargs
        assert kwargs["Key"] == expected_key
        assert kwargs["Body"] == b"YAML content"

    def test_05_download_returns_content(self):
        ws = _make_ws("lowes", "acme")
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_body(b"EDI data")}
        ws._client = mock_client
        content = ws.download("results/val.json")
        assert content == b"EDI data"
        kwargs = mock_client.get_object.call_args.kwargs
        assert kwargs["Key"] == "lowes/acme/results/val.json"

    def test_06_download_missing_key_raises(self):
        ws = _make_ws()
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _no_such_key()
        ws._client = mock_client
        with pytest.raises(FileNotFoundInWorkspace):
            ws.download("missing/file.json")


class TestSpecialPaths:

    def test_07_retailer_map_excludes_supplier_prefix(self):
        ws = _make_ws("lowes", "acme")
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_body(b"THESIS content")}
        ws._client = mock_client
        content = ws.download_retailer_map("THESIS.md")
        assert content == b"THESIS content"
        key_used = mock_client.get_object.call_args.kwargs["Key"]
        assert key_used == "lowes/THESIS.md"
        assert "acme" not in key_used

    def test_08_monica_memory_routes_to_admin(self):
        ws = _make_ws("lowes", "acme")
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _no_such_key()
        mock_client.put_object.return_value = {}
        ws._client = mock_client
        ws.append_log("MONICA-MEMORY.MD", "Test log entry")
        key_written = mock_client.put_object.call_args.kwargs["Key"]
        assert key_written == "admin/MONICA-MEMORY.MD"
        assert "acme" not in key_written
        body_text = mock_client.put_object.call_args.kwargs["Body"].decode("utf-8")
        assert "Test log entry" in body_text

    def test_09_write_pam_status_cross_supplier_blocked(self):
        ws = _make_ws("lowes", "acme")
        with pytest.raises(WorkspaceScopeViolation):
            ws.write_pam_status("other-supplier", {"hitl_flag": True})

    def test_10_append_log_normal_key_scoped_and_appends(self):
        ws = _make_ws("lowes", "acme")
        mock_client = MagicMock()
        existing = b"prior line\n"
        mock_client.get_object.return_value = {"Body": _make_body(existing)}
        mock_client.put_object.return_value = {}
        ws._client = mock_client
        ws.append_log("logs/ops.log", "new log entry")
        key_written = mock_client.put_object.call_args.kwargs["Key"]
        assert key_written == "lowes/acme/logs/ops.log"
        body_text = mock_client.put_object.call_args.kwargs["Body"].decode("utf-8")
        assert "prior line" in body_text
        assert "new log entry" in body_text
        assert body_text.index("prior line") < body_text.index("new log entry")
