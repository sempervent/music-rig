"""Reusable form field widgets for structured TUI editing."""

from __future__ import annotations

from typing import Any, Callable

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select, Static, Switch, TextArea

from music_rig.tui.fields import FieldSpec, FieldType


class FieldEditor(Widget):
    """Base: one labeled field that can read/write a value."""

    DEFAULT_CSS = """
    FieldEditor {
        height: auto;
        margin-bottom: 1;
    }
    FieldEditor .field-label {
        text-style: bold;
    }
    FieldEditor .field-help {
        color: $text-muted;
    }
    """

    def __init__(self, spec: FieldSpec, value: Any = None) -> None:
        super().__init__()
        self.spec = spec
        self._initial = value

    def get_value(self) -> Any:
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        raise NotImplementedError


class TextField(FieldEditor):
    def compose(self) -> ComposeResult:
        yield Label(self.spec.label, classes="field-label")
        if self.spec.help:
            yield Static(self.spec.help, classes="field-help")
        yield Input(
            value="" if self._initial is None else str(self._initial),
            id=f"field-{self.spec.name}",
            disabled=self.spec.read_only,
        )

    def get_value(self) -> str:
        return self.query_one(Input).value

    def set_value(self, value: Any) -> None:
        self.query_one(Input).value = "" if value is None else str(value)


class MultilineField(FieldEditor):
    def compose(self) -> ComposeResult:
        yield Label(self.spec.label, classes="field-label")
        if self.spec.help:
            yield Static(self.spec.help, classes="field-help")
        area = TextArea(
            "" if self._initial is None else str(self._initial),
            id=f"field-{self.spec.name}",
        )
        if self.spec.read_only:
            area.disabled = True
        yield area

    def get_value(self) -> str:
        return self.query_one(TextArea).text

    def set_value(self, value: Any) -> None:
        self.query_one(TextArea).load_text("" if value is None else str(value))


class EnumField(FieldEditor):
    def compose(self) -> ComposeResult:
        yield Label(self.spec.label, classes="field-label")
        if self.spec.help:
            yield Static(self.spec.help, classes="field-help")
        options = [(v, v) for v in self.spec.enum_values]
        current = self._initial if self._initial in self.spec.enum_values else Select.BLANK
        yield Select(
            options,
            value=current,
            id=f"field-{self.spec.name}",
            allow_blank=not self.spec.required,
            disabled=self.spec.read_only,
        )

    def get_value(self) -> str | None:
        val = self.query_one(Select).value
        if val is Select.BLANK:
            return None
        return str(val)

    def set_value(self, value: Any) -> None:
        sel = self.query_one(Select)
        if value in self.spec.enum_values:
            sel.value = value
        else:
            sel.value = Select.BLANK


class BoolField(FieldEditor):
    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(self.spec.label, classes="field-label")
            yield Switch(
                value=bool(self._initial),
                id=f"field-{self.spec.name}",
                disabled=self.spec.read_only,
            )
        if self.spec.help:
            yield Static(self.spec.help, classes="field-help")

    def get_value(self) -> bool:
        return self.query_one(Switch).value

    def set_value(self, value: Any) -> None:
        self.query_one(Switch).value = bool(value)


class IntField(FieldEditor):
    def compose(self) -> ComposeResult:
        yield Label(self.spec.label, classes="field-label")
        if self.spec.help:
            yield Static(self.spec.help, classes="field-help")
        yield Input(
            value="" if self._initial is None else str(self._initial),
            id=f"field-{self.spec.name}",
            type="integer",
            disabled=self.spec.read_only,
        )

    def get_value(self) -> int | None:
        raw = self.query_one(Input).value.strip()
        if not raw:
            return None
        return int(raw)

    def set_value(self, value: Any) -> None:
        self.query_one(Input).value = "" if value is None else str(value)


class ReadonlyField(FieldEditor):
    def compose(self) -> ComposeResult:
        yield Label(self.spec.label, classes="field-label")
        yield Static(
            "—" if self._initial is None else str(self._initial),
            id=f"field-{self.spec.name}",
        )

    def get_value(self) -> Any:
        return self._initial

    def set_value(self, value: Any) -> None:
        self._initial = value
        self.query_one(f"#field-{self.spec.name}", Static).update(
            "—" if value is None else str(value)
        )


class RefListField(FieldEditor):
    """Multi-ref display + Pick button (opens ReferencePickerModal via callback)."""

    def __init__(
        self,
        spec: FieldSpec,
        value: Any = None,
        *,
        on_pick: Callable[[FieldSpec, list[str]], None] | None = None,
    ) -> None:
        super().__init__(spec, value)
        self._refs: list[str] = list(value or [])
        self._on_pick = on_pick

    def compose(self) -> ComposeResult:
        yield Label(self.spec.label, classes="field-label")
        if self.spec.help:
            yield Static(self.spec.help, classes="field-help")
        yield Static(self._label_text(), id=f"field-{self.spec.name}-display")
        if not self.spec.read_only:
            yield Button("Pick…", id=f"pick-{self.spec.name}")

    def _label_text(self) -> str:
        return ", ".join(self._refs) if self._refs else "—"

    def get_value(self) -> list[str]:
        return list(self._refs)

    def set_value(self, value: Any) -> None:
        self._refs = list(value or [])
        self.query_one(f"#field-{self.spec.name}-display", Static).update(self._label_text())

    @on(Button.Pressed)
    def _pick(self, event: Button.Pressed) -> None:
        if event.button.id != f"pick-{self.spec.name}":
            return
        if self._on_pick:
            self._on_pick(self.spec, list(self._refs))


class OrderedListField(FieldEditor):
    def __init__(
        self,
        spec: FieldSpec,
        value: Any = None,
        *,
        on_edit: Callable[[FieldSpec, list[str]], None] | None = None,
    ) -> None:
        super().__init__(spec, value)
        self._items: list[str] = list(value or [])
        self._on_edit = on_edit

    def compose(self) -> ComposeResult:
        yield Label(self.spec.label, classes="field-label")
        if self.spec.help:
            yield Static(self.spec.help, classes="field-help")
        yield Static(self._label_text(), id=f"field-{self.spec.name}-display")
        if not self.spec.read_only:
            yield Button("Edit list…", id=f"editlist-{self.spec.name}")

    def _label_text(self) -> str:
        if not self._items:
            return "—"
        return " → ".join(self._items)

    def get_value(self) -> list[str]:
        return list(self._items)

    def set_value(self, value: Any) -> None:
        self._items = list(value or [])
        self.query_one(f"#field-{self.spec.name}-display", Static).update(self._label_text())

    @on(Button.Pressed)
    def _edit(self, event: Button.Pressed) -> None:
        if event.button.id != f"editlist-{self.spec.name}":
            return
        if self._on_edit:
            self._on_edit(self.spec, list(self._items))


class NestedField(FieldEditor):
    """Advanced nested object: key=value lines preview + edit as structured modal later."""

    def compose(self) -> ComposeResult:
        yield Label(f"{self.spec.label} (Advanced)", classes="field-label")
        if self.spec.help:
            yield Static(self.spec.help, classes="field-help")
        text = _nested_to_text(self._initial)
        area = TextArea(text, id=f"field-{self.spec.name}")
        if self.spec.read_only:
            area.disabled = True
        yield area
        yield Static("Advanced: key=value per line · validated on Apply", classes="field-help")

    def get_value(self) -> dict[str, Any] | None:
        raw = self.query_one(TextArea).text.strip()
        if not raw:
            return None
        return _text_to_nested(raw, self.spec)

    def set_value(self, value: Any) -> None:
        self.query_one(TextArea).load_text(_nested_to_text(value))


def _nested_to_text(value: Any) -> str:
    if not value or not isinstance(value, dict):
        return ""
    return "\n".join(f"{k}={'' if v is None else v}" for k, v in value.items())


def _text_to_nested(raw: str, spec: FieldSpec) -> dict[str, Any]:
    allowed = {f.name for f in spec.nested_fields} if spec.nested_fields else None
    out: dict[str, Any] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid nested line {line!r}; use key=value")
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if allowed is not None and key not in allowed:
            raise ValueError(f"Unknown nested key {key!r}")
        out[key] = None if val in {"", "null", "None", "—"} else val
    return out


def build_field_editor(
    spec: FieldSpec,
    value: Any,
    *,
    on_pick_refs: Callable[[FieldSpec, list[str]], None] | None = None,
    on_edit_list: Callable[[FieldSpec, list[str]], None] | None = None,
) -> FieldEditor:
    if spec.read_only or spec.type == FieldType.READONLY or spec.type == FieldType.TIMESTAMP:
        display = value
        if spec.type == FieldType.TIMESTAMP and value is not None:
            display = str(value)
        return ReadonlyField(spec, display)
    if spec.type == FieldType.MULTILINE or spec.multiline:
        return MultilineField(spec, value)
    if spec.type == FieldType.ENUM:
        return EnumField(spec, value)
    if spec.type == FieldType.BOOL:
        return BoolField(spec, value)
    if spec.type == FieldType.INT:
        return IntField(spec, value)
    if spec.type == FieldType.REF_LIST:
        return RefListField(spec, value, on_pick=on_pick_refs)
    if spec.type == FieldType.ORDERED_LIST:
        return OrderedListField(spec, value, on_edit=on_edit_list)
    if spec.type == FieldType.NESTED:
        return NestedField(spec, value)
    if spec.type == FieldType.REF:
        return TextField(spec, value)  # picker attached at form level for REF
    return TextField(spec, value)


class FieldForm(Vertical):
    """Collection of FieldEditors bound to a WorkingRecord-like dict."""

    def __init__(
        self,
        specs: list[FieldSpec],
        values: dict[str, Any],
        *,
        on_pick_refs: Callable[[FieldSpec, list[str]], None] | None = None,
        on_edit_list: Callable[[FieldSpec, list[str]], None] | None = None,
    ) -> None:
        super().__init__(id="field-form")
        self._specs = specs
        self._values = values
        self._on_pick_refs = on_pick_refs
        self._on_edit_list = on_edit_list
        self._editors: dict[str, FieldEditor] = {}

    def compose(self) -> ComposeResult:
        for spec in self._specs:
            editor = build_field_editor(
                spec,
                self._values.get(spec.name),
                on_pick_refs=self._on_pick_refs,
                on_edit_list=self._on_edit_list,
            )
            self._editors[spec.name] = editor
            yield editor

    def collect(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, editor in self._editors.items():
            if editor.spec.read_only or editor.spec.type in {
                FieldType.READONLY,
                FieldType.TIMESTAMP,
            }:
                continue
            out[name] = editor.get_value()
        return out

    def set_field(self, name: str, value: Any) -> None:
        if name in self._editors:
            self._editors[name].set_value(value)
