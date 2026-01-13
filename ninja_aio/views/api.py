from typing import List

from ninja import NinjaAPI, Router, Schema, Path, Query
from ninja.constants import NOT_SET
from ninja.pagination import paginate, AsyncPaginationBase, PageNumberPagination
from django.http import HttpRequest
from django.db.models import Model, QuerySet
from django.conf import settings
from pydantic import create_model

from ninja_aio.schemas.helpers import ModelQuerySetSchema, QuerySchema, DecoratorsSchema

from ninja_aio.models import ModelSerializer, ModelUtil
from ninja_aio.schemas import (
    GenericMessageSchema,
    M2MRelationSchema,
)
from ninja_aio.helpers.api import ManyToManyAPI
from ninja_aio.types import ModelSerializerMeta, VIEW_TYPES
from ninja_aio.decorators import unique_view, decorate_view, aatomic
from ninja_aio.models import serializers

ERROR_CODES = frozenset({400, 401, 404})


class API:
    api: NinjaAPI = None
    router_tag: str = ""
    router_tags: list[str] = []
    api_route_path: str = ""
    auth: list | None = NOT_SET
    router: Router = None

    def views(self):
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

    def _add_views(self):
        for name in dir(self.__class__):
            method = getattr(self.__class__, name)
            if hasattr(method, "_api_register"):
                method._api_register(self)

    def add_views_to_route(self):
        return self.api.add_router(f"{self.api_route_path}", self._add_views())


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

    def _add_views(self):
        super()._add_views()
        self.views()
        return self.router


class APIViewSet(API):
    """
    Base viewset generating async CRUD + optional M2M endpoints for a Django model.

    Usage:
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
        m2m_relations: List of M2MRelationSchema describing related model, related_name, custom path, auth, filters.
        m2m_add / m2m_remove / m2m_get: Enable add/remove/get M2M operations.
        m2m_auth: Auth list for all M2M endpoints unless overridden per relation.

    Overridable hooks:
        views(): Register extra custom endpoints on self.router.
        query_params_handler(queryset, filters): Sync/Async hook to apply list filters.
        <related_name>_query_params_handler(queryset, filters): Async hook for per-M2M filtering.

    Error responses:
        All endpoints may return GenericMessageSchema for codes in ERROR_CODES (400,401,404).

    Internal:
        Dynamic path/filter schemas built with pydantic.create_model.
        unique_view decorator prevents duplicate registration.
    """

    model: ModelSerializer | Model
    serializer_class: serializers.Serializer | None = None
    schema_in: Schema | None = None
    schema_out: Schema | None = None
    schema_update: Schema | None = None
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

    def __init__(
        self,
        api: NinjaAPI = None,
        model: Model | ModelSerializer = None,
        prefix: str = None,
        tags: list[str] = None,
    ) -> None:
        self.api = api or self.api
        self.error_codes = ERROR_CODES
        self.model = model or self.model
        self.serializer: serializers.Serializer | None = (
            None if self.serializer_class is None else self.serializer_class()
        )
        self.model_util = (
            ModelUtil(self.model, serializer_class=self.serializer_class)
            if not isinstance(self.model, ModelSerializerMeta)
            else self.model.util
        )
        self.schema_out, self.schema_in, self.schema_update = self.get_schemas()
        self.path_schema = self._generate_path_schema()
        self.filters_schema = self._generate_filters_schema()
        self.model_verbose_name = (
            self.model_verbose_name or self.model._meta.verbose_name.capitalize()
        )
        self.model_verbose_name_plural = (
            self.model_verbose_name_plural
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
        self.m2m_api = (
            None
            if not self.m2m_relations
            else ManyToManyAPI(relations=self.m2m_relations, view_set=self)
        )

    @property
    def _crud_views(self):
        """
        Mapping of CRUD operation name to (response schema, view factory).
        """
        return {
            "create": (self.schema_in, self.create_view),
            "list": (self.schema_out, self.list_view),
            "retrieve": (self.schema_out, self.retrieve_view),
            "update": (self.schema_update, self.update_view),
            "delete": (None, self.delete_view),
        }

    def _auth_view(self, view_type: str):
        """
        Resolve auth for a specific HTTP verb; falls back to self.auth if NOT_SET.
        """
        auth = getattr(self, f"{view_type}_auth", None)
        return auth if auth is not NOT_SET else self.auth

    def get_view_auth(self):
        return self._auth_view("get")

    def post_view_auth(self):
        return self._auth_view("post")

    def patch_view_auth(self):
        return self._auth_view("patch")

    def delete_view_auth(self):
        return self._auth_view("delete")

    def _generate_schema(self, fields: dict, name: str) -> Schema:
        """
        Dynamically build a Pydantic model for path / filter schemas.
        """
        return create_model(f"{self.model_util.model_name}{name}", **fields)

    def _generate_path_schema(self):
        """
        Schema containing only the primary key field for path resolution.
        """
        return self._generate_schema(
            {self.model_util.model_pk_name: self.model_util.pk_field_type}, "PathSchema"
        )

    def _generate_filters_schema(self):
        """
        Build filters schema from query_params definition.
        """
        return self._generate_schema(self.query_params, "FiltersSchema")

    def _get_pk(self, data: Schema):
        """
        Extract pk from a path schema instance.
        """
        return data.model_dump()[self.model_util.model_pk_name]

    def _get_query_data(self) -> ModelQuerySetSchema:
        """
        Return default query data for list/retrieve views.
        """
        return (
            ModelQuerySetSchema()
            if not isinstance(self.model, ModelSerializerMeta)
            else self.model.query_util.read_config
        )

    def get_schemas(self):
        """
        Compute and return (schema_out, schema_in, schema_update).

        - If model is a ModelSerializer (ModelSerializerMeta), auto-generate read/create/update schemas.
        - Otherwise, use existing schemas or generate from serializer_class if provided.
        """
        # ModelSerializer case: prefer explicitly set schemas, otherwise generate from the model
        if isinstance(self.model, ModelSerializerMeta):
            return (
                self.schema_out or self.model.generate_read_s(),
                self.schema_in or self.model.generate_create_s(),
                self.schema_update or self.model.generate_update_s(),
            )

        # Non-ModelSerializer: start from provided schemas
        schema_out, schema_in, schema_update = (
            self.schema_out,
            self.schema_in,
            self.schema_update,
        )

        # If a serializer_class is available, generate from it
        if self.serializer_class:
            schema_in = schema_in or self.serializer_class.generate_create_s()
            schema_out = schema_out or self.serializer_class.generate_read_s()
            schema_update = schema_update or self.serializer_class.generate_update_s()

        return (schema_out, schema_in, schema_update)

    async def query_params_handler(
        self, queryset: QuerySet[ModelSerializer], filters: dict
    ):
        """
        Override to apply custom filtering logic for list_view.
        filters is already validated and dumped.
        Return the (possibly modified) queryset.
        """
        return queryset

    def create_view(self):
        """
        Register create endpoint.
        """

        @self.router.post(
            self.path,
            auth=self.post_view_auth(),
            summary=f"Create {self.model_verbose_name}",
            description=self.create_docs,
            response={201: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        @decorate_view(aatomic, unique_view(self), *self.extra_decorators.create)
        async def create(request: HttpRequest, data: self.schema_in):  # type: ignore
            return 201, await self.model_util.create_s(request, data, self.schema_out)

        return create

    def list_view(self):
        """
        Register list endpoint with pagination and optional filters.
        """

        @self.router.get(
            self.get_path,
            auth=self.get_view_auth(),
            summary=f"List {self.model_verbose_name_plural}",
            description=self.list_docs,
            response={
                200: List[self.schema_out],
                self.error_codes: GenericMessageSchema,
            },
        )
        @decorate_view(
            paginate(self.pagination_class),
            unique_view(self, plural=True),
            *self.extra_decorators.list,
        )
        async def list(
            request: HttpRequest,
            filters: Query[self.filters_schema] = None,  # type: ignore
        ):
            qs = await self.model_util.get_objects(
                request,
                query_data=self._get_query_data(),
                is_for_read=True,
            )
            if filters is not None:
                qs = await self.query_params_handler(qs, filters.model_dump())
            return await self.model_util.list_read_s(self.schema_out, request, qs)

        return list

    def retrieve_view(self):
        """
        Register retrieve endpoint.
        """

        @self.router.get(
            self.get_path_retrieve,
            auth=self.get_view_auth(),
            summary=f"Retrieve {self.model_verbose_name}",
            description=self.retrieve_docs,
            response={200: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        @decorate_view(unique_view(self), *self.extra_decorators.retrieve)
        async def retrieve(request: HttpRequest, pk: Path[self.path_schema]):  # type: ignore
            query_data = self._get_query_data()
            return await self.model_util.read_s(
                self.schema_out,
                request,
                query_data=QuerySchema(
                    getters={"pk": self._get_pk(pk)}, **query_data.model_dump()
                ),
            )

        return retrieve

    def update_view(self):
        """
        Register update endpoint.
        """

        @self.router.patch(
            self.path_retrieve,
            auth=self.patch_view_auth(),
            summary=f"Update {self.model_verbose_name}",
            description=self.update_docs,
            response={200: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        @decorate_view(aatomic, unique_view(self), *self.extra_decorators.update)
        async def update(
            request: HttpRequest,
            data: self.schema_update,  # type: ignore
            pk: Path[self.path_schema],  # type: ignore
        ):
            return await self.model_util.update_s(
                request, data, self._get_pk(pk), self.schema_out
            )

        return update

    def delete_view(self):
        """
        Register delete endpoint.
        """

        @self.router.delete(
            self.path_retrieve,
            auth=self.delete_view_auth(),
            summary=f"Delete {self.model_verbose_name}",
            description=self.delete_docs,
            response={204: None, self.error_codes: GenericMessageSchema},
        )
        @decorate_view(aatomic, unique_view(self), *self.extra_decorators.delete)
        async def delete(request: HttpRequest, pk: Path[self.path_schema]):  # type: ignore
            return 204, await self.model_util.delete_s(request, self._get_pk(pk))

        return delete

    def views(self):
        """
        Override to register custom non-CRUD endpoints on self.router.
        Use auth=self.auth or verb specific auth attributes if needed.
        """
        pass

    def _set_additional_views(self):
        self.views()
        if self.m2m_api is not None:
            self.m2m_api._add_views()
        return self.router

    def _add_views(self):
        """
        Register CRUD (unless disabled), custom views, and M2M endpoints.
        If 'all' in disable only CRUD is skipped; M2M + custom still added.
        """
        super()._add_views()
        if "all" in self.disable:
            return self._set_additional_views()

        for views_type, (schema, view) in self._crud_views.items():
            if views_type not in self.disable and (
                schema is not None or views_type == "delete"
            ):
                view()

        return self._set_additional_views()


class ReadOnlyViewSet(APIViewSet):
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


class WriteOnlyViewSet(APIViewSet):
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
