from typing import List

from ninja import NinjaAPI, Router, Schema, Path
from ninja.constants import NOT_SET
from ninja.pagination import paginate, AsyncPaginationBase, PageNumberPagination
from django.http import HttpRequest
from django.db.models import Model
from pydantic import create_model

from .models import ModelSerializer, ModelUtil
from .schemas import GenericMessageSchema
from .types import ModelSerializerMeta, VIEW_TYPES

ERROR_CODES = frozenset({400, 401, 404, 428})


class APIView:
    api: NinjaAPI
    router_tag: str
    api_route_path: str
    auths: list | None = NOT_SET

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

        @self.router.get(some_path, response=some_schema, auth=self.auths)
        async def some_method(request, *args, **kwargs):
            pass

        NOT AUTHENTICATED VIEW:

        @self.router.post(some_path, response=some_schema)
        async def some_method(request, *args, **kwargs):
            pass
        """

    def add_views(self):
        self.views()
        return self.router

    def add_views_to_route(self):
        return self.api.add_router(f"{self.api_route_path}/", self.add_views())


class APIViewSet:
    model: ModelSerializer | Model
    api: NinjaAPI
    schema_in: Schema | None = None
    schema_out: Schema | None = None
    schema_update: Schema | None = None
    auths: list | None = NOT_SET
    pagination_class: type[AsyncPaginationBase] = PageNumberPagination
    disable: list[type[VIEW_TYPES]] = []

    def __init__(self) -> None:
        self.router = Router(tags=[self.model._meta.model_name.capitalize()])
        self.path = "/"
        self.path_retrieve = f"{{{self.model._meta.pk.attname}}}/"
        self.error_codes = ERROR_CODES
        self.model_util = ModelUtil(self.model)
        self.schema_out, self.schema_in, self.schema_update = self.get_schemas()
        self.path_schema = self._create_path_schema()

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

    def _create_path_schema(self):
        fields = {
            self.model._meta.pk.attname: (str | int , ...),
        }
        return create_model(f"{self.model._meta.model_name}PathSchema", **fields)

    def get_schemas(self):
        if isinstance(self.model, ModelSerializerMeta):
            return (
                self.model.generate_read_s(),
                self.model.generate_create_s(),
                self.model.generate_update_s(),
            )
        return self.schema_out, self.schema_in, self.schema_update

    def create_view(self):
        @self.router.post(
            self.path,
            auth=self.auths,
            response={201: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        async def create(request: HttpRequest, data: self.schema_in):
            return 201, await self.model_util.create_s(request, data, self.schema_out)

        create.__name__ = f"create_{self.model._meta.model_name}"
        return create

    def list_view(self):
        @self.router.get(
            self.path,
            auth=self.auths,
            response={
                200: List[self.schema_out],
                self.error_codes: GenericMessageSchema,
            },
        )
        @paginate(self.pagination_class)
        async def list(request: HttpRequest):
            qs = self.model.objects.select_related()
            if isinstance(self.model, ModelSerializerMeta):
                qs = await self.model.queryset_request(request)
            rels = self.model_util.get_reverse_relations()
            if len(rels) > 0:
                qs = qs.prefetch_related(*rels)
            objs = [
                await self.model_util.read_s(request, obj, self.schema_out)
                async for obj in qs.all()
            ]
            return objs

        list.__name__ = f"list_{self.model_util.verbose_name_view_resolver()}"
        return list

    def retrieve_view(self):
        @self.router.get(
            self.path_retrieve,
            auth=self.auths,
            response={200: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        async def retrieve(request: HttpRequest, pk: Path[self.path_schema]):
            obj = await self.model_util.get_object(request, pk)
            return await self.model_util.read_s(request, obj, self.schema_out)

        retrieve.__name__ = f"retrieve_{self.model._meta.model_name}"
        return retrieve

    def update_view(self):
        @self.router.patch(
            self.path_retrieve,
            auth=self.auths,
            response={200: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        async def update(request: HttpRequest, data: self.schema_update, pk: Path[self.path_schema]):
            return await self.model_util.update_s(request, data, pk, self.schema_out)

        update.__name__ = f"update_{self.model._meta.model_name}"
        return update

    def delete_view(self):
        @self.router.delete(
            self.path_retrieve,
            auth=self.auths,
            response={204: None, self.error_codes: GenericMessageSchema},
        )
        async def delete(request: HttpRequest, pk: Path[self.path_schema]):
            return 204, await self.model_util.delete_s(request, pk)

        delete.__name__ = f"delete_{self.model._meta.model_name}"
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

        @self.router.get(some_path, response=some_schema, auth=self.auths)
        async def some_method(request, *args, **kwargs):
            pass

        NOT AUTHENTICATED VIEW:

        @self.router.post(some_path, response=some_schema)
        async def some_method(request, *args, **kwargs):
            pass
        """

    def add_views(self):
        if "all" in self.disable:
            self.views()
            return self.router

        for views_type, (schema, view) in self._crud_views.items():
            if views_type not in self.disable and (
                schema is not None or views_type == "delete"
            ):
                view()

        self.views()
        return self.router

    def add_views_to_route(self):
        return self.api.add_router(
            f"{self.model_util.verbose_name_path_resolver()}/",
            self.add_views(),
        )
