from django.test import TestCase, tag

from ninja_aio import NinjaAIO
from ninja_aio.models import ModelUtil
from tests.generics.request import Request
from tests.test_app import models, views


@tag("search")
class SearchViewSetMixinTestCase(TestCase):
    """Test SearchViewSetMixin basic functionality."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "search_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.SearchTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

        cls.model.objects.bulk_create(
            [
                cls.model(name="Django Tutorial", description="Learn Django basics"),
                cls.model(name="Python Guide", description="Advanced Python topics"),
                cls.model(name="REST API Design", description="Django REST patterns"),
                cls.model(name="Flask Intro", description="Flask web framework"),
                cls.model(name="Async Programming", description="Django async views"),
            ]
        )

    def test_search_filters_schema_has_search_field(self):
        """Filters schema includes a 'search' field."""
        schema = self.viewset.filters_schema
        self.assertTrue(hasattr(schema, "model_fields"))
        self.assertIn("search", schema.model_fields)

    async def test_search_by_name(self):
        """Search matches records by name field."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(search="Flask")
        result = await view(self.request.get(), filters=filters)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["count"], 1)

    async def test_search_by_description(self):
        """Search matches records by description field."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(search="async")
        result = await view(self.request.get(), filters=filters)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["count"], 1)

    async def test_search_across_fields(self):
        """Search matches across both name and description with OR."""
        view = self.viewset.list_view()
        # "Django" in name: "Django Tutorial", "REST API Design" has "Django" in desc
        # Plus "Async Programming" has "Django" in desc
        filters = self.viewset.filters_schema(search="Django")
        result = await view(self.request.get(), filters=filters)

        self.assertEqual(result.status_code, 200)
        # Django Tutorial (name), REST API Design (desc: Django REST patterns),
        # Async Programming (desc: Django async views)
        self.assertEqual(result.value["count"], 3)

    async def test_search_case_insensitive(self):
        """Search is case-insensitive."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(search="django")
        result = await view(self.request.get(), filters=filters)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["count"], 3)

    async def test_search_no_match(self):
        """Search with no matches returns empty list."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(search="nonexistent_xyz")
        result = await view(self.request.get(), filters=filters)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["count"], 0)

    async def test_search_empty_string(self):
        """Search with empty string returns all records (no filtering)."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(search="")
        result = await view(self.request.get(), filters=filters)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["count"], 5)

    async def test_search_none(self):
        """Search with None returns all records (no filtering)."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(search=None)
        result = await view(self.request.get(), filters=filters)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["count"], 5)

    async def test_no_search_returns_all(self):
        """List without search param returns all records."""
        view = self.viewset.list_view()
        result = await view(self.request.get())

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["count"], 5)


@tag("search")
class SearchWithFiltersTestCase(TestCase):
    """Test SearchViewSetMixin composed with other filter mixins."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "search_filters_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.SearchWithFiltersTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

        cls.model.objects.bulk_create(
            [
                cls.model(name="Django REST", description="API framework"),
                cls.model(name="Django ORM", description="Database layer"),
                cls.model(name="Flask REST", description="Flask API"),
            ]
        )

    async def test_search_and_filter_combined(self):
        """Search and icontains filter work together."""
        view = self.viewset.list_view()
        # search="REST" matches 1st and 3rd, name filter "Django" narrows to 1st
        filters = self.viewset.filters_schema(search="REST", name="Django")
        result = await view(self.request.get(), filters=filters)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["count"], 1)


@tag("search")
class SearchDisabledTestCase(TestCase):
    """Test SearchViewSetMixin with empty search_fields (no-op)."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "search_disabled_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.SearchDisabledTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.request = Request(ModelUtil(cls.model).verbose_name_path_resolver())

    def test_no_search_field_in_schema(self):
        """Empty search_fields means no 'search' in filters schema."""
        schema = self.viewset.filters_schema
        self.assertNotIn("search", schema.model_fields)
