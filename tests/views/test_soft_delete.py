from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, tag

from ninja_aio import NinjaAIO
from ninja_aio.exceptions import NotFoundError
from ninja_aio.models import ModelUtil
from ninja_aio.views.mixins import SoftDeleteViewSetMixin
from tests.generics.request import Request
from tests.generics.views import GenericAPIViewSet
from tests.test_app import models, views, schema


@tag("soft_delete")
class SoftDeleteInitTestCase(TestCase):
    """Test SoftDeleteViewSetMixin initialization validation."""

    def test_valid_model_initializes(self):
        """Model with is_deleted field initializes without error."""
        api = NinjaAIO(urls_namespace="sd_init_valid")
        vs = views.SoftDeleteTestAPI()
        vs.api = api
        vs.add_views_to_route()

    def test_custom_field_initializes(self):
        """Model with custom soft delete field name initializes."""
        api = NinjaAIO(urls_namespace="sd_init_custom")
        vs = views.SoftDeleteCustomFieldTestAPI()
        vs.api = api
        vs.add_views_to_route()

    def test_missing_field_raises(self):
        """Model without the soft delete field raises ImproperlyConfigured."""

        class BadAPI(SoftDeleteViewSetMixin, GenericAPIViewSet):
            model = models.TestModel  # no is_deleted field
            schema_in = schema.TestModelSchemaIn
            schema_out = schema.TestModelSchemaOut
            schema_update = schema.TestModelSchemaPatch

        api = NinjaAIO(urls_namespace="sd_init_bad")
        with self.assertRaises(ImproperlyConfigured):
            vs = BadAPI()
            vs.api = api
            vs.add_views_to_route()


@tag("soft_delete")
class SoftDeleteTestCase(TestCase):
    """Test soft delete single-object operations."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "sd_test"
        cls.model = models.SoftDeleteTestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.SoftDeleteTestAPI()
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

    async def test_soft_delete_sets_flag(self):
        """DELETE sets is_deleted=True instead of removing the row."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="del_me", description="d")

        view = self.viewset.delete_view()
        result = await view(self.delete_request, self.viewset.path_schema(**{self.pk_att: obj.pk}))
        self.assertEqual(result.status_code, 204)

        # Row still exists in DB
        await obj.arefresh_from_db()
        self.assertTrue(obj.is_deleted)
        count = await self.model.objects.acount()
        self.assertEqual(count, 1)

    async def test_soft_deleted_excluded_from_list(self):
        """Soft-deleted records are excluded from list results."""
        await self.model.objects.all().adelete()
        await self.model.objects.acreate(name="visible", description="d", is_deleted=False)
        await self.model.objects.acreate(name="hidden", description="d", is_deleted=True)

        view = self.viewset.list_view()
        result = await view(self.get_request)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["count"], 1)

    async def test_soft_deleted_retrieve_returns_404(self):
        """Retrieving a soft-deleted record raises NotFoundError."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="gone", description="d", is_deleted=True)

        view = self.viewset.retrieve_view()
        with self.assertRaises(NotFoundError):
            await view(self.get_request, self.viewset.path_schema(**{self.pk_att: obj.pk}))

    async def test_soft_deleted_update_returns_404(self):
        """Updating a soft-deleted record raises NotFoundError."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="gone", description="d", is_deleted=True)

        view = self.viewset.update_view()
        update_data = schema.TestModelSchemaPatch(description="new")
        with self.assertRaises(NotFoundError):
            await view(
                self.patch_request,
                update_data,
                self.viewset.path_schema(**{self.pk_att: obj.pk}),
            )

    async def test_soft_delete_idempotent(self):
        """Soft-deleting an already soft-deleted record is idempotent."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="gone", description="d", is_deleted=True)

        view = self.viewset.delete_view()
        result = await view(self.delete_request, self.viewset.path_schema(**{self.pk_att: obj.pk}))
        self.assertEqual(result.status_code, 204)
        await obj.arefresh_from_db()
        self.assertTrue(obj.is_deleted)

    async def test_restore_endpoint(self):
        """POST /{pk}/restore un-deletes a soft-deleted record."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="restore_me", description="d", is_deleted=True)

        # Find the restore view
        ops = self.viewset.router.path_operations
        restore_path = f"{self.viewset.path_retrieve}/restore"
        restore_op = ops.get(restore_path)
        self.assertIsNotNone(restore_op, f"Restore endpoint not found at {restore_path}")
        restore_view = restore_op.operations[0].view_func

        result = await restore_view(
            self.post_request,
            self.viewset.path_schema(**{self.pk_att: obj.pk}),
        )
        self.assertEqual(result.status_code, 200)
        await obj.arefresh_from_db()
        self.assertFalse(obj.is_deleted)

    async def test_hard_delete_endpoint(self):
        """DELETE /{pk}/hard-delete permanently removes the record."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="perm_del", description="d")

        ops = self.viewset.router.path_operations
        hard_delete_path = f"{self.viewset.path_retrieve}/hard-delete"
        hard_delete_op = ops.get(hard_delete_path)
        self.assertIsNotNone(hard_delete_op, f"Hard delete endpoint not found at {hard_delete_path}")
        hard_delete_view = hard_delete_op.operations[0].view_func

        result = await hard_delete_view(
            self.delete_request,
            self.viewset.path_schema(**{self.pk_att: obj.pk}),
        )
        self.assertEqual(result.status_code, 204)
        count = await self.model.objects.acount()
        self.assertEqual(count, 0)


@tag("soft_delete", "bulk")
class SoftDeleteBulkTestCase(TestCase):
    """Test soft delete bulk operations."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "sd_bulk_test"
        cls.model = models.SoftDeleteTestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.SoftDeleteTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.pk_att = cls.model._meta.pk.attname
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

    @property
    def delete_request(self):
        return self.request.delete()

    async def test_bulk_soft_delete(self):
        """Bulk delete soft-deletes all matching records."""
        await self.model.objects.all().adelete()
        obj1 = await self.model.objects.acreate(name="b1", description="d")
        obj2 = await self.model.objects.acreate(name="b2", description="d")
        await self.model.objects.acreate(name="keep", description="d")

        delete_data = self.viewset.bulk_delete_schema(ids=[obj1.pk, obj2.pk])
        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["success"]["count"], 2)
        self.assertEqual(result.value["errors"]["count"], 0)

        # All 3 rows still exist in DB
        total = await self.model.objects.acount()
        self.assertEqual(total, 3)

        # 2 are soft-deleted
        deleted_count = await self.model.objects.filter(is_deleted=True).acount()
        self.assertEqual(deleted_count, 2)

    async def test_bulk_soft_delete_partial_failure(self):
        """Bulk soft delete with non-existent PKs returns partial success."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="exists", description="d")

        delete_data = self.viewset.bulk_delete_schema(ids=[obj.pk, 99999])
        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.value["success"]["count"], 1)
        self.assertEqual(result.value["errors"]["count"], 1)

        await obj.arefresh_from_db()
        self.assertTrue(obj.is_deleted)

    async def test_bulk_soft_delete_empty(self):
        """Bulk soft delete with empty list is a no-op."""
        delete_data = self.viewset.bulk_delete_schema(ids=[])
        view = self.viewset.bulk_delete_view()
        result = await view(self.delete_request, delete_data)

        self.assertEqual(result.value["success"]["count"], 0)
        self.assertEqual(result.value["errors"]["count"], 0)


@tag("soft_delete")
class SoftDeleteIncludeDeletedTestCase(TestCase):
    """Test soft delete with include_deleted=True (admin view)."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "sd_include_test"
        cls.model = models.SoftDeleteTestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.SoftDeleteIncludeDeletedTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.pk_att = cls.model._meta.pk.attname
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

    async def test_list_includes_soft_deleted(self):
        """With include_deleted=True, soft-deleted records appear in list."""
        await self.model.objects.all().adelete()
        await self.model.objects.acreate(name="active", description="d", is_deleted=False)
        await self.model.objects.acreate(name="deleted", description="d", is_deleted=True)

        view = self.viewset.list_view()
        result = await view(self.request.get())
        self.assertEqual(result.value["count"], 2)

    async def test_retrieve_includes_soft_deleted(self):
        """With include_deleted=True, soft-deleted records can be retrieved."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="deleted", description="d", is_deleted=True)

        view = self.viewset.retrieve_view()
        result = await view(
            self.request.get(),
            self.viewset.path_schema(**{self.pk_att: obj.pk}),
        )
        self.assertEqual(result.status_code, 200)

    async def test_update_includes_soft_deleted(self):
        """With include_deleted=True, soft-deleted records can be updated."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="deleted", description="d", is_deleted=True)

        view = self.viewset.update_view()
        update_data = schema.TestModelSchemaPatch(description="updated")
        result = await view(
            self.request.patch(),
            update_data,
            self.viewset.path_schema(**{self.pk_att: obj.pk}),
        )
        self.assertEqual(result.status_code, 200)
        await obj.arefresh_from_db()
        self.assertEqual(obj.description, "updated")


@tag("soft_delete")
class SoftDeleteCustomFieldTestCase(TestCase):
    """Test soft delete with custom field name."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "sd_custom_field"
        cls.model = models.SoftDeleteCustomFieldTestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.SoftDeleteCustomFieldTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.pk_att = cls.model._meta.pk.attname
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

    async def test_custom_field_soft_delete(self):
        """Soft delete uses the custom 'deleted' field."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="custom", description="d")

        view = self.viewset.delete_view()
        result = await view(
            self.request.delete(),
            self.viewset.path_schema(**{self.pk_att: obj.pk}),
        )
        self.assertEqual(result.status_code, 204)
        await obj.arefresh_from_db()
        self.assertTrue(obj.deleted)

    async def test_custom_field_list_filters(self):
        """List excludes records with custom 'deleted' field True."""
        await self.model.objects.all().adelete()
        await self.model.objects.acreate(name="visible", description="d", deleted=False)
        await self.model.objects.acreate(name="hidden", description="d", deleted=True)

        view = self.viewset.list_view()
        result = await view(self.request.get())
        self.assertEqual(result.value["count"], 1)


@tag("soft_delete")
class SoftDeleteNoObjectHooksTestCase(TestCase):
    """Test soft delete when _has_object_hooks is False (fallback path)."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "sd_no_hooks"
        cls.model = models.SoftDeleteTestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        class NoHooksAPI(SoftDeleteViewSetMixin, GenericAPIViewSet):
            model = models.SoftDeleteTestModel
            schema_in = schema.TestModelSchemaIn
            schema_out = schema.TestModelSchemaOut
            schema_update = schema.TestModelSchemaPatch
            _has_object_hooks = False

        cls.viewset = NoHooksAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.pk_att = cls.model._meta.pk.attname
        cls.request = Request(cls.viewset.model_util.verbose_name_path_resolver())

    async def test_soft_delete_without_hooks(self):
        """Soft delete works when _has_object_hooks is False (fallback fetch)."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="no_hooks", description="d")

        view = self.viewset.delete_view()
        result = await view(
            self.request.delete(),
            self.viewset.path_schema(**{self.pk_att: obj.pk}),
        )
        self.assertEqual(result.status_code, 204)
        await obj.arefresh_from_db()
        self.assertTrue(obj.is_deleted)
