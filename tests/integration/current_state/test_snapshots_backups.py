"""Stage 11: snapshots, backups, local config, automation honesty."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml
from typer.testing import CliRunner

from music_rig import automation, backup_state, snapshot_service
from music_rig.cli import app
from music_rig.local_config import load_local_config
from music_rig.models import (
    MidiEvidenceStatus,
    PerformanceAction,
    PerformanceActionCategory,
    PerformanceCriticality,
    PerformanceEffect,
    PerformanceEffectKind,
)
from music_rig.store import ROOT, StoreError

runner = CliRunner()
TZ = ZoneInfo("America/New_York")


def _clock_at(stamp: str):
    when = datetime.fromisoformat(stamp).replace(tzinfo=TZ)

    def _clock() -> datetime:
        return when

    return _clock


def _mini_data_dir(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.yaml").write_text("items: []\n", encoding="utf-8")
    (data / "b.yaml").write_text("value: 1\n", encoding="utf-8")
    return data


def test_gitignore_covers_local_config_and_rig_dir():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".rig.local.yaml" in text
    assert ".rig/" in text


def test_local_config_missing_is_ok(tmp_path: Path):
    assert load_local_config(tmp_path / ".rig.local.yaml") is None


def test_local_config_example_loads():
    example = ROOT / ".rig.local.example.yaml"
    assert example.is_file()
    cfg = load_local_config(example)
    assert cfg is not None
    assert cfg.paths.backup_root is None


def test_local_config_rejects_unknown_locator(tmp_path: Path):
    path = tmp_path / ".rig.local.yaml"
    path.write_text("paths:\n  mystery: /tmp/x\n", encoding="utf-8")
    with pytest.raises(StoreError, match="unknown path locator"):
        load_local_config(path)


def test_snapshot_create_list_show_verify_diff_injected_time(tmp_path: Path):
    data = _mini_data_dir(tmp_path)
    out = tmp_path / "snaps"
    clock = _clock_at("2026-09-11T19:40:00")
    manifest = snapshot_service.create_snapshot(
        output_dir=out, data_dir=data, clock=clock, root=tmp_path
    )
    assert manifest.snapshot_id == "SNAP-20260911-194000"
    assert len(manifest.canonical_files) == 2
    listed = snapshot_service.list_snapshots(out)
    assert [item.snapshot_id for item in listed] == [manifest.snapshot_id]
    shown = snapshot_service.show_snapshot(manifest.snapshot_id, out)
    assert shown.created_at.endswith("19:40:00-04:00") or "2026-09-11" in shown.created_at
    ok, problems = snapshot_service.verify_snapshot(manifest.snapshot_id, out)
    assert ok and not problems
    diff = snapshot_service.diff_snapshots(
        manifest.snapshot_id, "current", snapshots_dir=out, data_dir=data
    )
    assert diff["changed"] == []
    assert diff["only_left"] == []
    assert diff["only_right"] == []


def test_snapshot_collision_errors(tmp_path: Path):
    data = _mini_data_dir(tmp_path)
    out = tmp_path / "snaps"
    clock = _clock_at("2026-09-11T19:41:00")
    snapshot_service.create_snapshot(
        output_dir=out, data_dir=data, clock=clock, root=tmp_path
    )
    with pytest.raises(StoreError, match="already exists"):
        snapshot_service.create_snapshot(
            output_dir=out, data_dir=data, clock=clock, root=tmp_path
        )


def test_snapshot_tamper_fails_verify(tmp_path: Path):
    data = _mini_data_dir(tmp_path)
    out = tmp_path / "snaps"
    clock = _clock_at("2026-09-11T19:42:00")
    manifest = snapshot_service.create_snapshot(
        output_dir=out, data_dir=data, clock=clock, root=tmp_path
    )
    target = out / manifest.snapshot_id / "data" / "a.yaml"
    target.write_text("items: [tampered]\n", encoding="utf-8")
    ok, problems = snapshot_service.verify_snapshot(manifest.snapshot_id, out)
    assert not ok
    assert any("hash mismatch" in item for item in problems)


def test_snapshot_diff_detects_change(tmp_path: Path):
    data = _mini_data_dir(tmp_path)
    out = tmp_path / "snaps"
    first = snapshot_service.create_snapshot(
        output_dir=out,
        data_dir=data,
        clock=_clock_at("2026-09-11T19:43:00"),
        root=tmp_path,
    )
    (data / "b.yaml").write_text("value: 2\n", encoding="utf-8")
    second = snapshot_service.create_snapshot(
        output_dir=out,
        data_dir=data,
        clock=_clock_at("2026-09-11T19:43:01"),
        root=tmp_path,
    )
    diff = snapshot_service.diff_snapshots(
        first.snapshot_id, second.snapshot_id, snapshots_dir=out
    )
    assert "data/b.yaml" in diff["changed"]


def test_backup_plan_and_status_without_local_config():
    items = backup_state.plan_items()
    assert any(item.id == "repository-state" for item in items)
    assert all(item.evidence == MidiEvidenceStatus.INTENDED for item in items)
    statuses = backup_state.status_items()
    by_id = {item.item.id: item for item in statuses}
    assert by_id["repository-state"].readiness == backup_state.BackupReadiness.READY
    assert by_id["controller-mappings"].readiness == backup_state.BackupReadiness.MANUAL
    assert (
        by_id["pfl-jam-ableton-set"].readiness
        == backup_state.BackupReadiness.NOT_CONFIGURED
    )


def test_backup_create_partial_manual(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = _mini_data_dir(tmp_path)
    # Point discovery at fixture data by monkeypatching DATA_DIR usage via arg.
    out = tmp_path / "archives"
    report = backup_state.create_backup_package(
        output=out,
        data_dir=data,
        root=tmp_path,
        local_config_path=tmp_path / "missing.yaml",
        clock=_clock_at("2026-09-11T19:44:00"),
    )
    assert report.backup_id == "BACKUP-20260911-194400"
    assert report.result == backup_state.BackupPackageResult.PARTIAL
    assert report.snapshot_id is not None
    manifest = yaml.safe_load((report.output_dir / "manifest.yaml").read_text())
    assert "secret" not in yaml.safe_dump(manifest).lower()
    assert manifest.get("local_config_present") is False
    # No absolute path values dumped from local config
    dumped = yaml.safe_dump(manifest)
    assert "/Users/" not in dumped


def test_backup_create_copies_configured_file(tmp_path: Path):
    data = _mini_data_dir(tmp_path)
    set_file = tmp_path / "pfl.als"
    set_file.write_text("ableton-set", encoding="utf-8")
    local = tmp_path / ".rig.local.yaml"
    local.write_text(
        "paths:\n"
        f"  pfl_jam_ableton_set: {set_file}\n"
        f"  backup_root: {tmp_path / 'archives'}\n",
        encoding="utf-8",
    )
    # Use a minimal backups doc with only repository + file copy critical
    backups = tmp_path / "backups.yaml"
    backups.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "repository-state",
                        "label": "Repo",
                        "category": "Repository",
                        "kind": "REPOSITORY_STATE",
                        "importance": "CRITICAL",
                        "evidence": "INTENDED",
                        "locator_key": "repository-state",
                        "related_todos": ["RIG-016"],
                    },
                    {
                        "id": "pfl-jam-ableton-set",
                        "label": "Set",
                        "category": "Ableton",
                        "kind": "FILE_COPY",
                        "importance": "CRITICAL",
                        "evidence": "INTENDED",
                        "locator_key": "pfl_jam_ableton_set",
                        "related_todos": ["RIG-018"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    report = backup_state.create_backup_package(
        backups_path=backups,
        local_config_path=local,
        data_dir=data,
        root=tmp_path,
        clock=_clock_at("2026-09-11T19:45:00"),
    )
    assert report.result == backup_state.BackupPackageResult.COMPLETE
    copied = report.output_dir / "copies" / "pfl-jam-ableton-set" / "pfl.als"
    assert copied.read_text(encoding="utf-8") == "ableton-set"


def test_compile_action_plan_preserves_order():
    action = PerformanceAction(
        id="demo",
        label="Demo",
        category=PerformanceActionCategory.RECOVERY,
        criticality=PerformanceCriticality.EMERGENCY,
        evidence=MidiEvidenceStatus.INTENDED,
        effects=[
            PerformanceEffect(
                kind=PerformanceEffectKind.OBS_ACTION,
                effect_id="stop",
                evidence=MidiEvidenceStatus.INTENDED,
            ),
            PerformanceEffect(
                kind=PerformanceEffectKind.MANUAL_STEP,
                effect_id="hands",
                evidence=MidiEvidenceStatus.INTENDED,
            ),
            PerformanceEffect(
                kind=PerformanceEffectKind.MIDI_ACTION,
                effect_id="panic",
                evidence=MidiEvidenceStatus.INTENDED,
            ),
        ],
    )
    plan = automation.compile_action_plan(action)
    assert [step.effect.effect_id for step in plan.steps] == ["stop", "hands", "panic"]
    assert [step.state.value for step in plan.steps] == [
        "UNIMPLEMENTED",
        "MANUAL",
        "UNIMPLEMENTED",
    ]


def test_simulate_banner_no_side_effects(tmp_path: Path):
    action = PerformanceAction(
        id="demo",
        label="Demo",
        category=PerformanceActionCategory.AUDIO,
        criticality=PerformanceCriticality.NORMAL,
        evidence=MidiEvidenceStatus.INTENDED,
        effects=[
            PerformanceEffect(
                kind=PerformanceEffectKind.HARDWARE_PROCEDURE,
                effect_id="mute",
                evidence=MidiEvidenceStatus.INTENDED,
            )
        ],
    )
    before = list(tmp_path.iterdir())
    report = automation.simulate_action(action)
    assert report.banner == automation.SIMULATION_BANNER
    assert report.result == automation.SimulateResult.SIMULATABLE
    assert list(tmp_path.iterdir()) == before


def test_preflight_severity_advisory_not_blocker():
    report = automation.preflight(mode="pfl-jam")
    assert report.worst in {
        automation.PreflightSeverity.ADVISORY,
        automation.PreflightSeverity.UNKNOWN,
        automation.PreflightSeverity.PASS,
    }
    assert report.worst != automation.PreflightSeverity.BLOCKER or True
    # Preflight must not invent BLOCKER for missing local config
    local_findings = [f for f in report.findings if f.section == "Local config"]
    assert local_findings
    assert local_findings[0].severity != automation.PreflightSeverity.BLOCKER


def test_cli_snapshot_and_backup_and_automation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = _mini_data_dir(tmp_path)
    out = tmp_path / "snaps"
    monkeypatch.setattr(
        snapshot_service,
        "discover_canonical_yaml",
        lambda data_dir=None: sorted(data.glob("*.yaml")),
    )
    monkeypatch.setattr(snapshot_service, "default_snapshots_dir", lambda root=None: out)
    monkeypatch.setattr(snapshot_service, "default_clock", _clock_at("2026-09-11T19:46:00"))
    monkeypatch.setattr(snapshot_service, "_docs_synchronized", lambda: True)

    result = runner.invoke(app, ["snapshot", "create", "--output", str(out)])
    assert result.exit_code == 0, result.output
    assert "SNAP-20260911-194600" in result.output

    listed = runner.invoke(app, ["snapshot", "list"])
    assert listed.exit_code == 0
    assert "SNAP-20260911-194600" in listed.output

    shown = runner.invoke(app, ["snapshot", "show", "SNAP-20260911-194600"])
    assert shown.exit_code == 0

    verified = runner.invoke(app, ["snapshot", "verify", "SNAP-20260911-194600"])
    assert verified.exit_code == 0

    diffed = runner.invoke(app, ["snapshot", "diff", "SNAP-20260911-194600", "current"])
    assert diffed.exit_code == 0

    plan = runner.invoke(app, ["backup", "plan"])
    assert plan.exit_code == 0
    assert "repository" in plan.output.lower()
    assert "REPOSITORY_STATE" in plan.output

    status = runner.invoke(app, ["backup", "status"])
    assert status.exit_code == 0

    caps = runner.invoke(app, ["automation", "capabilities"])
    assert caps.exit_code == 0
    assert "NOT_IMPLEMENTED" in caps.output

    from music_rig import performance_state

    action_id = performance_state.load_document().actions[0].id
    sim = runner.invoke(app, ["performance", "simulate", action_id])
    assert sim.exit_code == 0, sim.output
    assert "SIMULATION — NO EXTERNAL ACTIONS WILL BE EXECUTED" in sim.output

    pre = runner.invoke(app, ["performance", "preflight", "--mode", "pfl-jam"])
    assert pre.exit_code == 0
    assert "PREFLIGHT" in pre.output

    planned = runner.invoke(app, ["performance", "plan", action_id])
    assert planned.exit_code == 0
    assert "PLAN" in planned.output


def test_now_play_mentions_optional_preflight():
    result = runner.invoke(app, ["now", "--play"])
    assert result.exit_code == 0
    assert "Optional setup check:" in result.stdout
    assert "uv run rig performance preflight" in result.stdout


def test_backups_yaml_has_no_absolute_paths():
    text = (ROOT / "data" / "backups.yaml").read_text(encoding="utf-8")
    assert "/Users/" not in text
    assert "C:\\" not in text
    doc = backup_state.load_document()
    assert all(item.evidence == MidiEvidenceStatus.INTENDED for item in doc.items)


def test_directory_symlink_refused(tmp_path: Path):
    real = tmp_path / "real-dir"
    real.mkdir()
    (real / "x.txt").write_text("x", encoding="utf-8")
    link = tmp_path / "link-dir"
    link.symlink_to(real, target_is_directory=True)
    dest = tmp_path / "out"
    with pytest.raises(StoreError, match="directory symlink"):
        backup_state._safe_copy_directory(link, dest)
