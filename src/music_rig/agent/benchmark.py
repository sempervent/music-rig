"""Read-only Ollama reconciliation-planning benchmark (fixture; no writes)."""

from __future__ import annotations

import time
from typing import Any

from music_rig.agent.ollama_provider import (
    OllamaProvider,
    ollama_reachable,
    ollama_tags,
)
from music_rig.agent.prompt import build_planner_prompt
from music_rig.agent.provider_packet import project_provider_packet


def benchmark_fixture_packet() -> dict[str, Any]:
    """Harmless agent-required packet (patchbay model mapping style)."""
    return {
        "schema": "music_rig.agent_packet.v1",
        "artifact": {"type": "question", "id": "Q-BENCH"},
        "question": "Which patchbay models are installed for PB-A through PB-D?",
        "final_human_answer": ("PB-A and PB-B are ART P48; PB-C and PB-D are Behringer PX3000"),
        "answer_state": "FINAL",
        "question_status": "RESOLVED",
        "verification_result": None,
        "typed_target": {"domain": "inventory.patchbay_mapping"},
        "reconciliation_state": "NEEDS_AGENT_ACTION",
        "capability": "MANUAL",
        "related_todos": [],
        "related_changes": [],
        "relevant_current_context": {
            "patchbay_models": {
                "PB-A": None,
                "PB-B": None,
                "PB-C": None,
                "PB-D": None,
            }
        },
        "allowed_operation_kinds": [
            "patchbay.set_model",
            "question.finalize_manual",
        ],
        "candidate_operations": [
            {
                "kind": "patchbay.set_model",
                "args": {"bay_id": "PB-A", "model": "ART P48"},
            }
        ],
        "required_postconditions": [
            "canonical CURRENT reflects the final human answer at the stated granularity"
        ],
        "forbidden_claims": [
            "Do not invent unique inventory unit IDs from model-only answers.",
            "Do not invent verification_result.",
        ],
        "truth_boundaries": ["Provider output is untrusted."],
        "plan_blockers": [],
        "packet_hash": "bench-fixture",
    }


def run_ollama_benchmark(
    *,
    models: list[str] | None = None,
    base_url: str = "http://127.0.0.1:11434",
    timeout_seconds: int = 180,
    warm: bool = True,
    think: bool | None = False,
) -> dict[str, Any]:
    """Benchmark reconciliation planning against installed Ollama models."""
    if not ollama_reachable(base_url):
        return {
            "ok": False,
            "error": f"Ollama not reachable at {base_url}",
            "rows": [],
        }
    available = ollama_tags(base_url)
    selected = list(models) if models else available[:5]
    packet = benchmark_fixture_packet()
    compact = project_provider_packet(packet)
    prompt_with_schema = build_planner_prompt(
        packet=packet, include_schema=True, compact_packet=True
    )
    prompt_ollama = build_planner_prompt(packet=packet, include_schema=False, compact_packet=True)
    rows: list[dict[str, Any]] = []
    for model in selected:
        if model not in available and ":" not in model:
            # try with :latest
            alt = f"{model}:latest"
            if alt in available:
                model = alt
        row = _bench_one(
            model=model,
            base_url=base_url,
            packet=packet,
            timeout_seconds=timeout_seconds,
            warm=warm,
            think=think,
        )
        rows.append(row)

    fastest = None
    valid_rows = [r for r in rows if r.get("schema_valid") and r.get("ok")]
    if valid_rows:
        fastest = min(
            valid_rows, key=lambda r: r.get("warm_total_s") or r.get("cold_total_s") or 1e9
        )
    return {
        "ok": True,
        "base_url": base_url,
        "prompt_chars_with_schema": len(prompt_with_schema),
        "prompt_chars_ollama": len(prompt_ollama),
        "compact_packet_keys": sorted(compact.keys()),
        "rows": rows,
        "fastest_valid": (fastest or {}).get("model"),
        "note": (
            "Single-run measurements — not a universal quality claim. "
            "Configuration is not rewritten."
        ),
    }


def _bench_one(
    *,
    model: str,
    base_url: str,
    packet: dict[str, Any],
    timeout_seconds: int,
    warm: bool,
    think: bool | None,
) -> dict[str, Any]:
    prov = OllamaProvider(
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        think=think,
    )
    result: dict[str, Any] = {"model": model, "ok": False}

    def _once(label: str) -> dict[str, Any]:
        t0 = time.monotonic()
        try:
            turn, diag = prov.run_turn(packet=packet, context=[])
            wall = time.monotonic() - t0
            metrics = diag.get("ollama_metrics") or {}
            return {
                "ok": True,
                "wall_s": round(wall, 3),
                "schema_valid": True,
                "turn_kind": turn.kind.value if hasattr(turn, "kind") else None,
                "prompt_chars": diag.get("prompt_chars"),
                "metrics": metrics,
                "prompt_tokens": metrics.get("prompt_eval_count"),
                "output_tokens": metrics.get("eval_count"),
                "load_s": metrics.get("load_s"),
                "prompt_eval_s": metrics.get("prompt_eval_s"),
                "eval_s": metrics.get("eval_s"),
                "total_s_api": metrics.get("total_s"),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "wall_s": round(time.monotonic() - t0, 3),
                "schema_valid": False,
                "error": str(exc),
                "code": getattr(exc, "code", type(exc).__name__),
            }

    cold = _once("cold")
    result["cold"] = cold
    result["cold_total_s"] = cold.get("wall_s")
    if warm:
        warm_run = _once("warm")
        result["warm"] = warm_run
        result["warm_total_s"] = warm_run.get("wall_s")
        best = warm_run
    else:
        best = cold
    result["ok"] = bool(best.get("ok"))
    result["schema_valid"] = bool(best.get("schema_valid"))
    result["prompt_tokens"] = best.get("prompt_tokens")
    result["output_tokens"] = best.get("output_tokens")
    result["turn_kind"] = best.get("turn_kind")
    result["prompt_chars"] = best.get("prompt_chars")
    if best.get("error"):
        result["error"] = best["error"]
    return result


def format_benchmark_table(report: dict[str, Any]) -> str:
    lines = [
        "OLLAMA RECONCILIATION BENCHMARK",
        "",
        f"{'Model':<28} {'Warm total':>10} {'Prompt tok':>11} {'Output tok':>11} {'Valid':>6}",
    ]
    for row in report.get("rows") or []:
        warm = row.get("warm_total_s")
        warm_s = f"{warm:.1f}s" if isinstance(warm, (int, float)) else "—"
        pt = row.get("prompt_tokens")
        ot = row.get("output_tokens")
        valid = "yes" if row.get("schema_valid") else "no"
        lines.append(
            f"{str(row.get('model')):<28} {warm_s:>10} "
            f"{(pt if pt is not None else '—'):>11} "
            f"{(ot if ot is not None else '—'):>11} {valid:>6}"
        )
    lines.append("")
    lines.append(f"Prompt chars (Ollama, no schema dup): {report.get('prompt_chars_ollama')}")
    lines.append(
        f"Prompt chars (with schema, Cursor-style): {report.get('prompt_chars_with_schema')}"
    )
    if report.get("fastest_valid"):
        lines.append(f"Fastest valid response in this run: {report['fastest_valid']}")
    lines.append(report.get("note") or "")
    return "\n".join(lines)
