from typing import Literal

from django.db.models import Model

S_TYPES = Literal["read", "create", "update"]
REL_TYPES = Literal["many", "one"]
F_TYPES = Literal["fields", "customs", "optionals", "excludes"]
SCHEMA_TYPES = Literal["In", "Out", "Patch"]
VIEW_TYPES = Literal["list", "retrieve", "create", "update", "delete", "all"]

class ModelSerializerType(type):
    def __repr__(self):
        return self.__name__


class ModelSerializerMeta(ModelSerializerType, type(Model)):
    pass
