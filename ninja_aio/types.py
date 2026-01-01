from typing import Literal

from joserfc import jwk
from django.db.models import Model
from typing import TypeAlias

S_TYPES = Literal["read", "create", "update"]
F_TYPES = Literal["fields", "customs", "optionals", "excludes"]
SCHEMA_TYPES = Literal["In", "Out", "Patch", "Related"]
VIEW_TYPES = Literal["list", "retrieve", "create", "update", "delete", "all"]
JwtKeys: TypeAlias = jwk.RSAKey | jwk.ECKey | jwk.OctKey

class ModelSerializerType(type):
    def __repr__(self):
        return self.__name__


class ModelSerializerMeta(ModelSerializerType, type(Model)):
    pass
