"""Execution-mode-independent rules used by model operations.

This module deliberately contains no database execution and no async adapters.
It is shared by the current asynchronous executor and the native synchronous
executor introduced by version 3.
"""

import base64
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol, Sequence, TypeVar

from django.db import models
from django.db.models.fields.related_descriptors import (
    ForwardManyToOneDescriptor,
    ForwardOneToOneDescriptor,
    ManyToManyDescriptor,
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
)
from django.http import HttpRequest
from ninja import Schema

from ninja_aio.exceptions import SerializeError
from ninja_aio.schemas.helpers import QuerySchema
from ninja_aio.types import Payload, PrimaryKey, SchemaType


ModelT = TypeVar("ModelT", bound=models.Model)


class FieldPolicy(Protocol):
    """Minimal serializer interface required to classify input fields."""

    def is_custom(self, name: str) -> bool: ...

    def is_optional(self, name: str) -> bool: ...


@dataclass(frozen=True)
class InputPayloadPlan:
    """Pure classification result for one validated input payload."""

    payload: Payload
    customs: Payload
    optionals: tuple[str, ...]
    skip_keys: frozenset[str]

    @property
    def fields_to_process(self) -> list[tuple[str, Any]]:
        """Return model fields that still need value-level transformation."""
        return [
            (name, value)
            for name, value in self.payload.items()
            if name not in self.skip_keys
        ]

    def model_payload(self) -> Payload:
        """Return the payload after applying the legacy exclusion rules."""
        # Preserve the existing behavior: customs take precedence over optionals.
        exclude: Iterable[str] = self.customs.keys() or self.optionals
        return {
            name: value for name, value in self.payload.items() if name not in exclude
        }


@dataclass(frozen=True)
class RelationPlan:
    """Lazy queryset relation plan, independent from execution mode."""

    select_related: tuple[str, ...] = ()
    prefetch_related: tuple[str, ...] = ()


def schema_to_payload(data: Schema, nested_fields: Iterable[str] = ()) -> Payload:
    """Dump validated input and remove owned nested-write collections."""
    payload = data.model_dump(mode="json")
    for name in nested_fields:
        payload.pop(name, None)
    return payload


def serializer_payload(payload: Payload | Schema) -> Payload:
    """Normalize standalone serializer input without performing database I/O."""
    if isinstance(payload, Schema):
        return payload.model_dump()
    return payload


def plan_input_payload(
    payload: Payload,
    *,
    model_fields: Sequence[str],
    field_policy: FieldPolicy | None,
) -> InputPayloadPlan:
    """Classify custom, optional, and model fields without resolving values."""
    if field_policy is None:
        return InputPayloadPlan(payload, {}, (), frozenset())

    model_field_names = frozenset(model_fields)
    customs = {
        name: value
        for name, value in payload.items()
        if field_policy.is_custom(name) and name not in model_field_names
    }
    optionals = tuple(
        name
        for name, value in payload.items()
        if field_policy.is_optional(name) and value is None
    )
    skip_keys = frozenset((*customs, *optionals))
    return InputPayloadPlan(payload, customs, optionals, skip_keys)


def decode_binary_value(field_name: str, value: Any) -> bytes:
    """Decode one base64 value using the established serialization error shape."""
    try:
        return base64.b64decode(value)
    except Exception as exc:
        raise SerializeError({field_name: ". ".join(exc.args)}, 400) from exc


def resolve_model_fields(
    model: type[models.Model], field_names: Sequence[str]
) -> list[models.Field]:
    """Resolve Django field metadata without crossing an async boundary."""
    return [getattr(model, name).field for name in field_names]


def build_lookup_query(
    pk_name: str,
    pk: PrimaryKey | None = None,
    getters: Mapping[str, Any] | None = None,
) -> Payload:
    """Build lookup criteria without evaluating a queryset."""
    lookup: Payload = {pk_name: pk} if pk is not None else {}
    if getters:
        lookup.update(getters)
    return lookup


def validate_read_params(
    request: HttpRequest | None,
    query_data: QuerySchema | None,
) -> None:
    """Validate query-mode serialization inputs without touching the ORM."""
    if request is None:
        raise SerializeError(
            {"request": "must be provided when object is not given"}, 400
        )
    if query_data is None:
        raise SerializeError(
            {"query_data": "must be provided when object is not given"}, 400
        )
    if (
        hasattr(query_data, "filters")
        and hasattr(query_data, "getters")
        and query_data.filters
        and query_data.getters
    ):
        raise SerializeError(
            {"query_data": "cannot contain both filters and getters"}, 400
        )


def discover_relation_plan(
    model: type[models.Model],
    serializable_fields: Sequence[str],
    *,
    configured_select: Sequence[str] = (),
    configured_prefetch: Sequence[str] = (),
) -> RelationPlan:
    """Discover a deterministic select/prefetch plan from model descriptors."""
    select_related = list(configured_select)
    prefetch_related = list(configured_prefetch)
    discover_select = not select_related
    discover_prefetch = not prefetch_related

    for field_name in serializable_fields:
        descriptor = getattr(model, field_name)
        if discover_select and isinstance(
            descriptor, (ForwardOneToOneDescriptor, ForwardManyToOneDescriptor)
        ):
            select_related.append(field_name)
        if not discover_prefetch:
            continue
        if isinstance(descriptor, ManyToManyDescriptor):
            prefetch_related.append(field_name)
        elif isinstance(descriptor, ReverseManyToOneDescriptor):
            prefetch_related.append(descriptor.field._related_name)
        elif isinstance(descriptor, ReverseOneToOneDescriptor):
            prefetch_related.append(descriptor.related.name)

    return RelationPlan(tuple(select_related), tuple(prefetch_related))


def combine_relation_plans(
    explicit: RelationPlan,
    discovered: RelationPlan | None = None,
) -> RelationPlan:
    """Combine caller-requested and serializer-derived queryset optimizations."""
    discovered = discovered or RelationPlan()
    return RelationPlan(
        explicit.select_related + discovered.select_related,
        explicit.prefetch_related + discovered.prefetch_related,
    )


def apply_relation_plan(
    queryset: models.QuerySet[ModelT],
    plan: RelationPlan,
) -> models.QuerySet[ModelT]:
    """Attach a relation plan to a lazy queryset without evaluating it."""
    if plan.select_related:
        queryset = queryset.select_related(*plan.select_related)
    if plan.prefetch_related:
        queryset = queryset.prefetch_related(*plan.prefetch_related)
    return queryset


def dump_model(instance: ModelT, schema: SchemaType) -> Payload:
    """Transform one already-loaded model instance into output data."""
    return schema.from_orm(instance).model_dump()


def dump_models(instances: Iterable[ModelT], schema: SchemaType) -> list[Payload]:
    """Transform already-loaded model instances into output data."""
    return [dump_model(instance, schema) for instance in instances]
