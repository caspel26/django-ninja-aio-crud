"""Coverage for APIViewSet/APIView's configurable `error_schema` attribute
(see ninja_aio/views/api.py's API base class)."""

from django.test import TestCase, tag
from ninja import Schema

from ninja_aio import NinjaAIO
from ninja_aio.schemas import GenericMessageSchema
from ninja_aio.views import APIView, APIViewSet
from ninja_aio.factory.operations import ApiMethodFactory
from tests.test_app import models as app_models


class CustomErrorSchema(Schema):
    error_id: str
    error_description: str


def _response_schema(operation, status_code):
    """Unwrap ninja's dynamically-generated NinjaResponseSchema wrapper
    (see Operation._create_response_model) to get back the schema class
    actually passed in `response={...}`."""
    return operation.response_models[status_code].__annotations__["response"]


@tag("view", "error_schema")
class ViewSetErrorSchemaTestCase(TestCase):
    def test_default_error_schema_is_generic_message_schema(self):
        api = NinjaAIO(urls_namespace="test_error_schema_default")

        class DefaultViewSet(APIViewSet):
            model = app_models.TestModelSerializer

        vs = DefaultViewSet(api=api)
        vs.add_views_to_route()

        create_op = vs.router.path_operations[""].operations[0]
        self.assertIs(_response_schema(create_op, 400), GenericMessageSchema)

    def test_overriding_error_schema_on_a_viewset_subclass(self):
        api = NinjaAIO(urls_namespace="test_error_schema_override")

        class CustomErrorViewSet(APIViewSet):
            model = app_models.TestModelSerializer
            error_schema = CustomErrorSchema

        vs = CustomErrorViewSet(api=api)
        vs.add_views_to_route()

        create_op = vs.router.path_operations[""].operations[0]
        retrieve_op = vs.router.path_operations[vs.get_path_retrieve].operations[0]

        for op in (create_op, retrieve_op):
            for status_code in (400, 401, 403, 404):
                self.assertIs(_response_schema(op, status_code), CustomErrorSchema)

    def test_overriding_error_schema_on_an_api_view_subclass(self):
        api = NinjaAIO(urls_namespace="test_error_schema_apiview")
        api_get = ApiMethodFactory.make("get")

        class CustomErrorAPIView(APIView):
            router_tag = "custom_error_api_view"
            error_schema = CustomErrorSchema

            @api_get("/hello", response={200: GenericMessageSchema, 404: None})
            async def hello(self, request):
                return {"ok": "true"}

        view = CustomErrorAPIView(api=api)
        self.assertIs(view.error_schema, CustomErrorSchema)
