#!/usr/bin/env python3
"""Stdio fake agent provider for Stage 21 tests.

Reads a JSON envelope from stdin. Behaviour is selected by FAKE_PROVIDER_MODE
(and optional FAKE_PROVIDER_STATE call counter). Optional CWD_PROBE_PATH records cwd.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def _count() -> int:
    path = os.environ.get("FAKE_PROVIDER_STATE")
    if not path:
        return 0
    p = Path(path)
    if not p.exists():
        return 0
    try:
        return int(p.read_text(encoding="utf-8").strip() or "0")
    except ValueError:
        return 0


def _bump() -> int:
    path = os.environ.get("FAKE_PROVIDER_STATE")
    n = _count() + 1
    if path:
        Path(path).write_text(str(n), encoding="utf-8")
    return n


def _artifact(envelope: dict) -> str:
    packet = envelope.get("packet") or {}
    return str((packet.get("artifact") or {}).get("id") or "Q-200").upper()


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def main() -> int:
    probe = os.environ.get("CWD_PROBE_PATH")
    if probe:
        Path(probe).write_text(os.getcwd(), encoding="utf-8")

    mode = (os.environ.get("FAKE_PROVIDER_MODE") or "READY").upper()
    raw = sys.stdin.read()
    try:
        envelope = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        envelope = {}

    artifact = _artifact(envelope)
    n = _bump()

    if mode == "TIMEOUT":
        time.sleep(30)
        return 0

    if mode == "NONZERO":
        sys.stderr.write("provider boom\n")
        return 1

    if mode == "MALFORMED":
        sys.stdout.write("this-is-not-json{{{")
        return 0

    if mode == "OVERSIZE":
        sys.stdout.write("x" * 50_000)
        return 0

    if mode == "CLARIFY":
        _emit(
            {
                "kind": "NEEDS_HUMAN_CLARIFICATION",
                "rationale": "ambiguous destinations",
                "clarification_questions": [
                    "Which Alesis return is Acoustic — 2 or 3?"
                ],
            }
        )
        return 0

    if mode in {"MORE_CONTEXT", "REPEAT"}:
        req = {
            "kind": "routing.path",
            "id": "dirty",
            "filters": {},
        }
        if mode == "MORE_CONTEXT" and n >= 2:
            _emit(
                {
                    "kind": "READY",
                    "rationale": "enough context after routing.path",
                    "proposal": {
                        "artifact_id": artifact,
                        "status": "READY",
                        "rationale": "set models from answer",
                        "finalize": False,
                        "operations": [
                            {
                                "namespace": "patchbay",
                                "action": "set_model",
                                "args": {
                                    "bay_id": "PB-A",
                                    "model": "ART P48",
                                    "question_id": artifact,
                                },
                            }
                        ],
                    },
                }
            )
            return 0
        _emit(
            {
                "kind": "NEEDS_MORE_CONTEXT",
                "rationale": "need routing path",
                "inspection_requests": [req],
            }
        )
        return 0

    if mode == "EVIDENCE_ATTACK":
        _emit(
            {
                "kind": "READY",
                "rationale": "try to verify without observation",
                "proposal": {
                    "artifact_id": artifact,
                    "status": "READY",
                    "rationale": "evidence attack",
                    "finalize": False,
                    "operations": [
                        {
                            "namespace": "path",
                            "action": "set_evidence",
                            "args": {
                                "path_id": "dirty",
                                "evidence": "VERIFIED",
                                "question_id": artifact,
                            },
                        }
                    ],
                },
            }
        )
        return 0

    if mode == "IRRELEVANT":
        _emit(
            {
                "kind": "READY",
                "rationale": "wrong domain",
                "proposal": {
                    "artifact_id": artifact,
                    "status": "READY",
                    "rationale": "wishlist noise",
                    "finalize": False,
                    "operations": [
                        {
                            "namespace": "wishlist",
                            "action": "add",
                            "args": {"item": "noise"},
                        }
                    ],
                },
            }
        )
        return 0

    if mode == "Q001":
        _emit(
            {
                "kind": "READY",
                "rationale": "map Alesis channels from answer",
                "proposal": {
                    "artifact_id": artifact,
                    "status": "READY",
                    "rationale": "Acoustic→2 Bass→1 Electric→3",
                    "finalize": False,
                    "operations": [
                        {
                            "namespace": "channels",
                            "action": "set_source",
                            "args": {
                                "device": "alesis",
                                "channel": "1",
                                "source": "Bass",
                                "question_id": artifact,
                            },
                        },
                        {
                            "namespace": "channels",
                            "action": "set_source",
                            "args": {
                                "device": "alesis",
                                "channel": "2",
                                "source": "Acoustic",
                                "question_id": artifact,
                            },
                        },
                        {
                            "namespace": "channels",
                            "action": "set_source",
                            "args": {
                                "device": "alesis",
                                "channel": "3",
                                "source": "Electric",
                                "question_id": artifact,
                            },
                        },
                    ],
                },
            }
        )
        return 0

    if mode == "Q007":
        _emit(
            {
                "kind": "READY",
                "rationale": "model-level mapping only",
                "proposal": {
                    "artifact_id": artifact,
                    "status": "READY",
                    "rationale": "PB-A/B ART P48; PB-C/D PX3000",
                    "finalize": False,
                    "operations": [
                        {
                            "namespace": "patchbay",
                            "action": "set_model",
                            "args": {
                                "bay_id": "PB-A",
                                "model": "ART P48",
                                "question_id": artifact,
                            },
                        },
                        {
                            "namespace": "patchbay",
                            "action": "set_model",
                            "args": {
                                "bay_id": "PB-B",
                                "model": "ART P48",
                                "question_id": artifact,
                            },
                        },
                        {
                            "namespace": "patchbay",
                            "action": "set_model",
                            "args": {
                                "bay_id": "PB-C",
                                "model": "Behringer PX3000",
                                "question_id": artifact,
                            },
                        },
                        {
                            "namespace": "patchbay",
                            "action": "set_model",
                            "args": {
                                "bay_id": "PB-D",
                                "model": "Behringer PX3000",
                                "question_id": artifact,
                            },
                        },
                    ],
                },
            }
        )
        return 0

    # Default READY — Q-200 style patchbay.set_model
    _emit(
        {
            "kind": "READY",
            "rationale": "map models from human answer",
            "proposal": {
                "artifact_id": artifact,
                "status": "READY",
                "rationale": "PB-A/B ART P48; PB-C/D Behringer PX3000",
                "finalize": False,
                "operations": [
                    {
                        "namespace": "patchbay",
                        "action": "set_model",
                        "args": {
                            "bay_id": "PB-A",
                            "model": "ART P48",
                            "question_id": artifact,
                        },
                    },
                    {
                        "namespace": "patchbay",
                        "action": "set_model",
                        "args": {
                            "bay_id": "PB-B",
                            "model": "ART P48",
                            "question_id": artifact,
                        },
                    },
                    {
                        "namespace": "patchbay",
                        "action": "set_model",
                        "args": {
                            "bay_id": "PB-C",
                            "model": "Behringer PX3000",
                            "question_id": artifact,
                        },
                    },
                    {
                        "namespace": "patchbay",
                        "action": "set_model",
                        "args": {
                            "bay_id": "PB-D",
                            "model": "Behringer PX3000",
                            "question_id": artifact,
                        },
                    },
                ],
            },
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
