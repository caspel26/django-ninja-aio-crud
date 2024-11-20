from django.test import TestCase, tag
from django.test.client import AsyncRequestFactory
from django.db import models

from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from ninja_aio.models import ModelUtil, ModelSerializer
from tests.test_app.models import TestModelSerializer, TestModel
from tests.test_app.schema import (
    TestModelSchemaIn,
    TestModelSchemaOut,
    TestModelSchemaPatch,
)


class TestModelSerializerAPI(APIViewSet):
    model = TestModelSerializer


class TestModelAPI(APIViewSet):
    model = TestModel
    schema_in = TestModelSchemaIn
    schema_out = TestModelSchemaOut
    schema_update = TestModelSchemaPatch


class Tests:
    @tag("viewset")
    class ApiViewSetTestCaseBase(TestCase):
        namespace: str
        model: ModelSerializer | models.Model
        viewset: APIViewSet

        @classmethod
        def setUpTestData(cls):
            cls.afactory = AsyncRequestFactory()
            cls.api = NinjaAIO(urls_namespace=cls.namespace)
            cls.test_util = ModelUtil(cls.model)
            cls.viewset.api = cls.api
            cls.viewset.add_views_to_route()
            cls.path = f"{cls.test_util.verbose_name_path_resolver()}/"
            cls.detail_path = f"{cls.path}{cls.model._meta.pk.attname}/"

        @property
        def path_names(self):
            return [
                f"create_{self.model._meta.model_name}",
                f"list_{self.test_util.verbose_name_view_resolver()}",
                f"retrieve_{self.model._meta.model_name}",
                f"update_{self.model._meta.model_name}",
                f"delete_{self.model._meta.model_name}",
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
            return {
                "name": f"test_name_{self.model._meta.model_name}",
                "description": f"test_description_{self.model._meta.model_name}",
            }

        @property
        def create_data(self):
            return self.viewset.schema_in(**self.payload_create)

        async def _create_view(self):
            view = self.viewset.create_view()
            request = self.afactory.post(self.path)
            status, content = await view(request, self.create_data)
            return status, content

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
            status, content = await self._create_view()
            pk = self.model._meta.pk.attname
            self.assertEqual(status, 201)
            self.assertIn(pk, content)
            content.pop(pk)
            self.assertEqual(content, self.payload_create)

        async def test_list(self):
            await self._create_view()
            view = self.viewset.list_view()
            request = self.afactory.get(self.path)
            content: dict = await view(request, **self.pagination_kwargs)
            self.assertEqual(["items", "count"], list(content.keys()))
            items = content["items"]
            count = content["count"]
            self.assertEqual(1, count)
            self.assertEqual([self.payload_create | {"id": 1}], items)


@tag("model_serializer_viewset")
class ApiViewSetModelSerializerTestCase(Tests.ApiViewSetTestCaseBase):
    namespace = "test_model_serializer_viewset"
    model = TestModelSerializer
    viewset = TestModelSerializerAPI()

    @property
    def schemas(self):
        return (
            self.model.generate_read_s(),
            self.model.generate_create_s(),
            self.model.generate_update_s(),
        )


@tag("model_viewset")
class ApiViewSetModelTestCase(Tests.ApiViewSetTestCaseBase):
    namespace = "test_model_viewset"
    model = TestModel
    viewset = TestModelAPI()

    @property
    def schemas(self):
        return (
            TestModelSchemaOut,
            TestModelSchemaIn,
            TestModelSchemaPatch,
        )
