from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, tag
from ninja import Schema
from ninja.pagination import AsyncPaginationBase, CursorPagination, LimitOffsetPagination
from ninja.testing import TestClient

from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from tests.test_app import models


class SmallLimitPagination(LimitOffsetPagination):
    def __init__(self, **kwargs):
        super().__init__(max_limit=2, **kwargs)


class FixedPagePagination(AsyncPaginationBase):
    """Page-based paginator that does not inherit from PageNumberPagination."""

    page_size = 2

    class Input(Schema):
        page: int = 1

    class Output(Schema):
        items: list
        count: int

    def paginate_queryset(self, queryset, pagination, **params):  # pragma: no cover
        raise NotImplementedError

    async def apaginate_queryset(self, queryset, pagination, **params):  # pragma: no cover
        raise NotImplementedError


@tag("pagination")
class PaginationClassTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for index in range(5):
            models.TestModelSerializer.objects.create(name=f"n{index}", description="d")

    def _client(self, pagination_class, namespace):
        class PaginatedAPI(APIViewSet):
            model = models.TestModelSerializer
            execution_mode = "sync"

        PaginatedAPI.pagination_class = pagination_class
        api = NinjaAIO(urls_namespace=namespace)
        PaginatedAPI(api=api, prefix="paginated").add_views_to_route()
        return TestClient(api)

    def test_limit_offset_respects_the_paginator_max_limit(self):
        client = self._client(SmallLimitPagination, "pagination_max_limit")
        body = client.get("/paginated?limit=10").json()
        self.assertEqual(len(body["items"]), 2)
        self.assertEqual(body["count"], 5)

    def test_page_paginator_without_page_size_helper_uses_its_page_size(self):
        client = self._client(FixedPagePagination, "pagination_fixed_page")
        body = client.get("/paginated?page=3").json()
        self.assertEqual(len(body["items"]), 1)

    def test_unsupported_paginator_is_rejected_at_startup(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "CursorPagination is not supported"):
            self._client(CursorPagination, "pagination_cursor")
