import functools
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Generic, List, Literal, NamedTuple, TypeVar

from ninja import NinjaAPI, Router, Schema, Path, Query, Status
from ninja.constants import NOT_SET
from ninja.pagination import AsyncPaginationBase, PageNumberPagination
from django.http import HttpRequest
from django.db import transaction
from django.db.models import Model, QuerySet, prefetch_related_objects
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from pydantic import create_model

from ninja_aio.schemas.helpers import DecoratorsSchema

from ninja_aio.models import ModelSerializer, ModelUtil
from ninja_aio.schemas import (
    GenericMessageSchema,
    M2MRelationSchema,
    BulkResultSchema,
)
from ninja_aio.exceptions import SerializeError
from ninja_aio.helpers.api import ManyToManyAPI
from ninja_aio.types import (
    BulkFailure,
    BulkResult,
    HttpMethod,
    ModelSerializerMeta,
    VIEW_TYPES,
    BULK_TYPES,
    VALID_DJANGO_LOOKUPS,
    get_ninja_aio_meta_attr,
)
from ninja_aio.decorators import unique_view, decorate_view, aatomic
from ninja_aio.decorators.actions import ActionConfig
from ninja_aio.factory import ApiMethodFactory
from ninja_aio.factory.operations import register_route
from ninja_aio.models import serializers
from ninja_aio.models import transformations as model_transformations
from ninja_aio.models.utils import bulk_failure

logger = logging.getLogger("ninja_aio.views")

ERROR_CODES = frozenset({400, 401, 403, 404})

# TypeVar for generic model typing in ViewSets
ModelT = TypeVar("ModelT", bound=Model)


@dataclass(frozen=True)
class GeneratedRoute:
    method: HttpMethod
    path: str
    auth: object
    summary: str
    description: str
    response: dict
    handler: Callable
    decorators: tuple = ()
    atomic: bool = False
    plural: bool = False


class ViewSchemas(NamedTuple):
    schema_out: type[Schema] | None
    schema_detail: type[Schema] | None
    schema_in: type[Schema] | None
    schema_update: type[Schema] | None
    schema_create_out: type[Schema] | None
    schema_update_out: type[Schema] | None
    schema_delete_out: type[Schema] | None


class API:
    api: NinjaAPI = None
    router_tag: str = ""
    router_tags: list[str] = []
    api_route_path: str = ""
    auth: list | None = NOT_SET
    router: Router = None
    # Schema used for the generic error responses declared alongside every
    # generated endpoint's success response (see `error_codes`). Override on
    # a subclass to replace GenericMessageSchema with your own project-wide
    # error contract without having to redeclare every view's `response=`.
    error_schema: type[Schema] = GenericMessageSchema

    def views(self) -> None:
        """
        Override this method to add your custom views. For example:
        @self.router.get(some_path, response=some_schema)
        async def some_method(request, *args, **kwargs):
            pass

        You can add views just doing:

        @self.router.get(some_path, response=some_schema)
        async def some_method(request, *args, **kwargs):
            pass

        @self.router.post(some_path, response=some_schema)
        async def some_method(request, *args, **kwargs):
            pass

        If you provided a list of auths you can chose which of your views
        should be authenticated:

        AUTHENTICATED VIEW:

        @self.router.get(some_path, response=some_schema, auth=self.auth)
        async def some_method(request, *args, **kwargs):
            pass

        NOT AUTHENTICATED VIEW:

        @self.router.post(some_path, response=some_schema)
        async def some_method(request, *args, **kwargs):
            pass
        """
        pass

    def _add_views(self) -> Router:
        """Register views decorated with @api_register."""
        for name in dir(self.__class__):
            method = getattr(self.__class__, name)
            if hasattr(method, "_api_register"):
                method._api_register(self)
        return self.router

    async def aon_before_operation(self, request: HttpRequest, operation: str) -> None:
        """Hook called before every CRUD/bulk/@action view. Override for view-level checks."""

    def on_before_operation(self, request: HttpRequest, operation: str) -> None:
        """Synchronous counterpart of aon_before_operation, used by sync endpoints."""

    def _iter_actions(self):
        for name in dir(self.__class__):
            method = getattr(self.__class__, name, None)
            config = getattr(method, "_action_config", None)
            if config is not None:
                yield name, method, config

    def _auth_view(self, view_type: str) -> list | None:
        """Auth applied to actions for an HTTP verb."""
        return self.auth

    def _action_summary_suffix(self) -> str:
        return ""

    def _action_name_suffix(self) -> str:
        return type(self).__name__.lower()

    def _resolve_action_path(self, name: str, config: ActionConfig) -> str:
        return config.url_path if config.url_path is not None else name.replace("_", "-")

    def _with_operation_hook(self, handler: Callable, name: str) -> Callable:
        """Wrap an @action handler so aon_before_operation runs in the handler's mode."""
        if inspect.iscoroutinefunction(handler):

            @functools.wraps(handler)
            async def hooked_handler(*args, **kwargs):
                request = args[0] if args else kwargs.get("request")
                await self.aon_before_operation(request, name)
                return await handler(*args, **kwargs)

        else:

            @functools.wraps(handler)
            def hooked_handler(*args, **kwargs):
                request = args[0] if args else kwargs.get("request")
                self.on_before_operation(request, name)
                return handler(*args, **kwargs)

        return hooked_handler

    def _action_core_handler(
        self, name: str, method: Callable, config: ActionConfig, http_method: HttpMethod
    ) -> Callable:
        factory = ApiMethodFactory(http_method.value)
        handler = factory._build_handler(self, method)
        factory._apply_metadata(handler, method)
        return self._with_operation_hook(handler, name)

    def _build_action_handler(
        self, name: str, method: Callable, config: ActionConfig, http_method: HttpMethod
    ) -> Callable:
        handler = self._action_core_handler(name, method, config, http_method)
        handler.__name__ = f"{name}_{http_method.value}_{self._action_name_suffix()}"
        for decorator in reversed(config.decorators or []):
            handler = decorator(handler)
        return handler

    def _register_single_action(
        self, name: str, method: Callable, config: ActionConfig
    ) -> None:
        """Register an @action/@on method on the router once per configured HTTP method."""
        path = self._resolve_action_path(name, config)
        for http_method in config.methods:
            summary = config.summary or (
                f"{http_method.value.upper()} {name.replace('_', ' ').title()}"
                f"{self._action_summary_suffix()}"
            )
            self._operations[name] = register_route(
                self.router,
                http_method,
                path,
                auth=config.auth if config.auth is not NOT_SET else self._auth_view(http_method.value),
                throttle=config.throttle,
                response=config.response,
                summary=summary,
                description=config.description,
                tags=config.tags,
                deprecated=config.deprecated,
                url_name=config.url_name,
                include_in_schema=config.include_in_schema,
                openapi_extra=config.openapi_extra,
            )(self._build_action_handler(name, method, config, http_method))
            logger.debug(f"Registered action {http_method.value.upper()} {path} on {type(self).__name__}")

    def _register_actions(self) -> None:
        """Discover and register @action-decorated methods on the router."""
        for name, method, config in self._iter_actions():
            self._register_single_action(name, method, config)

    def add_views_to_route(self) -> None:
        self.api.add_router(f"{self.api_route_path}", self._add_views())


class APIView(API):
    """
    Base class to register custom, non-CRUD endpoints on a Ninja Router.

    Usage:
        from ninja_aio.decorations import api_get

        @api.view(prefix="/custom", tags=["Custom"])
        class CustomAPIView(APIView):
            @api_get("/hello", response=SomeSchema)
            async def hello(request):
                return SomeSchema(...)

        or

        class CustomAPIView(APIView):
            api = api
            api_route_path = "/custom"
            router_tags = ["Custom"]

            def views(self):
                @self.router.get("/hello", response=SomeSchema)
                async def hello(request):
                    return SomeSchema(...)


        CustomAPIView().add_views_to_route()

    Attributes:
        api: NinjaAPI instance used to mount the router.
        router_tag: Single tag used if router_tags is not provided.
        router_tags: List of tags assigned to the router.
        api_route_path: Base path where the router is mounted.
        auth: Default auth list or NOT_SET for unauthenticated endpoints.
        router: Router instance where views are registered.
        error_codes: Common error codes returned by endpoints.
        error_schema: Schema documented for those error codes (default GenericMessageSchema);
            override on a subclass to use your own project-wide error contract.

    Overridable methods:
        views(): Register your endpoints using self.router.get/post/patch/delete.
    """

    def __init__(
        self, api: NinjaAPI = None, prefix: str = None, tags: list[str] = None
    ) -> None:
        self.api = api or self.api
        self.api_route_path = prefix or self.api_route_path
        self.router_tags = tags or self.router_tags or [self.router_tag]
        self.router = Router(tags=self.router_tags)
        self.error_codes = ERROR_CODES
        self._operations: dict[str, Callable] = {}
        for name, _, config in self._iter_actions():
            if config.detail:
                raise ImproperlyConfigured(
                    f"{type(self).__name__}.{name}: detail actions (@action(detail=True), @on) "
                    "require an APIViewSet."
                )

    def _add_views(self) -> Router:
        super()._add_views()
        self.views()
        self._register_actions()
        return self.router


class APIViewSet(API, Generic[ModelT]):
    """
    Generic base viewset generating async CRUD + optional M2M endpoints for Django models.

    Type Safety
    -----------
    Specify the model type parameter to get proper type hints for model_util methods:

        @api.viewset(Book)
        class BookAPI(APIViewSet[Book]):  # Explicitly typed
            async def my_method(self, request):
                # self.model_util is typed as ModelUtil[Book]
                book: Book = await self._get_serializer().aget(1, request=request)
                # IDE knows book.title, book.author, etc.

    If you use serializer methods instead, type the Serializer:

        class BookSerializer(Serializer[Book]):  # Type here
            class Meta:
                model = Book

        @api.viewset(Book)
        class BookAPI(APIViewSet):  # No generic needed
            serializer_class = BookSerializer
            async def my_method(self, request, data):
                book: Book = await self.serializer.acreate(data)  # Typed!

    Basic Usage
    -----------
        @api.viewset(model=MyModel)
        class MyModelViewSet(APIViewSet):
            pass

        or

        class MyModelViewSet(APIViewSet):
            model = MyModel
            api = api
        MyModelViewSet().add_views_to_route()

    Automatic schema generation:
        If model is a ModelSerializer (subclass of ModelSerializerMeta),
        read/create/update schemas are auto-generated from its serializers.
        Otherwise provide schema_in / schema_out / schema_update manually.

    Generated endpoints (unless disabled via `disable`):
        POST   /                       -> create_view      (201, schema_out)
        GET    /                       -> list_view        (200, List[schema_out] paginated)
        GET    /{pk}                   -> retrieve_view    (200, schema_out)
        PATCH  /{pk}/                  -> update_view      (200, schema_out)
        DELETE /{pk}/                  -> delete_view      (204)

    M2M endpoints (per entry in m2m_relations) if enabled:
        GET    /{pk}/{related_path}            -> list related objects (paginated)
        POST   /{pk}/{related_path}/           -> add/remove related objects (depending on m2m_add / m2m_remove)

    M2M filters:
        Each M2MRelationSchema may define a filters dict:
            filters = { "field_name": (type, default) }
        A dynamic Pydantic Filters schema is generated and exposed as query params
        on the related GET endpoint: /{pk}/{related_path}?field_name=value.
        To apply custom filter logic implement an hook named:
            <related_name>_query_params_handler(self, queryset, filters_dict)
        It receives the initial related queryset and the validated/dumped filters
        dict, and must return the (optionally) filtered queryset.

        Example:
            @api.viewset(model=models.User)
            class UserViewSet(APIViewSet):
                m2m_relations = [
                    M2MRelationSchema(
                        model=models.Tag,
                        related_name="tags",
                        filters={
                            "name": (str, "")
                        }
                    )
                ]

                def tags_query_params_handler(self, queryset, filters):
                    name_filter = filters.get("name")
                    if name_filter:
                        queryset = queryset.filter(name__icontains=name_filter)
                    return queryset

        If filters is empty or omitted no query params are added for that relation.

    Attribute summary:
        model: Django model or ModelSerializer.
        api: NinjaAPI instance.
        schema_in / schema_out / schema_update: Pydantic schemas (auto when ModelSerializer).
        auth: Default auth list or NOT_SET (no auth). Verb specific auth: get_auth, post_auth, patch_auth, delete_auth.
        pagination_class: AsyncPaginationBase subclass (default PageNumberPagination).
        query_params: Dict[str, (type, default)] to build a dynamic filters schema for list_view.
        disable: List of view type strings: 'create','list','retrieve','update','delete','all'.
        api_route_path: Base path; auto-resolved from verbose name if empty.
        list_docs / create_docs / retrieve_docs / update_docs / delete_docs: Endpoint descriptions.
        bulk_response_fields: Field(s) returned in bulk success details. None=PK (default), str=single field, list[str]=dict of fields.
        m2m_relations: List of M2MRelationSchema describing related model, related_name, custom path, auth, filters.
        m2m_add / m2m_remove / m2m_get: Enable add/remove/get M2M operations.
        m2m_auth: Auth list for all M2M endpoints unless overridden per relation.

    Overridable hooks:
        views(): Register extra custom endpoints on self.router.
        aquery_params_handler(queryset, filters): Sync/Async hook to apply list filters.
        <related_name>_query_params_handler(queryset, filters): Async hook for per-M2M filtering.

    Error responses:
        All endpoints may return `error_schema` (default GenericMessageSchema) for codes
        in ERROR_CODES (400,401,404). Override `error_schema` on a subclass to document
        your own error contract instead, without redeclaring every view's `response=`.

    Internal:
        Dynamic path/filter schemas built with pydantic.create_model.
        unique_view decorator prevents duplicate registration.
    """

    model: type[ModelT]
    serializer_class: type[serializers.Serializer] | None = None
    schema_in: Schema | None = None
    schema_out: Schema | None = None
    schema_detail: Schema | None = None
    schema_update: Schema | None = None
    schema_create_out: Schema | None = None
    schema_update_out: Schema | None = None
    schema_delete_out: Schema | None = None
    get_auth: list | None = NOT_SET
    post_auth: list | None = NOT_SET
    patch_auth: list | None = NOT_SET
    delete_auth: list | None = NOT_SET
    pagination_class: type[AsyncPaginationBase] = PageNumberPagination
    query_params: dict[str, tuple[type, ...]] = {}
    disable: list[type[VIEW_TYPES]] = []
    list_docs = "List all objects."
    create_docs = "Create a new object."
    retrieve_docs = "Retrieve a specific object by its primary key."
    update_docs = "Update an object by its primary key."
    delete_docs = "Delete an object by its primary key."
    m2m_relations: list[M2MRelationSchema] = []
    m2m_auth: list | None = NOT_SET
    extra_decorators: DecoratorsSchema = DecoratorsSchema()
    model_verbose_name: str = ""
    model_verbose_name_plural: str = ""
    bulk_operations: list[type[BULK_TYPES]] = []
    bulk_response_fields: list[str] | str | None = None
    bulk_create_docs = "Create multiple objects in a single request."
    bulk_update_docs = "Update multiple objects in a single request."
    bulk_delete_docs = "Delete multiple objects in a single request."
    ordering_fields: list[str] = []
    default_ordering: str | list[str] = []
    require_update_fields: bool = False
    execution_mode: Literal["async", "sync"] = "async"

    def __init__(
        self,
        api: NinjaAPI = None,
        model: type[ModelT] | None = None,
        prefix: str = None,
        tags: list[str] = None,
    ) -> None:
        if self.execution_mode not in ("async", "sync"):
            raise ValueError("execution_mode must be 'async' or 'sync'")
        self.api = api or self.api
        self.error_codes = ERROR_CODES
        self.model: type[ModelT] = model or self.model
        self.serializer: serializers.Serializer[ModelT] | None = (
            None if self.serializer_class is None else self.serializer_class()
        )
        self.model_util: ModelUtil[ModelT] = (
            ModelUtil(self.model, serializer_class=self.serializer_class)
            if not isinstance(self.model, ModelSerializerMeta)
            else self.model.util
        )
        self._operations: dict[str, Callable] = {}
        (
            self.schema_out,
            self.schema_detail,
            self.schema_in,
            self.schema_update,
            self.schema_create_out,
            self.schema_update_out,
            self.schema_delete_out,
        ) = self.get_schemas()
        self.path_schema = self._generate_path_schema()
        self.filters_schema = self._generate_filters_schema()
        self.model_verbose_name = (
            self.model_verbose_name
            or get_ninja_aio_meta_attr(self.model, "verbose_name")
            or self.model._meta.verbose_name.capitalize()
        )
        self.model_verbose_name_plural = (
            self.model_verbose_name_plural
            or get_ninja_aio_meta_attr(self.model, "verbose_name_plural")
            or self.model._meta.verbose_name_plural.capitalize()
        )
        self.router_tag = self.router_tag or self.model_verbose_name
        self.router_tags = self.router_tags or tags or [self.router_tag]
        self.router = Router(tags=self.router_tags)
        self.append_slash = getattr(settings, "NINJA_AIO_APPEND_SLASH", True)
        self.path = "/" if self.append_slash else ""
        self.get_path = ""
        self.get_path_retrieve = f"{{{self.model_util.model_pk_name}}}"
        self.path_retrieve = (
            f"{self.get_path_retrieve}/"
            if self.append_slash
            else self.get_path_retrieve
        )
        self.api_route_path = (
            self.api_route_path
            or prefix
            or self.model_util.verbose_name_path_resolver()
        )
        self.bulk_path = "bulk/" if self.append_slash else "bulk"
        self.bulk_update_schema = self._generate_bulk_update_schema()
        self.bulk_delete_schema = self._generate_bulk_delete_schema()
        self.m2m_api = (
            None
            if not self.m2m_relations
            else ManyToManyAPI(relations=self.m2m_relations, view_set=self)
        )
        self._validate_mode_hooks()
        logger.debug(
            f"APIViewSet initialized for {self.model.__name__} at /{self.api_route_path}"
        )

    @property
    def _crud_views(self) -> dict[str, tuple[Schema | None, Callable]]:
        """
        Mapping of CRUD operation name to (response schema, view factory).
        """
        create_factory = self.create_view if self.execution_mode == "sync" else self.acreate_view
        list_factory = self.list_view if self.execution_mode == "sync" else self.alist_view
        return {
            "create": (self.schema_in, create_factory),
            "list": (self.schema_out, list_factory),
            "retrieve": (self.schema_out, self.retrieve_view if self.execution_mode == "sync" else self.aretrieve_view),
            "update": (self.schema_update, self.update_view if self.execution_mode == "sync" else self.aupdate_view),
            "delete": (None, self.delete_view if self.execution_mode == "sync" else self.adelete_view),
        }

    @property
    def _bulk_views(self) -> dict[str, tuple[Schema | None, Callable]]:
        """
        Mapping of bulk operation name to (schema, view factory).
        Only operations listed in bulk_operations are included.
        """
        mapping = {
            "create": (self.schema_in, self._by_mode(self.bulk_create_view, self.abulk_create_view)),
            "update": (self.bulk_update_schema, self._by_mode(self.bulk_update_view, self.abulk_update_view)),
            "delete": (None, self._by_mode(self.bulk_delete_view, self.abulk_delete_view)),
        }
        return {k: v for k, v in mapping.items() if k in self.bulk_operations}

    def _by_mode(self, sync_factory: Callable, async_factory: Callable) -> Callable:
        return sync_factory if self.execution_mode == "sync" else async_factory

    def _check_relations_filters(self, filter: str) -> bool:
        return filter in getattr(self, "relations_filters_fields", [])

    def _check_match_cases_filters(self, filter: str) -> bool:
        return filter in getattr(self, "filters_match_cases_fields", [])

    def _is_special_filter(self, filter: str) -> bool:
        return self._check_relations_filters(filter) or self._check_match_cases_filters(
            filter
        )

    def _is_lookup_suffix(self, part: str) -> bool:
        """
        Check if a part is a valid Django lookup suffix.

        Args:
            part: The part to check

        Returns:
            bool: True if the part is a valid lookup suffix
        """
        return part in VALID_DJANGO_LOOKUPS

    def _get_related_model(self, field: Model) -> type[Model] | None:
        """
        Extract the related model from a field if it exists.

        Args:
            field: The Django field object

        Returns:
            Model class or None
        """
        if hasattr(field, "related_model") and field.related_model:
            return field.related_model
        if (
            hasattr(field, "remote_field")
            and field.remote_field
            and hasattr(field.remote_field, "model")
        ):
            return field.remote_field.model
        return None

    def _validate_non_relation_field(self, parts: list[str], i: int) -> bool:
        """
        Validate a non-relation field that appears before the end of the path.

        Args:
            parts: List of field path parts
            i: Current index in parts

        Returns:
            bool: True if valid, False otherwise
        """
        if i >= len(parts) - 1:
            return True
        next_part = parts[i + 1]
        return self._is_lookup_suffix(next_part)

    def _validate_filter_field(self, field_path: str) -> bool:
        """
        Validate that a filter field path corresponds to valid model fields.

        Security: Prevents field injection attacks by ensuring only valid model
        fields can be used in filters.

        Args:
            field_path: The field path to validate (e.g., "name", "author__name")

        Returns:
            bool: True if the field path is valid, False otherwise

        Examples:
            "name" -> validates against direct model field
            "author__name" -> validates author is a relation, then name on related model
            "created_at__gte" -> validates created_at field, lookup suffix is allowed
        """
        if not field_path:
            return False

        parts = field_path.split("__")
        current_model = self.model

        # Iterate through the path, validating each part
        for i, part in enumerate(parts):
            # Check if this is the last part and might be a lookup suffix
            is_last_part = i == len(parts) - 1
            if is_last_part and self._is_lookup_suffix(part):
                return True

            try:
                field = current_model._meta.get_field(part)
            except (FieldDoesNotExist, AttributeError):
                logger.debug(
                    f"Filter field validation failed: '{part}' not found on {current_model.__name__}"
                )
                return False

            # If this is a relation field and not the last part, traverse to related model
            related_model = self._get_related_model(field)
            if related_model and not is_last_part:
                current_model = related_model
            elif not is_last_part:
                # Non-relation field in the middle - must be followed by a lookup suffix
                if not self._validate_non_relation_field(parts, i):
                    return False

        return True

    def _auth_view(self, view_type: str) -> list | None:
        """
        Resolve auth for an HTTP verb: HEAD follows GET, PUT follows PATCH, and verbs
        without a specific setting (or set to NOT_SET) fall back to self.auth.
        """
        verb = {"head": "get", "put": "patch"}.get(view_type, view_type)
        auth = getattr(self, f"{verb}_auth", NOT_SET)
        return auth if auth is not NOT_SET else self.auth

    def get_view_auth(self) -> list | None:
        """Get authentication configuration for GET endpoints."""
        return self._auth_view("get")

    def post_view_auth(self) -> list | None:
        """Get authentication configuration for POST endpoints."""
        return self._auth_view("post")

    def patch_view_auth(self) -> list | None:
        """Get authentication configuration for PATCH endpoints."""
        return self._auth_view("patch")

    def delete_view_auth(self) -> list | None:
        """Get authentication configuration for DELETE endpoints."""
        return self._auth_view("delete")

    def _generate_schema(self, fields: dict, name: str) -> Schema:
        """
        Dynamically build a Pydantic model for path / filter schemas.
        """
        return create_model(f"{self.model_util.model_name}{name}", **fields)

    def _generate_path_schema(self) -> Schema:
        """
        Schema containing only the primary key field for path resolution.
        """
        return self._generate_schema(
            {self.model_util.model_pk_name: self.model_util.pk_field_type}, "PathSchema"
        )

    def _generate_filters_schema(self) -> Schema:
        """
        Build filters schema from query_params definition.
        Includes an 'ordering' field when ordering_fields is configured.
        """
        fields = dict(self.query_params)
        if self.ordering_fields:
            fields["ordering"] = (str, None)
        return self._generate_schema(fields, "FiltersSchema")

    def _apply_list_filters(self, qs: QuerySet, filters: Schema | None) -> QuerySet:
        if filters is None and not self.ordering_fields:
            return qs
        filters_dict, ordering_value = self._list_filter_data(filters)
        if filters_dict:
            qs = self.query_params_handler(qs, filters_dict)
        return self._apply_ordering(qs, ordering_value)

    async def _aapply_list_filters(
        self,
        qs: QuerySet,
        filters: Schema | None,
    ) -> QuerySet:
        """
        Apply query-param filters and ordering to a queryset.

        Returns the filtered and ordered queryset.
        """
        if filters is None and not self.ordering_fields:
            return qs
        filters_dict, ordering_value = self._list_filter_data(filters)
        if filters_dict:
            qs = await self.aquery_params_handler(qs, filters_dict)
        return self._apply_ordering(qs, ordering_value)

    def _list_filter_data(self, filters: Schema | None) -> tuple[dict, str | None]:
        values = filters.model_dump() if filters is not None else {}
        ordering = values.pop("ordering", None) if self.ordering_fields else None
        return values, ordering

    @staticmethod
    def _get_page_params(
        paginator: AsyncPaginationBase, pagination_input: Schema
    ) -> tuple[int, int]:
        """
        Extract (offset, page_size) from any pagination class input.
        """
        if hasattr(pagination_input, "page"):
            page_size = paginator._get_page_size(
                getattr(pagination_input, "page_size", None)
            )
            offset = (pagination_input.page - 1) * page_size
        else:
            page_size = getattr(pagination_input, "limit", 100)
            offset = getattr(pagination_input, "offset", 0)
        return offset, page_size

    def _apply_ordering(self, queryset: QuerySet, ordering_value: str | None) -> QuerySet:
        """
        Apply ordering to the queryset based on ordering_fields configuration.

        Parses a comma-separated ordering string, validates each field against
        ordering_fields, and applies valid fields via queryset.order_by().
        Falls back to default_ordering when no valid fields are provided.
        """
        if not self.ordering_fields:
            return queryset

        if ordering_value:
            valid = []
            for field in ordering_value.split(","):
                field = field.strip()
                if not field:
                    continue
                bare = field.lstrip("-")
                if bare in self.ordering_fields:
                    valid.append(field)
            if valid:
                return queryset.order_by(*valid)

        if self.default_ordering:
            if isinstance(self.default_ordering, str):
                return queryset.order_by(self.default_ordering)
            return queryset.order_by(*self.default_ordering)

        return queryset

    def _get_pk(self, data: Schema) -> int | str:
        """
        Extract pk from a path schema instance.
        """
        return getattr(data, self.model_util.model_pk_name)

    def get_schemas(self) -> ViewSchemas:
        """
        Resolve the view schemas: explicit attributes win, missing ones are
        generated by the ModelSerializer or serializer_class when available.

        schema_create_out / schema_update_out fall back to schema_out;
        schema_delete_out stays None (204 No Content) unless set.
        """
        schema_out = self._resolve_schema(self.schema_out, "read")
        return ViewSchemas(
            schema_out=schema_out,
            schema_detail=self._resolve_schema(self.schema_detail, "detail"),
            schema_in=self._resolve_schema(self.schema_in, "create"),
            schema_update=self._resolve_schema(self.schema_update, "update"),
            schema_create_out=self.schema_create_out or schema_out,
            schema_update_out=self.schema_update_out or schema_out,
            schema_delete_out=self.schema_delete_out,
        )

    def _resolve_schema(
        self, explicit: type[Schema] | None, kind: str
    ) -> type[Schema] | None:
        if explicit is not None:
            return explicit
        source = (
            self.model
            if isinstance(self.model, ModelSerializerMeta)
            else self.serializer_class
        )
        return None if source is None else source.get_schema(kind)

    async def aquery_params_handler(
        self, queryset: QuerySet[ModelSerializer], filters: dict
    ) -> QuerySet:
        """
        Override to apply custom filtering logic for list_view.
        filters is already validated and dumped.
        Return the (possibly modified) queryset.
        """
        return queryset

    def query_params_handler(
        self, queryset: QuerySet[ModelSerializer], filters: dict
    ) -> QuerySet:
        """Synchronous counterpart of aquery_params_handler, used by sync endpoints."""
        return queryset

    async def aon_before_object_operation(self, request: HttpRequest, operation: str, obj: ModelT) -> None:
        """Hook called after fetch, before mutation (retrieve/update/delete). Override for object-level checks."""

    def on_before_object_operation(
        self, request: HttpRequest, operation: str, obj: ModelT
    ) -> None:
        """Synchronous counterpart of aon_before_object_operation, used by sync endpoints."""

    def on_list_queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        """Hook to filter the list queryset before pagination. Override for row-level filtering."""
        return queryset

    _has_object_hooks: bool = False
    """Set to True by mixins that override aon_before_object_operation."""

    _mode_hooks: tuple[tuple[str, str], ...] = (
        ("aon_before_operation", "on_before_operation"),
        ("aon_before_object_operation", "on_before_object_operation"),
        ("aquery_params_handler", "query_params_handler"),
        ("_aapply_list_filters", "_apply_list_filters"),
    )
    """(async, sync) hook pairs that must be overridden together for the modes in use."""

    def _modes_in_use(self) -> set[str]:
        modes = {self.execution_mode}
        for _, method, _ in self._iter_actions():
            modes.add("async" if inspect.iscoroutinefunction(method) else "sync")
        return modes

    def _hook_owner(self, name: str) -> type:
        return next(klass for klass in type(self).__mro__ if name in klass.__dict__)

    def _validate_mode_hooks(self) -> None:
        """Fail at startup when an overridden hook would be skipped by an endpoint mode."""
        self._validate_hook_naming()
        for mode in sorted(self._modes_in_use()):
            self._validate_hook_owners(mode)

    def _validate_hook_naming(self) -> None:
        for async_name, sync_name in self._mode_hooks:
            if inspect.iscoroutinefunction(getattr(self, sync_name)):
                raise ImproperlyConfigured(
                    f"{type(self).__name__}.{sync_name} is async; rename it to "
                    f"{async_name} (sync hooks use the plain name)."
                )
            if not inspect.iscoroutinefunction(getattr(self, async_name)):
                raise ImproperlyConfigured(f"{type(self).__name__}.{async_name} must be async.")

    def _validate_hook_owners(self, mode: str) -> None:
        for async_name, sync_name in self._mode_hooks:
            active, inactive = (
                (sync_name, async_name) if mode == "sync" else (async_name, sync_name)
            )
            active_owner = self._hook_owner(active)
            inactive_owner = self._hook_owner(inactive)
            if inactive_owner is not active_owner and issubclass(
                inactive_owner, active_owner
            ):
                raise ImproperlyConfigured(
                    f"{type(self).__name__} overrides {inactive}() but not "
                    f"{active}(), which its {mode} endpoints call."
                )

    async def _arun_object_hooks(
        self,
        request: HttpRequest,
        operation: str,
        pk: int | str,
        is_for: str | None = None,
    ) -> ModelT | None:
        """
        Run view-level and object-level hooks, returning the fetched object.

        Combines aon_before_operation, get_object, and aon_before_object_operation
        into a single call used by retrieve, update, and delete views.
        Skips the object fetch when no object-level hooks are registered
        (avoids a redundant query when update_s/delete_s will fetch again).
        """
        await self.aon_before_operation(request, operation)
        if not self._has_object_hooks:
            return None
        obj = await self._get_serializer().aget(pk, request=request, optimize_for=is_for)
        await self.aon_before_object_operation(request, operation, obj)
        return obj

    def _run_object_hooks(
        self, request: HttpRequest, operation: str, pk: int | str,
        is_for: str | None = None,
    ) -> ModelT | None:
        self.on_before_operation(request, operation)
        if not self._has_object_hooks:
            return None
        obj = self._get_serializer().get(pk, request=request, optimize_for=is_for)
        self.on_before_object_operation(request, operation, obj)
        return obj

    def _get_serializer(self):
        """Return the CRUD facade: the serializer, or model_util for schema-only viewsets."""
        if isinstance(self.model, ModelSerializerMeta):
            return self.model
        return self.serializer_class or self.model_util

    def _relation_plan(self, schema: type[Schema]) -> model_transformations.RelationPlan:
        return model_transformations.schema_relation_plan(self.model_util.model, schema)

    def _dump(self, obj: ModelT, schema: type[Schema]) -> dict:
        plan = self._relation_plan(schema)
        relations = (*plan.select_related, *plan.prefetch_related)
        if relations:
            prefetch_related_objects([obj], *relations)
        return self._get_serializer().model_dump(obj, schema=schema)

    async def _adump(self, obj: ModelT, schema: type[Schema]) -> dict:
        return await self._get_serializer().amodel_dump(obj, schema=schema)

    def _register_generated(self, route: GeneratedRoute) -> Callable:
        transaction_decorator = None
        if route.atomic:
            transaction_decorator = (
                transaction.atomic if self.execution_mode == "sync" else aatomic
            )
        decorated = decorate_view(
            transaction_decorator, unique_view(self, plural=route.plural), *route.decorators
        )(route.handler)
        return getattr(self.router, route.method.value)(
            route.path,
            auth=route.auth,
            summary=route.summary,
            description=route.description,
            response=route.response,
        )(decorated)

    def create(self, request: HttpRequest, data: Schema) -> Status:
        """Execute a synchronous create. Override to customize the operation."""
        self.on_before_operation(request, "create")
        obj = self._get_serializer().create(data, request=request)
        return Status(201, self._dump(obj, self.schema_create_out))

    async def acreate(self, request: HttpRequest, data: Schema) -> Status:
        """Execute an asynchronous create. Override to customize the operation."""
        await self.aon_before_operation(request, "create")
        obj = await self._get_serializer().acreate(data, request=request)
        return Status(201, await self._adump(obj, self.schema_create_out))

    def _register_create(self, handler: Callable) -> Callable:
        return self._register_generated(
            GeneratedRoute(
                method=HttpMethod.POST,
                path=self.path,
                auth=self.post_view_auth(),
                summary=f"Create {self.model_verbose_name}",
                description=self.create_docs,
                response={201: self.schema_create_out, self.error_codes: self.error_schema},
                handler=handler,
                decorators=tuple(self.extra_decorators.create),
                atomic=True,
            )
        )

    def create_view(self) -> Callable:
        """Register the synchronous create endpoint."""
        def create(request: HttpRequest, data: self.schema_in):  # type: ignore
            return self.create(request, data)

        return self._register_create(create)

    def acreate_view(self) -> Callable:
        """Register the asynchronous create endpoint."""
        async def create(request: HttpRequest, data: self.schema_in):  # type: ignore
            return await self.acreate(request, data)

        return self._register_create(create)

    def list(
        self, request: HttpRequest, filters: Schema | None, ninja_pagination: Schema,
    ) -> Status:
        """Execute a synchronous paginated list. Override to customize the operation."""
        paginator, ninja_pagination = self._prepare_list_pagination(ninja_pagination)
        self.on_before_operation(request, "list")
        qs = self._get_serializer().get_queryset(request=request, optimize_for="read")
        qs = self.on_list_queryset(request, qs)
        qs = self._apply_list_filters(qs, filters)
        count = qs.count()
        offset, page_size = self._get_page_params(paginator, ninja_pagination)
        sliced_qs = model_transformations.apply_relation_plan(
            qs[offset : offset + page_size], self._relation_plan(self.schema_out)
        )
        items = self._get_serializer().model_dumps(list(sliced_qs), schema=self.schema_out)
        return Status(200, {"items": items, "count": count})

    async def alist(
        self, request: HttpRequest, filters: Schema | None, ninja_pagination: Schema,
    ) -> Status:
        """Execute an asynchronous paginated list. Override to customize the operation."""
        paginator, ninja_pagination = self._prepare_list_pagination(ninja_pagination)
        await self.aon_before_operation(request, "list")
        qs = await self._get_serializer().aget_queryset(request=request, optimize_for="read")
        qs = self.on_list_queryset(request, qs)
        qs = await self._aapply_list_filters(qs, filters)
        count = await qs.acount()
        offset, page_size = self._get_page_params(paginator, ninja_pagination)
        sliced_qs = qs[offset : offset + page_size]
        items = await self._get_serializer().amodel_dumps(sliced_qs, schema=self.schema_out)
        return Status(200, {"items": items, "count": count})

    def _prepare_list_pagination(self, pagination_input: Schema) -> tuple[AsyncPaginationBase, Schema]:
        paginator = self.pagination_class()
        if not isinstance(pagination_input, self.pagination_class.Input):
            pagination_input = self.pagination_class.Input()
        return paginator, pagination_input

    def _register_list(self, handler: Callable) -> Callable:
        paginated_schema = create_model(
            f"Paginated{self.schema_out.__name__}",
            __base__=Schema,
            items=(List[self.schema_out], ...),
            count=(int, ...),
        )
        return self._register_generated(
            GeneratedRoute(
                method=HttpMethod.GET, path=self.get_path, auth=self.get_view_auth(),
                summary=f"List {self.model_verbose_name_plural}", description=self.list_docs,
                response={200: paginated_schema, self.error_codes: self.error_schema},
                handler=handler, decorators=tuple(self.extra_decorators.list), plural=True,
            )
        )

    def list_view(self) -> Callable:
        """Register the synchronous list endpoint."""
        input_class = self.pagination_class.Input

        def list(
            request: HttpRequest,
            filters: Query[self.filters_schema] = None,  # type: ignore
            ninja_pagination: input_class = Query(input_class()),  # type: ignore
        ):
            return self.list(request, filters, ninja_pagination)

        return self._register_list(list)

    def alist_view(self) -> Callable:
        """Register the asynchronous list endpoint."""
        input_class = self.pagination_class.Input

        async def list(
            request: HttpRequest,
            filters: Query[self.filters_schema] = None,  # type: ignore
            ninja_pagination: input_class = Query(input_class()),  # type: ignore
        ):
            return await self.alist(request, filters, ninja_pagination)

        return self._register_list(list)

    def _get_retrieve_schema(self) -> type[Schema]:
        """
        Return the schema to use for retrieve endpoint.
        Uses schema_detail if available, otherwise falls back to schema_out.
        """
        return self.schema_detail or self.schema_out

    def retrieve(self, request: HttpRequest, pk: Schema) -> Status:
        """Execute a synchronous retrieve. Override to customize the operation."""
        obj_pk = self._get_pk(pk)
        is_for = "detail" if self.schema_detail else "read"
        obj = self._run_object_hooks(request, "retrieve", obj_pk, is_for)
        if obj is None:
            obj = self._get_serializer().get(obj_pk, request=request, optimize_for=is_for)
        return Status(200, self._dump(obj, self._get_retrieve_schema()))

    async def aretrieve(self, request: HttpRequest, pk: Schema) -> Status:
        """Execute an asynchronous retrieve. Override to customize the operation."""
        obj_pk = self._get_pk(pk)
        is_for = "detail" if self.schema_detail else "read"
        obj = await self._arun_object_hooks(request, "retrieve", obj_pk, is_for=is_for)
        if obj is None:
            obj = await self._get_serializer().aget(obj_pk, request=request, optimize_for=is_for)
        return Status(200, await self._adump(obj, self._get_retrieve_schema()))

    def _register_retrieve(self, handler: Callable) -> Callable:
        retrieve_schema = self._get_retrieve_schema()
        return self._register_generated(
            GeneratedRoute(
                method=HttpMethod.GET, path=self.get_path_retrieve, auth=self.get_view_auth(),
                summary=f"Retrieve {self.model_verbose_name}", description=self.retrieve_docs,
                response={200: retrieve_schema, self.error_codes: self.error_schema},
                handler=handler, decorators=tuple(self.extra_decorators.retrieve),
            )
        )

    def retrieve_view(self) -> Callable:
        """Register the synchronous retrieve endpoint."""
        def retrieve(request: HttpRequest, pk: Path[self.path_schema]):  # type: ignore
            return self.retrieve(request, pk)

        return self._register_retrieve(retrieve)

    def aretrieve_view(self) -> Callable:
        """Register the asynchronous retrieve endpoint."""
        async def retrieve(request: HttpRequest, pk: Path[self.path_schema]):  # type: ignore
            return await self.aretrieve(request, pk)

        return self._register_retrieve(retrieve)

    def update(self, request: HttpRequest, data: Schema, pk: Schema) -> Status:
        """Execute a synchronous update. Override to customize the operation."""
        obj_pk = self._get_pk(pk)
        loaded = self._run_object_hooks(request, "update", obj_pk)
        self._check_update_payload(data)
        obj = self._get_serializer().update(loaded or obj_pk, data, request=request)
        return Status(200, self._dump(obj, self.schema_update_out))

    async def aupdate(self, request: HttpRequest, data: Schema, pk: Schema) -> Status:
        """Execute an asynchronous update. Override to customize the operation."""
        obj_pk = self._get_pk(pk)
        loaded = await self._arun_object_hooks(request, "update", obj_pk)
        self._check_update_payload(data)
        obj = await self._get_serializer().aupdate(loaded or obj_pk, data, request=request)
        return Status(200, await self._adump(obj, self.schema_update_out))

    def _check_update_payload(self, data: Schema) -> None:
        if self.require_update_fields and not data.model_dump(exclude_unset=True):
            raise SerializeError("No fields provided for update.")

    def _register_update(self, handler: Callable) -> Callable:
        return self._register_generated(
            GeneratedRoute(
                method=HttpMethod.PATCH, path=self.path_retrieve, auth=self.patch_view_auth(),
                summary=f"Update {self.model_verbose_name}", description=self.update_docs,
                response={200: self.schema_update_out, self.error_codes: self.error_schema},
                handler=handler, decorators=tuple(self.extra_decorators.update), atomic=True,
            )
        )

    def update_view(self) -> Callable:
        """Register the synchronous update endpoint."""
        def update(
            request: HttpRequest,
            data: self.schema_update,  # type: ignore
            pk: Path[self.path_schema],  # type: ignore
        ):
            return self.update(request, data, pk)

        return self._register_update(update)

    def aupdate_view(self) -> Callable:
        """Register the asynchronous update endpoint."""
        async def update(
            request: HttpRequest,
            data: self.schema_update,  # type: ignore
            pk: Path[self.path_schema],  # type: ignore
        ):
            return await self.aupdate(request, data, pk)

        return self._register_update(update)

    def delete(self, request: HttpRequest, pk: Schema) -> Status:
        """Execute a synchronous delete. Override to customize the operation."""
        obj_pk = self._get_pk(pk)
        obj = self._run_object_hooks(request, "delete", obj_pk)
        serialized = None
        if self.schema_delete_out:
            obj = obj or self._get_serializer().get(obj_pk, request=request)
            serialized = self._dump(obj, self.schema_delete_out)
        self._get_serializer().destroy(obj or obj_pk, request=request)
        return self._delete_response(serialized)

    async def adelete(self, request: HttpRequest, pk: Schema) -> Status:
        """Execute an asynchronous delete. Override to customize the operation."""
        obj_pk = self._get_pk(pk)
        obj = await self._arun_object_hooks(request, "delete", obj_pk)
        serialized = None
        if self.schema_delete_out:
            obj = obj or await self._get_serializer().aget(obj_pk, request=request)
            serialized = await self._adump(obj, self.schema_delete_out)
        await self._get_serializer().adestroy(obj or obj_pk, request=request)
        return self._delete_response(serialized)

    def _delete_response(self, serialized: dict | None) -> Status:
        return Status(200, serialized) if self.schema_delete_out else Status(204, None)

    def _register_delete(self, handler: Callable) -> Callable:
        response = (
            {200: self.schema_delete_out, self.error_codes: self.error_schema}
            if self.schema_delete_out
            else {204: None, self.error_codes: self.error_schema}
        )
        return self._register_generated(
            GeneratedRoute(
                method=HttpMethod.DELETE, path=self.path_retrieve, auth=self.delete_view_auth(),
                summary=f"Delete {self.model_verbose_name}", description=self.delete_docs,
                response=response, handler=handler,
                decorators=tuple(self.extra_decorators.delete), atomic=True,
            )
        )

    def delete_view(self) -> Callable:
        """Register the synchronous delete endpoint."""
        def delete(request: HttpRequest, pk: Path[self.path_schema]):  # type: ignore
            return self.delete(request, pk)

        return self._register_delete(delete)

    def adelete_view(self) -> Callable:
        """Register the asynchronous delete endpoint."""
        async def delete(request: HttpRequest, pk: Path[self.path_schema]):  # type: ignore
            return await self.adelete(request, pk)

        return self._register_delete(delete)

    @staticmethod
    def _bulk_result(success: list, errors: list) -> dict:
        """Format bulk operation result into standard response structure."""
        return {
            "success": {"count": len(success), "details": success},
            "errors": {"count": len(errors), "details": errors},
        }

    def _bulk_response(self, result: BulkResult, details: List | None = None) -> Status:
        """Render a BulkResult with the legacy wire format."""
        if details is None:
            extract = self._get_bulk_detail_extractor() or (lambda obj: obj.pk)
            details = [extract(obj) for obj in result.succeeded]
        return Status(
            200, self._bulk_result(details, [failure.error for failure in result.failed])
        )

    def _get_bulk_detail_extractor(self) -> Callable | None:
        """
        Return a callable that extracts detail info from a model instance
        based on bulk_response_fields configuration.

        Returns None when default PK behavior should be used.
        """
        fields = self.bulk_response_fields
        if fields is None:
            return None
        if isinstance(fields, str):
            return lambda obj: getattr(obj, fields)
        return lambda obj: {f: getattr(obj, f) for f in fields}

    def _get_bulk_detail_fields(self) -> list[str] | None:
        """
        Return the list of field names for bulk delete detail extraction.

        bulk_delete_s doesn't have model instances, so it needs field names
        to query with values() before deletion.
        """
        fields = self.bulk_response_fields
        if fields is None:
            return None
        if isinstance(fields, str):
            return [fields]
        return fields

    def _generate_bulk_update_schema(self) -> Schema | None:
        """
        Dynamically build a schema combining the PK field (required) with update fields.
        Returns None if schema_update is not available.
        """
        if self.schema_update is None:
            return None
        return create_model(
            f"{self.model_util.model_name}BulkUpdateSchema",
            __base__=self.schema_update,
            **{self.model_util.model_pk_name: (self.model_util.pk_field_type, ...)},
        )

    def _generate_bulk_delete_schema(self) -> Schema:
        """
        Dynamically build a schema with a list of PK values for bulk deletion.
        """
        pk_python_type = self.model_util.pk_field_type
        return create_model(
            f"{self.model_util.model_name}BulkDeleteSchema",
            ids=(List[pk_python_type], ...),
        )

    def bulk_create(self, request: HttpRequest, data: List[Schema]) -> Status:
        """Execute a synchronous bulk create. Override to customize the operation."""
        self.on_before_operation(request, "bulk_create")
        return self._bulk_response(self._get_serializer().bulk_create(data, request=request))

    async def abulk_create(self, request: HttpRequest, data: List[Schema]) -> Status:
        """Execute an asynchronous bulk create. Override to customize the operation."""
        await self.aon_before_operation(request, "bulk_create")
        return self._bulk_response(
            await self._get_serializer().abulk_create(data, request=request)
        )

    def _register_bulk(
        self, method: HttpMethod, auth, summary: str, description: str, handler: Callable, decorators
    ) -> Callable:
        return self._register_generated(
            GeneratedRoute(
                method=method, path=self.bulk_path, auth=auth,
                summary=f"{summary} {self.model_verbose_name_plural}", description=description,
                response={200: BulkResultSchema, self.error_codes: self.error_schema},
                handler=handler, decorators=tuple(decorators), plural=True,
            )
        )

    def _register_bulk_create(self, handler: Callable) -> Callable:
        return self._register_bulk(
            HttpMethod.POST, self.post_view_auth(), "Bulk Create", self.bulk_create_docs,
            handler, self.extra_decorators.bulk_create,
        )

    def bulk_create_view(self) -> Callable:
        """Register the synchronous bulk create endpoint."""
        def bulk_create(request: HttpRequest, data: List[self.schema_in]):  # type: ignore
            return self.bulk_create(request, data)

        return self._register_bulk_create(bulk_create)

    def abulk_create_view(self) -> Callable:
        """Register the asynchronous bulk create endpoint."""
        async def bulk_create(request: HttpRequest, data: List[self.schema_in]):  # type: ignore
            return await self.abulk_create(request, data)

        return self._register_bulk_create(bulk_create)

    def bulk_update(self, request: HttpRequest, data: List[Schema]) -> Status:
        """Execute a synchronous bulk update. Override to customize the operation."""
        self.on_before_operation(request, "bulk_update")
        items, rejected = self._prepare_bulk_update(data)
        result = self._get_serializer().bulk_update(
            [item for _, item in items], request=request
        )
        return self._bulk_response(self._merge_bulk_rejections(result, items, rejected))

    async def abulk_update(self, request: HttpRequest, data: List[Schema]) -> Status:
        """Execute an asynchronous bulk update. Override to customize the operation."""
        await self.aon_before_operation(request, "bulk_update")
        items, rejected = self._prepare_bulk_update(data)
        result = await self._get_serializer().abulk_update(
            [item for _, item in items], request=request
        )
        return self._bulk_response(self._merge_bulk_rejections(result, items, rejected))

    def _prepare_bulk_update(self, data: List[Schema]) -> tuple[List, List[BulkFailure]]:
        """Split items into ``(index, (pk, update_data))`` pairs and rejected empty payloads."""
        pk_name = self.model_util.model_pk_name
        items, rejected = [], []
        for index, item in enumerate(data):
            fields = item.model_dump(exclude_unset=True)
            pk = fields.pop(pk_name)
            if self.require_update_fields and not fields:
                rejected.append(
                    bulk_failure(index, SerializeError("No fields provided for update."), pk)
                )
            else:
                items.append((index, (pk, self.schema_update(**fields))))
        return items, rejected

    @staticmethod
    def _merge_bulk_rejections(
        result: BulkResult, items: List, rejected: List[BulkFailure]
    ) -> BulkResult:
        positions = [index for index, _ in items]
        failed = [replace(failure, index=positions[failure.index]) for failure in result.failed]
        return BulkResult(
            result.succeeded, sorted(failed + rejected, key=lambda failure: failure.index)
        )

    def _register_bulk_update(self, handler: Callable) -> Callable:
        return self._register_bulk(
            HttpMethod.PATCH, self.patch_view_auth(), "Bulk Update", self.bulk_update_docs,
            handler, self.extra_decorators.bulk_update,
        )

    def bulk_update_view(self) -> Callable:
        """Register the synchronous bulk update endpoint."""
        def bulk_update(request: HttpRequest, data: List[self.bulk_update_schema]):  # type: ignore
            return self.bulk_update(request, data)

        return self._register_bulk_update(bulk_update)

    def abulk_update_view(self) -> Callable:
        """Register the asynchronous bulk update endpoint."""
        async def bulk_update(request: HttpRequest, data: List[self.bulk_update_schema]):  # type: ignore
            return await self.abulk_update(request, data)

        return self._register_bulk_update(bulk_update)

    def bulk_delete(self, request: HttpRequest, data: Schema) -> Status:
        """Execute a synchronous bulk delete. Override to customize the operation."""
        self.on_before_operation(request, "bulk_delete")
        found = {
            obj.pk: obj
            for obj in self._get_serializer().get_queryset(request=request).filter(pk__in=data.ids)
        }
        result = self._get_serializer().bulk_destroy(
            [found.get(pk, pk) for pk in data.ids], request=request
        )
        return self._bulk_delete_response(result, found)

    async def abulk_delete(self, request: HttpRequest, data: Schema) -> Status:
        """Execute an asynchronous bulk delete. Override to customize the operation."""
        await self.aon_before_operation(request, "bulk_delete")
        queryset = await self._get_serializer().aget_queryset(request=request)
        found = {obj.pk: obj async for obj in queryset.filter(pk__in=data.ids)}
        result = await self._get_serializer().abulk_destroy(
            [found.get(pk, pk) for pk in data.ids], request=request
        )
        return self._bulk_delete_response(result, found)

    def _bulk_delete_response(self, result: BulkResult, found: dict) -> Status:
        fields = self._get_bulk_detail_fields()
        if not fields:
            return self._bulk_response(result, list(result.succeeded))
        details = {
            pk: obj.serializable_value(fields[0])
            if len(fields) == 1
            else {name: obj.serializable_value(name) for name in fields}
            for pk, obj in found.items()
        }
        return self._bulk_response(result, [details[pk] for pk in result.succeeded])

    def _register_bulk_delete(self, handler: Callable) -> Callable:
        return self._register_bulk(
            HttpMethod.DELETE, self.delete_view_auth(), "Bulk Delete", self.bulk_delete_docs,
            handler, self.extra_decorators.bulk_delete,
        )

    def bulk_delete_view(self) -> Callable:
        """Register the synchronous bulk delete endpoint."""
        def bulk_delete(request: HttpRequest, data: self.bulk_delete_schema):  # type: ignore
            return self.bulk_delete(request, data)

        return self._register_bulk_delete(bulk_delete)

    def abulk_delete_view(self) -> Callable:
        """Register the asynchronous bulk delete endpoint."""
        async def bulk_delete(request: HttpRequest, data: self.bulk_delete_schema):  # type: ignore
            return await self.abulk_delete(request, data)

        return self._register_bulk_delete(bulk_delete)

    def views(self):
        """
        Override to register custom non-CRUD endpoints on self.router.
        Use auth=self.auth or verb specific auth attributes if needed.
        """
        pass

    def _resolve_action_path(self, name: str, config: ActionConfig) -> str:
        url_path = super()._resolve_action_path(name, config)
        return f"{self.get_path_retrieve}/{url_path}" if config.detail else url_path

    def _action_summary_suffix(self) -> str:
        return f" {self.model_verbose_name}"

    def _action_name_suffix(self) -> str:
        return self.model_util.model_name

    def _rename_pk_param(self, handler: Callable) -> None:
        """Rename the generic 'pk' parameter to the model's actual PK name."""
        pk_name = self.model_util.model_pk_name
        sig = inspect.signature(handler)
        params = [
            p.replace(name=pk_name) if p.name == "pk" else p
            for p in sig.parameters.values()
        ]
        handler.__signature__ = sig.replace(parameters=params)

    def _build_on_handler(self, name: str, method: Callable) -> Callable:
        """
        Build a handler for ``@on``-decorated detail methods.

        Runs ``aon_before_operation``, fetches the object by pk, runs
        ``aon_before_object_operation``, then calls ``method(self, request, obj)``.
        Sync methods get the sync hooks and ORM calls. The returned function
        carries a ``__signature__`` that exposes ``(request, pk)`` to Ninja.
        """
        pk_name = self.model_util.model_pk_name

        if inspect.iscoroutinefunction(method):

            @functools.wraps(method)
            async def on_handler(request, **kwargs):
                await self.aon_before_operation(request, name)
                obj = await self._get_serializer().aget(kwargs.get(pk_name), request=request)
                await self.aon_before_object_operation(request, name, obj)
                return await method(self, request, obj)

        else:

            @functools.wraps(method)
            def on_handler(request, **kwargs):
                self.on_before_operation(request, name)
                obj = self._get_serializer().get(kwargs.get(pk_name), request=request)
                self.on_before_object_operation(request, name, obj)
                return method(self, request, obj)

        on_handler.__signature__ = inspect.Signature([
            inspect.Parameter(
                "request",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=HttpRequest,
            ),
            inspect.Parameter(
                pk_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Path[self.path_schema],
            ),
        ])
        return on_handler

    def _action_core_handler(
        self, name: str, method: Callable, config: ActionConfig, http_method: HttpMethod
    ) -> Callable:
        if config.prefetch_object and config.detail:
            return self._build_on_handler(name, method)
        handler = super()._action_core_handler(name, method, config, http_method)
        if config.detail:
            self._rename_pk_param(handler)
        return handler

    def _set_additional_views(self) -> Router:
        self.views()
        self._register_actions()
        if self.m2m_api is not None:
            self.m2m_api._add_views()

        for bulk_type, (schema, view) in self._bulk_views.items():
            bulk_key = f"bulk_{bulk_type}"
            if bulk_key not in self.disable and (
                schema is not None or bulk_type == "delete"
            ):
                self._operations[bulk_key] = view()
                logger.debug(
                    f"Registered bulk_{bulk_type} view for {self.model.__name__}"
                )
        return self.router

    def _add_views(self) -> Router:
        """
        Register CRUD (unless disabled), bulk, custom views, and M2M endpoints.
        If 'all' in disable only CRUD is skipped; bulk + M2M + custom still added.
        """
        super()._add_views()
        if "all" in self.disable:
            logger.debug(f"All CRUD views disabled for {self.model.__name__}")
            return self._set_additional_views()
        for views_type, (schema, view) in self._crud_views.items():
            if views_type not in self.disable and (
                schema is not None or views_type == "delete"
            ):
                self._operations[views_type] = view()
                logger.debug(
                    f"Registered {views_type} view for {self.model.__name__}"
                )
        return self._set_additional_views()


class ReadOnlyViewSet(APIViewSet[ModelT]):
    """
    ReadOnly viewset generating async List + Retrieve endpoints for a Django model.

    Usage:
        @api.viewset(model=MyModel)
        class MyModelReadOnlyViewSet(ReadOnlyViewSet):
            pass

        or

        class MyModelReadOnlyViewSet(ReadOnlyViewSet):
            model = MyModel
            api = api
        MyModelReadOnlyViewSet().add_views_to_route()
    """

    disable = ["create", "update", "delete"]


class WriteOnlyViewSet(APIViewSet[ModelT]):
    """
    WriteOnly viewset generating async Create + Update + Delete endpoints for a Django model.

    Usage:
        @api.viewset(model=MyModel)
        class MyModelWriteOnlyViewSet(WriteOnlyViewSet):
            pass

        or

        class MyModelWriteOnlyViewSet(WriteOnlyViewSet):
            model = MyModel
            api = api
    """

    disable = ["list", "retrieve"]
