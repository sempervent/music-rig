"""Honest automation capability registry and dry-run performance planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from music_rig.local_config import load_local_config
from music_rig.models import (
    PerformanceAction,
    PerformanceDocument,
    PerformanceEffect,
    PerformanceEffectKind,
)
from music_rig.performance_state import evaluate_readiness
from music_rig.store import StoreError, load_performance


class AdapterFamily(StrEnum):
    MANUAL = "MANUAL"
    REPOSITORY_SNAPSHOT = "REPOSITORY_SNAPSHOT"
    FILE_BACKUP = "FILE_BACKUP"
    OBS = "OBS"
    ABLETON = "ABLETON"
    MIDI = "MIDI"
    MACOS = "MACOS"


class CapabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class PlanExecutionState(StrEnum):
    AUTOMATABLE = "AUTOMATABLE"
    MANUAL = "MANUAL"
    UNIMPLEMENTED = "UNIMPLEMENTED"
    UNKNOWN = "UNKNOWN"


class SimulateResult(StrEnum):
    SIMULATABLE = "SIMULATABLE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class PreflightSeverity(StrEnum):
    PASS = "PASS"
    ADVISORY = "ADVISORY"
    BLOCKER = "BLOCKER"
    UNKNOWN = "UNKNOWN"


SIMULATION_BANNER = "SIMULATION — NO EXTERNAL ACTIONS WILL BE EXECUTED"


CAPABILITIES: dict[AdapterFamily, CapabilityStatus] = {
    AdapterFamily.MANUAL: CapabilityStatus.AVAILABLE,
    AdapterFamily.REPOSITORY_SNAPSHOT: CapabilityStatus.AVAILABLE,
    AdapterFamily.FILE_BACKUP: CapabilityStatus.AVAILABLE,
    AdapterFamily.OBS: CapabilityStatus.NOT_IMPLEMENTED,
    AdapterFamily.ABLETON: CapabilityStatus.NOT_IMPLEMENTED,
    AdapterFamily.MIDI: CapabilityStatus.NOT_IMPLEMENTED,
    AdapterFamily.MACOS: CapabilityStatus.NOT_IMPLEMENTED,
}


EFFECT_ADAPTER: dict[PerformanceEffectKind, AdapterFamily] = {
    PerformanceEffectKind.OBS_ACTION: AdapterFamily.OBS,
    PerformanceEffectKind.ABLETON_ACTION: AdapterFamily.ABLETON,
    PerformanceEffectKind.MIDI_ACTION: AdapterFamily.MIDI,
    PerformanceEffectKind.HARDWARE_PROCEDURE: AdapterFamily.MANUAL,
    PerformanceEffectKind.MANUAL_STEP: AdapterFamily.MANUAL,
}


@dataclass(frozen=True)
class PlannedStep:
    index: int
    effect: PerformanceEffect
    adapter: AdapterFamily
    state: PlanExecutionState
    detail: str


@dataclass(frozen=True)
class ActionPlan:
    action_id: str
    label: str
    steps: list[PlannedStep]

    @property
    def overall(self) -> PlanExecutionState:
        states = {step.state for step in self.steps}
        if not states:
            return PlanExecutionState.UNKNOWN
        if PlanExecutionState.UNIMPLEMENTED in states:
            if states <= {
                PlanExecutionState.UNIMPLEMENTED,
                PlanExecutionState.MANUAL,
                PlanExecutionState.UNKNOWN,
            }:
                return PlanExecutionState.UNIMPLEMENTED
            return PlanExecutionState.UNIMPLEMENTED
        if PlanExecutionState.UNKNOWN in states:
            return PlanExecutionState.UNKNOWN
        if states == {PlanExecutionState.AUTOMATABLE}:
            return PlanExecutionState.AUTOMATABLE
        if PlanExecutionState.MANUAL in states and PlanExecutionState.AUTOMATABLE in states:
            return PlanExecutionState.MANUAL
        if states == {PlanExecutionState.MANUAL}:
            return PlanExecutionState.MANUAL
        return PlanExecutionState.UNKNOWN


@dataclass(frozen=True)
class SimulationReport:
    banner: str
    action_id: str
    result: SimulateResult
    plan: ActionPlan
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PreflightFinding:
    severity: PreflightSeverity
    section: str
    message: str


@dataclass(frozen=True)
class PreflightReport:
    mode: str
    findings: list[PreflightFinding]

    @property
    def worst(self) -> PreflightSeverity:
        order = [
            PreflightSeverity.PASS,
            PreflightSeverity.ADVISORY,
            PreflightSeverity.UNKNOWN,
            PreflightSeverity.BLOCKER,
        ]
        worst = PreflightSeverity.PASS
        for finding in self.findings:
            if order.index(finding.severity) > order.index(worst):
                worst = finding.severity
        return worst


def list_capabilities() -> list[tuple[AdapterFamily, CapabilityStatus]]:
    return [(family, CAPABILITIES[family]) for family in AdapterFamily]


def adapter_for_effect(effect: PerformanceEffect) -> AdapterFamily:
    return EFFECT_ADAPTER.get(effect.kind, AdapterFamily.MANUAL)


def execution_state_for(adapter: AdapterFamily) -> PlanExecutionState:
    status = CAPABILITIES.get(adapter, CapabilityStatus.NOT_IMPLEMENTED)
    if adapter == AdapterFamily.MANUAL:
        return PlanExecutionState.MANUAL
    if status == CapabilityStatus.AVAILABLE:
        return PlanExecutionState.AUTOMATABLE
    if status == CapabilityStatus.NOT_IMPLEMENTED:
        return PlanExecutionState.UNIMPLEMENTED
    return PlanExecutionState.UNKNOWN


def compile_effect(effect: PerformanceEffect, index: int) -> PlannedStep:
    adapter = adapter_for_effect(effect)
    state = execution_state_for(adapter)
    if state == PlanExecutionState.UNIMPLEMENTED:
        detail = f"{adapter.value} adapter not implemented"
    elif state == PlanExecutionState.MANUAL:
        detail = "operator / hardware procedure"
    elif state == PlanExecutionState.AUTOMATABLE:
        detail = f"{adapter.value} available"
    else:
        detail = "unknown adapter"
    return PlannedStep(
        index=index,
        effect=effect,
        adapter=adapter,
        state=state,
        detail=detail,
    )


def compile_action_plan(action: PerformanceAction) -> ActionPlan:
    steps = [compile_effect(effect, index) for index, effect in enumerate(action.effects, start=1)]
    return ActionPlan(action_id=action.id, label=action.label, steps=steps)


def get_action(doc: PerformanceDocument, action_id: str) -> PerformanceAction:
    action = next((item for item in doc.actions if item.id == action_id), None)
    if action is None:
        raise StoreError(f"Unknown performance action {action_id!r}")
    return action


def simulate_action(action: PerformanceAction) -> SimulationReport:
    plan = compile_action_plan(action)
    notes: list[str] = []
    unimplemented = [step for step in plan.steps if step.state == PlanExecutionState.UNIMPLEMENTED]
    manual = [step for step in plan.steps if step.state == PlanExecutionState.MANUAL]
    if unimplemented and not manual and len(unimplemented) == len(plan.steps):
        result = SimulateResult.BLOCKED
        notes.append("All effects require unimplemented adapters; nothing can run.")
    elif unimplemented:
        result = SimulateResult.PARTIAL
        notes.append(f"{len(unimplemented)} effect(s) blocked by unimplemented adapters.")
    elif manual and not any(step.state == PlanExecutionState.AUTOMATABLE for step in plan.steps):
        result = SimulateResult.SIMULATABLE
        notes.append("Plan is manual-only; simulation lists steps without executing.")
    else:
        result = SimulateResult.SIMULATABLE
        notes.append("Simulation only — no OBS/Ableton/MIDI/macOS side effects.")
    return SimulationReport(
        banner=SIMULATION_BANNER,
        action_id=action.id,
        result=result,
        plan=plan,
        notes=notes,
    )


def known_plan_category(effect: PerformanceEffect) -> bool:
    return effect.kind in EFFECT_ADAPTER


def preflight(
    *,
    mode: str = "pfl-jam",
    performance_doc: PerformanceDocument | None = None,
    root=None,
) -> PreflightReport:
    """Advisory readiness check. Never modifies files; never blocks play."""
    findings: list[PreflightFinding] = []
    doc = performance_doc or load_performance()
    mode_obj = next((item for item in doc.modes if item.id == mode), None)
    if mode_obj is None:
        findings.append(
            PreflightFinding(
                PreflightSeverity.UNKNOWN,
                "Mode",
                f"Mode {mode!r} not found in performance.yaml",
            )
        )
    else:
        findings.append(
            PreflightFinding(
                PreflightSeverity.PASS,
                "Mode",
                f"Mode {mode_obj.id} present ({mode_obj.evidence.value})",
            )
        )

    readiness = evaluate_readiness(doc)
    if readiness.result.value == "READY":
        findings.append(
            PreflightFinding(
                PreflightSeverity.PASS,
                "Readiness",
                "Structural readiness READY",
            )
        )
    elif readiness.result.value == "PARTIAL":
        findings.append(
            PreflightFinding(
                PreflightSeverity.ADVISORY,
                "Readiness",
                "Structural readiness PARTIAL — advisory only; does not block play",
            )
        )
        for reason in readiness.reasons[:5]:
            findings.append(PreflightFinding(PreflightSeverity.ADVISORY, "Readiness", reason))
    else:
        findings.append(
            PreflightFinding(
                PreflightSeverity.ADVISORY,
                "Readiness",
                "Structural readiness NOT_READY — advisory only; does not block play",
            )
        )
        for reason in readiness.reasons[:5]:
            findings.append(PreflightFinding(PreflightSeverity.ADVISORY, "Readiness", reason))

    config = load_local_config(root=root)
    if config is None:
        findings.append(
            PreflightFinding(
                PreflightSeverity.ADVISORY,
                "Local config",
                "`.rig.local.yaml` absent (optional; copy from .rig.local.example.yaml)",
            )
        )
    else:
        findings.append(
            PreflightFinding(
                PreflightSeverity.PASS,
                "Local config",
                "`.rig.local.yaml` present (paths not printed)",
            )
        )

    unimplemented = [
        family.value
        for family, status in CAPABILITIES.items()
        if status == CapabilityStatus.NOT_IMPLEMENTED
    ]
    findings.append(
        PreflightFinding(
            PreflightSeverity.ADVISORY,
            "Automation",
            "External adapters not implemented: " + ", ".join(unimplemented),
        )
    )
    findings.append(
        PreflightFinding(
            PreflightSeverity.PASS,
            "Safety",
            "Preflight does not connect to OBS, Ableton, MIDI, or Stream Deck",
        )
    )
    return PreflightReport(mode=mode, findings=findings)
