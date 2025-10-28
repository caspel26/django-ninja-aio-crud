from typing import Optional, Type

from ninja import Schema
from .models import ModelSerializer
from django.db.models import Model
from pydantic import BaseModel, RootModel, ConfigDict


class GenericMessageSchema(RootModel[dict[str, str]]):
    root: dict[str, str]


class M2MDetailSchema(Schema):
    count: int
    details: list[str]


class M2MSchemaOut(Schema):
    errors: M2MDetailSchema
    results: M2MDetailSchema


class M2MAddSchemaIn(Schema):
    add: list = []


class M2MRemoveSchemaIn(Schema):
    remove: list = []


class M2MSchemaIn(Schema):
    add: list = []
    remove: list = []


class M2MRelationSchema(BaseModel):
    model: Type[ModelSerializer] | Type[Model]
    related_name: str
    add: bool = True
    remove: bool = True
    get: bool = True
    path: Optional[str] = ""
    auth: Optional[list] = None
    filters: Optional[dict] = None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)