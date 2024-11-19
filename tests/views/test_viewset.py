from django.test import TestCase, tag
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
            cls.api = NinjaAIO(urls_namespace=cls.namespace)
            cls.test_util = ModelUtil(cls.model)
            cls.viewset.api = cls.api
            cls.viewset.add_views_to_route()
            cls.path = f"{cls.test_util.verbose_name_path_resolver()}/"
            cls.detail_path = f"{cls.path}{cls.model._meta.pk.attname}/"

        @property
        def urls_data(self):
            return [
                (self.path, f"create_{self.model._meta.model_name}"),
                (self.path, f"list_{self.test_util.verbose_name_view_resolver()}"),
                (self.detail_path, f"retrieve_{self.model._meta.model_name}"),
                (self.detail_path, f"update_{self.model._meta.model_name}"),
                (self.detail_path, f"delete_{self.model._meta.model_name}"),
            ]

        @property
        def schemas(self):
            """
            Should be implemented into the child class
            """

        def test_crud_routes(self):
            self.assertEqual(len(self.api._routers), 2)
            test_router_path = self.api._routers[1][0]
            test_router = self.api._routers[1][1]
            self.assertEqual(self.path, test_router_path)
            for index, path in enumerate(test_router.urls_paths(self.path)):
                url_data = self.urls_data[index]
                self.assertEqual(str(path.pattern), url_data[0])
                self.assertEqual(path.name, url_data[1])

        def test_get_schemas(self):
            schemas = self.viewset.get_schemas()
            self.assertEqual(len(schemas), 3)
            self.assertEqual(schemas, self.schemas)


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
