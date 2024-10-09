from typing import List

from ninja import NinjaAPI, Router, Schema
from ninja.constants import NOT_SET
from ninja.pagination import paginate, AsyncPaginationBase, PageNumberPagination
from django.http import HttpRequest
from django.db.models import Model

from .models import ModelSerializer, ModelUtil
from .schemas import GenericMessageSchema
from .exceptions import SerializeError
from .types import ModelSerializerMeta

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
        pass

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

    def __init__(self) -> None:
        self.router = Router(tags=[self.model._meta.model_name.capitalize()])
        self.path = "/"
        self.path_retrieve = f"{self.model._meta.pk.attname}/"
        self.error_codes = ERROR_CODES
        self.model_util = ModelUtil(self.model)
        self.schema_out, self.schema_update, self.schema_in = self.get_schemas()

    def get_schemas(self):
        if isinstance(self.model, ModelSerializerMeta):
            return (
                self.model.generate_read_s(),
                self.model.generate_update_s(),
                self.model.generate_create_s(),
            )
        return self.schema_out, self.schema_update, self.schema_in

    def create_view(self):
        @self.router.post(
            self.path,
            auth=self.auths,
            response={201: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        async def create(request: HttpRequest, data: self.schema_in):
            return await self.model_util.create_s(request, data, self.schema_out)

        create.__name__ = f"create_{self.model._meta.model_name}"

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
            print(rels)
            if len(rels) > 0:
                qs = qs.prefetch_related(*rels)
            objs = [
                await self.model_util.read_s(request, obj, self.schema_out)
                async for obj in qs.all()
            ]
            return objs

        list.__name__ = f"list_{self.model._meta.verbose_name_plural}"

    def retrieve_view(self):
        @self.router.get(
            self.path_retrieve,
            auth=self.auths,
            response={200: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        async def retrieve(request: HttpRequest, pk: int | str):
            try:
                obj = await self.model_util.get_object(request, pk)
            except SerializeError as e:
                return e.status_code, e.error
            return await self.model_util.read_s(request, obj, self.schema_out)

        retrieve.__name__ = f"retrieve_{self.model._meta.model_name}"

    def update_view(self):
        @self.router.patch(
            self.path_retrieve,
            auth=self.auths,
            response={200: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        async def update(request: HttpRequest, data: self.schema_update, pk: int | str):
            return await self.model_util.update_s(request, data, pk, self.schema_out)

        update.__name__ = f"update_{self.model._meta.model_name}"

    def delete_view(self):
        @self.router.delete(
            self.path_retrieve,
            auth=self.auths,
            response={204: None, self.error_codes: GenericMessageSchema},
        )
        async def delete(request: HttpRequest, pk: int | str):
            return await self.model_util.delete_s(request, pk)

        delete.__name__ = f"delete_{self.model._meta.model_name}"

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
        pass

    def add_views(self):
        self.create_view()
        self.list_view()
        self.retrieve_view()
        self.update_view()
        self.delete_view()
        self.views()
        return self.router

    def add_views_to_route(self):
        return self.api.add_router(
            f"{self.model_util.verbose_name_path_resolver()}/",
            self.add_views(),
        )
