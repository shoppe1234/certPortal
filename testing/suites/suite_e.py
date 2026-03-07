"""
testing/suites/suite_e.py — HITL Flow Tests (Monica + Kelly deterministic paths).

Tests the Human-in-the-Loop flow: HITL flag processing, sentiment escalation
detection, thread compression, and the Monica loop guard.

No live DB, S3, or OpenAI required — all external calls use mocked workspaces.

Architecture coverage:
  INV-02  — All inter-agent questions route through Monica via PAM-STATUS.json
  Monica  — process_hitl_flags, _validate_gate_consistency, _check_kelly_escalations
  Kelly   — compress_thread (deterministic), KELLY_TONE_PERSONA_MAP, _derive_scenario_id
"""
from __future__ import annotations

import traceback
from enum import Enum
from typing import Callable
from unittest.mock import MagicMock


class TestStatus(Enum):
    SKIP = "SKIP"
    PASS = "PASS"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

_MONICA_OK = False
_KELLY_OK = False
_IMPORT_ERRORS: list[str] = []

try:
    from agents.monica import (  # type: ignore[import]
        process_hitl_flags,
        _validate_gate_consistency,
        _check_kelly_escalations,
        MonicaLoopGuard,
        MAX_LOOP_ITERATIONS,
    )
    _MONICA_OK = True
except Exception as _e:  # noqa: BLE001
    _IMPORT_ERRORS.append(f"agents.monica: {_e}")

try:
    from agents.kelly import (  # type: ignore[import]
        compress_thread,
        KELLY_TONE_PERSONA_MAP,
        _derive_scenario_id,
    )
    _KELLY_OK = True
except Exception as _e:  # noqa: BLE001
    _IMPORT_ERRORS.append(f"agents.kelly: {_e}")

try:
    from certportal.core.workspace import FileNotFoundInWorkspace  # type: ignore[import]
    _FNF = FileNotFoundInWorkspace
except Exception:  # noqa: BLE001
    _FNF = Exception  # fallback so test can still be written


# ---------------------------------------------------------------------------
# Workspace mock builder
# ---------------------------------------------------------------------------

def _make_ws(pam_status: dict | None = None, feedback: bytes | None = None) -> MagicMock:
    """Minimal workspace mock for Monica/Kelly HITL tests."""
    ws = MagicMock()
    ws._supplier_slug = "acme"
    ws.read_pam_status.return_value = pam_status or {}
    ws.write_pam_status.return_value = None
    if feedback is not None:
        ws.download.return_value = feedback
    else:
        ws.download.side_effect = _FNF("GLOBAL-FEEDBACK.md not found")
    return ws


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
# Tests 01-03: Kelly compress_thread (pure Python, zero mocks)
# ---------------------------------------------------------------------------

def _test_01_compress_thread_empty() -> None:
    """compress_thread([]) returns an empty string."""
    assert _KELLY_OK, f"agents.kelly import failed: {_IMPORT_ERRORS}"
    result = compress_thread([], max_tokens=200)
    assert result == "", f"Expected empty string for empty thread, got: {result!r}"


def _test_02_compress_thread_single_message() -> None:
    """compress_thread with one message returns '[role]: content'."""
    assert _KELLY_OK, f"agents.kelly import failed: {_IMPORT_ERRORS}"
    thread = [{"role": "user", "content": "Please fix error BEG03."}]
    result = compress_thread(thread, max_tokens=200)
    assert "[user]" in result, f"Expected '[user]' in result: {result!r}"
    assert "BEG03" in result, f"Expected message content in result: {result!r}"


def _test_03_compress_thread_respects_token_limit() -> None:
    """compress_thread truncates output to approximately max_tokens * 4 characters."""
    assert _KELLY_OK, f"agents.kelly import failed: {_IMPORT_ERRORS}"
    long_content = "X" * 2000
    thread = [{"role": "user", "content": long_content}]
    result = compress_thread(thread, max_tokens=10)  # 10 tokens = 40 chars max
    # Result should be significantly shorter than the raw content
    assert len(result) < 200, \
        f"Expected compressed output <200 chars for max_tokens=10, got {len(result)}"


# ---------------------------------------------------------------------------
# Tests 04-05: Kelly pure-logic (tone map + scenario ID)
# ---------------------------------------------------------------------------

def _test_04_kelly_tone_persona_map_complete() -> None:
    """KELLY_TONE_PERSONA_MAP has all 4 tones with required keys: name, style, opener."""
    assert _KELLY_OK, f"agents.kelly import failed: {_IMPORT_ERRORS}"
    required_tones = {"frustrated", "neutral", "warm", "formal"}
    required_keys = {"name", "style", "opener"}

    assert set(KELLY_TONE_PERSONA_MAP.keys()) == required_tones, \
        f"Expected tones {required_tones}, got {set(KELLY_TONE_PERSONA_MAP.keys())}"

    for tone, persona in KELLY_TONE_PERSONA_MAP.items():
        missing = required_keys - set(persona.keys())
        assert not missing, f"Persona for tone '{tone}' missing keys: {missing}"
        for k in required_keys:
            assert persona[k], f"Persona key '{k}' for tone '{tone}' must be non-empty"


def _test_05_derive_scenario_id_stable() -> None:
    """_derive_scenario_id produces a stable, deterministic ID from trigger + thread."""
    assert _KELLY_OK, f"agents.kelly import failed: {_IMPORT_ERRORS}"

    id1 = _derive_scenario_id("validation_error:BEG03", "abc-123-xyz")
    id2 = _derive_scenario_id("validation_error:BEG03", "abc-123-xyz")
    assert id1 == id2, "Same inputs must produce same scenario ID"

    id3 = _derive_scenario_id("gate_approved:2", "abc-123-xyz")
    assert id3 != id1, "Different trigger events must produce different scenario IDs"


# ---------------------------------------------------------------------------
# Tests 06-08: Monica process_hitl_flags (mocked workspace)
# ---------------------------------------------------------------------------

def _test_06_process_hitl_flags_empty() -> None:
    """process_hitl_flags with no hitl_flags key in PAM-STATUS returns []."""
    assert _MONICA_OK, f"agents.monica import failed: {_IMPORT_ERRORS}"
    ws = _make_ws(pam_status={})  # no hitl_flags key
    result = process_hitl_flags(ws)
    assert result == [], f"Expected empty list for no flags, got: {result}"


def _test_07_process_hitl_flags_surfaces_pending_flag() -> None:
    """process_hitl_flags with 1 PENDING flag returns that flag with surfaced_at set."""
    assert _MONICA_OK, f"agents.monica import failed: {_IMPORT_ERRORS}"
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
    assert "surfaced_at" in surfaced, "PENDING flag must have 'surfaced_at' set after processing"
    assert surfaced.get("surfaced_by") == "monica", "Surfaced flags must be attributed to 'monica'"

    # write_pam_status must be called to persist the surfaced_at timestamp
    ws.write_pam_status.assert_called_once()


def _test_08_process_hitl_flags_skips_resolved() -> None:
    """process_hitl_flags skips flags with status != 'PENDING'."""
    assert _MONICA_OK, f"agents.monica import failed: {_IMPORT_ERRORS}"
    pam = {
        "hitl_flags": {
            "flag_resolved": {"agent": "ryan", "reason": "...", "status": "RESOLVED"},
            "flag_approved": {"agent": "kelly", "reason": "...", "status": "APPROVED"},
        }
    }
    ws = _make_ws(pam_status=pam)
    result = process_hitl_flags(ws)

    assert result == [], \
        f"Expected [] for all-non-PENDING flags, got: {result}"
    ws.write_pam_status.assert_not_called()


# ---------------------------------------------------------------------------
# Test 09: Monica _check_kelly_escalations (mocked workspace)
# ---------------------------------------------------------------------------

def _test_09_check_kelly_escalations_found() -> None:
    """_check_kelly_escalations extracts thread IDs from GLOBAL-FEEDBACK.md lines."""
    assert _MONICA_OK, f"agents.monica import failed: {_IMPORT_ERRORS}"

    feedback_content = (
        "[2024-01-01T00:00:00Z] [KELLY] SENTIMENT_ESCALATION thread_id=thread-42 supplier=acme\n"
        "[2024-01-01T00:01:00Z] [KELLY] SENTIMENT_ESCALATION thread_id=thread-99 supplier=acme\n"
        "[2024-01-01T00:02:00Z] [KELLY] Something else happened\n"
    ).encode("utf-8")

    ws = _make_ws(feedback=feedback_content)
    escalations = _check_kelly_escalations(ws, "acme")

    assert len(escalations) == 2, \
        f"Expected 2 escalations, got: {len(escalations)} -- {escalations}"
    assert "thread-42" in escalations, f"Expected thread-42 in {escalations}"
    assert "thread-99" in escalations, f"Expected thread-99 in {escalations}"


# ---------------------------------------------------------------------------
# Test 10: Monica process_hitl_flags loop guard
# ---------------------------------------------------------------------------

def _test_10_process_hitl_flags_loop_guard() -> None:
    """process_hitl_flags raises MonicaLoopGuard when flag count exceeds MAX_LOOP_ITERATIONS."""
    assert _MONICA_OK, f"agents.monica import failed: {_IMPORT_ERRORS}"

    # Create MAX_LOOP_ITERATIONS+1 PENDING flags (one more than the limit)
    big_flags = {
        f"flag_{i:04d}": {"agent": "ryan", "reason": "auto-gen", "status": "PENDING"}
        for i in range(MAX_LOOP_ITERATIONS + 1)
    }
    pam = {"hitl_flags": big_flags}
    ws = _make_ws(pam_status=pam)

    raised = False
    try:
        process_hitl_flags(ws)
    except MonicaLoopGuard:
        raised = True

    assert raised, \
        f"Expected MonicaLoopGuard with {MAX_LOOP_ITERATIONS + 1} flags (limit={MAX_LOOP_ITERATIONS})"


# ---------------------------------------------------------------------------
# Suite entry point
# ---------------------------------------------------------------------------

def run() -> list[dict]:
    """Run all 10 HITL flow tests. No live DB, S3, or OpenAI required."""
    tests = [
        ("suite_e_test_01", "Kelly: compress_thread([]) returns ''",                         _test_01_compress_thread_empty),
        ("suite_e_test_02", "Kelly: compress_thread single message has role+content",        _test_02_compress_thread_single_message),
        ("suite_e_test_03", "Kelly: compress_thread respects max_tokens limit",              _test_03_compress_thread_respects_token_limit),
        ("suite_e_test_04", "Kelly: TONE_PERSONA_MAP has 4 tones with name/style/opener",   _test_04_kelly_tone_persona_map_complete),
        ("suite_e_test_05", "Kelly: _derive_scenario_id is stable and deterministic",       _test_05_derive_scenario_id_stable),
        ("suite_e_test_06", "Monica: process_hitl_flags empty PAM -> []",                   _test_06_process_hitl_flags_empty),
        ("suite_e_test_07", "Monica: process_hitl_flags PENDING flag -> surfaced + written", _test_07_process_hitl_flags_surfaces_pending_flag),
        ("suite_e_test_08", "Monica: process_hitl_flags skips RESOLVED/APPROVED flags",     _test_08_process_hitl_flags_skips_resolved),
        ("suite_e_test_09", "Monica: _check_kelly_escalations finds thread IDs",            _test_09_check_kelly_escalations_found),
        ("suite_e_test_10", "Monica: process_hitl_flags raises MonicaLoopGuard at limit",   _test_10_process_hitl_flags_loop_guard),
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
