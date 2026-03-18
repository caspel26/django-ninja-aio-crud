from django.test import TestCase, tag

from ninja_aio import NinjaAIO
from ninja_aio.models import ModelUtil
from tests.generics.request import Request
from tests.test_app import models, views


@tag("ordering")
class OrderingTestCase(TestCase):
    """Test native ordering support on list endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "ordering_test"
        cls.model = models.TestModelSerializer
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.TestModelSerializerOrderingAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

    @property
    def get_request(self):
        return self.request.get()

    async def _create_objects(self):
        await self.model.objects.all().adelete()
        obj_a = await self.model.objects.acreate(name="alpha", description="desc")
        obj_b = await self.model.objects.acreate(name="beta", description="desc")
        obj_c = await self.model.objects.acreate(name="gamma", description="desc")
        return obj_a, obj_b, obj_c

    def test_ordering_field_in_filters_schema(self):
        """Ordering field appears in the filters schema when ordering_fields is set."""
        schema_fields = self.viewset.filters_schema.model_fields
        self.assertIn("ordering", schema_fields)

    async def test_list_view_applies_default_ordering_without_filters(self):
        """List view applies default_ordering when called without any query params."""
        obj_a, obj_b, obj_c = await self._create_objects()

        view = self.viewset.list_view()
        result = await view(self.get_request)

        # default_ordering is "-id", so highest id first
        self.assertEqual(result.status_code, 200)
        items = result.value["items"]
        self.assertEqual(items[0]["id"], obj_c.pk)
        self.assertEqual(items[-1]["id"], obj_a.pk)

    async def test_default_ordering_applied(self):
        """Default ordering is applied when no ?ordering parameter is provided."""
        obj_a, obj_b, obj_c = await self._create_objects()

        qs = self.model.objects.all()
        result = self.viewset._apply_ordering(qs, None)

        # default_ordering is "-id", so highest id first
        items = [obj async for obj in result]
        self.assertEqual(items[0].pk, obj_c.pk)
        self.assertEqual(items[-1].pk, obj_a.pk)

    async def test_single_field_ascending(self):
        """?ordering=name sorts ascending by name."""
        obj_a, obj_b, obj_c = await self._create_objects()

        qs = self.model.objects.all()
        result = self.viewset._apply_ordering(qs, "name")

        items = [obj async for obj in result]
        self.assertEqual(items[0].name, "alpha")
        self.assertEqual(items[1].name, "beta")
        self.assertEqual(items[2].name, "gamma")

    async def test_single_field_descending(self):
        """?ordering=-name sorts descending by name."""
        obj_a, obj_b, obj_c = await self._create_objects()

        qs = self.model.objects.all()
        result = self.viewset._apply_ordering(qs, "-name")

        items = [obj async for obj in result]
        self.assertEqual(items[0].name, "gamma")
        self.assertEqual(items[1].name, "beta")
        self.assertEqual(items[2].name, "alpha")

    async def test_multiple_fields(self):
        """?ordering=name,id applies composite ordering."""
        await self.model.objects.all().adelete()
        obj1 = await self.model.objects.acreate(name="alpha", description="d1")
        obj2 = await self.model.objects.acreate(name="alpha", description="d2")
        obj3 = await self.model.objects.acreate(name="beta", description="d3")

        qs = self.model.objects.all()
        result = self.viewset._apply_ordering(qs, "name,-id")

        items = [obj async for obj in result]
        # Both alphas first (by name), then within alpha: -id means obj2 before obj1
        self.assertEqual(items[0].pk, obj2.pk)
        self.assertEqual(items[1].pk, obj1.pk)
        self.assertEqual(items[2].pk, obj3.pk)

    async def test_invalid_field_ignored(self):
        """Invalid ordering field falls back to default_ordering."""
        obj_a, obj_b, obj_c = await self._create_objects()

        qs = self.model.objects.all()
        result = self.viewset._apply_ordering(qs, "nonexistent")

        # Falls back to default_ordering "-id"
        items = [obj async for obj in result]
        self.assertEqual(items[0].pk, obj_c.pk)
        self.assertEqual(items[-1].pk, obj_a.pk)

    async def test_mixed_valid_invalid_fields(self):
        """Valid fields are applied, invalid ones are silently discarded."""
        obj_a, obj_b, obj_c = await self._create_objects()

        qs = self.model.objects.all()
        result = self.viewset._apply_ordering(qs, "-name,invalid,id")

        items = [obj async for obj in result]
        # Only -name is applied (invalid and id after invalid is still valid)
        # Actually: -name and id are both valid, invalid is discarded
        self.assertEqual(items[0].name, "gamma")
        self.assertEqual(items[1].name, "beta")
        self.assertEqual(items[2].name, "alpha")

    async def test_empty_ordering_string(self):
        """Empty ordering string falls back to default_ordering."""
        obj_a, obj_b, obj_c = await self._create_objects()

        qs = self.model.objects.all()
        result = self.viewset._apply_ordering(qs, "")

        # Falls back to default_ordering "-id"
        items = [obj async for obj in result]
        self.assertEqual(items[0].pk, obj_c.pk)
        self.assertEqual(items[-1].pk, obj_a.pk)

    async def test_whitespace_handling(self):
        """Whitespace around field names is trimmed."""
        obj_a, obj_b, obj_c = await self._create_objects()

        qs = self.model.objects.all()
        result = self.viewset._apply_ordering(qs, " name , -id ")

        items = [obj async for obj in result]
        self.assertEqual(items[0].name, "alpha")


@tag("ordering")
class OrderingDisabledTestCase(TestCase):
    """Test that ordering is not active when ordering_fields is empty."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "ordering_disabled_test"
        cls.model = models.TestModelSerializer
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.TestModelSerializerAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()

    def test_no_ordering_field_in_filters_schema(self):
        """No ordering field in filters schema when ordering_fields is empty."""
        schema_fields = self.viewset.filters_schema.model_fields
        self.assertNotIn("ordering", schema_fields)

    async def test_apply_ordering_noop(self):
        """_apply_ordering returns queryset unchanged when ordering_fields is empty."""
        qs = self.model.objects.all()
        result = self.viewset._apply_ordering(qs, "name")
        # Should return the same queryset object, unchanged
        self.assertIs(result, qs)


@tag("ordering")
class OrderingWithFiltersTestCase(TestCase):
    """Test ordering combined with existing filters."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "ordering_with_filters_test"
        cls.model = models.TestModelSerializer
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.TestModelSerializerOrderingWithFiltersAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

    def test_ordering_and_filter_in_schema(self):
        """Both ordering and filter fields appear in filters schema."""
        schema_fields = self.viewset.filters_schema.model_fields
        self.assertIn("ordering", schema_fields)
        self.assertIn("name", schema_fields)

    async def test_ordering_with_filter(self):
        """Ordering works alongside icontains filter."""
        await self.model.objects.all().adelete()
        await self.model.objects.acreate(name="alpha_test", description="d1")
        await self.model.objects.acreate(name="beta_test", description="d2")
        await self.model.objects.acreate(name="gamma_other", description="d3")

        # Filter by "test" then order by -name
        qs = self.model.objects.all()
        qs = await self.viewset.query_params_handler(qs, {"name": "test"})
        result = self.viewset._apply_ordering(qs, "-name")

        items = [obj async for obj in result]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].name, "beta_test")
        self.assertEqual(items[1].name, "alpha_test")


@tag("ordering")
class OrderingDefaultListTestCase(TestCase):
    """Test that default_ordering accepts both str and list."""

    @classmethod
    def setUpTestData(cls):
        cls.model = models.TestModel

    async def test_default_ordering_as_string(self):
        """String default_ordering works correctly."""
        from ninja_aio.views import APIViewSet

        viewset = APIViewSet.__new__(APIViewSet)
        viewset.ordering_fields = ["name"]
        viewset.default_ordering = "-name"

        await self.model.objects.all().adelete()
        await self.model.objects.acreate(name="alpha", description="d")
        await self.model.objects.acreate(name="gamma", description="d")
        await self.model.objects.acreate(name="beta", description="d")

        qs = self.model.objects.all()
        result = viewset._apply_ordering(qs, None)

        items = [obj async for obj in result]
        self.assertEqual(items[0].name, "gamma")
        self.assertEqual(items[1].name, "beta")
        self.assertEqual(items[2].name, "alpha")

    async def test_default_ordering_as_list(self):
        """List default_ordering works correctly."""
        from ninja_aio.views import APIViewSet

        viewset = APIViewSet.__new__(APIViewSet)
        viewset.ordering_fields = ["name", "id"]
        viewset.default_ordering = ["name", "-id"]

        await self.model.objects.all().adelete()
        obj1 = await self.model.objects.acreate(name="alpha", description="d1")
        obj2 = await self.model.objects.acreate(name="alpha", description="d2")
        await self.model.objects.acreate(name="beta", description="d3")

        qs = self.model.objects.all()
        result = viewset._apply_ordering(qs, None)

        items = [obj async for obj in result]
        # name asc, then -id within same name
        self.assertEqual(items[0].name, "alpha")
        self.assertEqual(items[0].pk, obj2.pk)
        self.assertEqual(items[1].name, "alpha")
        self.assertEqual(items[1].pk, obj1.pk)
        self.assertEqual(items[2].name, "beta")

    async def test_no_default_ordering(self):
        """ordering_fields set but no default_ordering returns queryset unchanged."""
        from ninja_aio.views import APIViewSet

        viewset = APIViewSet.__new__(APIViewSet)
        viewset.ordering_fields = ["name"]
        viewset.default_ordering = []

        qs = self.model.objects.all()
        result = viewset._apply_ordering(qs, None)
        # No ordering applied, queryset returned as-is
        self.assertEqual(str(result.query), str(qs.query))

    async def test_consecutive_commas_ignored(self):
        """Consecutive commas produce empty fields that are skipped."""
        from ninja_aio.views import APIViewSet

        viewset = APIViewSet.__new__(APIViewSet)
        viewset.ordering_fields = ["name"]
        viewset.default_ordering = []

        await self.model.objects.all().adelete()
        await self.model.objects.acreate(name="beta", description="d")
        await self.model.objects.acreate(name="alpha", description="d")

        qs = self.model.objects.all()
        result = viewset._apply_ordering(qs, "name,,")

        items = [obj async for obj in result]
        self.assertEqual(items[0].name, "alpha")
        self.assertEqual(items[1].name, "beta")
