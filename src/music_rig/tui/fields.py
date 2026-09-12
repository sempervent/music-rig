"""Structured field metadata for TUI editors and `rig inspect schema`."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence


class FieldType(str, Enum):
    TEXT = "TEXT"
    MULTILINE = "MULTILINE"
    ENUM = "ENUM"
    BOOL = "BOOL"
    INT = "INT"
    REF = "REF"
    REF_LIST = "REF_LIST"
    ORDERED_LIST = "ORDERED_LIST"
    TIMESTAMP = "TIMESTAMP"
    NESTED = "NESTED"
    READONLY = "READONLY"


@dataclass(frozen=True)
class FieldSpec:
    """Declarative description of one editable (or display) field."""

    name: str
    label: str
    type: FieldType
    required: bool = False
    help: str = ""
    enum_values: tuple[str, ...] = ()
    ref_domain: str | None = None
    multiline: bool = False
    rename_only: bool = False
    read_only: bool = False
    nested_fields: tuple["FieldSpec", ...] = ()
    max_items: int | None = None
    min_value: int | None = None
    max_value: int | None = None
    allow_empty: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type.value,
            "required": self.required,
            "help": self.help,
            "enum_values": list(self.enum_values),
            "ref_domain": self.ref_domain,
            "multiline": self.multiline or self.type == FieldType.MULTILINE,
            "rename_only": self.rename_only,
            "read_only": self.read_only or self.type == FieldType.READONLY,
            "nested_fields": [f.to_dict() for f in self.nested_fields],
            "max_items": self.max_items,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "allow_empty": self.allow_empty,
        }


def enum_spec(
    name: str,
    label: str,
    values: Sequence[str],
    *,
    required: bool = True,
    help: str = "",
) -> FieldSpec:
    return FieldSpec(
        name=name,
        label=label,
        type=FieldType.ENUM,
        required=required,
        enum_values=tuple(values),
        help=help,
    )


def text_spec(
    name: str,
    label: str,
    *,
    required: bool = False,
    multiline: bool = False,
    help: str = "",
) -> FieldSpec:
    return FieldSpec(
        name=name,
        label=label,
        type=FieldType.MULTILINE if multiline else FieldType.TEXT,
        required=required,
        multiline=multiline,
        help=help,
        allow_empty=not required,
    )


def ref_list_spec(
    name: str,
    label: str,
    ref_domain: str,
    *,
    help: str = "",
    max_items: int | None = None,
) -> FieldSpec:
    return FieldSpec(
        name=name,
        label=label,
        type=FieldType.REF_LIST,
        ref_domain=ref_domain,
        help=help,
        max_items=max_items,
    )


def readonly_spec(name: str, label: str, *, help: str = "") -> FieldSpec:
    return FieldSpec(
        name=name,
        label=label,
        type=FieldType.READONLY,
        read_only=True,
        help=help,
    )
