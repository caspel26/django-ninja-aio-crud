import asyncio
import logging
import warnings
from collections import OrderedDict
from contextlib import nullcontext
from functools import cached_property
from typing import Any, Callable, Generic, Iterable, Literal, TypeVar

from ninja import Schema
from ninja.orm import fields
from ninja.errors import ConfigError
from pydantic import ValidationError

from django.db import models, router, transaction
from django.db.models import Q, aprefetch_related_objects
from django.http import HttpRequest
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from asgiref.sync import sync_to_async
from ninja_aio.exceptions import (
    BaseException as OperationError,
    NotFoundError,
    OperationValidationError,
    SerializeError,
)
from ninja_aio.decorators.views import AsyncAtomicContextManager
from ninja_aio.models.hooks import resolve_async_hook, resolve_sync_hook
from ninja_aio.types import (
    BulkFailure,
    BulkResult,
    ModelSerializerMeta,
    PrimaryKey,
    QueryPurpose,
    get_ninja_aio_meta_attr,
)

from ninja_aio.schemas.helpers import (
    ModelQuerySetSchema,
    QuerySchema,
    ObjectQuerySchema,
    ObjectsQuerySchema,
)
from ninja_aio.models import transformations as model_transformations

# TypeVar for generic model typing
ModelT = TypeVar("ModelT", bound=models.Model)
logger = logging.getLogger("ninja_aio.models")


# Registry mapping a Django model class to the Serializer/ModelSerializer subclass
# that scopes its querysets via `queryset_request`. Populated by
# `ModelSerializer.__init_subclass__` and `Serializer.__init_subclass__`.
#
# Used by `ModelUtil._resolve_fk` so that foreign keys pointing at vanilla
# Django models are still tenant-scoped when a serializer has been defined for
# the target model. When no serializer is registered for a model, FK lookups
# fall back to the unscoped manager (single-tenant default).
#
# Policy on duplicates: last registration wins. Multiple serializers can
# target the same model (e.g. different read shapes); their `queryset_request`
# is typically identical (tenant scope, not view). Users who need a specific
# serializer to win can control it via import order; an explicit opt-in flag
# can be layered on later without breaking this default.
_SERIALIZER_REGISTRY: dict[type[models.Model], type] = {}


def register_serializer_for_model(
    model: type[models.Model], serializer_cls: type
) -> None:
    """Register *serializer_cls* as the FK-resolution scope for *model*.

    Called automatically by `ModelSerializer` and `Serializer` subclasses.
    Last registration wins; an existing entry is overwritten and logged at
    DEBUG level so collisions are diagnosable without being fatal.
    """
    existing = _SERIALIZER_REGISTRY.get(model)
    if existing is not None and existing is not serializer_cls:
        logger.debug(
            f"FK-resolution serializer for {model.__name__} overridden:"
            f" {existing.__name__} -> {serializer_cls.__name__}"
        )
    _SERIALIZER_REGISTRY[model] = serializer_cls


def get_serializer_for_model(model: type[models.Model]) -> type | None:
    """Return the registered serializer for *model*, or None."""
    return _SERIALIZER_REGISTRY.get(model)


def _warn_deprecated(old: str, replacement: str) -> None:
    warnings.warn(
        f"ModelUtil.{old}() is deprecated; use {replacement} instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def bulk_failure(
    index: int, exc: Exception, pk: PrimaryKey | None = None
) -> BulkFailure:
    """Describe one failed bulk item, keeping the legacy HTTP error payload."""
    error = exc.error if hasattr(exc, "error") else {"error": str(exc)}
    if isinstance(exc, OperationError):
        return BulkFailure(index, exc.code, exc.message, exc.field_errors, pk, error)
    if isinstance(exc, ValidationError):
        return BulkFailure(
            index,
            "validation_error",
            str(exc),
            OperationValidationError(exc).field_errors,
            pk,
            error,
        )
    if isinstance(exc, ValueError):
        code = "invalid_value"
    elif isinstance(exc, TypeError):
        code = "invalid_type"
    else:
        code = "operation_error"
    return BulkFailure(index, code, str(exc), pk=pk, error=error)


def _no_prepare(item: Any) -> tuple[None, Any]:
    return None, item


def run_bulk(
    model: type[models.Model],
    items: Iterable[Any],
    operation: Callable[[Any], Any],
    prepare: Callable[[Any], tuple[PrimaryKey | None, Any]] = _no_prepare,
    atomic: bool = True,
) -> BulkResult:
    """Run *operation* per item in its own transaction, collecting partial results."""
    result = BulkResult()
    using = router.db_for_write(model)
    for index, item in enumerate(items):
        pk = None
        try:
            pk, payload = prepare(item)
            with transaction.atomic(using=using) if atomic else nullcontext():
                result.succeeded.append(operation(payload))
        except Exception as exc:
            result.failed.append(bulk_failure(index, exc, pk))
    return result


async def arun_bulk(
    model: type[models.Model],
    items: Iterable[Any],
    operation: Callable[[Any], Any],
    prepare: Callable[[Any], tuple[PrimaryKey | None, Any]] = _no_prepare,
    atomic: bool = True,
) -> BulkResult:
    """Async counterpart of run_bulk; *operation* returns an awaitable."""
    result = BulkResult()
    using = router.db_for_write(model)
    for index, item in enumerate(items):
        pk = None
        try:
            pk, payload = prepare(item)
            async with AsyncAtomicContextManager(using=using) if atomic else nullcontext():
                result.succeeded.append(await operation(payload))
        except Exception as exc:
            result.failed.append(bulk_failure(index, exc, pk))
    return result


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
    - aparse_input_data() : Transform inbound schema to model-ready payload
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
        request: HttpRequest | None,
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
            else await resolve_async_hook(self.serializer_class, "queryset_request")(request)
        )

        # Apply queryset_request hook if available. This may return an entirely
        # different queryset (e.g. request-scoped filtering), so it must run
        # before the read/detail-scoped optimizations below, or those would be
        # silently discarded.
        if isinstance(self.model, ModelSerializerMeta) and with_qs_request:
            obj_qs = await resolve_async_hook(self.model, "queryset_request")(request)

        return self._finalize_queryset(obj_qs, query_data, is_for)

    def _finalize_queryset(
        self,
        queryset: models.QuerySet[ModelT],
        query_data: QuerySchema,
        is_for: Literal["read", "detail"] | None,
    ) -> models.QuerySet[ModelT]:
        """Apply execution-mode-independent optimizations and filters."""
        queryset = self._apply_query_optimizations(queryset, query_data, is_for)
        filters = getattr(query_data, "filters", None)
        if isinstance(filters, Q):
            return queryset.filter(filters)
        if filters:
            return queryset.filter(**filters)
        return queryset

    def _apply_object_lookup(
        self,
        queryset: models.QuerySet[ModelT],
        pk: PrimaryKey | None,
        getters: dict[str, Any] | Q,
    ) -> tuple[models.QuerySet[ModelT], dict[str, Any]]:
        """Apply a Q lookup or build keyword lookup criteria for one object."""
        if isinstance(getters, Q):
            queryset = queryset.filter(getters)
            if pk is not None:
                queryset = queryset.filter(**{self.model_pk_name: pk})
            return queryset, {}
        return queryset, self._build_lookup_query(pk, getters)

    async def aget_objects(
        self,
        request: HttpRequest | None,
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

    def get_objects(
        self,
        request: HttpRequest | None,
        query_data: ObjectsQuerySchema | None = None,
        with_qs_request: bool = True,
        is_for: Literal["read", "detail"] | None = None,
    ) -> models.QuerySet[ModelT]:
        """Retrieve an optimized queryset using only synchronous ORM operations."""
        query_data = query_data or ObjectsQuerySchema()
        queryset = self.model._default_manager.all()
        if with_qs_request:
            if self.serializer_class is not None:
                queryset = resolve_sync_hook(self.serializer_class, "queryset_request")(request)
            elif isinstance(self.model, ModelSerializerMeta):
                queryset = resolve_sync_hook(self.model, "queryset_request")(request)
        return self._finalize_queryset(queryset, query_data, is_for)

    async def aget_object(
        self,
        request: HttpRequest | None,
        pk: PrimaryKey | None = None,
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

        obj_qs, lookup = self._apply_object_lookup(obj_qs, pk, query_data.getters)
        try:
            return await obj_qs.aget(**lookup)
        except ObjectDoesNotExist:
            logger.debug(f"{self.model.__name__} not found (pk={pk})")
            raise NotFoundError(self.model)

    def get_object(
        self,
        request: HttpRequest | None,
        pk: PrimaryKey | None = None,
        query_data: ObjectQuerySchema | None = None,
        with_qs_request: bool = True,
        is_for: Literal["read", "detail"] | None = None,
    ) -> ModelT:
        """Retrieve one object using only synchronous ORM operations."""
        query_data = query_data or ObjectQuerySchema()
        if not query_data.getters and pk is None:
            raise ValueError(
                "Either pk or getters must be provided for single object retrieval."
            )
        queryset = self.get_objects(
            request,
            query_data=query_data,
            with_qs_request=with_qs_request,
            is_for=is_for,
        )
        queryset, lookup = self._apply_object_lookup(queryset, pk, query_data.getters)
        try:
            return queryset.get(**lookup)
        except ObjectDoesNotExist as exc:
            raise NotFoundError(self.model) from exc

    def _build_lookup_query(
        self,
        pk: PrimaryKey | None = None,
        getters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
        return model_transformations.build_lookup_query(self.model_pk_name, pk, getters)

    def _apply_query_optimizations(
        self,
        queryset: models.QuerySet[ModelT],
        query_data: QuerySchema,
        is_for: Literal["read", "detail"] | None = None,
    ) -> models.QuerySet[ModelT]:
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
        explicit_plan = model_transformations.RelationPlan(
            tuple(query_data.select_related), tuple(query_data.prefetch_related)
        )
        discovered_plan = (
            model_transformations.RelationPlan(
                tuple(self.get_select_relateds(is_for)),
                tuple(self.get_reverse_relations(is_for)),
            )
            if is_for
            else None
        )
        plan = model_transformations.combine_relation_plans(
            explicit_plan, discovered_plan
        )
        queryset = model_transformations.apply_relation_plan(queryset, plan)

        if plan.select_related or plan.prefetch_related:
            logger.debug(
                f"Query optimizations for {self.model.__name__}:"
                f" select_related={list(plan.select_related)},"
                f" prefetch_related={list(plan.prefetch_related)}"
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
            logger.debug(
                f"Reverse relations cache hit for {self.model.__name__} (is_for={is_for})"
            )
            return cached

        config_rels = self._get_read_optimizations(is_for).prefetch_related
        if config_rels:
            self._relation_cache.set(cache_key, config_rels)
            logger.debug(
                f"Reverse relations from config for {self.model.__name__}: {config_rels}"
            )
            return config_rels

        relation_plan = model_transformations.discover_relation_plan(
            self.model, self._get_serializable_field_names(is_for)
        )
        reverse_rels = list(relation_plan.prefetch_related)

        # Cache the result
        self._relation_cache.set(cache_key, reverse_rels)
        logger.debug(
            f"Reverse relations discovered for {self.model.__name__}: {reverse_rels}"
        )
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
            logger.debug(
                f"Select related cache hit for {self.model.__name__} (is_for={is_for})"
            )
            return cached

        config_rels = self._get_read_optimizations(is_for).select_related
        if config_rels:
            self._relation_cache.set(cache_key, config_rels)
            logger.debug(
                f"Select related from config for {self.model.__name__}: {config_rels}"
            )
            return config_rels

        relation_plan = model_transformations.discover_relation_plan(
            self.model, self._get_serializable_field_names(is_for)
        )
        select_rels = list(relation_plan.select_related)

        # Cache the result
        self._relation_cache.set(cache_key, select_rels)
        logger.debug(
            f"Select related discovered for {self.model.__name__}: {select_rels}"
        )
        return select_rels

    def _resolve_field_objects(self, field_names: list[str]) -> list[models.Field]:
        """Resolve Django field objects for a list of field names (sync)."""
        return model_transformations.resolve_model_fields(self.model, field_names)

    def _dump_queryset(
        self,
        queryset: Iterable[ModelT],
        schema: type[Schema],
    ) -> list[dict[str, Any]]:
        """Serialize a queryset to a list of dicts using Pydantic schema (sync)."""
        return model_transformations.dump_models(queryset, schema)

    def _decode_binary(
        self,
        payload: dict[str, Any],
        k: str,
        v: Any,
        field_obj: models.Field,
    ) -> None:
        """Decode base64-encoded binary field values in place."""
        if not isinstance(field_obj, models.BinaryField):
            return
        payload[k] = model_transformations.decode_binary_value(k, v)
        logger.debug(f"Decoded binary field '{k}' for {self.model.__name__}")

    async def _bump_object_from_schema(
        self, obj: ModelT, schema: type[Schema]
    ) -> dict[str, Any]:
        """Convert model instance to dict using Pydantic schema."""
        return await sync_to_async(model_transformations.dump_model)(obj, schema)

    async def _bump_queryset_from_schema(
        self, queryset: models.QuerySet[ModelT], schema: type[Schema]
    ) -> list[dict[str, Any]]:
        """Convert a queryset to a list of dicts using Pydantic schema in a single sync_to_async call."""

        return await sync_to_async(self._dump_queryset)(queryset, schema)

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
        self,
        request: HttpRequest | None,
        query_data: QuerySchema | None,
    ) -> None:
        """Validate required parameters for read operations."""
        model_transformations.validate_read_params(request, query_data)

    async def _handle_query_mode(
        self,
        request: HttpRequest | None,
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
        request: HttpRequest | None,
        query_data: QuerySchema,
        schema: Schema,
        is_for: Literal["read", "detail"] | None = None,
    ):
        """Serialize a queryset of objects."""
        objs = await self.aget_objects(request, query_data=query_data, is_for=is_for)
        return await self._bump_queryset_from_schema(objs, schema)

    async def _serialize_single_object(
        self,
        request: HttpRequest | None,
        query_data: QuerySchema,
        obj_schema: Schema,
        is_for: Literal["read", "detail"] | None = None,
    ):
        """Serialize a single object."""
        obj = await self.aget_object(request, query_data=query_data, is_for=is_for)
        return await self._bump_object_from_schema(obj, obj_schema)

    def _collect_custom_and_optional_fields(
        self,
        payload: dict[str, Any],
        is_serializer: bool,
        serializer: model_transformations.FieldPolicy | None,
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
        policy = serializer if is_serializer else None
        plan = model_transformations.plan_input_payload(
            payload, model_fields=self.model_fields, field_policy=policy
        )
        return plan.customs, list(plan.optionals)

    def _determine_skip_keys(
        self,
        payload: dict[str, Any],
        is_serializer: bool,
        serializer: model_transformations.FieldPolicy | None,
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
        policy = serializer if is_serializer else None
        return set(
            model_transformations.plan_input_payload(
                payload, model_fields=self.model_fields, field_policy=policy
            ).skip_keys
        )

    @staticmethod
    def _scoped_fk_util(rel_model: type[models.Model]) -> "ModelUtil | None":
        if isinstance(rel_model, ModelSerializerMeta):
            return ModelUtil(rel_model)
        serializer_class = get_serializer_for_model(rel_model)
        if serializer_class is not None:
            return ModelUtil(rel_model, serializer_class=serializer_class)
        return None

    async def _aresolve_fk(
        self,
        request: HttpRequest | None,
        payload: dict,
        k: str,
        v: Any,
        field_obj: models.ForeignKey,
        fk_cache: dict[tuple[type, Any], Any] | None = None,
    ) -> None:
        """Resolve foreign key ID to model instance in place.

        Multi-tenant scoping rules:

        - If *rel_model* is a ``ModelSerializer`` subclass, its own
          ``queryset_request`` is applied via ``ModelUtil(rel_model)``.
        - If *rel_model* is a vanilla Django model that has a ``Serializer``
          subclass registered for it (see ``_SERIALIZER_REGISTRY``), that
          serializer's ``queryset_request`` is applied via
          ``ModelUtil(rel_model, serializer_class=...)``.
        - Otherwise (vanilla model, no registered serializer), the unscoped
          manager is used. In single-tenant setups this matches the historical
          behavior; in multi-tenant setups, define a ``Serializer`` for the
          related model to opt in to FK scoping.

        In every scoped path, a row outside the caller's scope raises the
        standard ``NotFoundError(rel_model)`` — indistinguishable from a real
        404, so cross-tenant probing cannot leak existence.

        Parameters
        ----------
        fk_cache : dict[tuple[type, Any], Any], optional
            Request-scoped cache of already-resolved ``(rel_model, pk)`` ->
            instance pairs, shared across the items of a single bulk
            create/update call. Avoids re-fetching the same related object
            once per item when the same FK value repeats across the batch.
            ``None`` (the default, used by single create/update) disables
            caching entirely.
        """
        rel_model = field_obj.related_model
        cache_key = (rel_model, v) if fk_cache is not None else None
        if cache_key is not None and cache_key in fk_cache:
            payload[k] = fk_cache[cache_key]
            return

        logger.debug(
            f"Resolving FK '{k}' -> {rel_model.__name__} (pk={v}) for {self.model.__name__}"
        )

        related_util = self._scoped_fk_util(rel_model)
        if related_util is not None:
            payload[k] = await related_util.aget_object(request, pk=v)
        else:
            try:
                payload[k] = await rel_model.objects.aget(pk=v)
            except rel_model.DoesNotExist:
                raise NotFoundError(rel_model)

        if cache_key is not None:
            fk_cache[cache_key] = payload[k]

    async def _process_payload_fields(
        self,
        request: HttpRequest | None,
        payload: dict,
        fields_to_process: list[tuple[str, Any]],
        fk_cache: dict[tuple[type, Any], Any] | None = None,
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
        fk_cache : dict[tuple[type, Any], Any], optional
            Request-scoped FK resolution cache, see ``_resolve_fk``.
        """
        if not fields_to_process:
            return

        field_names = [k for k, _ in fields_to_process]
        field_objs = model_transformations.resolve_model_fields(self.model, field_names)

        # Single pass: decode binary + collect FK tasks
        fk_tasks = []
        for (k, v), field_obj in zip(fields_to_process, field_objs):
            self._decode_binary(payload, k, v, field_obj)
            if isinstance(field_obj, models.ForeignKey) and v is not None:
                fk_tasks.append(
                    self._aresolve_fk(request, payload, k, v, field_obj, fk_cache)
                )

        if fk_tasks:
            await asyncio.gather(*fk_tasks)

    @cached_property
    def nested_fields(self) -> dict[str, tuple[type, str]]:
        """Validated reverse-FK relations enabled for nested creation."""
        if not isinstance(self.model, ModelSerializerMeta):
            return {}
        return {
            name: (child, self.model._get_nested_fk_field(name))
            for name, child in self.model.get_nested_fields().items()
        }

    async def aparse_input_data(
        self,
        request: HttpRequest | None,
        data: Schema,
        fk_cache: dict[tuple[type, Any], Any] | None = None,
        *,
        partial: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
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
        fk_cache : dict[tuple[type, Any], Any], optional
            Request-scoped cache of already-resolved FK instances, shared
            across items of a bulk create/update call. See ``_resolve_fk``.

        Returns
        -------
        tuple[dict, dict]
            (payload_without_customs, customs_dict)

        Raises
        ------
        SerializeError
            On base64 decoding failure or invalid field names.
        """
        payload, plan = self._prepare_input_payload(data, partial=partial)
        await self._process_payload_fields(
            request, payload, plan.fields_to_process, fk_cache
        )
        return plan.model_payload(), plan.customs

    def _prepare_input_payload(
        self, data: Schema, *, partial: bool = False
    ) -> tuple[dict[str, Any], model_transformations.InputPayloadPlan]:
        """Dump and classify validated input before execution-mode-specific work."""
        payload = model_transformations.schema_to_payload(data, self.nested_fields)
        is_serializer = (
            isinstance(self.model, ModelSerializerMeta) or self.with_serializer
        )
        serializer = self.serializer if self.with_serializer else self.model
        plan = model_transformations.plan_input_payload(
            payload,
            model_fields=self.model_fields,
            field_policy=serializer if is_serializer else None,
            set_fields=frozenset(data.model_fields_set) if partial else None,
        )
        return plan.payload, plan

    def parse_input_data(
        self,
        request: HttpRequest | None,
        data: Schema,
        fk_cache: dict[tuple[type, Any], Any] | None = None,
        *,
        partial: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Transform input data using only synchronous field resolution."""
        payload, plan = self._prepare_input_payload(data, partial=partial)
        fields_to_process = plan.fields_to_process
        fields = model_transformations.resolve_model_fields(
            self.model, [name for name, _ in fields_to_process]
        )
        for (name, value), field in zip(fields_to_process, fields):
            self._decode_binary(payload, name, value, field)
            if isinstance(field, models.ForeignKey) and value is not None:
                payload[name] = self._resolve_fk(
                    request, field.related_model, value, fk_cache
                )
        return plan.model_payload(), plan.customs

    def _resolve_fk(
        self,
        request: HttpRequest | None,
        related_model: type[models.Model],
        value: Any,
        fk_cache: dict[tuple[type, Any], Any] | None,
    ) -> models.Model:
        cache_key = (related_model, value)
        if fk_cache is not None and cache_key in fk_cache:
            return fk_cache[cache_key]

        related_util = self._scoped_fk_util(related_model)
        if related_util is not None:
            obj = related_util.get_object(request, pk=value)
        else:
            try:
                obj = related_model._default_manager.get(pk=value)
            except related_model.DoesNotExist as exc:
                raise NotFoundError(related_model) from exc
        if fk_cache is not None:
            fk_cache[cache_key] = obj
        return obj

    def create_instance(
        self,
        request: HttpRequest | None,
        data: Schema,
        fk_cache: dict[tuple[type, Any], Any] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> ModelT:
        """Create one model instance with Django's synchronous ORM."""
        using = router.db_for_write(self.model)
        if any(
            router.db_for_write(child) != using
            for child, _ in self.nested_fields.values()
        ):
            raise ImproperlyConfigured(
                "Nested writes require one database for the owned graph"
            )
        from ninja_aio.models.hooks import (
            get_hooks,
            suppress_signals,
        )

        payload, customs = self.parse_input_data(request, data, fk_cache)
        if extra_fields:
            for name in extra_fields:
                payload.pop(self.model._meta.get_field(name).attname, None)
            payload.update(extra_fields)
        hooks = get_hooks(self.serializer_class or self.model)
        atomic = (
            transaction.atomic(using=using)
            if self._needs_atomic(hooks) or self.nested_fields
            else nullcontext()
        )
        with atomic:
            with suppress_signals():
                obj = (
                    self.serializer._create_instance(payload)
                    if self.with_serializer
                    else self.model._default_manager.create(**payload)
                )
            self._invoke_create_hooks(request, obj, payload, customs, hooks)
            self._create_nested_children(request, data, obj)
        return obj

    @cached_property
    def _has_lifecycle_hooks(self) -> bool:
        """True when a hook runs after the row is written and may still fail."""
        from ninja_aio.models.hooks import _is_overridden

        target = self.serializer_class or self.model
        return any(
            _is_overridden(target, name)
            for name in (
                "post_create",
                "apost_create",
                "custom_actions",
                "acustom_actions",
                "after_save",
                "on_create_after_save",
                "on_delete",
                "save",
                "delete",
            )
        )

    def _needs_atomic(self, hooks: dict | None) -> bool:
        return bool(hooks) or self._has_lifecycle_hooks

    def _reactive_target(self, obj: ModelT) -> tuple[Any, ModelT | None]:
        """Return (hook owner, instance argument) for reactive hooks."""
        return (self.serializer, obj) if self.with_serializer else (obj, None)

    def _invoke_create_hooks(
        self,
        request: HttpRequest | None,
        obj: ModelT,
        payload: dict,
        customs: dict,
        hooks: dict | None,
    ) -> None:
        from ninja_aio.models.hooks import (
            OperationContext,
            execute_reactive_hooks,
            invoke_hook,
        )

        context = OperationContext(
            request, "create", self.serializer or obj, obj, payload
        )
        if self.with_serializer:
            invoke_hook(context, "custom_actions", customs, obj)
            invoke_hook(context, "post_create", obj)
            if hooks:
                execute_reactive_hooks(self.serializer, hooks["create"], obj)
        elif isinstance(self.model, ModelSerializerMeta):
            invoke_hook(context, "custom_actions", customs)
            invoke_hook(context, "post_create")
            if hooks:
                execute_reactive_hooks(obj, hooks["create"])

    def _create_nested_children(
        self, request: HttpRequest | None, data: Schema, obj: ModelT
    ) -> None:
        for name, (child_model, fk_name) in self.nested_fields.items():
            child_util = ModelUtil(child_model)
            child_schema = child_model.generate_nested_child_schema(fk_name)
            for child_data in getattr(data, name, ()):
                if not isinstance(child_data, child_schema):
                    child_data = child_schema.model_validate(
                        child_data.model_dump(by_alias=True)
                        if isinstance(child_data, Schema)
                        else child_data
                    )
                child_util.create_instance(
                    request, child_data, extra_fields={fk_name: obj}
                )

    def update_instance(
        self,
        request: HttpRequest | None,
        data: Schema,
        pk: PrimaryKey,
        instance: ModelT | None = None,
        fk_cache: dict[tuple[type, Any], Any] | None = None,
    ) -> ModelT:
        """Update one model instance with Django's synchronous ORM."""
        from ninja_aio.models.hooks import (
            OperationContext,
            detect_changed_fields,
            fire_update_hooks,
            get_hooks,
            invoke_hook,
            suppress_signals,
        )

        obj = instance or self.get_object(request, pk, is_for="read")
        payload, customs = self.parse_input_data(
            request, data, fk_cache, partial=True
        )
        hooks = get_hooks(self.serializer_class or self.model)
        changed = (
            detect_changed_fields(obj, payload, hooks["update_field"])
            if hooks
            else set()
        )
        context = OperationContext(
            request, "update", self.serializer or obj, obj, payload, changed
        )
        atomic = (
            transaction.atomic(using=router.db_for_write(self.model))
            if self._needs_atomic(hooks)
            else nullcontext()
        )
        with atomic:
            for name, value in payload.items():
                setattr(obj, name, value)
            if self.with_serializer:
                invoke_hook(context, "custom_actions", customs, obj)
            elif isinstance(self.model, ModelSerializerMeta):
                invoke_hook(context, "custom_actions", customs)
            with suppress_signals():
                if self.with_serializer:
                    self.serializer._save_instance(obj)
                else:
                    obj.save()
            if hooks:
                target, hook_instance = self._reactive_target(obj)
                fire_update_hooks(target, changed, hooks, hook_instance)
        return obj

    def destroy_instance(
        self,
        request: HttpRequest | None,
        pk: PrimaryKey,
        instance: ModelT | None = None,
    ) -> None:
        """Destroy one model instance with Django's synchronous ORM."""
        from ninja_aio.models.hooks import (
            _is_overridden,
            execute_reactive_hooks,
            get_hooks,
            suppress_signals,
        )

        obj = instance or self.get_object(request, pk)
        hooks = get_hooks(self.serializer_class or self.model)
        atomic = (
            transaction.atomic(using=router.db_for_write(self.model))
            if self._needs_atomic(hooks)
            else nullcontext()
        )
        with atomic:
            with suppress_signals():
                obj.delete()
            if self.with_serializer and _is_overridden(self.serializer, "on_delete"):
                self.serializer.on_delete(obj)
            if hooks:
                target, hook_instance = self._reactive_target(obj)
                execute_reactive_hooks(target, hooks["delete"], hook_instance)

    async def acreate_instance(
        self,
        request: HttpRequest | None,
        data: Schema,
        fk_cache: dict[tuple[type, Any], Any] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> ModelT:
        """Create an owned object graph atomically, including direct/bulk calls."""
        if not self.nested_fields:
            from ninja_aio.models.hooks import get_hooks

            hooks = get_hooks(self.serializer_class or self.model)
            atomic = (
                AsyncAtomicContextManager(using=router.db_for_write(self.model))
                if self._needs_atomic(hooks)
                else nullcontext()
            )
            async with atomic:
                return await self._persist_instance(
                    request, data, fk_cache, extra_fields
                )
        using = router.db_for_write(self.model)
        if any(
            router.db_for_write(child) != using
            for child, _ in self.nested_fields.values()
        ):
            raise ImproperlyConfigured(
                "Nested writes require one database for the owned graph"
            )
        async with AsyncAtomicContextManager(using=using):
            obj = await self._persist_instance(request, data, fk_cache, extra_fields)
            for name, (child_model, fk_name) in self.nested_fields.items():
                child_util = ModelUtil(child_model)
                child_schema = child_model.generate_nested_child_schema(fk_name)
                # Sequential writes ensure no child task survives a rollback.
                for child_data in getattr(data, name, ()):
                    if not isinstance(child_data, child_schema):
                        child_data = child_schema.model_validate(
                            child_data.model_dump(by_alias=True)
                            if isinstance(child_data, Schema)
                            else child_data
                        )
                    await child_util.acreate_instance(
                        request, child_data, extra_fields={fk_name: obj}
                    )
            return obj

    async def _persist_instance(
        self,
        request: HttpRequest | None,
        data: Schema,
        fk_cache: dict[tuple[type, Any], Any] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> ModelT:
        """
        Create a new instance and run hooks.

        Handles input parsing, object creation, and custom_actions/post_create
        hooks. Does not serialize the output.

        Parameters
        ----------
        request : HttpRequest
        data : Schema
            Input schema instance.
        fk_cache : dict[tuple[type, Any], Any], optional
            Request-scoped cache of already-resolved FK instances, shared
            across items of a bulk create call. See ``_resolve_fk``.

        Returns
        -------
        ModelT
            The created model instance.
        """
        from ninja_aio.models.hooks import (
            OperationContext,
            ainvoke_hook,
            asuppress_signals,
            get_hooks,
            aexecute_reactive_hooks,
        )

        logger.info(f"Creating {self.model.__name__}")
        payload, customs = await self.aparse_input_data(request, data, fk_cache)
        if extra_fields:
            for name in extra_fields:
                # The parent owns this FK, including its raw *_id alias.
                payload.pop(self.model._meta.get_field(name).attname, None)
            payload.update(extra_fields)
        async with asuppress_signals():
            obj = (
                await self.model.objects.acreate(**payload)
                if not self.with_serializer
                else await self.serializer._acreate(payload)
            )
        logger.debug(f"Created {self.model.__name__} (pk={obj.pk})")
        context = OperationContext(
            request, "create", self.serializer or obj, obj, payload
        )
        if self.with_serializer:
            await ainvoke_hook(context, "custom_actions", customs, obj)
            await ainvoke_hook(context, "post_create", obj)
        elif isinstance(self.model, ModelSerializerMeta):
            await ainvoke_hook(context, "custom_actions", customs)
            await ainvoke_hook(context, "post_create")
        hooks = get_hooks(self.serializer_class or self.model)
        if hooks and hooks["create"]:
            target, hook_instance = self._reactive_target(obj)
            await aexecute_reactive_hooks(target, hooks["create"], hook_instance)
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
        _warn_deprecated("create_s", "acreate() and amodel_dump()")
        obj = await self.acreate_instance(request, data)
        # Only prefetch reverse relations (forward FKs already loaded)
        obj = await self._prefetch_reverse_relations_on_instance(obj, is_for="read")
        return await self._read_s(obj_schema, request, obj)

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
        _warn_deprecated("read_s", "aget_object() and amodel_dump()")
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
        _warn_deprecated("list_read_s", "aget_objects() and amodel_dumps()")
        return await self._read_s(
            schema,
            request,
            instances,
            query_data,
            is_for,
        )

    async def aupdate_instance(
        self,
        request: HttpRequest | None,
        data: Schema,
        pk: PrimaryKey,
        require_fields: bool = False,
        fk_cache: dict[tuple[type, Any], Any] | None = None,
        instance: ModelT | None = None,
    ) -> ModelT:
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
        fk_cache : dict[tuple[type, Any], Any], optional
            Request-scoped cache of already-resolved FK instances, shared
            across items of a bulk update call. See ``_resolve_fk``.

        Returns
        -------
        ModelT
            The updated model instance.
        """
        from ninja_aio.models.hooks import (
            OperationContext,
            ainvoke_hook,
            asuppress_signals,
            get_hooks,
            detect_changed_fields,
            afire_update_hooks,
        )

        logger.info(f"Updating {self.model.__name__} (pk={pk})")
        obj = (
            instance
            if instance is not None
            else await self.aget_object(request, pk, is_for="read")
        )
        payload, customs = await self.aparse_input_data(
            request, data, fk_cache, partial=True
        )
        context = OperationContext(
            request, "update", self.serializer or obj, obj, payload
        )
        if require_fields and not payload and not customs:
            raise SerializeError("No fields provided for update.")

        hooks = get_hooks(self.serializer_class or self.model)
        changed_fields = (
            detect_changed_fields(obj, payload, hooks.get("update_field", {}))
            if hooks
            else set()
        )
        context.changed_fields = changed_fields

        atomic = (
            AsyncAtomicContextManager(using=router.db_for_write(self.model))
            if self._needs_atomic(hooks)
            else nullcontext()
        )
        async with atomic:
            for k, v in payload.items():
                setattr(obj, k, v)

            if self.with_serializer:
                await ainvoke_hook(context, "custom_actions", customs, obj)
            elif isinstance(self.model, ModelSerializerMeta):
                await ainvoke_hook(context, "custom_actions", customs)
            async with asuppress_signals():
                if self.with_serializer:
                    await self.serializer._asave_instance(obj)
                else:
                    await obj.asave()

            if hooks:
                target, hook_instance = self._reactive_target(obj)
                await afire_update_hooks(target, changed_fields, hooks, hook_instance)

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
        _warn_deprecated("update_s", "aupdate() and amodel_dump()")
        obj = await self.aupdate_instance(request, data, pk, require_fields)
        # FK instances from aparse_input_data are already attached to obj
        # Only refresh reverse relations since they might have changed
        updated_object = await self._prefetch_reverse_relations_on_instance(
            obj, is_for="read"
        )
        return await self._read_s(obj_schema, request, updated_object)

    async def delete_s(
        self,
        request: HttpRequest | None,
        pk: PrimaryKey,
        instance: ModelT | None = None,
    ):
        """Deprecated alias of ``adestroy()``."""
        _warn_deprecated("delete_s", "adestroy()")
        await self.adestroy_instance(request, pk, instance=instance)

    async def adestroy_instance(
        self,
        request: HttpRequest | None,
        pk: PrimaryKey,
        instance: ModelT | None = None,
    ) -> None:
        """
        Delete an instance by primary key.

        Parameters
        ----------
        request : HttpRequest
        pk : int | str
            Primary key.
        instance : ModelT, optional
            Already-fetched instance to delete. When provided, skips the
            lookup query entirely (e.g. the caller already fetched the object
            to serialize it before deletion, as ``delete_view`` does when
            ``schema_delete_out`` is set).

        Returns
        -------
        None
        """
        from ninja_aio.models.hooks import (
            asuppress_signals,
            get_hooks,
            aexecute_reactive_hooks,
            _is_overridden,
        )

        logger.info(f"Deleting {self.model.__name__} (pk={pk})")
        obj = instance if instance is not None else await self.aget_object(request, pk)
        hooks = get_hooks(self.serializer_class or self.model)
        atomic = (
            AsyncAtomicContextManager(using=router.db_for_write(self.model))
            if self._needs_atomic(hooks)
            else nullcontext()
        )
        async with atomic:
            async with asuppress_signals():
                await obj.adelete()
            logger.debug(f"Deleted {self.model.__name__} (pk={pk})")
            if self.with_serializer and _is_overridden(self.serializer, "on_delete"):
                await sync_to_async(self.serializer.on_delete)(obj)

            if hooks and hooks["delete"]:
                target, hook_instance = self._reactive_target(obj)
                await aexecute_reactive_hooks(target, hooks["delete"], hook_instance)

    @staticmethod
    def _split_target(target: ModelT | PrimaryKey) -> tuple[PrimaryKey, ModelT | None]:
        if isinstance(target, models.Model):
            return target.pk, target
        return target, None

    def get(
        self,
        pk: PrimaryKey,
        *,
        request: HttpRequest | None = None,
        optimize_for: QueryPurpose | None = None,
    ) -> ModelT:
        """Retrieve one request-scoped instance synchronously."""
        return self.get_object(request, pk, is_for=optimize_for)

    async def aget(
        self,
        pk: PrimaryKey,
        *,
        request: HttpRequest | None = None,
        optimize_for: QueryPurpose | None = None,
    ) -> ModelT:
        """Retrieve one request-scoped instance asynchronously."""
        return await self.aget_object(request, pk, is_for=optimize_for)

    def get_queryset(
        self,
        *,
        request: HttpRequest | None = None,
        optimize_for: QueryPurpose | None = None,
    ) -> models.QuerySet[ModelT]:
        """Return the request-scoped queryset synchronously."""
        return self.get_objects(request, is_for=optimize_for)

    async def aget_queryset(
        self,
        *,
        request: HttpRequest | None = None,
        optimize_for: QueryPurpose | None = None,
    ) -> models.QuerySet[ModelT]:
        """Return the request-scoped queryset asynchronously."""
        return await self.aget_objects(request, is_for=optimize_for)

    def create(self, data: Schema, *, request: HttpRequest | None = None) -> ModelT:
        """Create one instance from already-validated input synchronously."""
        return self.create_instance(request, data)

    async def acreate(
        self, data: Schema, *, request: HttpRequest | None = None
    ) -> ModelT:
        """Create one instance from already-validated input asynchronously."""
        return await self.acreate_instance(request, data)

    def update(
        self,
        target: ModelT | PrimaryKey,
        data: Schema,
        *,
        request: HttpRequest | None = None,
    ) -> ModelT:
        """Update one instance, reusing *target* when it is already loaded."""
        pk, instance = self._split_target(target)
        return self.update_instance(request, data, pk, instance=instance)

    async def aupdate(
        self,
        target: ModelT | PrimaryKey,
        data: Schema,
        *,
        request: HttpRequest | None = None,
    ) -> ModelT:
        """Update one instance asynchronously, reusing a loaded *target*."""
        pk, instance = self._split_target(target)
        return await self.aupdate_instance(request, data, pk, instance=instance)

    def destroy(
        self, target: ModelT | PrimaryKey, *, request: HttpRequest | None = None
    ) -> None:
        """Delete one instance synchronously."""
        pk, instance = self._split_target(target)
        self.destroy_instance(request, pk, instance=instance)

    async def adestroy(
        self, target: ModelT | PrimaryKey, *, request: HttpRequest | None = None
    ) -> None:
        """Delete one instance asynchronously."""
        pk, instance = self._split_target(target)
        await self.adestroy_instance(request, pk, instance=instance)

    def model_dump(self, instance: ModelT, *, schema: type[Schema]) -> dict[str, Any]:
        """Serialize one instance with *schema*."""
        return model_transformations.dump_model(instance, schema)

    def model_dumps(
        self, instances: Iterable[ModelT], *, schema: type[Schema]
    ) -> list[dict[str, Any]]:
        """Serialize instances with *schema*."""
        return model_transformations.dump_models(instances, schema)

    async def amodel_dump(
        self, instance: ModelT, *, schema: type[Schema]
    ) -> dict[str, Any]:
        """Serialize one instance with *schema* from async code."""
        return await self._bump_object_from_schema(instance, schema)

    async def amodel_dumps(
        self,
        instances: Iterable[ModelT] | models.QuerySet[ModelT],
        *,
        schema: type[Schema],
    ) -> list[dict[str, Any]]:
        """Serialize instances with *schema* from async code."""
        return await self._bump_queryset_from_schema(instances, schema)

    def _bulk_target(self, target: ModelT | PrimaryKey) -> tuple[PrimaryKey, Any]:
        return self._split_target(target)[0], target

    def _bulk_update_target(self, item: tuple) -> tuple[PrimaryKey, tuple]:
        return self._split_target(item[0])[0], item

    @property
    def _item_transaction(self) -> bool:
        # Plain models write once per item and open their own transaction for
        # hooks/nested writes; serializer custom hooks need the per-item rollback.
        return self.with_serializer or isinstance(self.model, ModelSerializerMeta)

    def bulk_create(
        self, items: Iterable[Schema], *, request: HttpRequest | None = None
    ) -> BulkResult[ModelT]:
        """Create each validated item in its own transaction."""
        fk_cache: dict[tuple[type, Any], Any] = {}
        return run_bulk(
            self.model,
            items,
            lambda data: self.create_instance(request, data, fk_cache),
            atomic=self._item_transaction,
        )

    async def abulk_create(
        self, items: Iterable[Schema], *, request: HttpRequest | None = None
    ) -> BulkResult[ModelT]:
        """Create each validated item in its own transaction, asynchronously."""
        fk_cache: dict[tuple[type, Any], Any] = {}
        return await arun_bulk(
            self.model,
            items,
            lambda data: self.acreate_instance(request, data, fk_cache),
            atomic=self._item_transaction,
        )

    def bulk_update(
        self,
        items: Iterable[tuple[ModelT | PrimaryKey, Schema]],
        *,
        request: HttpRequest | None = None,
    ) -> BulkResult[ModelT]:
        """Update each ``(target, data)`` pair in its own transaction."""
        fk_cache: dict[tuple[type, Any], Any] = {}

        def update(item: tuple) -> ModelT:
            pk, instance = self._split_target(item[0])
            return self.update_instance(
                request, item[1], pk, instance=instance, fk_cache=fk_cache
            )

        return run_bulk(
            self.model, items, update, self._bulk_update_target, self._item_transaction
        )

    async def abulk_update(
        self,
        items: Iterable[tuple[ModelT | PrimaryKey, Schema]],
        *,
        request: HttpRequest | None = None,
    ) -> BulkResult[ModelT]:
        """Update each ``(target, data)`` pair in its own transaction, asynchronously."""
        fk_cache: dict[tuple[type, Any], Any] = {}

        async def update(item: tuple) -> ModelT:
            pk, instance = self._split_target(item[0])
            return await self.aupdate_instance(
                request, item[1], pk, fk_cache=fk_cache, instance=instance
            )

        return await arun_bulk(
            self.model, items, update, self._bulk_update_target, self._item_transaction
        )

    def bulk_destroy(
        self,
        targets: Iterable[ModelT | PrimaryKey],
        *,
        request: HttpRequest | None = None,
    ) -> BulkResult[PrimaryKey]:
        """Delete each target in its own transaction, returning deleted primary keys."""

        def destroy(target: ModelT | PrimaryKey) -> PrimaryKey:
            pk, instance = self._split_target(target)
            self.destroy_instance(request, pk, instance=instance)
            return pk

        return run_bulk(
            self.model, targets, destroy, self._bulk_target, self._item_transaction
        )

    async def abulk_destroy(
        self,
        targets: Iterable[ModelT | PrimaryKey],
        *,
        request: HttpRequest | None = None,
    ) -> BulkResult[PrimaryKey]:
        """Delete each target in its own transaction asynchronously."""

        async def destroy(target: ModelT | PrimaryKey) -> PrimaryKey:
            pk, instance = self._split_target(target)
            await self.adestroy_instance(request, pk, instance=instance)
            return pk

        return await arun_bulk(
            self.model, targets, destroy, self._bulk_target, self._item_transaction
        )

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
        _warn_deprecated("bulk_create_s", "abulk_create()")
        logger.info(f"Bulk creating {len(data_list)} {self.model.__name__} instances")
        extractor = detail_extractor or (lambda obj: obj.pk)
        success_details = []
        error_details = []
        # Request-scoped cache: repeated FK values across items in the batch
        # (e.g. many rows sharing the same category/tenant) are resolved once
        # instead of once per item. See `_resolve_fk`.
        fk_cache: dict[tuple[type, Any], Any] = {}

        for data in data_list:
            try:
                obj = await self.acreate_instance(request, data, fk_cache)
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
        _warn_deprecated("bulk_update_s", "abulk_update()")
        logger.info(f"Bulk updating {len(data_list)} {self.model.__name__} instances")
        extractor = detail_extractor or (lambda obj: obj.pk)
        success_details = []
        error_details = []
        # Request-scoped cache: repeated FK values across items in the batch
        # are resolved once instead of once per item. See `_resolve_fk`.
        fk_cache: dict[tuple[type, Any], Any] = {}

        for pk, data in data_list:
            try:
                obj = await self.aupdate_instance(
                    request, data, pk, require_fields, fk_cache
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
            existing_pks = {
                pk_val
                async for pk_val in matched_qs.values_list(
                    self.model_pk_name, flat=True
                )
            }
            return existing_pks, {}

        fields_with_pk = list(dict.fromkeys([self.model_pk_name] + detail_fields))
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
        _warn_deprecated("bulk_delete_s", "abulk_destroy()")
        logger.info(f"Bulk deleting {len(pks)} {self.model.__name__} instances")
        if not pks:
            return [], []

        qs = await self.aget_objects(request, is_for="read")
        matched_qs = qs.filter(**{f"{self.model_pk_name}__in": pks})

        existing_pks, detail_map = await self._resolve_existing_pks(
            matched_qs, detail_fields
        )

        error_details = [
            NotFoundError(self.model).error for pk in pks if pk not in existing_pks
        ]

        success_details: list = []
        if existing_pks:
            await qs.filter(**{f"{self.model_pk_name}__in": existing_pks}).adelete()
            success_details = self._build_success_details(pks, existing_pks, detail_map)

        logger.debug(
            f"Bulk delete {self.model.__name__}: "
            f"{len(success_details)} deleted, {len(error_details)} errors"
        )
        return success_details, error_details
