"""
testing/suites/suite_i.py — Kelly Agent: Gemini Memory Consolidation (ADR-024). 2 tests.

Tests agents/kelly.consolidate_memory_adk() using mocked google.generativeai.

No live Gemini API, S3, or DB required — all external calls are mocked.

Architecture coverage:
  ADR-024 — Kelly Gemini Flash-Lite thread memory consolidation
             (google-generativeai SDK, gemini-1.5-flash-8b, fail-safe pattern)
"""
from __future__ import annotations

import traceback
from enum import Enum
from typing import Callable


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


# ---------------------------------------------------------------------------
# Test i01: consolidate_memory_adk returns structured dict when Gemini responds
# ---------------------------------------------------------------------------

def _test_i01_consolidate_success() -> None:
    """consolidate_memory_adk returns structured dict when Gemini API responds correctly."""
    import json
    from unittest.mock import MagicMock, patch

    try:
        from agents.kelly import consolidate_memory_adk  # type: ignore[import]
    except Exception as exc:
        raise AssertionError(f"Cannot import agents.kelly: {exc}") from exc

    fake_payload = {
        "summary": "Supplier confirmed spec v2 and acknowledged the 850 requirement.",
        "sentiment_trend": "improving",
        "key_exchanges": 3,
    }
    fake_json = json.dumps(fake_payload)

    mock_model = MagicMock()
    mock_model.generate_content.return_value = MagicMock(text=fake_json)

    history = [
        {"role": "user", "content": "Hello, we received your 850."},
        {"role": "assistant", "content": "Spec v2 confirmed."},
    ]

    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key-not-real"}):
        with patch("google.generativeai.configure"):
            with patch("google.generativeai.GenerativeModel", return_value=mock_model):
                result = consolidate_memory_adk("thread-t1", history)

    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result["thread_id"] == "thread-t1", \
        f"thread_id mismatch: {result['thread_id']!r}"
    assert result["summary"] == fake_payload["summary"], \
        f"summary mismatch: {result['summary']!r}"
    assert result["sentiment_trend"] == "improving", \
        f"sentiment_trend: {result['sentiment_trend']!r}"
    assert result["key_exchanges"] == 3, \
        f"key_exchanges: {result['key_exchanges']!r}"
    assert result["consolidated_at"] is not None, \
        "consolidated_at should be set on successful call"
    assert isinstance(result["consolidated_at"], str), \
        f"consolidated_at should be str, got {type(result['consolidated_at'])}"

    # Verify Gemini was actually called
    mock_model.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# Test i02: consolidate_memory_adk returns fallback dict on API error / missing key
# ---------------------------------------------------------------------------

def _test_i02_consolidate_fallback_on_error() -> None:
    """consolidate_memory_adk returns empty-summary fallback on API error or missing key."""
    import os
    from unittest.mock import patch

    try:
        from agents.kelly import consolidate_memory_adk  # type: ignore[import]
    except Exception as exc:
        raise AssertionError(f"Cannot import agents.kelly: {exc}") from exc

    # ── Case 1: GEMINI_API_KEY absent -> immediate fallback ────────────────
    env_without_gemini = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    with patch.dict("os.environ", env_without_gemini, clear=True):
        result_no_key = consolidate_memory_adk("thread-t2", [])

    assert result_no_key["thread_id"] == "thread-t2", \
        f"thread_id wrong: {result_no_key['thread_id']!r}"
    assert result_no_key["summary"] == "", \
        f"Expected empty summary, got {result_no_key['summary']!r}"
    assert result_no_key["sentiment_trend"] == "unknown", \
        f"Expected 'unknown', got {result_no_key['sentiment_trend']!r}"
    assert result_no_key["consolidated_at"] is None, \
        "consolidated_at should be None on fallback"

    # ── Case 2: GenerativeModel raises RuntimeError -> graceful fallback ───
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
        with patch("google.generativeai.configure"):
            with patch("google.generativeai.GenerativeModel",
                       side_effect=RuntimeError("Simulated API failure")):
                result_err = consolidate_memory_adk(
                    "thread-t3",
                    [{"role": "user", "content": "Hi"}],
                )

    assert result_err["thread_id"] == "thread-t3", \
        f"thread_id wrong on error path: {result_err['thread_id']!r}"
    assert result_err["summary"] == "", \
        f"Expected empty summary on error, got {result_err['summary']!r}"
    assert result_err["consolidated_at"] is None, \
        "consolidated_at should be None on API error"
    assert result_err["key_exchanges"] == 1, \
        f"key_exchanges should fallback to len(history)=1, got {result_err['key_exchanges']}"


# ---------------------------------------------------------------------------
# Suite entry point
# ---------------------------------------------------------------------------

def run() -> list[dict]:
    """Run all 2 Kelly ADK memory consolidation tests. No live Gemini API required."""
    tests = [
        (
            "suite_i_01",
            "Kelly: consolidate_memory_adk returns structured dict (ADR-024)",
            _test_i01_consolidate_success,
        ),
        (
            "suite_i_02",
            "Kelly: consolidate_memory_adk returns fallback on API error / missing key (ADR-024)",
            _test_i02_consolidate_fallback_on_error,
        ),
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
