from typing import Literal

from joserfc import jwk
from django.db.models import Model
from typing import TypeAlias

S_TYPES = Literal["read", "detail", "create", "update"]
F_TYPES = Literal["fields", "customs", "optionals", "excludes"]
SCHEMA_TYPES = Literal["In", "Out", "Detail", "Patch", "Related"]
VIEW_TYPES = Literal["list", "retrieve", "create", "update", "delete", "all"]
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
