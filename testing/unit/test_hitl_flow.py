"""Migrated from testing/suites/suite_e.py — HITL Flow Tests (Monica + Kelly)."""
import pytest
from unittest.mock import MagicMock

pytestmark = [pytest.mark.unit]

monica = pytest.importorskip("agents.monica")
process_hitl_flags = monica.process_hitl_flags
_check_kelly_escalations = monica._check_kelly_escalations
MonicaLoopGuard = monica.MonicaLoopGuard
MAX_LOOP_ITERATIONS = monica.MAX_LOOP_ITERATIONS

kelly = pytest.importorskip("agents.kelly")
compress_thread = kelly.compress_thread
KELLY_TONE_PERSONA_MAP = kelly.KELLY_TONE_PERSONA_MAP
_derive_scenario_id = kelly._derive_scenario_id

try:
    from certportal.core.workspace import FileNotFoundInWorkspace as _FNF
except Exception:
    _FNF = Exception


def _make_ws(pam_status=None, feedback=None):
    ws = MagicMock()
    ws._supplier_slug = "acme"
    ws.read_pam_status.return_value = pam_status or {}
    ws.write_pam_status.return_value = None
    if feedback is not None:
        ws.download.return_value = feedback
    else:
        ws.download.side_effect = _FNF("GLOBAL-FEEDBACK.md not found")
    return ws


class TestKellyCompressThread:

    def test_01_compress_thread_empty(self):
        result = compress_thread([], max_tokens=200)
        assert result == "", f"Expected empty string for empty thread, got: {result!r}"

    def test_02_compress_thread_single_message(self):
        thread = [{"role": "user", "content": "Please fix error BEG03."}]
        result = compress_thread(thread, max_tokens=200)
        assert "[user]" in result, f"Expected '[user]' in result: {result!r}"
        assert "BEG03" in result, f"Expected message content in result: {result!r}"

    def test_03_compress_thread_respects_token_limit(self):
        long_content = "X" * 2000
        thread = [{"role": "user", "content": long_content}]
        result = compress_thread(thread, max_tokens=10)
        assert len(result) < 200, f"Expected compressed output <200 chars, got {len(result)}"


class TestKellyPureLogic:

    def test_04_tone_persona_map_complete(self):
        required_tones = {"frustrated", "neutral", "warm", "formal"}
        required_keys = {"name", "style", "opener"}
        assert set(KELLY_TONE_PERSONA_MAP.keys()) == required_tones
        for tone, persona in KELLY_TONE_PERSONA_MAP.items():
            missing = required_keys - set(persona.keys())
            assert not missing, f"Persona for tone '{tone}' missing keys: {missing}"
            for k in required_keys:
                assert persona[k], f"Persona key '{k}' for tone '{tone}' must be non-empty"

    def test_05_derive_scenario_id_stable(self):
        id1 = _derive_scenario_id("validation_error:BEG03", "abc-123-xyz")
        id2 = _derive_scenario_id("validation_error:BEG03", "abc-123-xyz")
        assert id1 == id2, "Same inputs must produce same scenario ID"
        id3 = _derive_scenario_id("gate_approved:2", "abc-123-xyz")
        assert id3 != id1, "Different trigger events must produce different scenario IDs"


class TestMonicaHitlFlags:

    def test_06_process_hitl_flags_empty(self):
        ws = _make_ws(pam_status={})
        result = process_hitl_flags(ws)
        assert result == [], f"Expected empty list for no flags, got: {result}"

    def test_07_process_hitl_flags_surfaces_pending(self):
        pam = {
            "hitl_flags": {
                "flag_001": {
                    "agent": "ryan",
                    "reason": "No THESIS rule for BEG03",
                    "status": "PENDING",
                }
            }
        }
        ws = _make_ws(pam_status=pam)
        result = process_hitl_flags(ws)
        assert len(result) == 1, f"Expected 1 flag, got: {len(result)}"
        surfaced = result[0]
        assert "surfaced_at" in surfaced
        assert surfaced.get("surfaced_by") == "monica"
        ws.write_pam_status.assert_called_once()

    def test_08_process_hitl_flags_skips_resolved(self):
        pam = {
            "hitl_flags": {
                "flag_resolved": {"agent": "ryan", "reason": "...", "status": "RESOLVED"},
                "flag_approved": {"agent": "kelly", "reason": "...", "status": "APPROVED"},
            }
        }
        ws = _make_ws(pam_status=pam)
        result = process_hitl_flags(ws)
        assert result == []
        ws.write_pam_status.assert_not_called()

    def test_09_check_kelly_escalations_found(self):
        feedback_content = (
            "[2024-01-01T00:00:00Z] [KELLY] SENTIMENT_ESCALATION thread_id=thread-42 supplier=acme\n"
            "[2024-01-01T00:01:00Z] [KELLY] SENTIMENT_ESCALATION thread_id=thread-99 supplier=acme\n"
            "[2024-01-01T00:02:00Z] [KELLY] Something else happened\n"
        ).encode("utf-8")
        ws = _make_ws(feedback=feedback_content)
        escalations = _check_kelly_escalations(ws, "acme")
        assert len(escalations) == 2
        assert "thread-42" in escalations
        assert "thread-99" in escalations

    def test_10_process_hitl_flags_loop_guard(self):
        big_flags = {
            f"flag_{i:04d}": {"agent": "ryan", "reason": "auto-gen", "status": "PENDING"}
            for i in range(MAX_LOOP_ITERATIONS + 1)
        }
        pam = {"hitl_flags": big_flags}
        ws = _make_ws(pam_status=pam)
        with pytest.raises(MonicaLoopGuard):
            process_hitl_flags(ws)
