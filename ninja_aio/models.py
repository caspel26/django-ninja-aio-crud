import asyncio
import base64
from typing import Any, ClassVar

from ninja import Schema
from ninja.orm import create_schema, fields
from ninja.errors import ConfigError

from django.db import models
from django.http import HttpRequest
from django.core.exceptions import ObjectDoesNotExist
from asgiref.sync import sync_to_async
from django.db.models.fields.related_descriptors import (
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
    ManyToManyDescriptor,
    ForwardManyToOneDescriptor,
    ForwardOneToOneDescriptor,
)

from ninja_aio.exceptions import SerializeError, NotFoundError
from ninja_aio.types import S_TYPES, F_TYPES, SCHEMA_TYPES, ModelSerializerMeta
from ninja_aio.schemas.helpers import (
    ModelQuerySetSchema,
    ModelQuerySetExtraSchema,
    QuerySchema,
    ObjectQuerySchema,
    ObjectsQuerySchema,
)
from ninja_aio.helpers.query import QueryUtil


async def agetattr(obj, name: str, default=None):
    """
    Async wrapper around getattr using sync_to_async.

    Parameters
    ----------
    obj : Any
        Object from which to retrieve the attribute.
    name : str
        Attribute name.
    default : Any, optional
        Default value if attribute is missing.

    Returns
    -------
    Any
        Attribute value (or default).
    """
    return await sync_to_async(getattr)(obj, name, default)


class ModelUtil:
    """
    ModelUtil
    =========
    Async utility bound to a Django model class (or a ModelSerializer subclass)
    providing high‑level CRUD helpers plus (de)serialization glue for Django Ninja.

    Overview
    --------
    Central responsibilities:
    - Introspect model metadata (field list, pk name, verbose names).
    - Normalize inbound payloads (custom / optional fields, FK resolution, base64 decoding).
    - Normalize outbound payloads (resolve nested relation dicts into model instances).
    - Prefetch reverse relations to mitigate N+1 issues.
    - Invoke optional serializer hooks: custom_actions(), post_create(), queryset_request().

    Compatible With
    ---------------
    - Plain Django models.
    - Models using ModelSerializerMeta exposing:
        get_fields(mode), is_custom(name), is_optional(name),
        queryset_request(request), custom_actions(payload), post_create().

    Key Methods
    -----------
    - get_object()
    - parse_input_data()
    - parse_output_data()
    - create_s / read_s / update_s / delete_s

    Error Handling
    --------------
    - Missing objects -> NotFoundError(...)
    - Bad base64 -> SerializeError({...}, 400)

    Performance Notes
    -----------------
    - Each FK resolution is an async DB hit; batch when necessary externally.

    Design
    ------
    - Stateless wrapper; safe per-request instantiation.
    """

    def __init__(self, model: type["ModelSerializer"] | models.Model):
        """
        Initialize with a Django model or ModelSerializer subclass.

        Parameters
        ----------
        model : Model | ModelSerializerMeta
            Target model class.
        """
        self.model = model

    @property
    def pk_field_type(self):
        """
        Python type corresponding to the model's primary key field.

        Resolution
        ----------
        Uses the Django field's internal type and ninja.orm.fields.TYPES mapping.
        If the internal type is unknown, instructs how to register a custom mapping.

        Returns
        -------
        type
            Native Python type for the PK suitable for schema generation.

        Raises
        ------
        ConfigError
            If the internal type is not registered in ninja.orm.fields.TYPES.
        """
        try:
            internal_type = self.model._meta.pk.get_internal_type()
            return fields.TYPES[internal_type]
        except KeyError as e:
            msg = [
                f"Do not know how to convert django field '{internal_type}'.",
                "Try: from ninja.orm import register_field",
                "register_field('{internal_type}', <your-python-type>)",
            ]
            raise ConfigError("\n".join(msg)) from e

    @property
    def serializable_fields(self):
        """
        List of fields considered serializable for read operations.

        Returns
        -------
        list[str]
            Explicit read fields if ModelSerializerMeta, otherwise all model fields.
        """
        if isinstance(self.model, ModelSerializerMeta):
            return self.model.get_fields("read")
        return self.model_fields

    @property
    def model_fields(self):
        """
        Raw model field names (including forward relations).

        Returns
        -------
        list[str]
        """
        return [field.name for field in self.model._meta.get_fields()]

    @property
    def model_name(self) -> str:
        """
        Django internal model name.

        Returns
        -------
        str
        """
        return self.model._meta.model_name

    @property
    def model_pk_name(self) -> str:
        """
        Primary key attribute name (attname).

        Returns
        -------
        str
        """
        return self.model._meta.pk.attname

    @property
    def model_verbose_name_plural(self) -> str:
        """
        Human readable plural verbose name.

        Returns
        -------
        str
        """
        return self.model._meta.verbose_name_plural

    def verbose_name_path_resolver(self) -> str:
        """
        Slugify plural verbose name for URL path usage.

        Returns
        -------
        str
        """
        return "-".join(self.model_verbose_name_plural.split(" "))

    def verbose_name_view_resolver(self) -> str:
        """
        Camel-case plural verbose name for view name usage.

        Returns
        -------
        str
        """
        return self.model_verbose_name_plural.replace(" ", "")

    async def _get_base_queryset(
        self,
        request: HttpRequest,
        query_data: QuerySchema,
        with_qs_request: bool,
        is_for_read: bool,
    ) -> models.QuerySet[type["ModelSerializer"] | models.Model]:
        """
        Build base queryset with optimizations and filters.

        Parameters
        ----------
        request : HttpRequest
            The HTTP request object.
        query_data : QuerySchema
            Query configuration with filters and optimizations.
        with_qs_request : bool
            Whether to apply queryset_request hook.
        is_for_read : bool
            Whether this is a read operation.

        Returns
        -------
        models.QuerySet
            Optimized and filtered queryset.
        """
        # Start with base queryset
        obj_qs = self.model.objects.all()

        # Apply query optimizations
        obj_qs = self._apply_query_optimizations(obj_qs, query_data, is_for_read)

        # Apply queryset_request hook if available
        if isinstance(self.model, ModelSerializerMeta) and with_qs_request:
            obj_qs = await self.model.queryset_request(request)

        # Apply filters if present
        if hasattr(query_data, "filters") and query_data.filters:
            obj_qs = obj_qs.filter(**query_data.filters)

        return obj_qs

    async def get_objects(
        self,
        request: HttpRequest,
        query_data: ObjectsQuerySchema = None,
        with_qs_request=True,
        is_for_read: bool = False,
    ) -> models.QuerySet[type["ModelSerializer"] | models.Model]:
        """
        Retrieve a queryset with optimized database queries.

        This method fetches a queryset applying query optimizations including
        select_related and prefetch_related based on the model's relationships
        and the query parameters.

        Parameters
        ----------
        request : HttpRequest
            The HTTP request object, used for queryset_request hooks.
        query_data : ObjectsQuerySchema, optional
            Schema containing filters and query optimization parameters.
            Defaults to an empty ObjectsQuerySchema instance.
        with_qs_request : bool, optional
            Whether to apply the model's queryset_request hook if available.
            Defaults to True.
        is_for_read : bool, optional
            Flag indicating if the query is for read operations, which may affect
            query optimization strategies. Defaults to False.

        Returns
        -------
        models.QuerySet[type["ModelSerializer"] | models.Model]
            A QuerySet of model instances.

        Notes
        -----
        - Query optimizations are automatically applied based on discovered relationships
        - The queryset_request hook is called if the model implements ModelSerializerMeta
        """
        if query_data is None:
            query_data = ObjectsQuerySchema()

        return await self._get_base_queryset(
            request, query_data, with_qs_request, is_for_read
        )

    async def get_object(
        self,
        request: HttpRequest,
        pk: int | str = None,
        query_data: ObjectQuerySchema = None,
        with_qs_request=True,
        is_for_read: bool = False,
    ) -> type["ModelSerializer"] | models.Model:
        """
        Retrieve a single object with optimized database queries.

        This method handles single-object retrieval with automatic query optimizations
        including select_related and prefetch_related based on the model's relationships
        and the query parameters.

        Parameters
        ----------
        request : HttpRequest
            The HTTP request object, used for queryset_request hooks.
        pk : int | str, optional
            Primary key value for single object lookup. Defaults to None.
        query_data : ObjectQuerySchema, optional
            Schema containing getters and query optimization parameters.
            Defaults to an empty ObjectQuerySchema instance.
        with_qs_request : bool, optional
            Whether to apply the model's queryset_request hook if available.
            Defaults to True.
        is_for_read : bool, optional
            Flag indicating if the query is for read operations, which may affect
            query optimization strategies. Defaults to False.

        Returns
        -------
        type["ModelSerializer"] | models.Model
            A single model instance.

        Raises
        ------
        ValueError
            If neither pk nor getters are provided.
        NotFoundError
            If no matching object exists in the database.

        Notes
        -----
        - Query optimizations are automatically applied based on discovered relationships
        - The queryset_request hook is called if the model implements ModelSerializerMeta
        """
        if query_data is None:
            query_data = ObjectQuerySchema()

        if not query_data.getters and pk is None:
            raise ValueError(
                "Either pk or getters must be provided for single object retrieval."
            )

        # Build lookup query and get optimized queryset
        get_q = self._build_lookup_query(pk, query_data.getters)
        obj_qs = await self._get_base_queryset(
            request, query_data, with_qs_request, is_for_read
        )

        # Perform lookup
        try:
            obj = await obj_qs.aget(**get_q)
        except ObjectDoesNotExist:
            raise NotFoundError(self.model)

        return obj

    def _build_lookup_query(self, pk: int | str = None, getters: dict = None) -> dict:
        """
        Build lookup query dict from pk and additional getters.

        Parameters
        ----------
        pk : int | str, optional
            Primary key value.
        getters : dict, optional
            Additional field lookups.

        Returns
        -------
        dict
            Combined lookup criteria.
        """
        get_q = {self.model_pk_name: pk} if pk is not None else {}
        if getters:
            get_q |= getters
        return get_q

    def _apply_query_optimizations(
        self,
        queryset: models.QuerySet,
        query_data: QuerySchema,
        is_for_read: bool,
    ) -> models.QuerySet:
        """
        Apply select_related and prefetch_related optimizations to queryset.

        Parameters
        ----------
        queryset : QuerySet
            Base queryset to optimize.
        query_data : ModelQuerySchema
            Query configuration with select_related/prefetch_related lists.
        is_for_read : bool
            Whether to include model-level relation discovery.

        Returns
        -------
        QuerySet
            Optimized queryset.
        """
        select_related = (
            query_data.select_related + self.get_select_relateds()
            if is_for_read
            else query_data.select_related
        )
        prefetch_related = (
            query_data.prefetch_related + self.get_reverse_relations()
            if is_for_read
            else query_data.prefetch_related
        )

        if select_related:
            queryset = queryset.select_related(*select_related)
        if prefetch_related:
            queryset = queryset.prefetch_related(*prefetch_related)

        return queryset

    def get_reverse_relations(self) -> list[str]:
        """
        Discover reverse relation names for safe prefetching.

        Returns
        -------
        list[str]
            Relation attribute names.
        """
        reverse_rels = []
        for f in self.serializable_fields:
            field_obj = getattr(self.model, f)
            if isinstance(field_obj, ManyToManyDescriptor):
                reverse_rels.append(f)
                continue
            if isinstance(field_obj, ReverseManyToOneDescriptor):
                reverse_rels.append(field_obj.field._related_name)
                continue
            if isinstance(field_obj, ReverseOneToOneDescriptor):
                reverse_rels.append(field_obj.related.name)
        return reverse_rels

    def get_select_relateds(self) -> list[str]:
        """
        Discover forward relation names for safe select_related.

        Returns
        -------
        list[str]
            Relation attribute names.
        """
        select_rels = []
        for f in self.serializable_fields:
            field_obj = getattr(self.model, f)
            if isinstance(field_obj, ForwardManyToOneDescriptor):
                select_rels.append(f)
                continue
            if isinstance(field_obj, ForwardOneToOneDescriptor):
                select_rels.append(f)
        return select_rels

    async def _get_field(self, k: str):
        return (await agetattr(self.model, k)).field

    def _decode_binary(self, payload: dict, k: str, v: Any, field_obj: models.Field):
        if not isinstance(field_obj, models.BinaryField):
            return
        try:
            payload[k] = base64.b64decode(v)
        except Exception as exc:
            raise SerializeError({k: ". ".join(exc.args)}, 400)

    async def _resolve_fk(
        self,
        request: HttpRequest,
        payload: dict,
        k: str,
        v: Any,
        field_obj: models.Field,
    ):
        if not isinstance(field_obj, models.ForeignKey):
            return
        rel_util = ModelUtil(field_obj.related_model)
        rel = await rel_util.get_object(request, v, with_qs_request=False)
        payload[k] = rel

    async def _bump_object_from_schema(
        self, obj: type["ModelSerializer"] | models.Model, schema: Schema
    ):
        return (await sync_to_async(schema.from_orm)(obj)).model_dump(mode="json")

    def _validate_read_params(self, request: HttpRequest, query_data: QuerySchema):
        """Validate required parameters for read operations."""
        if request is None:
            raise SerializeError(
                {"request": "must be provided when object is not given"}, 400
            )

        if query_data is None:
            raise SerializeError(
                {"query_data": "must be provided when object is not given"}, 400
            )

        if (
            hasattr(query_data, "filters")
            and hasattr(query_data, "getters")
            and query_data.filters
            and query_data.getters
        ):
            raise SerializeError(
                {"query_data": "cannot contain both filters and getters"}, 400
            )

    async def _handle_query_mode(
        self,
        request: HttpRequest,
        query_data: QuerySchema,
        schema: Schema,
        is_for_read: bool,
    ):
        """Handle different query modes (filters vs getters)."""
        if hasattr(query_data, "filters") and query_data.filters:
            return await self._serialize_queryset(
                request, query_data, schema, is_for_read
            )

        if hasattr(query_data, "getters") and query_data.getters:
            return await self._serialize_single_object(
                request, query_data, schema, is_for_read
            )

        raise SerializeError(
            {"query_data": "must contain either filters or getters"}, 400
        )

    async def _serialize_queryset(
        self,
        request: HttpRequest,
        query_data: QuerySchema,
        schema: Schema,
        is_for_read: bool,
    ):
        """Serialize a queryset of objects."""
        objs = await self.get_objects(
            request, query_data=query_data, is_for_read=is_for_read
        )
        return [await self._bump_object_from_schema(obj, schema) async for obj in objs]

    async def _serialize_single_object(
        self,
        request: HttpRequest,
        query_data: QuerySchema,
        obj_schema: Schema,
        is_for_read: bool,
    ):
        """Serialize a single object."""
        obj = await self.get_object(
            request, query_data=query_data, is_for_read=is_for_read
        )
        return await self._bump_object_from_schema(obj, obj_schema)

    async def parse_input_data(self, request: HttpRequest, data: Schema):
        """
        Transform inbound schema data to a model-ready payload.

        Steps
        -----
        - Strip custom fields (retain separately).
        - Drop optional fields with None (ModelSerializer only).
        - Decode BinaryField base64 values.
        - Resolve ForeignKey ids to model instances.

        Parameters
        ----------
        request : HttpRequest
        data : Schema
            Incoming validated schema instance.

        Returns
        -------
        tuple[dict, dict]
            (payload_without_customs, customs_dict)

        Raises
        ------
        SerializeError
            On base64 decoding failure.
        """
        payload = data.model_dump(mode="json")

        is_serializer = isinstance(self.model, ModelSerializerMeta)

        # Collect custom and optional fields (only if ModelSerializerMeta)
        customs: dict[str, Any] = {}
        optionals: list[str] = []
        if is_serializer:
            customs = {
                k: v
                for k, v in payload.items()
                if self.model.is_custom(k) and k not in self.model_fields
            }
            optionals = [
                k for k, v in payload.items() if self.model.is_optional(k) and v is None
            ]

        skip_keys = set()
        if is_serializer:
            # Keys to skip during model field processing
            skip_keys = {
                k
                for k, v in payload.items()
                if (self.model.is_custom(k) and k not in self.model_fields)
                or (self.model.is_optional(k) and v is None)
            }

        # Process payload fields
        for k, v in payload.items():
            if k in skip_keys:
                continue
            field_obj = await self._get_field(k)
            self._decode_binary(payload, k, v, field_obj)
            await self._resolve_fk(request, payload, k, v, field_obj)

        # Preserve original exclusion semantics (customs if present else optionals)
        exclude_keys = customs.keys() or optionals
        new_payload = {k: v for k, v in payload.items() if k not in exclude_keys}

        return new_payload, customs

    async def create_s(self, request: HttpRequest, data: Schema, obj_schema: Schema):
        """
        Create a new instance and return serialized output.

        Applies custom_actions + post_create hooks if available.

        Parameters
        ----------
        request : HttpRequest
        data : Schema
            Input schema instance.
        obj_schema : Schema
            Read schema class for output.

        Returns
        -------
        dict
            Serialized created object.
        """
        payload, customs = await self.parse_input_data(request, data)
        pk = (await self.model.objects.acreate(**payload)).pk
        obj = await self.get_object(request, pk)
        if isinstance(self.model, ModelSerializerMeta):
            await asyncio.gather(obj.custom_actions(customs), obj.post_create())
        return await self.read_s(obj_schema, request, obj)

    async def _read_s(
        self,
        schema: Schema,
        request: HttpRequest = None,
        instance: models.QuerySet[type["ModelSerializer"] | models.Model]
        | type["ModelSerializer"]
        | models.Model = None,
        query_data: QuerySchema = None,
        is_for_read: bool = False,
    ):
        """
        Internal serialization method handling both single instances and querysets.

        Parameters
        ----------
        schema : Schema
            Read schema class for serialization.
        request : HttpRequest, optional
            HTTP request object, required when instance is None.
        instance : QuerySet | Model, optional
            Instance(s) to serialize. If None, fetches based on query_data.
        query_data : QuerySchema, optional
            Query parameters for fetching objects when instance is None.
        is_for_read : bool, optional
            Whether to apply read-specific query optimizations.

        Returns
        -------
        dict | list[dict]
            Serialized instance(s).

        Raises
        ------
        SerializeError
            If schema is None or validation fails.
        """
        if schema is None:
            raise SerializeError({"schema": "must be provided"}, 400)

        if instance is not None:
            if isinstance(instance, models.QuerySet):
                return [
                    await self._bump_object_from_schema(obj, schema)
                    async for obj in instance
                ]
            return await self._bump_object_from_schema(instance, schema)

        self._validate_read_params(request, query_data)
        return await self._handle_query_mode(request, query_data, schema, is_for_read)

    async def read_s(
        self,
        schema: Schema,
        request: HttpRequest = None,
        instance: type["ModelSerializer"] = None,
        query_data: ObjectQuerySchema = None,
        is_for_read: bool = False,
    ) -> dict:
        """
        Serialize a single model instance or fetch and serialize using query parameters.

        This method handles single-object serialization. It can serialize a provided
        instance directly or fetch and serialize a single object using query_data.getters.

        Parameters
        ----------
        schema : Schema
            Read schema class for serialization output.
        request : HttpRequest, optional
            HTTP request object, required when instance is None.
        instance : ModelSerializer | Model, optional
            Single instance to serialize. If None, fetched based on query_data.
        query_data : ObjectQuerySchema, optional
            Query parameters with getters for single object lookup.
            Required when instance is None.
        is_for_read : bool, optional
            Whether to apply read-specific query optimizations. Defaults to False.

        Returns
        -------
        dict
            Serialized model instance as dictionary.

        Raises
        ------
        SerializeError
            - If schema is None
            - If instance is None and request or query_data is None
            - If query_data validation fails
        NotFoundError
            If using getters and no matching object is found.

        Notes
        -----
        - Uses Pydantic's from_orm() with mode="json" for serialization
        - When instance is provided, request and query_data are ignored
        - Query optimizations applied when is_for_read=True
        """
        return await self._read_s(
            schema,
            request,
            instance,
            query_data,
            is_for_read,
        )

    async def list_read_s(
        self,
        schema: Schema,
        request: HttpRequest = None,
        instances: models.QuerySet[type["ModelSerializer"] | models.Model] = None,
        query_data: ObjectsQuerySchema = None,
        is_for_read: bool = False,
    ) -> list[dict]:
        """
        Serialize multiple model instances or fetch and serialize using query parameters.

        This method handles queryset serialization. It can serialize provided instances
        directly or fetch and serialize multiple objects using query_data.filters.

        Parameters
        ----------
        schema : Schema
            Read schema class for serialization output.
        request : HttpRequest, optional
            HTTP request object, required when instances is None.
        instances : QuerySet, optional
            Queryset of instances to serialize. If None, fetched based on query_data.
        query_data : ObjectsQuerySchema, optional
            Query parameters with filters for multiple object lookup.
            Required when instances is None.
        is_for_read : bool, optional
            Whether to apply read-specific query optimizations. Defaults to False.

        Returns
        -------
        list[dict]
            List of serialized model instances as dictionaries.

        Raises
        ------
        SerializeError
            - If schema is None
            - If instances is None and request or query_data is None
            - If query_data validation fails

        Notes
        -----
        - Uses Pydantic's from_orm() with mode="json" for serialization
        - When instances is provided, request and query_data are ignored
        - Query optimizations applied when is_for_read=True
        - Processes queryset asynchronously for efficiency
        """
        return await self._read_s(
            schema,
            request,
            instances,
            query_data,
            is_for_read,
        )

    async def update_s(
        self, request: HttpRequest, data: Schema, pk: int | str, obj_schema: Schema
    ):
        """
        Update an existing instance and return serialized output.

        Only non-null fields are applied to the instance.

        Parameters
        ----------
        request : HttpRequest
        data : Schema
            Input update schema instance.
        pk : int | str
            Primary key of target object.
        obj_schema : Schema
            Read schema class for output.

        Returns
        -------
        dict
            Serialized updated object.
        """
        obj = await self.get_object(request, pk)
        payload, customs = await self.parse_input_data(request, data)
        for k, v in payload.items():
            if v is not None:
                setattr(obj, k, v)
        if isinstance(self.model, ModelSerializerMeta):
            await obj.custom_actions(customs)
        await obj.asave()
        updated_object = await self.get_object(request, pk)
        return await self.read_s(obj_schema, request, updated_object)

    async def delete_s(self, request: HttpRequest, pk: int | str):
        """
        Delete an instance by primary key.

        Parameters
        ----------
        request : HttpRequest
        pk : int | str
            Primary key.

        Returns
        -------
        None
        """
        obj = await self.get_object(request, pk)
        await obj.adelete()
        return None


class ModelSerializer(models.Model, metaclass=ModelSerializerMeta):
    """
    ModelSerializer
    =================
    Abstract mixin for Django models centralizing (on the model class itself) the
    declarative configuration required to auto-generate create / update / read /
    related schemas.

    Goals
    -----
    - Remove duplication between Model and separate serializer classes.
    - Provide clear extension points (sync + async hooks, custom synthetic fields).

    See inline docstrings for per-method behavior.
    """

    util: ClassVar[ModelUtil]
    query_util: ClassVar[QueryUtil]

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Bind a ModelUtil instance to the subclass for convenient access
        cls.util = ModelUtil(cls)
        cls.query_util = QueryUtil(cls)

    class QuerySet:
        """
        Configuration container describing how to build query schemas for a model.
        Purpose
        -------
        Describes which fields and extras are available when querying for model
        instances. A factory/metaclass can read this configuration to generate
        Pydantic / Ninja query schemas.
        Attributes
        ----------
        read : ModelQuerySetSchema
            Schema configuration for read operations.
        queryset_request : ModelQuerySetSchema
            Schema configuration for queryset_request hook.
        extras : list[ModelQuerySetExtraSchema]
            Additional computed / synthetic query parameters.
        """
        read = ModelQuerySetSchema()
        queryset_request = ModelQuerySetSchema()
        extras: list[ModelQuerySetExtraSchema] = []

    class CreateSerializer:
        """Configuration container describing how to build a create (input) schema for a model.

        Purpose
        -------
        Describes which fields are accepted (and in what form) when creating a new
        instance. A factory/metaclass can read this configuration to generate a
        Pydantic / Ninja input schema.

        Attributes
        ----------
        fields : list[str]
            REQUIRED model fields.
        optionals : list[tuple[str, type]]
            Optional model fields (nullable / patch-like).
        customs : list[tuple[str, type, Any]]
            Synthetic input fields (non-model).
        excludes : list[str]
            Disallowed model fields on create (e.g., id, timestamps).
        """

        fields: list[str] = []
        customs: list[tuple[str, type, Any]] = []
        optionals: list[tuple[str, type]] = []
        excludes: list[str] = []

    class ReadSerializer:
        """Configuration describing how to build a read (output) schema.

        Attributes
        ----------
        fields : list[str]
            Explicit model fields to include.
        excludes : list[str]
            Fields to force exclude (safety).
        customs : list[tuple[str, type, Any]]
            Computed / synthetic output attributes.
        """

        fields: list[str] = []
        excludes: list[str] = []
        customs: list[tuple[str, type, Any]] = []

    class UpdateSerializer:
        """Configuration describing update (PATCH/PUT) schema.

        Attributes
        ----------
        fields : list[str]
            Required update fields (rare).
        optionals : list[tuple[str, type]]
            Editable optional fields.
        customs : list[tuple[str, type, Any]]
            Synthetic operational inputs.
        excludes : list[str]
            Immutable / blocked fields.
        """

        fields: list[str] = []
        customs: list[tuple[str, type, Any]] = []
        optionals: list[tuple[str, type]] = []
        excludes: list[str] = []

    @classmethod
    def _get_fields(cls, s_type: type[S_TYPES], f_type: type[F_TYPES]):
        """
        Internal accessor for raw configuration lists.

        Parameters
        ----------
        s_type : str
            Serializer type ("create" | "update" | "read").
        f_type : str
            Field category ("fields" | "optionals" | "customs" | "excludes").

        Returns
        -------
        list
            Raw configuration list or empty list.
        """
        match s_type:
            case "create":
                fields = getattr(cls.CreateSerializer, f_type, [])
            case "update":
                fields = getattr(cls.UpdateSerializer, f_type, [])
            case "read":
                fields = getattr(cls.ReadSerializer, f_type, [])
        return fields

    @classmethod
    def _is_special_field(
        cls, s_type: type[S_TYPES], field: str, f_type: type[F_TYPES]
    ):
        """
        Determine if a field is declared in a given category for a serializer type.

        Parameters
        ----------
        s_type : str
        field : str
        f_type : str

        Returns
        -------
        bool
        """
        special_fields = cls._get_fields(s_type, f_type)
        return any(field in special_f for special_f in special_fields)

    @classmethod
    def _generate_model_schema(
        cls,
        schema_type: type[SCHEMA_TYPES],
        depth: int = None,
    ) -> Schema:
        """
        Core schema factory bridging configuration and ninja.orm.create_schema.

        Parameters
        ----------
        schema_type : str
            "In" | "Patch" | "Out" | "Related".
        depth : int, optional
            Relation depth for read schema.

        Returns
        -------
        Schema | None
            Generated schema class or None if no fields.
        """
        match schema_type:
            case "In":
                s_type = "create"
            case "Patch":
                s_type = "update"
            case "Out":
                fields, reverse_rels, excludes, customs = cls.get_schema_out_data()
                if not fields and not reverse_rels and not excludes and not customs:
                    return None
                return create_schema(
                    model=cls,
                    name=f"{cls._meta.model_name}SchemaOut",
                    depth=depth,
                    fields=fields,
                    custom_fields=reverse_rels + customs,
                    exclude=excludes,
                )
            case "Related":
                fields, customs = cls.get_related_schema_data()
                if not fields and not customs:
                    return None
                return create_schema(
                    model=cls,
                    name=f"{cls._meta.model_name}SchemaRelated",
                    fields=fields,
                    custom_fields=customs,
                )

        fields = cls.get_fields(s_type)
        optionals = cls.get_optional_fields(s_type)
        customs = cls.get_custom_fields(s_type) + optionals
        excludes = cls.get_excluded_fields(s_type)
        if not fields and not excludes:
            fields = [f[0] for f in optionals]
        return (
            create_schema(
                model=cls,
                name=f"{cls._meta.model_name}Schema{schema_type}",
                fields=fields,
                custom_fields=customs,
                exclude=excludes,
            )
            if fields or customs or excludes
            else None
        )

    @classmethod
    def verbose_name_path_resolver(cls) -> str:
        """
        Slugify plural verbose name for URL path segment.

        Returns
        -------
        str
        """
        return "-".join(cls._meta.verbose_name_plural.split(" "))

    def has_changed(self, field: str) -> bool:
        """
        Check if a model field has changed compared to the persisted value.

        Parameters
        ----------
        field : str
            Field name.

        Returns
        -------
        bool
            True if in-memory value differs from DB value.
        """
        if not self.pk:
            return False
        old_value = (
            self.__class__._default_manager.filter(pk=self.pk)
            .values(field)
            .get()[field]
        )
        return getattr(self, field) != old_value

    @classmethod
    async def queryset_request(cls, request: HttpRequest):
        """
        Override to return a request-scoped filtered queryset.

        Parameters
        ----------
        request : HttpRequest

        Returns
        -------
        QuerySet
        """
        return cls.query_util.apply_queryset_optimizations(
            queryset=cls.objects.all(),
            scope=cls.query_util.SCOPES.QUERYSET_REQUEST,
        )

    async def post_create(self) -> None:
        """
        Async hook executed after first persistence (create path).
        """
        pass

    async def custom_actions(self, payload: dict[str, Any]):
        """
        Async hook for reacting to provided custom (synthetic) fields.

        Parameters
        ----------
        payload : dict
            Custom field name/value pairs.
        """
        pass

    @classmethod
    def get_related_schema_data(cls):
        """
        Build field/custom lists for 'Related' schema (flattening non-relational fields).

        Returns
        -------
        tuple[list[str] | None, list[tuple] | None]
            (related_fields, custom_related_fields) or (None, None)
        """
        fields = cls.get_fields("read")
        custom_f = {
            name: (value, default)
            for name, value, default in cls.get_custom_fields("read")
        }
        _related_fields = []
        for f in fields + list(custom_f.keys()):
            field_obj = getattr(cls, f)
            if not isinstance(
                field_obj,
                (
                    ManyToManyDescriptor,
                    ReverseManyToOneDescriptor,
                    ReverseOneToOneDescriptor,
                    ForwardManyToOneDescriptor,
                    ForwardOneToOneDescriptor,
                ),
            ):
                _related_fields.append(f)

        if not _related_fields:
            return None, None

        custom_related_fields = [
            (f, *custom_f[f]) for f in _related_fields if f in custom_f
        ]
        related_fields = [f for f in _related_fields if f not in custom_f]
        return related_fields, custom_related_fields

    @classmethod
    def _build_schema_reverse_rel(cls, field_name: str, descriptor: Any):
        """
        Build a reverse relation schema component for 'Out' schema generation.
        """
        if isinstance(descriptor, ManyToManyDescriptor):
            rel_model: ModelSerializer = descriptor.field.related_model
            if descriptor.reverse:  # reverse side of M2M
                rel_model = descriptor.field.model
            rel_type = "many"
        elif isinstance(descriptor, ReverseManyToOneDescriptor):
            rel_model = descriptor.field.model
            rel_type = "many"
        else:  # ReverseOneToOneDescriptor
            rel_model = descriptor.related.related_model
            rel_type = "one"

        if not isinstance(rel_model, ModelSerializerMeta):
            return None
        if not rel_model.get_fields("read") and not rel_model.get_custom_fields("read"):
            return None

        rel_schema = (
            rel_model.generate_related_s()
            if rel_type == "one"
            else list[rel_model.generate_related_s()]
        )
        return (field_name, rel_schema | None, None)

    @classmethod
    def _build_schema_forward_rel(cls, field_name: str, descriptor: Any):
        """
        Build a forward relation schema component for 'Out' schema generation.
        """
        rel_model = descriptor.field.related_model
        if not isinstance(rel_model, ModelSerializerMeta):
            return True  # Signal: treat as plain field
        if not rel_model.get_fields("read") and not rel_model.get_custom_fields("read"):
            return None  # Skip entirely
        rel_schema = rel_model.generate_related_s()
        return (field_name, rel_schema | None, None)

    @classmethod
    def get_schema_out_data(cls):
        """
        Collect components for 'Out' read schema generation.

        Returns
        -------
        tuple
            (fields, reverse_rel_descriptors, excludes, custom_fields_with_forward_relations)
        """

        fields: list[str] = []
        reverse_rels: list[tuple] = []
        rels: list[tuple] = []

        for f in cls.get_fields("read"):
            field_obj = getattr(cls, f)

            # Reverse relations
            if isinstance(
                field_obj,
                (
                    ManyToManyDescriptor,
                    ReverseManyToOneDescriptor,
                    ReverseOneToOneDescriptor,
                ),
            ):
                rel_tuple = cls._build_schema_reverse_rel(f, field_obj)
                if rel_tuple:
                    reverse_rels.append(rel_tuple)
                    continue

            # Forward relations
            if isinstance(
                field_obj, (ForwardOneToOneDescriptor, ForwardManyToOneDescriptor)
            ):
                rel_tuple = cls._build_schema_forward_rel(f, field_obj)
                if rel_tuple is True:
                    fields.append(f)
                elif rel_tuple:
                    rels.append(rel_tuple)
                # If rel_tuple is None -> skip
                continue

            # Plain field
            fields.append(f)

        return (
            fields,
            reverse_rels,
            cls.get_excluded_fields("read"),
            cls.get_custom_fields("read") + rels,
        )

    @classmethod
    def is_custom(cls, field: str):
        """
        Check if a field is declared as a custom input (create or update).

        Parameters
        ----------
        field : str

        Returns
        -------
        bool
        """
        return cls._is_special_field(
            "create", field, "customs"
        ) or cls._is_special_field("update", field, "customs")

    @classmethod
    def is_optional(cls, field: str):
        """
        Check if a field is declared as optional (create or update).

        Parameters
        ----------
        field : str

        Returns
        -------
        bool
        """
        return cls._is_special_field(
            "create", field, "optionals"
        ) or cls._is_special_field("update", field, "optionals")

    @classmethod
    def get_custom_fields(cls, s_type: type[S_TYPES]) -> list[tuple[str, type, Any]]:
        """
        Normalize declared custom field specs into (name, py_type, default) triples.

        Accepted tuple shapes:
          (name, py_type, default) -> keeps provided default (callable or literal)
          (name, py_type)          -> marks as required (default = Ellipsis)
        Any other arity raises ValueError.

        Parameters
        ----------
        s_type : str
            "create" | "update" | "read"

        Returns
        -------
        list[tuple[str, type, Any]]
        """
        raw_customs = cls._get_fields(s_type, "customs") or []
        normalized: list[tuple[str, type, Any]] = []
        for spec in raw_customs:
            if not isinstance(spec, tuple):
                raise ValueError(f"Custom field spec must be a tuple, got {type(spec)}")
            match len(spec):
                case 3:
                    name, py_type, default = spec
                case 2:
                    name, py_type = spec
                    default = ...
                case _:
                    raise ValueError(
                        f"Custom field tuple must have length 2 or 3 (name, type[, default]); got {len(spec)}"
                    )
            normalized.append((name, py_type, default))
        return normalized

    @classmethod
    def get_optional_fields(cls, s_type: type[S_TYPES]):
        """
        Return optional field specifications normalized to (name, type, None).

        Parameters
        ----------
        s_type : str

        Returns
        -------
        list[tuple[str, type, None]]
        """
        return [
            (field, field_type, None)
            for field, field_type in cls._get_fields(s_type, "optionals")
        ]

    @classmethod
    def get_excluded_fields(cls, s_type: type[S_TYPES]):
        """
        Return excluded field names for a serializer type.

        Parameters
        ----------
        s_type : str

        Returns
        -------
        list[str]
        """
        return cls._get_fields(s_type, "excludes")

    @classmethod
    def get_fields(cls, s_type: type[S_TYPES]):
        """
        Return explicit declared fields for a serializer type.

        Parameters
        ----------
        s_type : str

        Returns
        -------
        list[str]
        """
        return cls._get_fields(s_type, "fields")

    @classmethod
    def generate_read_s(cls, depth: int = 1) -> Schema:
        """
        Generate read (Out) schema.

        Parameters
        ----------
        depth : int
            Relation depth.

        Returns
        -------
        Schema | None
        """
        return cls._generate_model_schema("Out", depth)

    @classmethod
    def generate_create_s(cls) -> Schema:
        """
        Generate create (In) schema.

        Returns
        -------
        Schema | None
        """
        return cls._generate_model_schema("In")

    @classmethod
    def generate_update_s(cls) -> Schema:
        """
        Generate update (Patch) schema.

        Returns
        -------
        Schema | None
        """
        return cls._generate_model_schema("Patch")

    @classmethod
    def generate_related_s(cls) -> Schema:
        """
        Generate related (nested) schema.

        Returns
        -------
        Schema | None
        """
        return cls._generate_model_schema("Related")

    def after_save(self):
        """
        Sync hook executed after any save (create or update).
        """
        pass

    def before_save(self):
        """
        Sync hook executed before any save (create or update).
        """
        pass

    def on_create_after_save(self):
        """
        Sync hook executed only after initial creation save.
        """
        pass

    def on_create_before_save(self):
        """
        Sync hook executed only before initial creation save.
        """
        pass

    def on_delete(self):
        """
        Sync hook executed after delete.
        """
        pass

    def save(self, *args, **kwargs):
        """
        Override save lifecycle to inject create/update hooks.
        """
        state_adding = self._state.adding
        if state_adding:
            self.on_create_before_save()
        self.before_save()
        super().save(*args, **kwargs)
        if state_adding:
            self.on_create_after_save()
        self.after_save()

    def delete(self, *args, **kwargs):
        """
        Override delete to inject on_delete hook.

        Returns
        -------
        tuple(int, dict)
            Django delete return signature.
        """
        res = super().delete(*args, **kwargs)
        self.on_delete()
        return res
