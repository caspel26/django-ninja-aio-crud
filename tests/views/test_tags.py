from django.test import TestCase, tag
from ninja import Schema

from ninja_aio import NinjaAIO
from ninja_aio.decorators import action
from ninja_aio.views import APIView, APIViewSet
from tests.test_app import models


def _operation_tags(api: NinjaAIO) -> dict[str, list | None]:
    schema = api.get_openapi_schema(path_prefix="")
    return {
        f"{method.upper()} {path}": operation.get("tags")
        for path, operations in schema["paths"].items()
        for method, operation in operations.items()
    }


@tag("tags")
class TagPrecedenceTestCase(TestCase):
    """Explicit ``tags`` win over ``router_tags`` on viewsets and views alike."""

    def test_viewset_explicit_tags_win_over_router_tags(self):
        class Items(APIViewSet):
            model = models.TestModelSerializer
            router_tags = ["FromClass"]

        api = NinjaAIO(urls_namespace="tags_viewset_explicit")
        Items(api=api, prefix="items", tags=["Explicit"]).add_views_to_route()
        self.assertEqual(set(map(tuple, _operation_tags(api).values())), {("Explicit",)})

    def test_view_explicit_tags_win_over_router_tags(self):
        class Reports(APIView):
            router_tags = ["FromClass"]

            @action(detail=False)
            async def totals(self, request):
                return {}

        api = NinjaAIO(urls_namespace="tags_view_explicit")
        Reports(api=api, prefix="reports", tags=["Explicit"]).add_views_to_route()
        self.assertEqual(_operation_tags(api), {"GET /reports/totals": ["Explicit"]})

    def test_router_tags_apply_without_explicit_tags(self):
        class Items(APIViewSet):
            model = models.TestModelSerializer
            router_tags = ["FromClass"]

        api = NinjaAIO(urls_namespace="tags_viewset_class")
        Items(api=api, prefix="items").add_views_to_route()
        self.assertEqual(set(map(tuple, _operation_tags(api).values())), {("FromClass",)})

    def test_untagged_view_has_no_empty_tag(self):
        class Health(APIView):
            @action(detail=False)
            async def ping(self, request):
                return {}

        api = NinjaAIO(urls_namespace="tags_view_untagged")
        Health(api=api, prefix="health").add_views_to_route()
        self.assertEqual(_operation_tags(api), {"GET /health/ping": None})


class _Echo(Schema):
    message: str


class _Missing(Schema):
    reason: str


@tag("actions")
class ActionErrorResponsesTestCase(TestCase):
    """Actions document the same error responses as the generated CRUD endpoints."""

    @classmethod
    def setUpTestData(cls):
        class Items(APIViewSet):
            model = models.TestModelSerializer

            @action(detail=False)
            async def stats(self, request):
                return {"count": 0}

            @action(detail=True, methods=["post"], response=_Echo)
            async def echo(self, request, pk: int):
                return {"message": "hi"}

            @action(detail=True, response={200: _Echo, 404: _Missing})
            async def custom(self, request, pk: int):
                return {"message": "hi"}

        api = NinjaAIO(urls_namespace="action_error_responses")
        Items(api=api, prefix="items").add_views_to_route()
        cls.paths = api.get_openapi_schema(path_prefix="")["paths"]

    def _codes(self, path, method):
        return {str(code) for code in self.paths[path][method]["responses"]}

    def test_collection_action_documents_errors_without_404(self):
        self.assertEqual(self._codes("/items/stats", "get"), {"200", "400", "401", "403"})

    def test_detail_action_with_schema_documents_all_errors(self):
        self.assertEqual(self._codes("/items/{id}/echo", "post"), {"200", "400", "401", "403", "404"})

    def test_declared_responses_are_kept(self):
        response = self.paths["/items/{id}/custom"]["get"]["responses"][404]
        schema_ref = response["content"]["application/json"]["schema"]["$ref"]
        self.assertTrue(schema_ref.endswith("_Missing"))
