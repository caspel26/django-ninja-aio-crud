from typing import Literal

from joserfc import jwk
from django.db.models import Model
from typing import TypeAlias

S_TYPES = Literal["read", "detail", "create", "update"]
F_TYPES = Literal["fields", "customs", "optionals", "excludes"]
SCHEMA_TYPES = Literal["In", "Out", "Detail", "Patch", "Related"]
VIEW_TYPES = Literal["list", "retrieve", "create", "update", "delete", "all"]
JwtKeys: TypeAlias = jwk.RSAKey | jwk.ECKey | jwk.OctKey


class SerializerMeta(type):
    """Metaclass for serializers - extend with custom behavior as needed."""

    def __repr__(cls):
        return cls.__name__


class ModelSerializerMeta(SerializerMeta, type(Model)):
    """Metaclass combining SerializerMeta with Django's ModelBase."""

    pass
