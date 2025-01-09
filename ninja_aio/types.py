from typing import Literal

from django.db.models import Model

S_TYPES = Literal["create", "update"]
REL_TYPES = Literal["many", "one"]
F_TYPES = Literal["fields", "customs", "optionals"]
SCHEMA_TYPES = Literal["In", "Out", "Patch"]


class ModelSerializerType(type):
    def __repr__(self):
        return self.__name__


class ModelSerializerMeta(ModelSerializerType, type(Model)):
    pass
