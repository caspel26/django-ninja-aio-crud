import asyncio

from django.test import TestCase, tag
from django.test.client import AsyncRequestFactory
from django.db import models

from tests.test_app import schema
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from ninja_aio.models import ModelSerializer, ModelUtil


class GenericAPI(APIViewSet):
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


class Tests:
    @tag("viewset")
    class GenericViewSetTestCase(TestCase):
        namespace: str
        model: ModelSerializer | models.Model
        viewset: GenericAPI

        @classmethod
        def setUpTestData(cls):
            cls.afactory = AsyncRequestFactory()
            cls.api = NinjaAIO(urls_namespace=cls.namespace)
            cls.test_util = ModelUtil(cls.model)
            cls.viewset.api = cls.api
            cls.viewset.add_views_to_route()
            cls.pk_att = cls.model._meta.pk.attname
            cls.path = f"{cls.test_util.verbose_name_path_resolver()}/"
            cls.detail_path = f"{cls.path}{cls.pk_att}/"

        @property
        def path_names(self):
            return [
                f"create_{self.model._meta.model_name}",
                f"list_{self.test_util.verbose_name_view_resolver()}",
                f"retrieve_{self.model._meta.model_name}",
                f"update_{self.model._meta.model_name}",
                f"delete_{self.model._meta.model_name}",
                self.viewset.path_name,
            ]

        @property
        def schemas(self):
            """
            Should be implemented into the child class
            """

        @property
        def pagination_kwargs(self):
            return {"ninja_pagination": self.viewset.pagination_class.Input(page=1)}

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
        def create_data(self):
            return self.viewset.schema_in(**self.payload_create)

        @property
        def update_data(self):
            return self.viewset.schema_update(**self.payload_update)

        @property
        def get_request(self):
            return self.afactory.get(self.path)

        @property
        def post_request(self):
            return self.afactory.post(self.path)

        @property
        def patch_request(self):
            return self.afactory.patch(self.path)

        @property
        def delete_request(self):
            return self.afactory.delete(self.path)

        async def _create_view(self):
            view = self.viewset.create_view()
            status, content = await view(self.post_request, self.create_data)
            self.assertEqual(status, 201)
            self.assertIn(self.pk_att, content)
            self.assertEqual(self.response_data | {self.pk_att: 1}, content)
            return content

        def test_crud_routes(self):
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
            self.assertIn(self.path, paths)
            self.assertIn(self.detail_path, paths)
            self.assertEqual(self.path_names, path_names)

        def test_get_schemas(self):
            schemas = self.viewset.get_schemas()
            self.assertEqual(len(schemas), 3)
            self.assertEqual(schemas, self.schemas)

        async def test_create(self):
            await self._create_view()

        async def test_list(self):
            create_content = await self._create_view()
            view = self.viewset.list_view()
            content: dict = await view(self.get_request, **self.pagination_kwargs)
            self.assertEqual(["items", "count"], list(content.keys()))
            items = content["items"]
            count = content["count"]
            pk = create_content[self.pk_att]
            self.assertEqual(1, count)
            self.assertEqual([self.response_data | {self.pk_att: pk}], items)

        async def test_retrieve(self):
            create_content = await self._create_view()
            view = self.viewset.retrieve_view()
            pk = create_content[self.pk_att]
            content = await view(self.get_request, pk)
            self.assertEqual(self.response_data | {self.pk_att: pk}, content)

        async def test_retrieve_object_not_found(self):
            view = self.viewset.retrieve_view()
            status, content = await view(self.get_request, 1)
            self.assertEqual(status, 404)
            self.assertEqual(content, {self.model._meta.model_name: "not found"})

        async def test_update(self):
            create_content = await self._create_view()
            view = self.viewset.update_view()
            pk = create_content[self.pk_att]
            content = await view(self.patch_request, self.update_data, pk)
            self.assertEqual(
                self.response_data | self.payload_update | {self.pk_att: pk}, content
            )

        async def test_delete(self):
            create_content = await self._create_view()
            view = self.viewset.delete_view()
            pk = create_content[self.pk_att]
            status, content = await view(self.delete_request, pk)
            self.assertEqual(status, 204)
            self.assertEqual(content, None)

        async def test_additional_view(self):
            view = self.viewset.views()
            content = await view(
                self.viewset.additional_view_path, schema.SumSchemaIn(a=1, b=2)
            )
            self.assertEqual({"result": 3}, content)
