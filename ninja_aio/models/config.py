from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

ConfigKind: TypeAlias = Literal["create", "update", "read", "detail"]
CONFIG_KINDS: tuple[ConfigKind, ...] = ("create", "update", "read", "detail")

FieldSpec: TypeAlias = str | tuple[str, Any] | tuple[str, Any, Any]
CustomSpec: TypeAlias = tuple[str, Any] | tuple[str, Any, Any]


@dataclass(frozen=True)
class SchemaConfig:
    """Field configuration for one generated schema kind.

    Declared on a serializer's ``Schemas`` class as ``create``, ``update``,
    ``read`` or ``detail``; an omitted ``detail`` reuses ``read``.
    ``relations_as_id`` applies to ``read``/``detail`` and ``nested`` to
    ``create`` on ``ModelSerializer`` only.
    """

    fields: list[FieldSpec] = field(default_factory=list)
    optionals: list[tuple[str, Any]] = field(default_factory=list)
    customs: list[CustomSpec] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)
    relations_as_id: list[str] = field(default_factory=list)
    nested: dict[str, Any] = field(default_factory=dict)
    model_config: dict | None = None


EMPTY_SCHEMA_CONFIG = SchemaConfig()
