from typing import List, Optional, Type

from ninja import Schema
from ninja_aio.types import ModelSerializerMeta
from django.db.models import Model
from pydantic import BaseModel, ConfigDict, model_validator


class M2MRelationSchema(BaseModel):
    """
    Configuration schema for declaring and controlling a Many-to-Many (M2M) relation in the API.

    This schema is used to describe an M2M relationship between a primary resource and its related
    objects, and to automatically provision CRUD-like endpoints for managing that relation
    (add, remove, and get). It supports both direct Django model classes and model serializers,
    and can optionally expose a custom schema for the related output.

        model (ModelSerializerMeta | Type[Model]):
            The target related entity, provided either as a ModelSerializer (preferred) or a Django model.
            If a plain model is supplied, you must also provide `related_schema`.
        related_name (str):
            The name of the M2M field on the Django model that links to the related objects.
        add (bool):
            Whether to enable an endpoint for adding related objects. Defaults to True.
        remove (bool):
            Whether to enable an endpoint for removing related objects. Defaults to True.
        get (bool):
            Whether to enable an endpoint for listing/retrieving related objects. Defaults to True.
        path (str | None):
            Optional custom URL path segment for the relation endpoints. If empty or None, a path
            is auto-generated based on `related_name`.
        auth (list | None):
            Optional list of authentication backends to protect the relation endpoints.
        filters (dict[str, tuple] | None):
            Optional mapping of queryable filter fields for the GET endpoint, defined as:
            field_name -> (type, default). Example: {"country": ("str", "")}.
        related_schema (Type[Schema] | None):
            Optional explicit schema to represent related objects in responses.
            If `model` is a ModelSerializerMeta, this is auto-derived via `model.generate_related_s()`.
            If `model` is a plain Django model, this must be provided.
        append_slash (bool):
            Whether to append a trailing slash to the generated GET endpoint path. Defaults to False for backward compatibility.

    Validation:
        - If `model` is not a ModelSerializerMeta, `related_schema` is required.
        - When `model` is a ModelSerializerMeta and `related_schema` is not provided, it will be
          automatically generated.

    Usage example:
            filters={"country": ("str", "")},
            auth=[AuthBackend],
            add=True,
            remove=True,
            get=True,
    """

    model: ModelSerializerMeta | Type[Model]
    related_name: str
    add: bool = True
    remove: bool = True
    get: bool = True
    path: Optional[str] = ""
    auth: Optional[list] = None
    filters: Optional[dict[str, tuple]] = None
    related_schema: Optional[Type[Schema]] = None
    append_slash: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="before")
    @classmethod
    def validate_related_schema(cls, data):
        related_schema = data.get("related_schema")
        if related_schema is not None:
            return data
        model = data.get("model")
        if not isinstance(model, ModelSerializerMeta):
            raise ValueError(
                "related_schema must be provided if model is not a ModelSerializer",
            )
        data["related_schema"] = model.generate_related_s()
        return data


class ModelQuerySetSchema(BaseModel):
    select_related: Optional[list[str]] = []
    prefetch_related: Optional[list[str]] = []


class ModelQuerySetExtraSchema(ModelQuerySetSchema):
    """
    Schema defining extra query parameters for model queryset operations in API endpoints.
    Attributes:
        scope (str): The scope defining the level of access for the queryset operation.
        select_related (Optional[list[str]]): List of related fields for select_related optimization.
        prefetch_related (Optional[list[str]]): List of related fields for prefetch_related optimization
    """
    scope: str


class ObjectQuerySchema(ModelQuerySetSchema):
    """
    Schema defining query parameters for single object retrieval in API endpoints.
    Attributes:
        getters (Optional[dict]): A dictionary of getters to apply to the query.
        select_related (Optional[list[str]]): List of related fields for select_related optimization.
        prefetch_related (Optional[list[str]]): List of related fields for prefetch_related optimization
    """
    getters: Optional[dict] = {}


class ObjectsQuerySchema(ModelQuerySetSchema):
    """
    Schema defining query parameters for multiple object retrieval in API endpoints.
    Attributes:
        filters (Optional[dict]): A dictionary of filters to apply to the query.
        select_related (Optional[list[str]]): List of related fields for select_related optimization.
        prefetch_related (Optional[list[str]]): List of related fields for prefetch_related optimization
    """
    filters: Optional[dict] = {}


class QuerySchema(ModelQuerySetSchema):
    """
    Schema defining query parameters for API endpoints.
    Attributes:
        filters (Optional[dict]): A dictionary of filters to apply to the query.
        getters (Optional[dict]): A dictionary of getters to apply to the query.
        select_related (Optional[list[str]]): List of related fields for select_related optimization.
        prefetch_related (Optional[list[str]]): List of related fields for prefetch_related optimization
    """
    filters: Optional[dict] = {}
    getters: Optional[dict] = {}


class QueryUtilBaseScopesSchema(BaseModel):
    """
    Schema defining base scopes for query utilities.
    Attributes:
        READ (str): Scope for read operations.
        QUERYSET_REQUEST (str): Scope for queryset request operations.
    """
    READ: str = "read"
    QUERYSET_REQUEST: str = "queryset_request"


class DecoratorsSchema(Schema):
    """
    Schema defining optional decorator lists for CRUD operations.

    Attributes:
        list (Optional[List]): Decorators applied to the list endpoint.
        retrieve (Optional[List]): Decorators applied to the retrieve endpoint.
        create (Optional[List]): Decorators applied to the create endpoint.
        update (Optional[List]): Decorators applied to the update endpoint.
        delete (Optional[List]): Decorators applied to the delete endpoint.

    Notes:
        - Each attribute holds an ordered collection of decorators (callables or decorator references)
          to be applied to the corresponding endpoint.
        - Defaults are empty lists, meaning no decorators are applied unless explicitly provided.
        - Using mutable defaults (empty lists) at the class level may lead to shared state between instances.
          Consider initializing these in __init__ or using default_factory (if using pydantic/dataclasses)
          to avoid unintended side effects.
    """
    list: Optional[List] = []
    retrieve: Optional[List] = []
    create: Optional[List] = []
    update: Optional[List] = []
    delete: Optional[List] = []
