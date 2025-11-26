import asyncio

from django.test import TestCase, tag
from django.db import models
from django.db.models.base import ModelBase
from asgiref.sync import async_to_sync

from ninja_aio.exceptions import NotFoundError
from ninja_aio.types import ModelSerializerMeta
from tests.generics.literals import NOT_FOUND
from tests.test_app import schema
from tests.generics.request import Request
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet, APIView
from ninja_aio.models import ModelSerializer, ModelUtil
from ninja.orm.factory import create_schema


class GenericAdditionalView:
    additional_view_path = "sum"

    def views(self):
        @self.router.post(self.additional_view_path, response=schema.SumSchemaOut)
        async def sum(request, data: schema.SumSchemaIn):
            await asyncio.sleep(0.1)
            return {"result": data.a + data.b}

        return sum

    @property
    def path_name(self):
        return "sum"


class GenericAPIView(GenericAdditionalView, APIView):
    router_tag = "test_api_view"
    api_route_path = "sum/"
    additional_view_path = "/"


class GenericAPIViewSet(GenericAdditionalView, APIViewSet):
    pass


class Tests:
    @tag("viewset")
    class GenericViewSetTestCase(TestCase):
        namespace: str
        model: ModelSerializer | models.Model
        viewset: GenericAPIViewSet
        excluded_views: list[str] = []

        @classmethod
        def setUpTestData(cls):
            cls.api = NinjaAIO(urls_namespace=cls.namespace)
            cls.test_util = ModelUtil(cls.model)
            cls.viewset.api = cls.api
            cls.viewset.add_views_to_route()
            cls.pk_att = cls.model._meta.pk.attname
            cls.path = f"{cls.test_util.verbose_name_path_resolver()}"
            cls.detail_path = f"{cls.path}/<{cls.pk_att}>/"
            cls.request = Request(cls.path)

        @property
        def create_view_path_name(self):
            return f"create_{self.model._meta.model_name}"

        @property
        def list_view_path_name(self):
            return f"list_{self.test_util.verbose_name_view_resolver()}"

        @property
        def retrieve_view_path_name(self):
            return f"retrieve_{self.model._meta.model_name}"

        @property
        def update_view_path_name(self):
            return f"update_{self.model._meta.model_name}"

        @property
        def delete_view_path_name(self):
            return f"delete_{self.model._meta.model_name}"

        @property
        def view_path_names(self):
            return [
                self.create_view_path_name,
                self.list_view_path_name,
                self.retrieve_view_path_name,
                self.update_view_path_name,
                self.delete_view_path_name,
            ]

        @property
        def path_names(self):
            return self.view_path_names + [self.viewset.path_name]

        @property
        def schemas(self):
            """
            Should be implemented into the child class
            """

        @property
        def pagination_kwargs(self):
            return {"ninja_pagination": self.viewset.pagination_class.Input(page=1)}

        @property
        def filters_kwargs(self):
            return {"filters": self.viewset.filters_schema()}

        @property
        def list_kwargs(self):
            return self.pagination_kwargs | self.filters_kwargs

        @property
        def payload_create(self):
            """
            Should be implemented into the child class
            """

        @property
        def payload_update(self):
            """
            Should be implemented into the child class
            """

        @property
        def response_data(self):
            """
            Should be implemented into the child class
            """

        @property
        def create_response_data(self):
            """
            Should be implemented into the child class
            """

        @property
        def create_data(self):
            return self.viewset.schema_in(**self.payload_create)

        @property
        def update_data(self):
            return self.viewset.schema_update(**self.payload_update)

        @property
        def get_request(self):
            return self.request.get()

        @property
        def post_request(self):
            return self.request.post()

        @property
        def patch_request(self):
            return self.request.patch()

        @property
        def delete_request(self):
            return self.request.delete()

        def _path_schema(self, pk: int | str):
            return self.viewset.path_schema(**{self.pk_att: pk})

        def _get_routes(self):
            self.assertEqual(len(self.api._routers), 2)
            test_router_path = self.api._routers[1][0]
            test_router = self.api._routers[1][1]
            self.assertEqual(self.path, test_router_path)
            paths = [str(route.pattern) for route in test_router.urls_paths(self.path)]
            path_names = list(
                dict.fromkeys(
                    [route.name for route in test_router.urls_paths(self.path)]
                )
            )
            return paths, path_names

        async def _parse_output_data(self, data):
            new_data = data.copy()
            for k, v in data.items():
                if isinstance(v, ModelSerializer):
                    new_data[k] = await ModelUtil(v.__class__).read_s(
                        v.__class__.generate_related_s(), self.get_request, v
                    )
                elif isinstance(v, models.Model):
                    new_data[k] = await ModelUtil(v.__class__).read_s(
                        create_schema(v.__class__), self.get_request, v
                    )
            return new_data

        async def _create_view(self):
            view = self.viewset.create_view()
            status, content = await view(self.post_request, self.create_data)
            self.assertEqual(status, 201)
            self.assertIn(self.pk_att, content)

            self.assertEqual(
                await self._parse_output_data(self.create_response_data)
                | {self.pk_att: content[self.pk_att]},
                content,
            )
            return content

        def test_crud_routes(self):
            paths, path_names = self._get_routes()
            if not self.excluded_views:
                self.assertIn(self.path, paths)
                self.assertIn(self.detail_path, paths)
                self.assertEqual(self.path_names, path_names)
            if "all" in self.excluded_views:
                self.assertNotIn(self.path, paths)
                self.assertNotIn(self.detail_path, paths)
                self.assertNotIn(self.create_view_path_name, path_names)
                self.assertNotIn(self.list_view_path_name, path_names)
                self.assertNotIn(self.retrieve_view_path_name, path_names)
                self.assertNotIn(self.update_view_path_name, path_names)
                self.assertNotIn(self.delete_view_path_name, path_names)
            if "create" in self.excluded_views:
                self.assertNotIn(self.create_view_path_name, path_names)
            if "list" in self.excluded_views:
                self.assertNotIn(self.list_view_path_name, path_names)
            if "retrieve" in self.excluded_views:
                self.assertNotIn(self.retrieve_view_path_name, path_names)
            if "update" in self.excluded_views:
                self.assertNotIn(self.update_view_path_name, path_names)
            if "delete" in self.excluded_views:
                self.assertNotIn(self.delete_view_path_name, path_names)

        def test_get_schemas(self):
            schemas = self.viewset.get_schemas()
            self.assertEqual(len(schemas), 3)
            self.assertEqual(schemas, self.schemas)

        async def test_create(self):
            await self.model.objects.select_related().all().adelete()
            await self._create_view()

        async def test_list(self):
            view = self.viewset.list_view()
            content: dict = await view(self.get_request, **self.list_kwargs)
            self.assertEqual(["items", "count"], list(content.keys()))
            items = content["items"]
            count = content["count"]
            obj_count = await self.model.objects.select_related().acount()
            self.assertEqual(obj_count, count)
            item = items[0]
            item.pop(self.pk_att)
            self.assertEqual(await self._parse_output_data(self.response_data), item)

        async def test_retrieve(self):
            view = self.viewset.retrieve_view()
            content = await view(self.get_request, self._path_schema(1))
            content.pop(self.pk_att)
            self.assertEqual(await self._parse_output_data(self.response_data), content)

        async def test_retrieve_object_not_found(self):
            with self.assertRaises(NotFoundError) as exc:
                await self.model.objects.select_related().all().adelete()
                view = self.viewset.retrieve_view()
                await view(self.get_request, self._path_schema(1))
            self.assertEqual(exc.exception.status_code, 404)
            self.assertEqual(
                exc.exception.error,
                {self.model._meta.verbose_name.replace(" ", "_"): NOT_FOUND},
            )

        async def test_update(self):
            view = self.viewset.update_view()
            content = await view(
                self.patch_request, self.update_data, self._path_schema(1)
            )
            content.pop(self.pk_att)
            self.assertEqual(
                await self._parse_output_data(self.response_data | self.payload_update),
                content,
            )

        async def test_delete(self):
            view = self.viewset.delete_view()
            pk = self.obj_content[self.pk_att]
            status, content = await view(self.delete_request, self._path_schema(pk))
            self.assertEqual(status, 204)
            self.assertEqual(content, None)

        async def test_additional_view(self):
            view = self.viewset.views()
            content = await view(
                self.viewset.additional_view_path, schema.SumSchemaIn(a=1, b=2)
            )
            self.assertEqual({"result": 3}, content)

    class ViewSetTestCase(GenericViewSetTestCase):
        @classmethod
        def setUpTestData(cls):
            super().setUpTestData()
            cls.obj_content = async_to_sync(cls()._create_view)()

    class RelationViewSetTestCase(GenericViewSetTestCase):
        relation_viewset: GenericAPIViewSet
        relation_related_name: str

        @classmethod
        def setUpTestData(cls):
            super().setUpTestData()
            cls.relation_pk_att = cls.relation_viewset.model._meta.pk.attname
            cls.relation_model = cls.relation_viewset.model
            cls.relation_model_name = cls.relation_model._meta.model_name
            cls.relation_pk = async_to_sync(cls._create_relation)(cls.relation_data)
            cls.relation_util = ModelUtil(cls.relation_viewset.model)
            cls.relation_request = cls.request.get(cls.relation_viewset.path)
            cls.relation_obj = async_to_sync(cls.relation_util.get_object)(
                cls.relation_request, cls.relation_pk
            )
            cls.relation_read_s = async_to_sync(cls.relation_util.read_s)(
                cls.relation_viewset.schema_out, cls.relation_request, cls.relation_obj
            )
            cls.relation_schema_data = cls.relation_read_s
            cls.obj_content = async_to_sync(cls()._create_view)()

        @classmethod
        async def _create_relation(cls, data: dict) -> int:
            cls.relation_viewset.api = cls.api
            view = cls.relation_viewset.create_view()
            _, content = await view(
                cls.post_request, cls.relation_viewset.schema_in(**data)
            )
            return content[cls.relation_pk_att]

    class ReverseRelationViewSetTestCase(RelationViewSetTestCase):
        foreign_key_field: str

        @classmethod
        def setUpTestData(cls):
            super().setUpTestData()
            cls.relation_schema_data.pop(cls.foreign_key_field)

        @classmethod
        def _update_data(cls, data: dict, pk: int | str):
            if isinstance(cls.model, ModelSerializerMeta):
                data |= {f"{cls.foreign_key_field}_id": pk}
            if isinstance(cls.model, ModelBase):
                data |= {cls.foreign_key_field: pk}
            return data

        @classmethod
        async def _create_relation(cls, data: dict) -> int:
            obj = await cls.model.objects.select_related().acreate(
                **cls().payload_create
            )
            return await super()._create_relation(cls._update_data(data, obj.pk))

        async def _create_view(self):
            create_content = await super()._create_view()
            rel_view = self.relation_viewset.create_view()
            await rel_view(
                self.post_request,
                self.relation_viewset.schema_in(
                    **self._update_data(self.relation_data, create_content[self.pk_att])
                ),
            )
            return create_content
