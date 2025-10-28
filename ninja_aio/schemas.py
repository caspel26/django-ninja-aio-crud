from ninja import Schema
from ninja_aio.models import ModelSerializer
from django.db.models import Model
from pydantic import RootModel


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


class M2MRelationSchema(Schema):
    model: ModelSerializer | Model
    related_name: str
    path: str | None = ""
    auth: list | None = None
    filters: dict | None = None