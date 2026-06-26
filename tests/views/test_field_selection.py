import json

from django.http import JsonResponse
from django.test import TestCase, tag
from ninja import Status

from ninja_aio import NinjaAIO
from ninja_aio.models import ModelUtil
from tests.generics.request import Request
from tests.test_app import models, views


@tag("field_selection")
class FieldSelectionListTestCase(TestCase):
    """Test FieldSelectionViewSetMixin on list endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "field_selection_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.FieldSelectionTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

        cls.model.objects.bulk_create([
            cls.model(name="Alpha", description="first"),
            cls.model(name="Beta", description="second"),
            cls.model(name="Gamma", description="third"),
        ])

    def test_filters_schema_has_fields_param(self):
        """Filters schema includes the 'fields' parameter."""
        self.assertIn("fields", self.viewset.filters_schema.model_fields)

    async def test_list_without_fields_returns_full_response(self):
        """List without ?fields returns Status(200, ...) as usual."""
        view = self.viewset.list_view()
        result = await view(self.request.get())
        self.assertIsInstance(result, Status)
        self.assertEqual(result.status_code, 200)
        items = result.value["items"]
        self.assertTrue(len(items) > 0)
        self.assertIn("name", items[0])
        self.assertIn("description", items[0])

    async def test_list_with_valid_fields_returns_json_response(self):
        """List with ?fields returns JsonResponse with only requested fields."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(fields="id,name")
        result = await view(self.request.get(), filters=filters)
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.content)
        self.assertIn("items", data)
        self.assertIn("count", data)
        item = data["items"][0]
        self.assertIn("id", item)
        self.assertIn("name", item)
        self.assertNotIn("description", item)

    async def test_list_fields_single_field(self):
        """Requesting a single field returns only that field."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(fields="name")
        result = await view(self.request.get(), filters=filters)
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.content)
        item = data["items"][0]
        self.assertIn("name", item)
        self.assertNotIn("id", item)
        self.assertNotIn("description", item)

    async def test_list_fields_ignores_unknown_fields(self):
        """Unknown field names are silently ignored."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(fields="id,nonexistent_field")
        result = await view(self.request.get(), filters=filters)
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.content)
        item = data["items"][0]
        self.assertIn("id", item)
        self.assertNotIn("nonexistent_field", item)

    async def test_list_all_unknown_fields_returns_full_response(self):
        """All-unknown fields fall back to full response (no valid fields found)."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(fields="nonexistent,also_bad")
        result = await view(self.request.get(), filters=filters)
        self.assertIsInstance(result, Status)
        self.assertEqual(result.status_code, 200)

    async def test_list_empty_fields_returns_full_response(self):
        """Empty ?fields value returns the full response."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(fields="")
        result = await view(self.request.get(), filters=filters)
        self.assertIsInstance(result, Status)

    async def test_list_fields_none_returns_full_response(self):
        """fields=None returns the full response."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(fields=None)
        result = await view(self.request.get(), filters=filters)
        self.assertIsInstance(result, Status)

    async def test_list_count_preserved_with_field_selection(self):
        """Count is correct when field selection is active."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(fields="id")
        result = await view(self.request.get(), filters=filters)
        data = json.loads(result.content)
        self.assertEqual(data["count"], 3)

    async def test_list_fields_not_passed_to_query_params_handler(self):
        """'fields' does not leak into the queryset filter (no invalid queryset filter)."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(fields="id,name")
        # Should not raise FieldError or similar
        result = await view(self.request.get(), filters=filters)
        data = json.loads(result.content)
        self.assertEqual(data["count"], 3)


@tag("field_selection")
class FieldSelectionRetrieveTestCase(TestCase):
    """Test FieldSelectionViewSetMixin on retrieve endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "field_selection_retrieve_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.FieldSelectionTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)
        cls.obj = cls.model.objects.create(name="Test", description="desc")

    async def test_retrieve_without_fields_returns_status(self):
        """Retrieve without ?fields returns Status(200, ...) as usual."""
        pk_schema = cls.viewset.path_schema if hasattr(self, "cls") else self.viewset.path_schema
        pk_name = self.viewset.model_util.model_pk_name
        view = self.viewset.retrieve_view()
        pk_schema = self.viewset.path_schema(**{pk_name: self.obj.pk})
        result = await view(self.request.get(), pk=pk_schema)
        self.assertIsInstance(result, Status)
        self.assertEqual(result.status_code, 200)
        self.assertIn("name", result.value)
        self.assertIn("description", result.value)

    async def test_retrieve_with_fields_returns_json_response(self):
        """Retrieve with ?fields returns JsonResponse with only requested fields."""
        pk_name = self.viewset.model_util.model_pk_name
        view = self.viewset.retrieve_view()
        pk_schema = self.viewset.path_schema(**{pk_name: self.obj.pk})
        result = await view(self.request.get(), pk=pk_schema, fields="id,name")
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.content)
        self.assertIn("id", data)
        self.assertIn("name", data)
        self.assertNotIn("description", data)

    async def test_retrieve_unknown_fields_ignored(self):
        """Unknown field names are silently ignored in retrieve."""
        pk_name = self.viewset.model_util.model_pk_name
        view = self.viewset.retrieve_view()
        pk_schema = self.viewset.path_schema(**{pk_name: self.obj.pk})
        result = await view(self.request.get(), pk=pk_schema, fields="id,does_not_exist")
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.content)
        self.assertIn("id", data)
        self.assertNotIn("does_not_exist", data)

    async def test_retrieve_all_unknown_fields_returns_full(self):
        """All-unknown fields fall back to full response."""
        pk_name = self.viewset.model_util.model_pk_name
        view = self.viewset.retrieve_view()
        pk_schema = self.viewset.path_schema(**{pk_name: self.obj.pk})
        result = await view(self.request.get(), pk=pk_schema, fields="totally_fake")
        self.assertIsInstance(result, Status)
        self.assertEqual(result.status_code, 200)


@tag("field_selection")
class FieldSelectionRetrieveWithObjectHooksTestCase(TestCase):
    """Test retrieve field selection when _has_object_hooks=True (obj is pre-fetched)."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "field_selection_hooks_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.FieldSelectionWithPermissionsTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.obj = cls.model.objects.create(name="HookTest", description="hook_desc")

    async def test_retrieve_with_fields_and_object_hooks(self):
        """Retrieve with field selection works when obj is pre-fetched via hooks."""
        pk_name = self.viewset.model_util.model_pk_name
        view = self.viewset.retrieve_view()
        pk_schema = self.viewset.path_schema(**{pk_name: self.obj.pk})
        request = views.FieldSelectionWithPermissionsTestAPI.__bases__[0].__bases__[0]  # just need the request

        from tests.generics.request import Request
        req = Request(self.viewset.model_util.verbose_name_path_resolver()).get()
        result = await view(req, pk=pk_schema, fields="id,name")
        import json
        from django.http import JsonResponse
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.content)
        self.assertIn("id", data)
        self.assertIn("name", data)
        self.assertNotIn("description", data)

    async def test_retrieve_without_fields_and_object_hooks(self):
        """Retrieve without field selection returns full Status response with hooks."""
        pk_name = self.viewset.model_util.model_pk_name
        view = self.viewset.retrieve_view()
        pk_schema = self.viewset.path_schema(**{pk_name: self.obj.pk})

        from tests.generics.request import Request
        req = Request(self.viewset.model_util.verbose_name_path_resolver()).get()
        result = await view(req, pk=pk_schema)
        self.assertIsInstance(result, Status)
        self.assertEqual(result.status_code, 200)
        self.assertIn("name", result.value)


@tag("field_selection")
class FieldSelectionWithFiltersTestCase(TestCase):
    """Test FieldSelectionViewSetMixin composed with IcontainsFilterViewSetMixin."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "field_selection_filters_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.FieldSelectionWithFiltersTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

        cls.model.objects.bulk_create([
            cls.model(name="Apple", description="fruit"),
            cls.model(name="Apricot", description="fruit"),
            cls.model(name="Banana", description="fruit"),
        ])

    async def test_field_selection_with_filter(self):
        """Field selection and icontains filter work together."""
        view = self.viewset.list_view()
        filters = self.viewset.filters_schema(fields="id,name", name="ap")
        result = await view(self.request.get(), filters=filters)
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.content)
        self.assertEqual(data["count"], 2)
        item = data["items"][0]
        self.assertIn("id", item)
        self.assertIn("name", item)
        self.assertNotIn("description", item)
