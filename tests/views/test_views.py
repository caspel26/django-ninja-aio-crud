from ninja_aio import NinjaAIO
from django.test import TestCase, tag

from tests.test_app import schema
from tests.generics.request import Request
from tests.generics.views import GenericAPIView


@tag("view")
class APIViewTestCase(TestCase):
    namespace = "test_api_view"
    view = GenericAPIView()

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.view.api = cls.api
        cls.view.add_views_to_route()
        cls.path = f"{cls.view.path_name}/"
        cls.request = Request(cls.path)

    @property
    def path_names(self):
        return [self.view.path_name]

    @property
    def schema_in_payload(self):
        return {"a": 1, "b": 2}

    @property
    def schema_out_payload(self):
        return {"result": 3}

    @property
    def request_data(self):
        return schema.SumSchemaIn(**self.schema_in_payload)

    @property
    def response_data(self):
        return schema.SumSchemaOut(**self.schema_out_payload).model_dump()

    def test_routes(self):
        self.assertEqual(len(self.api._routers), 2)
        test_router_path = self.api._routers[1][0]
        test_router = self.api._routers[1][1]
        self.assertEqual(self.path, test_router_path)
        paths = [str(route.pattern) for route in test_router.urls_paths(self.path)]
        path_names = list(
            dict.fromkeys([route.name for route in test_router.urls_paths(self.path)])
        )
        self.assertIn(self.path, paths)
        self.assertEqual(self.path_names, path_names)

    async def test_view(self):
        view = self.view.views()
        response = await view(self.request.post(), self.request_data)
        self.assertEqual(response, self.response_data)
