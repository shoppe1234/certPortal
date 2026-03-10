"""Migrated from testing/suites/suite_i.py — Kelly Gemini Memory Consolidation (ADR-024)."""
import json
import os
import pytest
from unittest.mock import MagicMock, patch

pytestmark = [pytest.mark.unit]


class TestKellyConsolidateMemory:

    def test_01_consolidate_success(self):
        from agents.kelly import consolidate_memory_adk

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

        assert isinstance(result, dict)
        assert result["thread_id"] == "thread-t1"
        assert result["summary"] == fake_payload["summary"]
        assert result["sentiment_trend"] == "improving"
        assert result["key_exchanges"] == 3
        assert result["consolidated_at"] is not None
        assert isinstance(result["consolidated_at"], str)
        mock_model.generate_content.assert_called_once()

    def test_02_consolidate_fallback_on_error(self):
        from agents.kelly import consolidate_memory_adk

        # Case 1: GEMINI_API_KEY absent
        env_without_gemini = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict("os.environ", env_without_gemini, clear=True):
            result_no_key = consolidate_memory_adk("thread-t2", [])

        assert result_no_key["thread_id"] == "thread-t2"
        assert result_no_key["summary"] == ""
        assert result_no_key["sentiment_trend"] == "unknown"
        assert result_no_key["consolidated_at"] is None

        # Case 2: GenerativeModel raises RuntimeError
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            with patch("google.generativeai.configure"):
                with patch("google.generativeai.GenerativeModel",
                           side_effect=RuntimeError("Simulated API failure")):
                    result_err = consolidate_memory_adk(
                        "thread-t3",
                        [{"role": "user", "content": "Hi"}],
                    )

        assert result_err["thread_id"] == "thread-t3"
        assert result_err["summary"] == ""
        assert result_err["consolidated_at"] is None
        assert result_err["key_exchanges"] == 1
