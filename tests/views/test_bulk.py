from unittest.mock import patch

from django.test import TestCase, tag

from ninja_aio import NinjaAIO
from ninja_aio.exceptions import SerializeError
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

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 3)
        self.assertEqual(result.value["errors"]["count"], 0)
        self.assertEqual(len(result.value["success"]["details"]), 3)

        # Success details contain PKs
        for pk in result.value["success"]["details"]:
            self.assertTrue(await self.model.objects.filter(pk=pk).aexists())

        # Verify objects exist in DB
        count = await self.model.objects.acount()
        self.assertEqual(count, 3)

    async def test_bulk_create_empty_list(self):
        """Bulk create with an empty list returns empty result."""
        view = self.viewset.bulk_create_view()
        result = await view(self.post_request, [])

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 0)
        self.assertEqual(result.value["errors"]["count"], 0)

    async def test_bulk_update(self):
        """Update multiple objects in one request."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="orig_1", description="desc_1")
        obj2 = await self.model.objects.acreate(name="orig_2", description="desc_2")

        update_items = [
            self.viewset.bulk_update_schema(id=obj1.pk, description="updated_1"),
            self.viewset.bulk_update_schema(id=obj2.pk, description="updated_2"),
        ]

        view = self.viewset.bulk_update_view()
        result = await view(self.patch_request, update_items)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 2)
        self.assertEqual(result.value["errors"]["count"], 0)
        self.assertIn(obj1.pk, result.value["success"]["details"])
        self.assertIn(obj2.pk, result.value["success"]["details"])

        # Verify data was actually updated in DB
        await obj1.arefresh_from_db()
        await obj2.arefresh_from_db()
        self.assertEqual(obj1.description, "updated_1")
        self.assertEqual(obj2.description, "updated_2")

    async def test_bulk_update_partial_failure(self):
        """Bulk update with one valid and one non-existent PK returns partial success."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="orig_1", description="desc_1")

        update_items = [
            self.viewset.bulk_update_schema(id=obj1.pk, description="updated_1"),
            self.viewset.bulk_update_schema(id=99999, description="nope"),
        ]

        view = self.viewset.bulk_update_view()
        result = await view(self.patch_request, update_items)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 1)
        self.assertEqual(result.value["errors"]["count"], 1)
        self.assertIn(obj1.pk, result.value["success"]["details"])

    async def test_bulk_delete(self):
        """Delete multiple objects in one request."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="del_1", description="desc_1")
        obj2 = await self.model.objects.acreate(name="del_2", description="desc_2")
        obj3 = await self.model.objects.acreate(name="keep", description="desc_3")

        delete_data = self.viewset.bulk_delete_schema(ids=[obj1.pk, obj2.pk])

        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 2)
        self.assertEqual(result.value["errors"]["count"], 0)
        self.assertIn(obj1.pk, result.value["success"]["details"])
        self.assertIn(obj2.pk, result.value["success"]["details"])

        # Verify only obj3 remains
        count = await self.model.objects.acount()
        self.assertEqual(count, 1)
        remaining = await self.model.objects.afirst()
        self.assertEqual(remaining.pk, obj3.pk)

    async def test_bulk_delete_partial_failure(self):
        """Bulk delete with some non-existent PKs returns partial success."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="del_1", description="desc_1")

        delete_data = self.viewset.bulk_delete_schema(ids=[obj1.pk, 99999])

        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 1)
        self.assertEqual(result.value["errors"]["count"], 1)
        self.assertIn(obj1.pk, result.value["success"]["details"])

        count = await self.model.objects.acount()
        self.assertEqual(count, 0)

    async def test_bulk_delete_empty_list(self):
        """Bulk delete with an empty list is a no-op."""
        initial_count = await self.model.objects.acount()

        delete_data = self.viewset.bulk_delete_schema(ids=[])

        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 0)
        self.assertEqual(result.value["errors"]["count"], 0)
        final_count = await self.model.objects.acount()
        self.assertEqual(initial_count, final_count)

    async def test_bulk_create_serialize_error(self):
        """Bulk create collects SerializeError as error details."""
        await self.model.objects.all().adelete()

        items = [
            schema.TestModelSchemaIn(name="ok_item", description="desc"),
            schema.TestModelSchemaIn(name="bad_item", description="desc"),
        ]

        original = self.viewset.model_util._create_instance

        async def mock_create(request, data):
            if data.name == "bad_item":
                raise SerializeError("create failed")
            return await original(request, data)

        with patch.object(
            self.viewset.model_util, "_create_instance", side_effect=mock_create
        ):
            view = self.viewset.bulk_create_view()
            result = await view(self.post_request, items)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 1)
        self.assertEqual(result.value["errors"]["count"], 1)

    async def test_bulk_create_generic_exception(self):
        """Bulk create collects generic exceptions via _format_bulk_error fallback."""
        await self.model.objects.all().adelete()

        items = [
            schema.TestModelSchemaIn(name="bad", description="desc"),
        ]

        with patch.object(
            self.viewset.model_util,
            "_create_instance",
            side_effect=RuntimeError("unexpected"),
        ):
            view = self.viewset.bulk_create_view()
            result = await view(self.post_request, items)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 0)
        self.assertEqual(result.value["errors"]["count"], 1)
        self.assertEqual(result.value["errors"]["details"][0]["error"], "unexpected")

    async def test_bulk_update_generic_exception(self):
        """Bulk update collects generic exceptions via _format_bulk_error fallback."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="orig", description="desc")

        update_items = [
            self.viewset.bulk_update_schema(id=obj1.pk, description="updated"),
        ]

        with patch.object(
            self.viewset.model_util,
            "_update_instance",
            side_effect=RuntimeError("unexpected update"),
        ):
            view = self.viewset.bulk_update_view()
            result = await view(self.patch_request, update_items)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 0)
        self.assertEqual(result.value["errors"]["count"], 1)
        self.assertEqual(
            result.value["errors"]["details"][0]["error"], "unexpected update"
        )


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

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 2)
        self.assertEqual(result.value["errors"]["count"], 0)

        # Success details contain PKs
        for pk in result.value["success"]["details"]:
            self.assertTrue(await self.model.objects.filter(pk=pk).aexists())

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
        self.assertEqual(result.value["success"]["count"], 2)
        self.assertEqual(result.value["errors"]["count"], 0)
        self.assertIn(obj1.pk, result.value["success"]["details"])
        self.assertIn(obj2.pk, result.value["success"]["details"])

    async def test_bulk_delete(self):
        """Bulk delete with ModelSerializer."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="ms_del_1", description="d1")
        obj2 = await self.model.objects.acreate(name="ms_del_2", description="d2")

        delete_data = self.viewset.bulk_delete_schema(ids=[obj1.pk, obj2.pk])

        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 2)
        self.assertEqual(result.value["errors"]["count"], 0)
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


@tag("bulk", "bulk_response_fields")
class BulkResponseFieldsSingleTestCase(TestCase):
    """Test bulk operations with bulk_response_fields set to a single field name."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "bulk_single_field_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.TestModelBulkSingleFieldAPI()
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

    async def test_bulk_create_returns_single_field(self):
        """Bulk create returns the configured field value instead of PK."""
        await self.model.objects.all().adelete()

        items = [
            schema.TestModelSchemaIn(name="field_1", description="desc_1"),
            schema.TestModelSchemaIn(name="field_2", description="desc_2"),
        ]

        view = self.viewset.bulk_create_view()
        result = await view(self.post_request, items)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 2)
        details = result.value["success"]["details"]
        self.assertEqual(details, ["field_1", "field_2"])

    async def test_bulk_update_returns_single_field(self):
        """Bulk update returns the configured field value instead of PK."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="upd_1", description="d1")
        obj2 = await self.model.objects.acreate(name="upd_2", description="d2")

        update_items = [
            self.viewset.bulk_update_schema(id=obj1.pk, description="new_d1"),
            self.viewset.bulk_update_schema(id=obj2.pk, description="new_d2"),
        ]

        view = self.viewset.bulk_update_view()
        result = await view(self.patch_request, update_items)

        self.assertEqual(result.status_code, 200)
        details = result.value["success"]["details"]
        self.assertEqual(details, ["upd_1", "upd_2"])

    async def test_bulk_delete_returns_single_field(self):
        """Bulk delete returns the configured field value instead of PK."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="del_1", description="d1")
        obj2 = await self.model.objects.acreate(name="del_2", description="d2")

        delete_data = self.viewset.bulk_delete_schema(ids=[obj1.pk, obj2.pk])

        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.status_code, 200)
        details = result.value["success"]["details"]
        self.assertEqual(sorted(details), ["del_1", "del_2"])

        count = await self.model.objects.acount()
        self.assertEqual(count, 0)


@tag("bulk", "bulk_response_fields")
class BulkResponseFieldsMultiTestCase(TestCase):
    """Test bulk operations with bulk_response_fields set to a list of fields."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "bulk_multi_field_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.TestModelBulkMultiFieldAPI()
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

    async def test_bulk_create_returns_multi_fields(self):
        """Bulk create returns dicts with configured fields."""
        await self.model.objects.all().adelete()

        items = [
            schema.TestModelSchemaIn(name="multi_1", description="desc_1"),
            schema.TestModelSchemaIn(name="multi_2", description="desc_2"),
        ]

        view = self.viewset.bulk_create_view()
        result = await view(self.post_request, items)

        self.assertEqual(result.status_code, 200)
        details = result.value["success"]["details"]
        self.assertEqual(len(details), 2)
        for detail in details:
            self.assertIn("id", detail)
            self.assertIn("name", detail)
            self.assertIsInstance(detail, dict)

        names = [d["name"] for d in details]
        self.assertEqual(names, ["multi_1", "multi_2"])

    async def test_bulk_update_returns_multi_fields(self):
        """Bulk update returns dicts with configured fields."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="upd_multi", description="d1")

        update_items = [
            self.viewset.bulk_update_schema(id=obj1.pk, description="new_d1"),
        ]

        view = self.viewset.bulk_update_view()
        result = await view(self.patch_request, update_items)

        self.assertEqual(result.status_code, 200)
        details = result.value["success"]["details"]
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["id"], obj1.pk)
        self.assertEqual(details[0]["name"], "upd_multi")

    async def test_bulk_delete_returns_multi_fields(self):
        """Bulk delete returns dicts with configured fields."""
        await self.model.objects.all().adelete()

        obj1 = await self.model.objects.acreate(name="del_1", description="d1")
        obj2 = await self.model.objects.acreate(name="del_2", description="d2")

        delete_data = self.viewset.bulk_delete_schema(ids=[obj1.pk, obj2.pk])

        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.status_code, 200)
        details = result.value["success"]["details"]
        self.assertEqual(len(details), 2)
        for detail in details:
            self.assertIn("id", detail)
            self.assertIn("name", detail)

        count = await self.model.objects.acount()
        self.assertEqual(count, 0)
