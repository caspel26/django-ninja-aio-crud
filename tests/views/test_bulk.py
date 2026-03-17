from django.test import TestCase, tag

from ninja_aio import NinjaAIO
from ninja_aio.exceptions import NotFoundError
from ninja_aio.models import ModelUtil
from tests.generics.request import Request
from tests.test_app import models, views, schema


@tag("bulk")
class BulkModelViewSetTestCase(TestCase):
    """Test bulk operations on a plain model (non-ModelSerializer) viewset."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "bulk_model_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.TestModelBulkAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.pk_att = cls.model._meta.pk.attname
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

    @property
    def get_request(self):
        return self.request.get()

    @property
    def post_request(self):
        return self.request.post()

    @property
    def patch_request(self):
        return self.request.patch()

    @property
    def delete_request(self):
        return self.request.delete()

    def test_bulk_routes_registered(self):
        """Verify that bulk endpoints are registered on the router."""
        test_router = self.api._routers[1][1]
        paths = [str(route.pattern) for route in test_router.urls_paths(self.path)]
        bulk_path = f"{self.path}/bulk/"
        self.assertIn(bulk_path, paths)

    async def test_bulk_create(self):
        """Create multiple objects in one request."""
        await self.model.objects.all().adelete()

        items = [
            schema.TestModelSchemaIn(name="bulk_1", description="desc_1"),
            schema.TestModelSchemaIn(name="bulk_2", description="desc_2"),
            schema.TestModelSchemaIn(name="bulk_3", description="desc_3"),
        ]

        view = self.viewset.bulk_create_view()
        result = await view(self.post_request, items)

        self.assertEqual(result.status_code, 201)
        self.assertEqual(len(result.value), 3)

        # Verify response data
        self.assertEqual(result.value[0]["name"], "bulk_1")
        self.assertEqual(result.value[1]["name"], "bulk_2")
        self.assertEqual(result.value[2]["name"], "bulk_3")

        # Verify objects exist in DB
        count = await self.model.objects.acount()
        self.assertEqual(count, 3)

    async def test_bulk_create_empty_list(self):
        """Bulk create with an empty list returns empty result."""
        view = self.viewset.bulk_create_view()
        result = await view(self.post_request, [])

        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.value, [])

    async def test_bulk_update(self):
        """Update multiple objects in one request."""
        await self.model.objects.all().adelete()

        # Create objects first
        obj1 = await self.model.objects.acreate(name="orig_1", description="desc_1")
        obj2 = await self.model.objects.acreate(name="orig_2", description="desc_2")

        update_items = [
            self.viewset.bulk_update_schema(id=obj1.pk, description="updated_1"),
            self.viewset.bulk_update_schema(id=obj2.pk, description="updated_2"),
        ]

        view = self.viewset.bulk_update_view()
        result = await view(self.patch_request, update_items)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.value), 2)

        # Verify updated data
        self.assertEqual(result.value[0]["description"], "updated_1")
        self.assertEqual(result.value[0]["name"], "orig_1")
        self.assertEqual(result.value[1]["description"], "updated_2")
        self.assertEqual(result.value[1]["name"], "orig_2")

    async def test_bulk_update_not_found(self):
        """Bulk update raises NotFoundError for non-existent PK."""
        await self.model.objects.all().adelete()

        update_items = [
            self.viewset.bulk_update_schema(id=99999, description="nope"),
        ]

        view = self.viewset.bulk_update_view()
        with self.assertRaises(NotFoundError):
            await view(self.patch_request, update_items)

    async def test_bulk_delete(self):
        """Delete multiple objects in one request."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="del_1", description="desc_1")
        obj2 = await self.model.objects.acreate(name="del_2", description="desc_2")
        obj3 = await self.model.objects.acreate(name="keep", description="desc_3")

        delete_data = self.viewset.bulk_delete_schema(ids=[obj1.pk, obj2.pk])

        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.status_code, 204)
        self.assertIsNone(result.value)

        # Verify only obj3 remains
        count = await self.model.objects.acount()
        self.assertEqual(count, 1)
        remaining = await self.model.objects.afirst()
        self.assertEqual(remaining.pk, obj3.pk)

    async def test_bulk_delete_not_found(self):
        """Bulk delete raises NotFoundError for non-existent PK."""
        await self.model.objects.all().adelete()

        delete_data = self.viewset.bulk_delete_schema(ids=[99999])

        view = self.viewset.bulk_delete_view()
        with self.assertRaises(NotFoundError):
            await view(self.delete_request, delete_data)

    async def test_bulk_delete_empty_list(self):
        """Bulk delete with an empty list is a no-op."""
        initial_count = await self.model.objects.acount()

        delete_data = self.viewset.bulk_delete_schema(ids=[])

        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.status_code, 204)
        final_count = await self.model.objects.acount()
        self.assertEqual(initial_count, final_count)


@tag("bulk")
class BulkModelSerializerViewSetTestCase(TestCase):
    """Test bulk operations on a ModelSerializer viewset."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "bulk_model_serializer_test"
        cls.model = models.TestModelSerializer
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.TestModelSerializerBulkAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.pk_att = cls.model._meta.pk.attname
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

    @property
    def post_request(self):
        return self.request.post()

    @property
    def patch_request(self):
        return self.request.patch()

    @property
    def delete_request(self):
        return self.request.delete()

    async def test_bulk_create(self):
        """Bulk create with ModelSerializer."""
        await self.model.objects.all().adelete()

        schema_in = self.viewset.schema_in
        items = [
            schema_in(name="ms_bulk_1", description="desc_1"),
            schema_in(name="ms_bulk_2", description="desc_2"),
        ]

        view = self.viewset.bulk_create_view()
        result = await view(self.post_request, items)

        self.assertEqual(result.status_code, 201)
        self.assertEqual(len(result.value), 2)
        self.assertEqual(result.value[0]["name"], "ms_bulk_1")
        self.assertEqual(result.value[1]["name"], "ms_bulk_2")

        count = await self.model.objects.acount()
        self.assertEqual(count, 2)

    async def test_bulk_update(self):
        """Bulk update with ModelSerializer."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="ms_1", description="desc_1")
        obj2 = await self.model.objects.acreate(name="ms_2", description="desc_2")

        update_items = [
            self.viewset.bulk_update_schema(id=obj1.pk, description="ms_updated_1"),
            self.viewset.bulk_update_schema(id=obj2.pk, description="ms_updated_2"),
        ]

        view = self.viewset.bulk_update_view()
        result = await view(self.patch_request, update_items)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.value), 2)
        self.assertEqual(result.value[0]["description"], "ms_updated_1")
        self.assertEqual(result.value[1]["description"], "ms_updated_2")

    async def test_bulk_delete(self):
        """Bulk delete with ModelSerializer."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="ms_del_1", description="d1")
        obj2 = await self.model.objects.acreate(name="ms_del_2", description="d2")

        delete_data = self.viewset.bulk_delete_schema(ids=[obj1.pk, obj2.pk])

        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.status_code, 204)
        count = await self.model.objects.acount()
        self.assertEqual(count, 0)


@tag("bulk")
class BulkOperationsDisabledTestCase(TestCase):
    """Test that bulk operations are not registered by default."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "bulk_disabled_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.TestModelAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()

    def test_no_bulk_routes_by_default(self):
        """Verify that bulk endpoints are NOT registered when bulk_operations is empty."""
        test_router = self.api._routers[1][1]
        paths = [str(route.pattern) for route in test_router.urls_paths(self.path)]
        bulk_path = f"{self.path}/bulk/"
        self.assertNotIn(bulk_path, paths)


@tag("bulk")
class BulkOperationsSelectiveTestCase(TestCase):
    """Test that individual bulk operations can be selectively enabled."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "bulk_selective_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        class SelectiveBulkAPI(views.GenericAPIViewSet):
            model = models.TestModel
            schema_in = schema.TestModelSchemaIn
            schema_out = schema.TestModelSchemaOut
            schema_update = schema.TestModelSchemaPatch
            bulk_operations = ["create"]

        cls.viewset = SelectiveBulkAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

    def test_only_bulk_create_registered(self):
        """Only bulk_create should be in _bulk_views when bulk_operations=['create']."""
        bulk_views = self.viewset._bulk_views
        self.assertIn("create", bulk_views)
        self.assertNotIn("update", bulk_views)
        self.assertNotIn("delete", bulk_views)
