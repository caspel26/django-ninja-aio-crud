import asyncio
import base64
from typing import Any

from ninja import Schema
from ninja.orm import fields
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
from ninja_aio.models.serializers import ModelSerializer
from ninja_aio.types import ModelSerializerMeta
from ninja_aio.schemas.helpers import (
    ModelQuerySetSchema,
    QuerySchema,
    ObjectQuerySchema,
    ObjectsQuerySchema,
)


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

    def __init__(
        self, model: type["ModelSerializer"] | models.Model, serializer_class=None
    ):
        """
        Initialize with a Django model or ModelSerializer subclass.

        Parameters
        ----------
        model : Model | ModelSerializerMeta
            Target model class.
        """
        from ninja_aio.models.serializers import Serializer

        self.model = model
        self.serializer_class: Serializer = serializer_class
        if serializer_class is not None and isinstance(model, ModelSerializerMeta):
            raise ConfigError(
                "ModelUtil cannot accept both model and serializer_class if the model is a ModelSerializer."
            )
        self.serializer: Serializer = serializer_class() if serializer_class else None

    @property
    def with_serializer(self) -> bool:
        """
        Indicates if a serializer_class is associated.

        Returns
        -------
        bool
        """
        return self.serializer_class is not None

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
        obj_qs = (
            self.model.objects.all()
            if self.serializer_class is None
            else await self.serializer_class.queryset_request(request)
        )

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

    def _get_read_optimizations(self) -> ModelQuerySetSchema:
        """
        Retrieve read optimizations from model or serializer class.

        Returns
        -------
        ModelQuerySetSchema
            Read optimization configuration.
        """
        if isinstance(self.model, ModelSerializerMeta):
            return getattr(self.model.QuerySet, "read", ModelQuerySetSchema())
        if self.with_serializer:
            return getattr(
                self.serializer_class.QuerySet, "read", ModelQuerySetSchema()
            )
        return ModelQuerySetSchema()

    def get_reverse_relations(self) -> list[str]:
        """
        Discover reverse relation names for safe prefetching.

        Returns
        -------
        list[str]
            Relation attribute names.
        """
        reverse_rels = self._get_read_optimizations().prefetch_related.copy()
        if reverse_rels:
            return reverse_rels
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
        select_rels = self._get_read_optimizations().select_related.copy()
        if select_rels:
            return select_rels
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

        is_serializer = isinstance(self.model, ModelSerializerMeta) or self.with_serializer
        serializer = self.serializer if self.with_serializer else self.model

        # Collect custom and optional fields (only if ModelSerializerMeta)
        customs: dict[str, Any] = {}
        optionals: list[str] = []
        if is_serializer:
            customs = {
                k: v
                for k, v in payload.items()
                if serializer.is_custom(k) and k not in self.model_fields
            }
            optionals = [
                k for k, v in payload.items() if serializer.is_optional(k) and v is None
            ]

        skip_keys = set()
        if is_serializer:
            # Keys to skip during model field processing
            skip_keys = {
                k
                for k, v in payload.items()
                if (serializer.is_custom(k) and k not in self.model_fields)
                or (serializer.is_optional(k) and v is None)
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
        pk = (
            (await self.model.objects.acreate(**payload)).pk
            if not self.with_serializer
            else (await self.serializer.create(payload)).pk
        )
        obj = await self.get_object(request, pk)
        if isinstance(self.model, ModelSerializerMeta):
            await asyncio.gather(obj.custom_actions(customs), obj.post_create())
        if self.with_serializer:
            await asyncio.gather(
                self.serializer.custom_actions(customs, obj),
                self.serializer.post_create(obj),
            )
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
        if self.with_serializer:
            await self.serializer.custom_actions(customs, obj)
            await self.serializer.save(obj)
        else:
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
