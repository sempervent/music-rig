"""Editable domain adapter protocol and working-record apply lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from music_rig.tui.fields import FieldSpec
from music_rig.tui.working import ConcurrentModificationError, WorkingDocument, sha256_file


@dataclass
class WorkingRecord:
    """Staged field mutations for one record, with source-hash concurrency."""

    record_id: str
    baseline: dict[str, Any]
    source_path: Path | None = None
    source_hash: str | None = None
    mutations: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source_path is not None and self.source_hash is None and self.source_path.exists():
            self.source_hash = sha256_file(self.source_path)

    @property
    def is_dirty(self) -> bool:
        return bool(self.mutations)

    def stage(self, name: str, value: Any) -> None:
        baseline = self.baseline.get(name)
        if _values_equal(baseline, value):
            self.mutations.pop(name, None)
        else:
            self.mutations[name] = value

    def get(self, name: str) -> Any:
        if name in self.mutations:
            return self.mutations[name]
        return self.baseline.get(name)

    def merged(self) -> dict[str, Any]:
        out = dict(self.baseline)
        out.update(self.mutations)
        return out

    def discard(self) -> None:
        self.mutations.clear()

    def source_unchanged(self) -> bool:
        if self.source_path is None or self.source_hash is None:
            return True
        if not self.source_path.exists():
            return False
        return sha256_file(self.source_path) == self.source_hash

    def refresh_source_hash(self) -> None:
        if self.source_path is not None and self.source_path.exists():
            self.source_hash = sha256_file(self.source_path)

    def ensure_current(self) -> None:
        if not self.source_unchanged():
            raise ConcurrentModificationError(
                "CURRENT data changed since this editor was opened. Reload before applying."
            )


def _values_equal(a: Any, b: Any) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        return list(a) == list(b)
    if a is None and b in ("", None, []):
        return True
    if b is None and a in ("", None, []):
        return True
    return a == b


@dataclass(frozen=True)
class DiffRow:
    field: str
    before: str
    after: str


@dataclass
class ApplyResult:
    record_id: str
    message: str
    hidden_by_filter: bool = False
    filter_hint: str = ""


@runtime_checkable
class EditableDomainAdapter(Protocol):
    """Typed interface for list/edit/apply of one canonical domain."""

    id: str
    label: str

    def list_records(self, *, status_filter: str | None = None, search: str = "") -> list[dict[str, Any]]:
        """Return row dicts with at least `id` and `cells` (list[str]) and `search_text`."""
        ...

    def get_record(self, record_id: str) -> dict[str, Any]:
        """Flat field map used by the form."""
        ...

    def get_field_specs(self) -> list[FieldSpec]:
        ...

    def source_path(self) -> Path | None:
        ...

    def create_working(self, record_id: str) -> WorkingRecord:
        ...

    def validate_working(self, working: WorkingRecord) -> list[str]:
        ...

    def diff(self, working: WorkingRecord) -> list[DiffRow]:
        ...

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        ...

    def detail_markdown(self, record_id: str) -> str:
        ...

    def columns(self) -> list[str]:
        ...

    def filter_cycle(self) -> tuple[str, ...] | None:
        """Optional status filter cycle (e.g. OPEN/RESOLVED/ALL)."""
        ...

    def semantic_actions(self) -> list[tuple[str, str, str]]:
        """Return (action_id, key, label) for domain-specific shortcuts."""
        ...

    def run_semantic(
        self,
        action_id: str,
        record_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> ApplyResult:
        ...


class BaseEditableAdapter:
    """Convenience base with default create_working / diff / validate."""

    id: str = ""
    label: str = ""

    def columns(self) -> list[str]:
        return ["ID", "Summary"]

    def filter_cycle(self) -> tuple[str, ...] | None:
        return None

    def semantic_actions(self) -> list[tuple[str, str, str]]:
        return []

    def source_path(self) -> Path | None:
        return None

    def create_working(self, record_id: str) -> WorkingRecord:
        baseline = self.get_record(record_id)
        return WorkingRecord(
            record_id=record_id,
            baseline=baseline,
            source_path=self.source_path(),
        )

    def validate_working(self, working: WorkingRecord) -> list[str]:
        errors: list[str] = []
        specs = {s.name: s for s in self.get_field_specs()}
        merged = working.merged()
        for name, spec in specs.items():
            if spec.read_only or spec.type.value == "READONLY":
                continue
            value = merged.get(name)
            if spec.required and (value is None or value == "" or value == []):
                errors.append(f"{spec.label} is required")
            if spec.type.value == "ENUM" and value not in (None, "") and value not in spec.enum_values:
                errors.append(f"{spec.label} must be one of {', '.join(spec.enum_values)}")
            if spec.type.value == "INT" and value not in (None, ""):
                try:
                    int(value)
                except (TypeError, ValueError):
                    errors.append(f"{spec.label} must be an integer")
        return errors

    def diff(self, working: WorkingRecord) -> list[DiffRow]:
        rows: list[DiffRow] = []
        labels = {s.name: s.label for s in self.get_field_specs()}
        for key, after in sorted(working.mutations.items()):
            before = working.baseline.get(key)
            rows.append(
                DiffRow(
                    field=labels.get(key, key),
                    before=_fmt(before),
                    after=_fmt(after),
                )
            )
        return rows

    def run_semantic(
        self,
        action_id: str,
        record_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> ApplyResult:
        raise NotImplementedError(f"Semantic action {action_id!r} not supported")

    # subclasses implement:
    # list_records, get_record, get_field_specs, commit, detail_markdown


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "—"
    if isinstance(value, dict):
        parts = [f"{k}={v}" for k, v in value.items() if v not in (None, "", [])]
        return ", ".join(parts) if parts else "—"
    return str(value)


def working_document_from_path(path: Path, baseline: Any) -> WorkingDocument:
    """Helper for domains that stage free-form mutations against a whole file."""
    return WorkingDocument(baseline, source_path=path)
