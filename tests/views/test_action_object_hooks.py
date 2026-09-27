from django.test import TestCase, tag
from ninja.testing import TestAsyncClient, TestClient

from ninja_aio import NinjaAIO
from ninja_aio.decorators import action
from ninja_aio.exceptions import ForbiddenError
from ninja_aio.views import APIViewSet, mixins
from tests.test_app import models


def _viewsets(prefix: str):
    """The same viewsets in both execution modes."""

    class LockedCheck:
        """A plain object hook, without any mixin."""

        async def aon_before_object_operation(self, request, operation, obj):
            if obj.name == "locked":
                raise ForbiddenError()

        def on_before_object_operation(self, request, operation, obj):
            if obj.name == "locked":
                raise ForbiddenError()

    class AsyncHooked(LockedCheck, APIViewSet):
        model = models.TestModelSerializer

        @action(detail=True, methods=["post"])
        async def touch(self, request, pk: int):
            return {"touched": pk}

    class SyncHooked(LockedCheck, APIViewSet):
        model = models.TestModelSerializer
        execution_mode = "sync"

        @action(detail=True, methods=["post"])
        def touch(self, request, pk: int):
            return {"touched": pk}

    class AsyncPlain(APIViewSet):
        model = models.TestModelSerializer

        @action(detail=True, methods=["post"])
        async def touch(self, request, pk: int):
            return {"touched": pk}

    class SyncSoftDeleted(mixins.SoftDeleteViewSetMixin, APIViewSet):
        model = models.SoftDeleteTestModel
        execution_mode = "sync"

        @action(detail=True, methods=["post"])
        def touch(self, request, pk: int):
            return {"touched": pk}

    api = NinjaAIO(urls_namespace=f"action_object_hooks_{prefix}")
    AsyncHooked(api=api, prefix="async-hooked").add_views_to_route()
    SyncHooked(api=api, prefix="sync-hooked").add_views_to_route()
    AsyncPlain(api=api, prefix="async-plain").add_views_to_route()
    SyncSoftDeleted(api=api, prefix="sync-soft").add_views_to_route()
    return api


@tag("actions")
class DetailActionObjectHooksTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.api = _viewsets("http")
        cls.open = models.TestModelSerializer.objects.create(name="open", description="d")
        cls.locked = models.TestModelSerializer.objects.create(name="locked", description="d")
        cls.gone = models.SoftDeleteTestModel.objects.create(name="gone", description="d", is_deleted=True)
        cls.live = models.SoftDeleteTestModel.objects.create(name="live", description="d")

    def setUp(self):
        self.sync_client = TestClient(self.api)
        self.async_client = TestAsyncClient(self.api)

    def test_custom_object_hook_is_detected_without_mixins(self):
        response = self.sync_client.get(f"/sync-hooked/{self.locked.pk}")
        self.assertEqual(response.status_code, 403)

    async def test_custom_object_hook_runs_on_async_retrieve(self):
        response = await self.async_client.get(f"/async-hooked/{self.locked.pk}")
        self.assertEqual(response.status_code, 403)

    def test_sync_detail_action_runs_object_hooks(self):
        self.assertEqual(self.sync_client.post(f"/sync-hooked/{self.open.pk}/touch").status_code, 200)
        self.assertEqual(self.sync_client.post(f"/sync-hooked/{self.locked.pk}/touch").status_code, 403)
        self.assertEqual(self.sync_client.post("/sync-hooked/999999/touch").status_code, 404)

    async def test_async_detail_action_runs_object_hooks(self):
        ok = await self.async_client.post(f"/async-hooked/{self.open.pk}/touch")
        forbidden = await self.async_client.post(f"/async-hooked/{self.locked.pk}/touch")
        missing = await self.async_client.post("/async-hooked/999999/touch")
        self.assertEqual((ok.status_code, forbidden.status_code, missing.status_code), (200, 403, 404))
        self.assertEqual(ok.json(), {"touched": self.open.pk})

    async def test_detail_action_without_object_hooks_does_not_load_the_object(self):
        response = await self.async_client.post("/async-plain/999999/touch")
        self.assertEqual(response.status_code, 200)

    def test_detail_action_rejects_soft_deleted_objects(self):
        self.assertEqual(self.sync_client.post(f"/sync-soft/{self.live.pk}/touch").status_code, 200)
        self.assertEqual(self.sync_client.post(f"/sync-soft/{self.gone.pk}/touch").status_code, 404)


class _NotLocked(mixins.PermissionViewSetMixin):
    def has_object_permission(self, request, operation, obj):
        return obj.name != "locked"

    async def ahas_object_permission(self, request, operation, obj):
        return obj.name != "locked"


def _bulk_viewsets(prefix: str):
    class AsyncBulk(_NotLocked, APIViewSet):
        model = models.TestModelSerializer
        bulk_operations = ["update", "delete"]

    class SyncBulk(_NotLocked, APIViewSet):
        model = models.TestModelSerializer
        execution_mode = "sync"
        bulk_operations = ["update", "delete"]

    class SyncSoftBulk(_NotLocked, mixins.SoftDeleteViewSetMixin, APIViewSet):
        model = models.SoftDeleteTestModel
        execution_mode = "sync"
        bulk_operations = ["delete"]

    class AsyncSoftBulk(_NotLocked, mixins.SoftDeleteViewSetMixin, APIViewSet):
        model = models.SoftDeleteTestModel
        bulk_operations = ["delete"]

    api = NinjaAIO(urls_namespace=f"bulk_object_hooks_{prefix}")
    AsyncBulk(api=api, prefix="async-bulk").add_views_to_route()
    SyncBulk(api=api, prefix="sync-bulk").add_views_to_route()
    SyncSoftBulk(api=api, prefix="sync-soft-bulk").add_views_to_route()
    AsyncSoftBulk(api=api, prefix="async-soft-bulk").add_views_to_route()
    return api


@tag("bulk")
class BulkObjectPermissionTestCase(TestCase):
    """Bulk update and delete check every object like the single-object endpoints."""

    @classmethod
    def setUpTestData(cls):
        cls.api = _bulk_viewsets("http")

    def setUp(self):
        self.open = models.TestModelSerializer.objects.create(name="open", description="d")
        self.locked = models.TestModelSerializer.objects.create(name="locked", description="d")
        self.soft_open = models.SoftDeleteTestModel.objects.create(name="open", description="d")
        self.soft_locked = models.SoftDeleteTestModel.objects.create(name="locked", description="d")
        self.sync_client = TestClient(self.api)
        self.async_client = TestAsyncClient(self.api)

    def _assert_result(self, body, succeeded, errors):
        self.assertEqual(body["success"]["details"], succeeded)
        self.assertEqual(body["errors"]["count"], errors)

    def test_sync_bulk_delete_skips_forbidden_objects(self):
        response = self.sync_client.delete(
            "/sync-bulk/bulk/", json={"ids": [self.open.pk, self.locked.pk, 999999]}
        )
        self._assert_result(response.json(), [self.open.pk], 2)
        self.assertTrue(models.TestModelSerializer.objects.filter(pk=self.locked.pk).exists())
        self.assertFalse(models.TestModelSerializer.objects.filter(pk=self.open.pk).exists())

    async def test_async_bulk_delete_skips_forbidden_objects(self):
        response = await self.async_client.delete(
            "/async-bulk/bulk/", json={"ids": [self.locked.pk, self.open.pk]}
        )
        self._assert_result(response.json(), [self.open.pk], 1)
        self.assertTrue(await models.TestModelSerializer.objects.filter(pk=self.locked.pk).aexists())

    def test_sync_bulk_update_skips_forbidden_objects(self):
        response = self.sync_client.patch(
            "/sync-bulk/bulk/",
            json=[{"id": self.open.pk, "description": "new"}, {"id": self.locked.pk, "description": "new"}],
        )
        self._assert_result(response.json(), [self.open.pk], 1)
        self.locked.refresh_from_db()
        self.assertEqual(self.locked.description, "d")

    async def test_async_bulk_update_skips_forbidden_objects(self):
        response = await self.async_client.patch(
            "/async-bulk/bulk/",
            json=[{"id": self.locked.pk, "description": "new"}, {"id": self.open.pk, "description": "new"}],
        )
        self._assert_result(response.json(), [self.open.pk], 1)
        await self.locked.arefresh_from_db()
        self.assertEqual(self.locked.description, "d")

    def test_sync_soft_bulk_delete_skips_forbidden_objects(self):
        response = self.sync_client.delete(
            "/sync-soft-bulk/bulk/", json={"ids": [self.soft_open.pk, self.soft_locked.pk, 999999]}
        )
        self._assert_result(response.json(), [self.soft_open.pk], 2)
        self.soft_locked.refresh_from_db()
        self.soft_open.refresh_from_db()
        self.assertFalse(self.soft_locked.is_deleted)
        self.assertTrue(self.soft_open.is_deleted)

    async def test_async_soft_bulk_delete_skips_forbidden_objects(self):
        response = await self.async_client.delete(
            "/async-soft-bulk/bulk/", json={"ids": [self.soft_locked.pk, self.soft_open.pk]}
        )
        self._assert_result(response.json(), [self.soft_open.pk], 1)
        await self.soft_locked.arefresh_from_db()
        self.assertFalse(self.soft_locked.is_deleted)
