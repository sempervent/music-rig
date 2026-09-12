"""Tests migrated to unit/agent/test_ollama_metrics.py."""

from __future__ import annotations

import json

from music_rig.progress import CollectingProgress, ProgressPhase, ProgressTracker


def test_progress_json_isolation():
    """Progress sink must not be required for JSON; CollectingProgress is clean."""
    sink = CollectingProgress()
    tracker = ProgressTracker(sink=sink, provider="Ollama", model="qwen")
    tracker.emit(ProgressPhase.PROVIDER_GENERATING, "generating")
    assert len(sink.events) == 1
    assert sink.events[0].message == "generating"
    # Event serializes without Rich markup
    blob = json.dumps(sink.events[0].to_dict())
    assert "generating" in blob


def test_ollama_metrics_parser():
    from music_rig.agent.ollama_provider import extract_ollama_metrics

    raw = {
        "total_duration": 34_200_000_000,
        "load_duration": 1_000_000_000,
        "prompt_eval_count": 2104,
        "prompt_eval_duration": 5_000_000_000,
        "eval_count": 167,
        "eval_duration": 28_000_000_000,
    }
    m = extract_ollama_metrics(raw)
    assert m["prompt_eval_count"] == 2104
    assert m["total_s"] == 34.2
    assert "invented" not in m


def test_benchmark_format_includes_header():
    from music_rig.agent.benchmark import format_benchmark_table

    text = format_benchmark_table(
        {
            "prompt_chars_ollama": 100,
            "prompt_chars_with_schema": 500,
            "rows": [
                {
                    "model": "qwen3.5:latest",
                    "warm_total_s": 12.3,
                    "prompt_tokens": 100,
                    "output_tokens": 20,
                    "schema_valid": True,
                }
            ],
            "fastest_valid": "qwen3.5:latest",
            "note": "note",
        }
    )
    assert "OLLAMA RECONCILIATION BENCHMARK" in text
    assert "qwen3.5:latest" in text
