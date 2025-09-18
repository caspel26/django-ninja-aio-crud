import asyncio
from typing import List

from ninja import NinjaAPI, Router, Schema, Path, Query
from ninja.constants import NOT_SET
from ninja.pagination import paginate, AsyncPaginationBase, PageNumberPagination
from django.http import HttpRequest
from django.db.models import Model, QuerySet
from pydantic import create_model

from .models import ModelSerializer, ModelUtil
from .schemas import (
    GenericMessageSchema,
    M2MSchemaOut,
    M2MSchemaIn,
    M2MAddSchemaIn,
    M2MRemoveSchemaIn,
)
from .types import ModelSerializerMeta, VIEW_TYPES

ERROR_CODES = frozenset({400, 401, 404, 428})


class APIView:
    api: NinjaAPI
    router_tag: str
    api_route_path: str
    auth: list | None = NOT_SET

    def __init__(self) -> None:
        self.router = Router(tags=[self.router_tag])
        self.error_codes = ERROR_CODES

    def views(self):
        """
        Override this method to add your custom views. For example:
        @self.router.get(some_path, response=some_schema)
        async def some_method(request, *args, **kwargs):
            pass

        You can add multilple views just doing:

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

    def _add_views(self):
        self.views()
        return self.router

    def add_views_to_route(self):
        return self.api.add_router(f"{self.api_route_path}", self._add_views())


class APIViewSet:
    """
    A base class for creating API views with CRUD operations.

    This class provides methods for creating, listing, retrieving, updating,
    and deleting objects of a specified model. It supports pagination,
    authentication, and custom query parameters.

    ## Attributes:
        - **model** (`ModelSerializer | Model`): The model for CRUD operations.
        - **api** (`NinjaAPI`): The API instance to which the views are added.
        - **schema_in** (`Schema | None`): Schema for input data in create/update operations.
        - **schema_out** (`Schema | None`): Schema for output data in list/retrieve operations.
        - **schema_update** (`Schema | None`): Schema for update operations.
        - **auth** (`list | None`): Authentication classes for the views.
        - **get_auth** (`list | None`): Authentication for GET requests.
        - **post_auth** (`list | None`): Authentication for POST requests.
        - **patch_auth** (`list | None`): Authentication for PATCH requests.
        - **delete_auth** (`list | None`): Authentication for DELETE requests.
        - **pagination_class** (`type[AsyncPaginationBase]`): Pagination class to use.
        - **query_params** (`dict[str, tuple[type, ...]]`): Query parameters for filtering.
        - **disable** (`list[type[VIEW_TYPES]]`): List of view types to disable.
        - **api_route_path** (`str`): Base path for the API route.
        - **list_docs** (`str`): Documentation for the list view.
        - **create_docs** (`str`): Documentation for the create view.
        - **retrieve_docs** (`str`): Documentation for the retrieve view.
        - **update_docs** (`str`): Documentation for the update view.
        - **delete_docs** (`str`): Documentation for the delete view.
        - **m2m_relations** (`tuple[ModelSerializer | Model, str]`): Many-to-many relations to manage.
        - **m2m_add** (`bool`): Enable add operation for M2M relations.
        - **m2m_remove** (`bool`): Enable remove operation for M2M relations.
        - **m2m_get** (`bool`): Enable get operation for M2M relations.
        - **m2m_auth** (`list | None`): Authentication for M2M views.

    ## Notes:
        If the model is a ModelSerializer instance, schemas are generated
        automatically based on Create, Read, and Update serializers.
        Override the `views` method to add custom views.
        Override the `query_params_handler` method to handle query params
        and return a filtered queryset.

    ## Methods:
        - **create_view**: Creates a new object.
        - **list_view**: Lists all objects.
        - **retrieve_view**: Retrieves an object by its primary key.
        - **update_view**: Updates an object by its primary key.
        - **delete_view**: Deletes an object by its primary key.
        - **views**: Override to add custom views.
        - **add_views_to_route**: Adds the views to the API route.

    ## Example:
        class MyModelViewSet(APIViewSet):
            model = MyModel  # Your Django model
            api = my_api_instance  # Your NinjaAPI instance

        MyModelViewSet().add_views_to_route()
    """

    model: ModelSerializer | Model
    api: NinjaAPI
    schema_in: Schema | None = None
    schema_out: Schema | None = None
    schema_update: Schema | None = None
    auth: list | None = NOT_SET
    get_auth: list | None = NOT_SET
    post_auth: list | None = NOT_SET
    patch_auth: list | None = NOT_SET
    delete_auth: list | None = NOT_SET
    pagination_class: type[AsyncPaginationBase] = PageNumberPagination
    query_params: dict[str, tuple[type, ...]] = {}
    disable: list[type[VIEW_TYPES]] = []
    api_route_path: str = ""
    list_docs = "List all objects."
    create_docs = "Create a new object."
    retrieve_docs = "Retrieve a specific object by its primary key."
    update_docs = "Update an object by its primary key."
    delete_docs = "Delete an object by its primary key."
    m2m_relations: tuple[ModelSerializer | Model, str] = []
    m2m_add = True
    m2m_remove = True
    m2m_get = True
    m2m_auth: list | None = NOT_SET

    def __init__(self) -> None:
        self.error_codes = ERROR_CODES
        self.model_util = ModelUtil(self.model)
        self.schema_out, self.schema_in, self.schema_update = self.get_schemas()
        self.path_schema = self._generate_path_schema()
        self.filters_schema = self._generate_filters_schema()
        self.model_verbose_name = self.model._meta.verbose_name.capitalize()
        self.router_tag = self.model_verbose_name
        self.router = Router(tags=[self.router_tag])
        self.path = "/"
        self.get_path = ""
        self.path_retrieve = f"{{{self.model_util.model_pk_name}}}/"
        self.get_path_retrieve = f"{{{self.model_util.model_pk_name}}}"
        self.api_route_path = (
            self.api_route_path or self.model_util.verbose_name_path_resolver()
        )

    @property
    def _crud_views(self):
        """
        key: view type (create, list, retrieve, update, delete or all)
        value: tuple with schema and view method
        """
        return {
            "create": (self.schema_in, self.create_view),
            "list": (self.schema_out, self.list_view),
            "retrieve": (self.schema_out, self.retrieve_view),
            "update": (self.schema_update, self.update_view),
            "delete": (None, self.delete_view),
        }

    def _auth_view(self, view_type: str):
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
        return create_model(f"{self.model_util.model_name}{name}", **fields)

    def _generate_path_schema(self):
        return self._generate_schema(
            {self.model_util.model_pk_name: (int | str, ...)}, "PathSchema"
        )

    def _generate_filters_schema(self):
        return self._generate_schema(self.query_params, "FiltersSchema")

    def _get_pk(self, data: Schema):
        return data.model_dump()[self.model_util.model_pk_name]

    def get_schemas(self):
        if isinstance(self.model, ModelSerializerMeta):
            return (
                self.model.generate_read_s(),
                self.model.generate_create_s(),
                self.model.generate_update_s(),
            )
        return self.schema_out, self.schema_in, self.schema_update

    async def query_params_handler(
        self, queryset: QuerySet[ModelSerializer], filters: dict
    ):
        """
        Override this method to handle request query params making queries to the database
        based on filters or any other logic. This method should return a queryset. filters
        are given already dumped by the schema.
        """
        return queryset

    def create_view(self):
        @self.router.post(
            self.path,
            auth=self.post_view_auth(),
            summary=f"Create {self.model._meta.verbose_name.capitalize()}",
            description=self.create_docs,
            response={201: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        async def create(request: HttpRequest, data: self.schema_in):  # type: ignore
            return 201, await self.model_util.create_s(request, data, self.schema_out)

        create.__name__ = f"create_{self.model_util.model_name}"
        return create

    def list_view(self):
        @self.router.get(
            self.get_path,
            auth=self.get_view_auth(),
            summary=f"List {self.model._meta.verbose_name_plural.capitalize()}",
            description=self.list_docs,
            response={
                200: List[self.schema_out],
                self.error_codes: GenericMessageSchema,
            },
        )
        @paginate(self.pagination_class)
        async def list(
            request: HttpRequest,
            filters: Query[self.filters_schema] = None,  # type: ignore
        ):
            qs = self.model.objects.select_related()
            if isinstance(self.model, ModelSerializerMeta):
                qs = await self.model.queryset_request(request)
            rels = self.model_util.get_reverse_relations()
            if len(rels) > 0:
                qs = qs.prefetch_related(*rels)
            if filters is not None:
                qs = await self.query_params_handler(qs, filters.model_dump())
            objs = [
                await self.model_util.read_s(request, obj, self.schema_out)
                async for obj in qs.all()
            ]
            return objs

        list.__name__ = f"list_{self.model_util.verbose_name_view_resolver()}"
        return list

    def retrieve_view(self):
        @self.router.get(
            self.get_path_retrieve,
            auth=self.get_view_auth(),
            summary=f"Retrieve {self.model._meta.verbose_name.capitalize()}",
            description=self.retrieve_docs,
            response={200: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        async def retrieve(request: HttpRequest, pk: Path[self.path_schema]):  # type: ignore
            obj = await self.model_util.get_object(request, self._get_pk(pk))
            return await self.model_util.read_s(request, obj, self.schema_out)

        retrieve.__name__ = f"retrieve_{self.model_util.model_name}"
        return retrieve

    def update_view(self):
        @self.router.patch(
            self.path_retrieve,
            auth=self.patch_view_auth(),
            summary=f"Update {self.model._meta.verbose_name.capitalize()}",
            description=self.update_docs,
            response={200: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        async def update(
            request: HttpRequest,
            data: self.schema_update,  # type: ignore
            pk: Path[self.path_schema],  # type: ignore
        ):
            return await self.model_util.update_s(
                request, data, self._get_pk(pk), self.schema_out
            )

        update.__name__ = f"update_{self.model_util.model_name}"
        return update

    def delete_view(self):
        @self.router.delete(
            self.path_retrieve,
            auth=self.delete_view_auth(),
            summary=f"Delete {self.model._meta.verbose_name.capitalize()}",
            description=self.delete_docs,
            response={204: None, self.error_codes: GenericMessageSchema},
        )
        async def delete(request: HttpRequest, pk: Path[self.path_schema]):  # type: ignore
            return 204, await self.model_util.delete_s(request, self._get_pk(pk))

        delete.__name__ = f"delete_{self.model_util.model_name}"
        return delete

    def views(self):
        """
        Override this method to add your custom views. For example:
        @self.router.get(some_path, response=some_schema)
        async def some_method(request, *args, **kwargs):
            pass

        You can add multilple views just doing:

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

    async def _check_m2m_objs(
        self,
        request: HttpRequest,
        objs_pks: list,
        model: ModelSerializer | Model,
        related_manager: QuerySet,
        remove: bool = False,
    ):
        errors, objs_detail, objs = [], [], []
        rel_objs = [rel_obj async for rel_obj in related_manager.select_related().all()]
        rel_model_name = model._meta.verbose_name.capitalize()
        for obj_pk in objs_pks:
            rel_obj = await (
                await ModelUtil(model).get_object(request, filters={"pk": obj_pk})
            ).afirst()
            if rel_obj is None:
                errors.append(f"{rel_model_name} with pk {obj_pk} not found.")
                continue
            if remove ^ (rel_obj in rel_objs):
                errors.append(
                    f"{rel_model_name} with id {obj_pk} is {'not ' if remove else ''} in {self.model_util.model_name}"
                )
                continue
            objs.append(rel_obj)
            objs_detail.append(
                f"{rel_model_name} with id {obj_pk} successfully {'removed' if remove else 'added'}"
            )
        return errors, objs_detail, objs

    def _m2m_views(self):
        for model, related_name in self.m2m_relations:
            rel_util = ModelUtil(model)
            rel_path = rel_util.verbose_name_path_resolver()
            if self.m2m_get:

                @self.router.get(
                    f"{self.path_retrieve}{rel_path}",
                    response={
                        200: List[model.generate_related_s(),],
                        self.error_codes: GenericMessageSchema,
                    },
                    auth=self.m2m_auth,
                    summary=f"Get {rel_util.model._meta.verbose_name_plural.capitalize()}",
                    description=f"Get all related {rel_util.model._meta.verbose_name_plural.capitalize()}",
                )
                @paginate(self.pagination_class)
                async def get_related(request: HttpRequest, pk: Path[self.path_schema]):  # type: ignore
                    obj = await self.model_util.get_object(request, self._get_pk(pk))
                    related_manager = getattr(obj, related_name)
                    related_qs = related_manager.all()
                    related_objs = [
                        await rel_util.read_s(
                            request, rel_obj, model.generate_related_s()
                        )
                        async for rel_obj in related_qs
                    ]
                    return related_objs

                get_related.__name__ = f"get_{self.model_util.model_name}_{rel_path}"

                if self.m2m_add or self.m2m_remove:
                    summary = f"{'Add or Remove' if self.m2m_add and self.m2m_remove else 'Add' if self.m2m_add else 'Remove'} {rel_util.model._meta.verbose_name_plural.capitalize()}"
                    description = f"{'Add or remove' if self.m2m_add and self.m2m_remove else 'Add' if self.m2m_add else 'Remove'} {rel_util.model._meta.verbose_name_plural.capitalize()}"
                    schema_in = (
                        M2MSchemaIn
                        if self.m2m_add and self.m2m_remove
                        else M2MAddSchemaIn
                        if self.m2m_add
                        else M2MRemoveSchemaIn
                    )

                    @self.router.post(
                        f"{self.path_retrieve}{rel_path}/",
                        response={
                            200: M2MSchemaOut,
                            self.error_codes: GenericMessageSchema,
                        },
                        auth=self.m2m_auth,
                        summary=summary,
                        description=description,
                    )
                    async def manage_related(
                        request: HttpRequest,
                        pk: Path[self.path_schema],  # type: ignore
                        data: schema_in,  # type: ignore
                    ):
                        obj = await self.model_util.get_object(
                            request, self._get_pk(pk)
                        )
                        related_manager: QuerySet = getattr(obj, related_name)
                        add_errors, add_details, add_objs = [], [], []
                        remove_errors, remove_details, remove_objs = [], [], []

                        if self.m2m_add and hasattr(data, "add"):
                            (
                                add_errors,
                                add_details,
                                add_objs,
                            ) = await self._check_m2m_objs(
                                request, data.add, model, related_manager
                            )
                        if self.m2m_remove and hasattr(data, "remove"):
                            (
                                remove_errors,
                                remove_details,
                                remove_objs,
                            ) = await self._check_m2m_objs(
                                request,
                                data.remove,
                                model,
                                related_manager,
                                remove=True,
                            )

                        await asyncio.gather(
                            related_manager.aadd(*add_objs),
                            related_manager.aremove(*remove_objs),
                        )
                        results = add_details + remove_details
                        errors = add_errors + remove_errors

                        return {
                            "results": {
                                "count": len(results),
                                "details": results,
                            },
                            "errors": {
                                "count": len(errors),
                                "details": errors,
                            },
                        }

                    manage_related.__name__ = (
                        f"manage_{self.model_util.model_name}_{rel_path}"
                    )

    def _add_views(self):
        if "all" in self.disable:
            if self.m2m_relations:
                self._m2m_views()
            self.views()
            return self.router

        for views_type, (schema, view) in self._crud_views.items():
            if views_type not in self.disable and (
                schema is not None or views_type == "delete"
            ):
                view()

        self.views()
        if self.m2m_relations:
            self._m2m_views()
        return self.router

    def add_views_to_route(self):
        return self.api.add_router(f"{self.api_route_path}", self._add_views())