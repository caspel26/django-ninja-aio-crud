from asgiref.sync import async_to_sync
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ninja_aio.models import ModelUtil
from tests.generics.request import Request
from tests.test_app.models import TestModelSerializer


class V2QueryCountBaselineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.obj = TestModelSerializer.objects.create(
            name="baseline",
            description="baseline",
        )
        cls.request = Request("v3-baseline")
        cls.util = ModelUtil(TestModelSerializer)
        cls.create_schema = TestModelSerializer.generate_create_s()
        cls.update_schema = TestModelSerializer.generate_update_s()
        cls.read_schema = TestModelSerializer.generate_read_s()

    def assertAsyncQueryCount(self, expected, operation):
        with CaptureQueriesContext(connection) as queries:
            result = async_to_sync(operation)()
        self.assertEqual(
            len(queries),
            expected,
            msg="\n".join(query["sql"] for query in queries.captured_queries),
        )
        return result

    def assertSyncQueryCount(self, expected, operation):
        with CaptureQueriesContext(connection) as queries:
            result = operation()
        self.assertEqual(
            len(queries),
            expected,
            msg="\n".join(query["sql"] for query in queries.captured_queries),
        )
        return result

    def test_get_object_query_count(self):
        async def operation():
            return await self.util.aget_object(self.request.get(), self.obj.pk)

        self.assertAsyncQueryCount(1, operation)

    def test_create_and_serialize_query_count(self):
        data = self.create_schema(name="created", description="created")

        async def operation():
            return await self.util.create_s(
                self.request.post(),
                data,
                self.read_schema,
            )

        self.assertAsyncQueryCount(1, operation)

    def test_update_and_serialize_query_count(self):
        data = self.update_schema(description="updated")

        async def operation():
            return await self.util.update_s(
                self.request.patch(),
                data,
                self.obj.pk,
                self.read_schema,
            )

        self.assertAsyncQueryCount(2, operation)

    def test_destroy_query_count(self):
        doomed = TestModelSerializer.objects.create(
            name="doomed",
            description="doomed",
        )

        async def operation():
            return await self.util.delete_s(self.request.delete(), doomed.pk)

        self.assertAsyncQueryCount(2, operation)

    def test_existing_object_serialization_performs_no_queries(self):
        async def operation():
            return await self.util.read_s(
                self.read_schema,
                self.request.get(),
                self.obj,
            )

        self.assertAsyncQueryCount(0, operation)

    def test_queryset_serialization_query_count(self):
        queryset = TestModelSerializer.objects.order_by("pk")

        async def operation():
            return await self.util.list_read_s(
                self.read_schema,
                self.request.get(),
                queryset,
            )

        self.assertAsyncQueryCount(1, operation)

    def test_async_facade_create_query_count(self):
        async def operation():
            return await TestModelSerializer.acreate(
                {"name": "facade-create", "description": "facade-create"}
            )

        self.assertAsyncQueryCount(1, operation)

    def test_async_facade_get_query_count(self):
        async def operation():
            return await TestModelSerializer.aget(self.obj.pk)

        self.assertAsyncQueryCount(1, operation)

    def test_async_facade_update_by_pk_query_count(self):
        async def operation():
            return await TestModelSerializer.aupdate(
                self.obj.pk,
                {"description": "facade-update-pk"},
            )

        self.assertAsyncQueryCount(2, operation)

    def test_async_facade_update_loaded_instance_query_count(self):
        async def operation():
            return await TestModelSerializer.aupdate(
                self.obj,
                {"description": "facade-update-instance"},
            )

        self.assertAsyncQueryCount(1, operation)

    def test_async_facade_destroy_by_pk_query_count(self):
        doomed = TestModelSerializer.objects.create(
            name="facade-destroy-pk",
            description="facade-destroy-pk",
        )

        async def operation():
            return await TestModelSerializer.adestroy(doomed.pk)

        self.assertAsyncQueryCount(2, operation)

    def test_async_facade_destroy_loaded_instance_query_count(self):
        doomed = TestModelSerializer.objects.create(
            name="facade-destroy-instance",
            description="facade-destroy-instance",
        )

        async def operation():
            return await TestModelSerializer.adestroy(doomed)

        self.assertAsyncQueryCount(1, operation)

    def test_sync_facade_create_query_count(self):
        self.assertSyncQueryCount(
            1,
            lambda: TestModelSerializer.create(
                {"name": "facade-create-sync", "description": "facade-create-sync"}
            ),
        )

    def test_sync_facade_get_query_count(self):
        self.assertSyncQueryCount(1, lambda: TestModelSerializer.get(self.obj.pk))

    def test_sync_facade_update_by_pk_query_count(self):
        self.assertSyncQueryCount(
            2,
            lambda: TestModelSerializer.update(
                self.obj.pk,
                {"description": "facade-update-pk-sync"},
            ),
        )

    def test_sync_facade_update_loaded_instance_query_count(self):
        self.assertSyncQueryCount(
            1,
            lambda: TestModelSerializer.update(
                self.obj,
                {"description": "facade-update-instance-sync"},
            ),
        )

    def test_sync_facade_destroy_by_pk_query_count(self):
        doomed = TestModelSerializer.objects.create(
            name="facade-destroy-pk-sync",
            description="facade-destroy-pk-sync",
        )

        self.assertSyncQueryCount(2, lambda: TestModelSerializer.destroy(doomed.pk))

    def test_sync_facade_destroy_loaded_instance_query_count(self):
        doomed = TestModelSerializer.objects.create(
            name="facade-destroy-instance-sync",
            description="facade-destroy-instance-sync",
        )

        self.assertSyncQueryCount(1, lambda: TestModelSerializer.destroy(doomed))
