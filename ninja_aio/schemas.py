from uuid import UUID
from ninja import Schema
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
    add: list[UUID] = []


class M2MRemoveSchemaIn(Schema):
    remove: list[UUID] = []


class M2MSchemaIn(Schema):
    add: list[UUID] = []
    remove: list[UUID] = []