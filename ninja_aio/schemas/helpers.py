from typing import Optional, Type

from ninja import Schema
from ninja_aio.models import ModelSerializer
from django.db.models import Model
from pydantic import BaseModel, ConfigDict, model_validator


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
    related_schema: Optional[Type[Schema]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="before")
    @classmethod
    def validate_related_schema(cls, data):
        related_schema = data.get("related_schema")
        if related_schema is not None:
            return data
        model = data.get("model")
        if not issubclass(model, ModelSerializer):
            raise ValueError(
                "related_schema must be provided if model is not a ModelSerializer",
            )
        data["related_schema"] = model.generate_related_s()
        return data
