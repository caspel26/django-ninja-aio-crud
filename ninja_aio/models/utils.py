import asyncio
import base64
import logging
from collections import OrderedDict
from functools import cached_property
from typing import Any, Generic, Literal, TypeVar

from ninja import Schema
from ninja.orm import fields
from ninja.errors import ConfigError

from django.db import models
from django.db.models import Q, aprefetch_related_objects
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
from ninja_aio.types import ModelSerializerMeta, get_ninja_aio_meta_attr

from ninja_aio.schemas.helpers import (
    ModelQuerySetSchema,
    QuerySchema,
    ObjectQuerySchema,
    ObjectsQuerySchema,
)

# TypeVar for generic model typing
ModelT = TypeVar("ModelT", bound=models.Model)
logger = logging.getLogger("ninja_aio.models")


class LRUCache:
    """
    Thread-safe LRU cache backed by OrderedDict.

    Evicts least-recently-used entries when maxsize is exceeded.
    get() promotes entries to most-recent position.
    """

    __slots__ = ("_data", "_maxsize")

    def __init__(self, maxsize: int = 512):
        self._data: OrderedDict = OrderedDict()
        self._maxsize = maxsize

    def get(self, key):
        try:
            self._data.move_to_end(key)
            return self._data[key]
        except KeyError:
            return None

    def set(self, key, value):
        if key in self._data:
            self._data.move_to_end(key)
            self._data[key] = value
        else:
            self._data[key] = value
            if len(self._data) > self._maxsize:
                evicted = self._data.popitem(last=False)
                logger.debug(f"LRU cache evicted entry: {evicted[0]}")

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)

    def clear(self):
        self._data.clear()


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


class ModelUtil(Generic[ModelT]):
    """
    ModelUtil
    =========
    Generic async utility for Django models providing type-safe CRUD operations
    and (de)serialization for Django Ninja.

    Type Safety
    -----------
    ModelUtil is generic over the model type. Type inference works automatically:

    >>> util = ModelUtil(Book)  # Type automatically inferred as ModelUtil[Book]
    >>> book: Book = await util.get_object(request, pk=1)  # Returns Book
    >>> books: QuerySet[Book] = await util.get_objects(request)  # Returns QuerySet[Book]

    When used in ViewSets, specify the generic type parameter on the ViewSet:

    >>> class BookAPI(APIViewSet[Book]):
    ...     # self.model_util is typed as ModelUtil[Book]
    ...     async def my_method(self, request):
    ...         book: Book = await self.model_util.get_object(request, pk=1)

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
    - get_object() -> ModelT : Retrieve a single typed instance
    - get_objects() -> QuerySet[ModelT] : Retrieve a typed queryset
    - parse_input_data() : Transform inbound schema to model-ready payload
    - create_s / read_s / update_s / delete_s : High-level CRUD operations

    Error Handling
    --------------
    - Missing objects -> NotFoundError(...)
    - Bad base64 -> SerializeError({...}, 400)

    Performance Notes
    -----------------
    - Each FK resolution is an async DB hit; batch when necessary externally.
    - Relation discovery results are cached per (model, serializer_class, is_for) tuple.

    Design
    ------
    - Stateless wrapper; safe per-request instantiation.
    - Generic type parameter ensures all operations are properly typed.
    """

    # Performance: Bounded LRU cache for relation discovery (model structure is static)
    _relation_cache: LRUCache = LRUCache(maxsize=512)

    def __init__(self, model: type[ModelT], serializer_class=None):
        """
        Initialize with a Django model or ModelSerializer subclass.

        Parameters
        ----------
        model : type[ModelT]
            Target model class.
        serializer_class : type[Serializer] | None
            Optional serializer class for the model.
        """
        from ninja_aio.models.serializers import Serializer

        self.model: type[ModelT] = model
        self.serializer_class: type[Serializer[ModelT]] | None = serializer_class
        if serializer_class is not None and isinstance(model, ModelSerializerMeta):
            raise ConfigError(
                "ModelUtil cannot accept both model and serializer_class if the model is a ModelSerializer."
            )
        self.serializer: Serializer[ModelT] | None = (
            serializer_class() if serializer_class else None
        )
        model_name = getattr(model, "__name__", str(model))
        logger.debug(
            f"ModelUtil initialized for {model_name}"
            f" (serializer={serializer_class.__name__ if serializer_class else None})"
        )

    @property
    def with_serializer(self) -> bool:
        """
        Indicates if a serializer_class is associated.

        Returns
        -------
        bool
        """
        return self.serializer_class is not None

    @cached_property
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
        return self._get_serializable_field_names("read")

    @property
    def serializable_detail_fields(self):
        """
        List of fields considered serializable for detail operations.

        Returns
        -------
        list[str]
            Explicit detail fields if ModelSerializerMeta, otherwise all model fields.
        """
        return self._get_serializable_field_names("detail")

    @cached_property
    def model_fields(self):
        """
        Raw model field names (including forward relations).

        Returns
        -------
        list[str]
        """
        return [field.name for field in self.model._meta.get_fields()]

    @cached_property
    def model_name(self) -> str:
        """
        Django internal model name.

        Returns
        -------
        str
        """
        return self.model._meta.model_name

    @cached_property
    def model_pk_name(self) -> str:
        """
        Primary key attribute name (attname).

        Returns
        -------
        str
        """
        return self.model._meta.pk.attname

    @property
    def model_verbose_name(self) -> str:
        """
        Human readable singular verbose name.

        Returns
        -------
        str
        """
        return (
            get_ninja_aio_meta_attr(self.model, "verbose_name")
            or self.model._meta.verbose_name
        )

    @property
    def model_verbose_name_plural(self) -> str:
        """
        Human readable plural verbose name.

        Returns
        -------
        str
        """
        return (
            get_ninja_aio_meta_attr(self.model, "verbose_name_plural")
            or self.model._meta.verbose_name_plural
        )

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

    def _get_serializable_field_names(
        self, fields_type: Literal["read", "detail"]
    ) -> list[str]:
        """
        Get serializable field names for the model.

        Returns
        -------
        list[str]
            List of serializable field names.
        """
        if isinstance(self.model, ModelSerializerMeta):
            return self.model.get_fields(fields_type)
        if self.with_serializer:
            return self.serializer_class.get_fields(fields_type)
        return self.model_fields

    async def _get_base_queryset(
        self,
        request: HttpRequest,
        query_data: QuerySchema,
        with_qs_request: bool,
        is_for: Literal["read", "detail"] | None = None,
    ) -> models.QuerySet[ModelT]:
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
        is_for : Literal["read", "detail"] | None
            Purpose of the query, determines which serializable fields to use.
            If None, only query_data optimizations are applied.

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
        obj_qs = self._apply_query_optimizations(obj_qs, query_data, is_for)

        # Apply queryset_request hook if available
        if isinstance(self.model, ModelSerializerMeta) and with_qs_request:
            obj_qs = await self.model.queryset_request(request)

        # Apply filters if present (supports dict or Q object)
        if hasattr(query_data, "filters") and query_data.filters:
            if isinstance(query_data.filters, Q):
                obj_qs = obj_qs.filter(query_data.filters)
            else:
                obj_qs = obj_qs.filter(**query_data.filters)

        return obj_qs

    async def get_objects(
        self,
        request: HttpRequest,
        query_data: ObjectsQuerySchema = None,
        with_qs_request=True,
        is_for: Literal["read", "detail"] | None = None,
    ) -> models.QuerySet[ModelT]:
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
        is_for : Literal["read", "detail"] | None, optional
            Purpose of the query, determines which serializable fields to use.
            If None, only query_data optimizations are applied.

        Returns
        -------
        models.QuerySet[ModelT]
            A QuerySet of model instances.

        Notes
        -----
        - Query optimizations are automatically applied based on discovered relationships
        - The queryset_request hook is called if the model implements ModelSerializerMeta
        """
        if query_data is None:
            query_data = ObjectsQuerySchema()

        return await self._get_base_queryset(
            request, query_data, with_qs_request, is_for
        )

    async def get_object(
        self,
        request: HttpRequest,
        pk: int | str = None,
        query_data: ObjectQuerySchema = None,
        with_qs_request=True,
        is_for: Literal["read", "detail"] | None = None,
    ) -> ModelT:
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
        is_for : Literal["read", "detail"] | None, optional
            Purpose of the query, determines which serializable fields to use.
            If None, only query_data optimizations are applied.

        Returns
        -------
        ModelT
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

        logger.debug(f"Getting {self.model.__name__} (pk={pk})")

        # Build lookup query and get optimized queryset
        obj_qs = await self._get_base_queryset(
            request, query_data, with_qs_request, is_for
        )

        # Apply getters (supports dict or Q object)
        if isinstance(query_data.getters, Q):
            obj_qs = obj_qs.filter(query_data.getters)
            if pk is not None:
                obj_qs = obj_qs.filter(**{self.model_pk_name: pk})
            try:
                obj = await obj_qs.aget()
            except ObjectDoesNotExist:
                logger.debug(f"{self.model.__name__} not found (pk={pk})")
                raise NotFoundError(self.model)
        else:
            get_q = self._build_lookup_query(pk, query_data.getters)
            try:
                obj = await obj_qs.aget(**get_q)
            except ObjectDoesNotExist:
                logger.debug(f"{self.model.__name__} not found (pk={pk})")
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
        is_for: Literal["read", "detail"] | None = None,
    ) -> models.QuerySet:
        """
        Apply select_related and prefetch_related optimizations to queryset.

        Parameters
        ----------
        queryset : QuerySet
            Base queryset to optimize.
        query_data : ModelQuerySchema
            Query configuration with select_related/prefetch_related lists.
        is_for : Literal["read", "detail"] | None
            Purpose of the query, determines which serializable fields to use.
            If None, only query_data optimizations are applied.

        Returns
        -------
        QuerySet
            Optimized queryset.
        """
        select_related = (
            query_data.select_related + self.get_select_relateds(is_for)
            if is_for
            else query_data.select_related
        )
        prefetch_related = (
            query_data.prefetch_related + self.get_reverse_relations(is_for)
            if is_for
            else query_data.prefetch_related
        )

        if select_related:
            queryset = queryset.select_related(*select_related)
        if prefetch_related:
            queryset = queryset.prefetch_related(*prefetch_related)

        if select_related or prefetch_related:
            logger.debug(
                f"Query optimizations for {self.model.__name__}:"
                f" select_related={select_related}, prefetch_related={prefetch_related}"
            )

        return queryset

    def _get_read_optimizations(
        self, is_for: Literal["read", "detail"] = "read"
    ) -> ModelQuerySetSchema:
        """
        Retrieve read optimizations from model or serializer class.

        When is_for="detail" and no detail config exists, falls back to read config.

        Returns
        -------
        ModelQuerySetSchema
            Read optimization configuration.
        """
        if isinstance(self.model, ModelSerializerMeta):
            result = getattr(self.model.QuerySet, is_for, None)
            if result is None and is_for == "detail":
                result = getattr(self.model.QuerySet, "read", None)
            return result or ModelQuerySetSchema()
        if self.with_serializer:
            result = getattr(self.serializer_class.QuerySet, is_for, None)
            if result is None and is_for == "detail":
                result = getattr(self.serializer_class.QuerySet, "read", None)
            return result or ModelQuerySetSchema()
        return ModelQuerySetSchema()

    def get_reverse_relations(
        self, is_for: Literal["read", "detail"] = "read"
    ) -> list[str]:
        """
        Discover reverse relation names for safe prefetching.

        Performance: Results are cached per (model, serializer_class, is_for) tuple
        since model structure is static.

        Parameters
        ----------
        is_for : Literal["read", "detail"]
            Purpose of the query, determines which serializable fields to use.

        Returns
        -------
        list[str]
            Relation attribute names.
        """
        # Check cache first (performance optimization)
        cache_key = (id(self.model), id(self.serializer_class), is_for)
        cached = self._relation_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Reverse relations cache hit for {self.model.__name__} (is_for={is_for})")
            return cached

        config_rels = self._get_read_optimizations(is_for).prefetch_related
        if config_rels:
            self._relation_cache.set(cache_key, config_rels)
            logger.debug(f"Reverse relations from config for {self.model.__name__}: {config_rels}")
            return config_rels

        reverse_rels = []
        serializable_fields = self._get_serializable_field_names(is_for)
        for f in serializable_fields:
            field_obj = getattr(self.model, f)
            if isinstance(field_obj, ManyToManyDescriptor):
                reverse_rels.append(f)
                continue
            if isinstance(field_obj, ReverseManyToOneDescriptor):
                reverse_rels.append(field_obj.field._related_name)
                continue
            if isinstance(field_obj, ReverseOneToOneDescriptor):
                reverse_rels.append(field_obj.related.name)

        # Cache the result
        self._relation_cache.set(cache_key, reverse_rels)
        logger.debug(f"Reverse relations discovered for {self.model.__name__}: {reverse_rels}")
        return reverse_rels

    def get_select_relateds(
        self, is_for: Literal["read", "detail"] = "read"
    ) -> list[str]:
        """
        Discover forward relation names for safe select_related.

        Performance: Results are cached per (model, serializer_class, is_for) tuple
        since model structure is static.

        Parameters
        ----------
        is_for : Literal["read", "detail"]
            Purpose of the query, determines which serializable fields to use.

        Returns
        -------
        list[str]
            Relation attribute names.
        """
        # Check cache first (performance optimization)
        cache_key = (id(self.model), id(self.serializer_class), "select", is_for)
        cached = self._relation_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Select related cache hit for {self.model.__name__} (is_for={is_for})")
            return cached

        config_rels = self._get_read_optimizations(is_for).select_related
        if config_rels:
            self._relation_cache.set(cache_key, config_rels)
            logger.debug(f"Select related from config for {self.model.__name__}: {config_rels}")
            return config_rels

        select_rels = []
        serializable_fields = self._get_serializable_field_names(is_for)
        for f in serializable_fields:
            field_obj = getattr(self.model, f)
            if isinstance(field_obj, ForwardOneToOneDescriptor):
                select_rels.append(f)
                continue
            if isinstance(field_obj, ForwardManyToOneDescriptor):
                select_rels.append(f)

        # Cache the result
        self._relation_cache.set(cache_key, select_rels)
        logger.debug(f"Select related discovered for {self.model.__name__}: {select_rels}")
        return select_rels

    def _resolve_field_objects(self, field_names: list[str]) -> list[models.Field]:
        """Resolve Django field objects for a list of field names (sync)."""
        return [getattr(self.model, k).field for k in field_names]

    def _serialize_queryset_sync(self, queryset, schema: Schema) -> list[dict]:
        """Serialize a queryset to a list of dicts using Pydantic schema (sync)."""
        return [schema.from_orm(obj).model_dump() for obj in queryset]

    def _decode_binary(
        self, payload: dict, k: str, v: Any, field_obj: models.Field
    ) -> None:
        """Decode base64-encoded binary field values in place."""
        if not isinstance(field_obj, models.BinaryField):
            return
        try:
            payload[k] = base64.b64decode(v)
            logger.debug(f"Decoded binary field '{k}' for {self.model.__name__}")
        except Exception as exc:
            logger.warning(f"Failed to decode binary field '{k}' for {self.model.__name__}: {exc}")
            raise SerializeError({k: ". ".join(exc.args)}, 400)

    async def _bump_object_from_schema(self, obj: ModelT, schema: Schema) -> dict:
        """Convert model instance to dict using Pydantic schema."""
        return (await sync_to_async(schema.from_orm)(obj)).model_dump()

    async def _bump_queryset_from_schema(
        self, queryset: models.QuerySet[ModelT], schema: Schema
    ) -> list[dict]:
        """Convert a queryset to a list of dicts using Pydantic schema in a single sync_to_async call."""

        return await sync_to_async(self._serialize_queryset_sync)(queryset, schema)

    async def _prefetch_reverse_relations_on_instance(
        self,
        obj: ModelT,
        is_for: Literal["read", "detail"] = "read",
    ) -> ModelT:
        """
        Prefetch reverse relations on an existing instance.

        This is used to load reverse relations (reverse FK, reverse O2O, M2M)
        on an instance that already has forward FKs loaded.

        Uses ``aprefetch_related_objects`` to apply prefetch directly on the
        instance without refetching it from the database, preserving any
        forward FK data already in memory.

        Parameters
        ----------
        obj : ModelT
            Instance to prefetch relations on.
        is_for : Literal["read", "detail"]
            Purpose of the query, determines which relations to prefetch.

        Returns
        -------
        ModelT
            The same instance with reverse relations prefetched.
        """
        reverse_rels = self.get_reverse_relations(is_for)
        if not reverse_rels:
            return obj

        await aprefetch_related_objects([obj], *reverse_rels)
        return obj

    def _validate_read_params(
        self, request: HttpRequest, query_data: QuerySchema
    ) -> None:
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
        is_for: Literal["read", "detail"] | None = None,
    ):
        """Handle different query modes (filters vs getters)."""
        if hasattr(query_data, "filters") and query_data.filters:
            return await self._serialize_queryset(request, query_data, schema, is_for)

        if hasattr(query_data, "getters") and query_data.getters:
            return await self._serialize_single_object(
                request, query_data, schema, is_for
            )

        raise SerializeError(
            {"query_data": "must contain either filters or getters"}, 400
        )

    async def _serialize_queryset(
        self,
        request: HttpRequest,
        query_data: QuerySchema,
        schema: Schema,
        is_for: Literal["read", "detail"] | None = None,
    ):
        """Serialize a queryset of objects."""
        objs = await self.get_objects(request, query_data=query_data, is_for=is_for)
        return await self._bump_queryset_from_schema(objs, schema)

    async def _serialize_single_object(
        self,
        request: HttpRequest,
        query_data: QuerySchema,
        obj_schema: Schema,
        is_for: Literal["read", "detail"] | None = None,
    ):
        """Serialize a single object."""
        obj = await self.get_object(request, query_data=query_data, is_for=is_for)
        return await self._bump_object_from_schema(obj, obj_schema)

    def _collect_custom_and_optional_fields(
        self, payload: dict, is_serializer: bool, serializer
    ) -> tuple[dict[str, Any], list[str]]:
        """
        Collect custom and optional fields from payload.

        Parameters
        ----------
        payload : dict
            Input payload.
        is_serializer : bool
            Whether using a ModelSerializer.
        serializer : ModelSerializer | Serializer
            Serializer instance if applicable.

        Returns
        -------
        tuple[dict[str, Any], list[str]]
            (custom_fields_dict, optional_field_names)
        """
        customs: dict[str, Any] = {}
        optionals: list[str] = []

        if not is_serializer:
            return customs, optionals

        customs = {
            k: v
            for k, v in payload.items()
            if serializer.is_custom(k) and k not in self.model_fields
        }
        optionals = [
            k for k, v in payload.items() if serializer.is_optional(k) and v is None
        ]

        return customs, optionals

    def _determine_skip_keys(
        self, payload: dict, is_serializer: bool, serializer
    ) -> set[str]:
        """
        Determine which keys to skip during model field processing.

        Parameters
        ----------
        payload : dict
            Input payload.
        is_serializer : bool
            Whether using a ModelSerializer.
        serializer : ModelSerializer | Serializer
            Serializer instance if applicable.

        Returns
        -------
        set[str]
            Set of keys to skip.
        """
        if not is_serializer:
            return set()

        skip_keys = {
            k
            for k, v in payload.items()
            if (serializer.is_custom(k) and k not in self.model_fields)
            or (serializer.is_optional(k) and v is None)
        }
        return skip_keys

    async def _resolve_fk(
        self,
        payload: dict,
        k: str,
        v: Any,
        field_obj: models.ForeignKey,
    ) -> None:
        """Resolve foreign key ID to model instance in place."""
        rel_model = field_obj.related_model
        logger.debug(f"Resolving FK '{k}' -> {rel_model.__name__} (pk={v}) for {self.model.__name__}")
        try:
            payload[k] = await rel_model.objects.aget(pk=v)
        except rel_model.DoesNotExist:
            raise NotFoundError(rel_model)

    async def _process_payload_fields(
        self,
        request: HttpRequest,
        payload: dict,
        fields_to_process: list[tuple[str, Any]],
    ) -> None:
        """
        Process payload fields: decode binary and resolve foreign keys.

        Binary fields are decoded in-place. FK fields are resolved in
        parallel via asyncio.gather.

        Parameters
        ----------
        request : HttpRequest
            HTTP request object.
        payload : dict
            Payload dict to modify in place.
        fields_to_process : list[tuple[str, Any]]
            List of (field_name, field_value) tuples to process.
        """
        if not fields_to_process:
            return

        field_names = [k for k, _ in fields_to_process]
        field_objs = await sync_to_async(self._resolve_field_objects)(field_names)

        # Single pass: decode binary + collect FK tasks
        fk_tasks = []
        for (k, v), field_obj in zip(fields_to_process, field_objs):
            self._decode_binary(payload, k, v, field_obj)
            if isinstance(field_obj, models.ForeignKey) and v is not None:
                fk_tasks.append(self._resolve_fk(payload, k, v, field_obj))

        if fk_tasks:
            await asyncio.gather(*fk_tasks)

    async def parse_input_data(self, request: HttpRequest, data: Schema):
        """
        Transform inbound schema data to a model-ready payload.

        Steps
        -----
        - Validate fields against schema (including aliases and custom fields).
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
            On base64 decoding failure or invalid field names.
        """
        payload = data.model_dump(mode="json")

        is_serializer = (
            isinstance(self.model, ModelSerializerMeta) or self.with_serializer
        )
        serializer = self.serializer if self.with_serializer else self.model

        # Note: Field validation is handled by Pydantic during schema deserialization
        # No additional validation needed here since data is already a validated Schema instance

        # Collect custom and optional fields
        customs, optionals = self._collect_custom_and_optional_fields(
            payload, is_serializer, serializer
        )

        # Determine which keys to skip during model field processing
        skip_keys = self._determine_skip_keys(payload, is_serializer, serializer)

        # Process payload fields - gather field objects in parallel for better performance
        fields_to_process = [(k, v) for k, v in payload.items() if k not in skip_keys]
        await self._process_payload_fields(request, payload, fields_to_process)

        # Preserve original exclusion semantics (customs if present else optionals)
        exclude_keys = customs.keys() or optionals
        new_payload = {k: v for k, v in payload.items() if k not in exclude_keys}

        return new_payload, customs

    async def _create_instance(self, request: HttpRequest, data: Schema):
        """
        Create a new instance and run hooks.

        Handles input parsing, object creation, and custom_actions/post_create
        hooks. Does not serialize the output.

        Parameters
        ----------
        request : HttpRequest
        data : Schema
            Input schema instance.

        Returns
        -------
        ModelT
            The created model instance.
        """
        from ninja_aio.models.hooks import (
            suppress_signals, get_hooks, execute_reactive_hooks,
        )

        logger.info(f"Creating {self.model.__name__}")
        payload, customs = await self.parse_input_data(request, data)
        async with suppress_signals():
            obj = (
                await self.model.objects.acreate(**payload)
                if not self.with_serializer
                else await self.serializer.create(payload)
            )
        logger.debug(f"Created {self.model.__name__} (pk={obj.pk})")
        if isinstance(self.model, ModelSerializerMeta):
            await asyncio.gather(obj.custom_actions(customs), obj.post_create())
            hooks = get_hooks(self.model)
            if hooks and hooks["create"]:
                await execute_reactive_hooks(obj, hooks["create"])
        if self.with_serializer:
            await asyncio.gather(
                self.serializer.custom_actions(customs, obj),
                self.serializer.post_create(obj),
            )
        return obj

    async def create_s(self, request: HttpRequest, data: Schema, obj_schema: Schema):
        """
        Create a new instance and return serialized output.

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
        obj = await self._create_instance(request, data)
        # Only prefetch reverse relations (forward FKs already loaded)
        obj = await self._prefetch_reverse_relations_on_instance(obj, is_for="read")
        return await self.read_s(obj_schema, request, obj)

    async def _read_s(
        self,
        schema: Schema,
        request: HttpRequest = None,
        instance: models.QuerySet[ModelT] | ModelT | None = None,
        query_data: QuerySchema = None,
        is_for: Literal["read", "detail"] | None = None,
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
        is_for : Literal["read", "detail"] | None, optional
            Purpose of the query, determines which serializable fields to use.

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
            if isinstance(instance, (models.QuerySet, list)):
                return await self._bump_queryset_from_schema(instance, schema)
            return await self._bump_object_from_schema(instance, schema)

        self._validate_read_params(request, query_data)
        return await self._handle_query_mode(request, query_data, schema, is_for)

    async def read_s(
        self,
        schema: Schema,
        request: HttpRequest = None,
        instance: ModelT | None = None,
        query_data: ObjectQuerySchema = None,
        is_for: Literal["read", "detail"] | None = None,
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
        instance : ModelT | None, optional
            Single instance to serialize. If None, fetched based on query_data.
        query_data : ObjectQuerySchema, optional
            Query parameters with getters for single object lookup.
            Required when instance is None.
        is_for : Literal["read", "detail"] | None, optional
            Purpose of the query, determines which serializable fields to use.
            Defaults to None.

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
        - Query optimizations applied when is_for is specified
        """
        return await self._read_s(
            schema,
            request,
            instance,
            query_data,
            is_for,
        )

    async def list_read_s(
        self,
        schema: Schema,
        request: HttpRequest = None,
        instances: models.QuerySet[ModelT] | None = None,
        query_data: ObjectsQuerySchema = None,
        is_for: Literal["read", "detail"] | None = None,
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
        is_for : Literal["read", "detail"] | None, optional
            Purpose of the query, determines which serializable fields to use.
            Defaults to None.

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
        - Query optimizations applied when is_for is specified
        - Processes queryset asynchronously for efficiency
        """
        return await self._read_s(
            schema,
            request,
            instances,
            query_data,
            is_for,
        )

    async def _update_instance(
        self,
        request: HttpRequest,
        data: Schema,
        pk: int | str,
        require_fields: bool = False,
    ):
        """
        Update an existing instance and run hooks.

        Handles input parsing, field assignment, custom_actions hooks, and
        saving. Does not serialize the output.

        Parameters
        ----------
        request : HttpRequest
        data : Schema
            Input update schema instance.
        pk : int | str
            Primary key of target object.
        require_fields : bool
            When True, raises SerializeError if no fields are provided.

        Returns
        -------
        ModelT
            The updated model instance.
        """
        from ninja_aio.models.hooks import (
            suppress_signals, get_hooks, detect_changed_fields, fire_update_hooks,
        )

        logger.info(f"Updating {self.model.__name__} (pk={pk})")
        obj = await self.get_object(request, pk, is_for="read")
        payload, customs = await self.parse_input_data(request, data)
        if require_fields and not payload and not customs:
            raise SerializeError("No fields provided for update.")

        hooks = get_hooks(self.model)
        changed_fields = (
            detect_changed_fields(obj, payload, hooks.get("update_field", {}))
            if hooks
            else set()
        )

        for k, v in payload.items():
            if v is not None:
                setattr(obj, k, v)

        async with suppress_signals():
            if isinstance(self.model, ModelSerializerMeta):
                await obj.custom_actions(customs)
            if self.with_serializer:
                await self.serializer.custom_actions(customs, obj)
                await self.serializer.save(obj)
            else:
                await obj.asave()

        if isinstance(self.model, ModelSerializerMeta) and hooks:
            await fire_update_hooks(obj, changed_fields, hooks)

        logger.debug(f"Updated {self.model.__name__} (pk={pk})")
        return obj

    async def update_s(
        self,
        request: HttpRequest,
        data: Schema,
        pk: int | str,
        obj_schema: Schema,
        require_fields: bool = False,
    ):
        """
        Update an existing instance and return serialized output.

        Parameters
        ----------
        request : HttpRequest
        data : Schema
            Input update schema instance.
        pk : int | str
            Primary key of target object.
        obj_schema : Schema
            Read schema class for output.
        require_fields : bool
            When True, raises SerializeError if no fields are provided.

        Returns
        -------
        dict
            Serialized updated object.
        """
        obj = await self._update_instance(request, data, pk, require_fields)
        # FK instances from parse_input_data are already attached to obj
        # Only refresh reverse relations since they might have changed
        updated_object = await self._prefetch_reverse_relations_on_instance(
            obj, is_for="read"
        )
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
        from ninja_aio.models.hooks import (
            suppress_signals, get_hooks, execute_reactive_hooks,
        )

        logger.info(f"Deleting {self.model.__name__} (pk={pk})")
        obj = await self.get_object(request, pk)
        async with suppress_signals():
            await obj.adelete()
        logger.debug(f"Deleted {self.model.__name__} (pk={pk})")

        hooks = get_hooks(self.model)
        if hooks and hooks["delete"]:
            await execute_reactive_hooks(obj, hooks["delete"])
        if self.with_serializer:
            ser_hooks = get_hooks(self.serializer_class)
            if ser_hooks and ser_hooks["delete"]:
                await execute_reactive_hooks(self.serializer, ser_hooks["delete"], obj)

        return None

    @staticmethod
    def _format_bulk_error(exc: Exception) -> dict[str, str]:
        """
        Extract error detail from an exception for bulk result reporting.

        Parameters
        ----------
        exc : Exception
            The caught exception.

        Returns
        -------
        dict[str, str]
            Error detail dict.
        """
        if hasattr(exc, "error"):
            return exc.error
        return {"error": str(exc)}

    async def bulk_create_s(
        self,
        request: HttpRequest,
        data_list: list[Schema],
        detail_extractor: callable = None,
    ):
        """
        Create multiple instances with partial success semantics.

        Each item is processed independently. Failures are collected without
        affecting other items.

        Parameters
        ----------
        request : HttpRequest
        data_list : list[Schema]
            List of input schema instances.
        detail_extractor : callable, optional
            Function that extracts detail info from a model instance.
            Defaults to returning the PK.

        Returns
        -------
        tuple[list, list[dict]]
            (success_details, error_details)
        """
        logger.info(f"Bulk creating {len(data_list)} {self.model.__name__} instances")
        extractor = detail_extractor or (lambda obj: obj.pk)
        success_details = []
        error_details = []

        for data in data_list:
            try:
                obj = await self._create_instance(request, data)
                success_details.append(extractor(obj))
            except (SerializeError, NotFoundError) as e:
                error_details.append(self._format_bulk_error(e))
            except Exception as e:
                error_details.append(self._format_bulk_error(e))

        logger.debug(
            f"Bulk create {self.model.__name__}: "
            f"{len(success_details)} success, {len(error_details)} errors"
        )
        return success_details, error_details

    async def bulk_update_s(
        self,
        request: HttpRequest,
        data_list: list[tuple[int | str, Schema]],
        detail_extractor: callable = None,
        require_fields: bool = False,
    ):
        """
        Update multiple instances with partial success semantics.

        Each item is processed independently. Failures are collected without
        affecting other items.

        Parameters
        ----------
        request : HttpRequest
        data_list : list[tuple[int | str, Schema]]
            List of (pk, update_schema_instance) tuples.
        detail_extractor : callable, optional
            Function that extracts detail info from a model instance.
            Defaults to returning the PK.
        require_fields : bool
            When True, raises SerializeError if no fields are provided.

        Returns
        -------
        tuple[list, list[dict]]
            (success_details, error_details)
        """
        logger.info(f"Bulk updating {len(data_list)} {self.model.__name__} instances")
        extractor = detail_extractor or (lambda obj: obj.pk)
        success_details = []
        error_details = []

        for pk, data in data_list:
            try:
                obj = await self._update_instance(
                    request, data, pk, require_fields
                )
                success_details.append(extractor(obj))
            except (SerializeError, NotFoundError) as e:
                error_details.append(self._format_bulk_error(e))
            except Exception as e:
                error_details.append(self._format_bulk_error(e))

        logger.debug(
            f"Bulk update {self.model.__name__}: "
            f"{len(success_details)} success, {len(error_details)} errors"
        )
        return success_details, error_details

    async def _resolve_existing_pks(
        self,
        matched_qs: models.QuerySet,
        detail_fields: list[str] | None,
    ) -> tuple[set, dict]:
        """
        Identify which PKs exist and optionally collect detail field values.

        Returns
        -------
        tuple[set, dict]
            (existing_pks, detail_map). detail_map is empty when detail_fields
            is None.
        """
        if not detail_fields:
            existing_pks: set = set()
            async for pk_val in matched_qs.values_list(
                self.model_pk_name, flat=True
            ):
                existing_pks.add(pk_val)
            return existing_pks, {}

        fields_with_pk = list(
            dict.fromkeys([self.model_pk_name] + detail_fields)
        )
        detail_map: dict = {}
        single_field = len(detail_fields) == 1
        async for row in matched_qs.values(*fields_with_pk):
            pk_val = row[self.model_pk_name]
            detail_map[pk_val] = (
                row[detail_fields[0]]
                if single_field
                else {f: row[f] for f in detail_fields}
            )
        return set(detail_map.keys()), detail_map

    def _build_success_details(
        self,
        pks: list[int | str],
        existing_pks: set,
        detail_map: dict,
    ) -> list:
        """Build ordered success details from existing PKs."""
        if detail_map:
            return [detail_map[pk] for pk in pks if pk in existing_pks]
        return [pk for pk in pks if pk in existing_pks]

    async def bulk_delete_s(
        self,
        request: HttpRequest,
        pks: list[int | str],
        detail_fields: list[str] | None = None,
    ) -> tuple[list, list[dict]]:
        """
        Delete multiple instances with partial success and optimized queries.

        Uses a single query to identify existing PKs and a single query to delete them.
        Missing PKs are reported as errors.

        Parameters
        ----------
        request : HttpRequest
        pks : list[int | str]
            List of primary keys.
        detail_fields : list[str], optional
            Field names to include in success details. When provided, queries
            field values before deletion. Defaults to returning PKs only.

        Returns
        -------
        tuple[list, list[dict]]
            (success_details, error_details)
        """
        logger.info(f"Bulk deleting {len(pks)} {self.model.__name__} instances")
        if not pks:
            return [], []

        qs = await self.get_objects(request, is_for="read")
        matched_qs = qs.filter(**{f"{self.model_pk_name}__in": pks})

        existing_pks, detail_map = await self._resolve_existing_pks(
            matched_qs, detail_fields
        )

        error_details = [
            NotFoundError(self.model).error
            for pk in pks
            if pk not in existing_pks
        ]

        success_details: list = []
        if existing_pks:
            await qs.filter(
                **{f"{self.model_pk_name}__in": existing_pks}
            ).adelete()
            success_details = self._build_success_details(
                pks, existing_pks, detail_map
            )

        logger.debug(
            f"Bulk delete {self.model.__name__}: "
            f"{len(success_details)} deleted, {len(error_details)} errors"
        )
        return success_details, error_details
