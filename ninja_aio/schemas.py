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
    """
    Configuration schema for declaring a Many-to-Many relation in the API.

    Attributes:
        model (Type[ModelSerializer] | Type[Model]): Target model class or its serializer.
        related_name (str): Name of the relationship field on the Django model.
        add (bool): Enable adding related objects (default True).
        remove (bool): Enable removing related objects (default True).
        get (bool): Enable retrieving related objects (default True).
        path (str | None): Optional custom URL path segment (None/"" => auto-generated).
        auth (list | None): Optional list of authentication backends for the endpoints.
        filters (dict[str, tuple] | None): Field name -> (type, default) pairs for query filtering.

    Example:
        M2MRelationSchema(
            model=BookSerializer,
            related_name="authors",
            filters={"country": ("str", '')}
        )
    """

    model: Type[ModelSerializer] | Type[Model]
    related_name: str
    add: bool = True
    remove: bool = True
    get: bool = True
    path: Optional[str] = ""
    auth: Optional[list] = None
    filters: Optional[dict[str, tuple]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
