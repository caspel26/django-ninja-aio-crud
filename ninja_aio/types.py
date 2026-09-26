from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Literal, TypeAlias, TypeVar
from uuid import UUID

from django.db.models import Model
from joserfc import jwk
from ninja import Schema

S_TYPES = Literal["read", "detail", "create", "update"]
F_TYPES = Literal["fields", "customs", "optionals", "excludes"]
SCHEMA_TYPES = Literal["In", "Out", "Detail", "Patch", "Related"]
SchemaKind: TypeAlias = Literal["create", "update", "read", "detail", "related"]
SchemaType: TypeAlias = type[Schema]
InputData: TypeAlias = dict[str, Any] | Schema
Payload: TypeAlias = dict[str, Any]
PrimaryKey: TypeAlias = int | str | UUID


class HttpMethod(str, Enum):
    """HTTP methods supported by generated routes and actions; members compare equal to their value."""

    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"

    def __str__(self) -> str:
        return self.value


HttpMethodName: TypeAlias = Literal["get", "post", "put", "patch", "delete"]
QueryPurpose: TypeAlias = Literal["read", "detail"]
"""Which read/detail relation optimizations a lookup applies."""
BulkItemT = TypeVar("BulkItemT")


@dataclass(frozen=True)
class BulkFailure:
    index: int
    code: str
    message: str
    fields: dict[str, list[str]] = field(default_factory=dict)
    pk: PrimaryKey | None = None
    error: dict[str, Any] = field(default_factory=dict)
    """Legacy error payload, as returned in HTTP bulk responses."""


@dataclass
class BulkResult(Generic[BulkItemT]):
    succeeded: list[BulkItemT] = field(default_factory=list)
    failed: list[BulkFailure] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.failed)

    @property
    def success_count(self) -> int:
        return len(self.succeeded)

    @property
    def failure_count(self) -> int:
        return len(self.failed)

VIEW_TYPES = Literal[
    "list",
    "retrieve",
    "create",
    "update",
    "delete",
    "bulk_create",
    "bulk_update",
    "bulk_delete",
    "all",
]
BULK_TYPES = Literal["create", "update", "delete"]
JwtKeys: TypeAlias = jwk.RSAKey | jwk.ECKey | jwk.OctKey

# Django ORM field lookup suffixes for QuerySet filtering
# See: https://docs.djangoproject.com/en/stable/ref/models/querysets/#field-lookups
DjangoLookup = Literal[
    "exact",
    "iexact",
    "contains",
    "icontains",
    "in",
    "gt",
    "gte",
    "lt",
    "lte",
    "startswith",
    "istartswith",
    "endswith",
    "iendswith",
    "range",
    "date",
    "year",
    "iso_year",
    "month",
    "day",
    "week",
    "week_day",
    "iso_week_day",
    "quarter",
    "time",
    "hour",
    "minute",
    "second",
    "isnull",
    "regex",
    "iregex",
]

# Set of valid Django lookup suffixes for runtime validation
VALID_DJANGO_LOOKUPS: set[str] = set(DjangoLookup.__args__)


class SerializerMeta(type):
    """Metaclass for serializers - extend with custom behavior as needed."""

    def __repr__(cls):
        return cls.__name__


class ModelSerializerMeta(SerializerMeta, type(Model)):
    """Metaclass combining SerializerMeta with Django's ModelBase."""

    pass


def get_ninja_aio_meta_attr(model, attr: str, default=None):
    """Look up an attribute on the model's NinjaAIOMeta inner class, or return default."""
    ninja_meta = getattr(model, "NinjaAIOMeta", None)
    if ninja_meta is None:
        return default
    return getattr(ninja_meta, attr, default)
