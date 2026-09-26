import datetime
import inspect
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from django.test import tag, TestCase
from django.utils import timezone
from ninja import Schema

from ninja_aio.models import ModelUtil
from ninja_aio.exceptions import SerializeError
from ninja_aio.models import serializers as ninja_serializers
from ninja_aio.schemas import (
    MatchCaseFilterSchema,
    MatchConditionFilterSchema,
    BooleanMatchFilterSchema,
)
from ninja_aio.views import mixins
from tests.generics.views import Tests
from tests.test_app import schema, models, views, serializers
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from ninja_aio.decorators import api_get, api_post
from tests.generics.request import Request


class OptionalUpdateSchema(Schema):
    description: str | None = None


class ExecutionModeTests(TestCase):
    def test_sync_create_registers_a_native_sync_handler(self):
        class SyncViewSet(views.TestModelSerializerAPI):
            execution_mode = "sync"

        viewset = SyncViewSet()
        handler = viewset.create_view()
        self.assertFalse(inspect.iscoroutinefunction(handler))

    def test_default_async_route_uses_separate_factory(self):
        class AsyncViewSet(views.TestModelSerializerAPI):
            def acreate_view(self):
                self.async_factory_called = True
                return super().acreate_view()

        viewset = AsyncViewSet()
        viewset._add_views()
        self.assertTrue(viewset.async_factory_called)
        for operation in ("create", "list", "retrieve", "update", "delete"):
            with self.subTest(operation=operation):
                self.assertTrue(inspect.iscoroutinefunction(viewset._operations[operation]))

    async def test_async_create_uses_serializer_facade(self):
        viewset = views.TestModelSerializerAPI()
        with mock.patch.object(
            viewset.model_util,
            "create_s",
            side_effect=AssertionError("legacy create_s must not run"),
        ):
            result = await viewset.acreate_view()(
                Request("test-model-serializers").post(),
                viewset.schema_in(name="facade", description="async"),
            )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.value["name"], "facade")

    def test_sync_create_handler_can_be_overridden(self):
        class SyncViewSet(views.TestModelSerializerAPI):
            execution_mode = "sync"

            def create(self, request, data):
                self.create_called = True
                return super().create(request, data)

        viewset = SyncViewSet()
        result = viewset.create_view()(
            Request("test-model-serializers").post(),
            viewset.schema_in(name="override", description="sync"),
        )
        self.assertTrue(viewset.create_called)
        self.assertEqual(result.status_code, 201)

    async def test_async_create_handler_can_be_overridden(self):
        class AsyncViewSet(views.TestModelSerializerAPI):
            async def acreate(self, request, data):
                self.create_called = True
                return await super().acreate(request, data)

        viewset = AsyncViewSet()
        result = await viewset.acreate_view()(
            Request("test-model-serializers").post(),
            viewset.schema_in(name="override", description="async"),
        )
        self.assertTrue(viewset.create_called)
        self.assertEqual(result.status_code, 201)

    def test_sync_retrieve_handler_can_be_overridden(self):
        class SyncViewSet(views.TestModelSerializerAPI):
            execution_mode = "sync"

            def retrieve(self, request, pk):
                self.retrieve_called = True
                return super().retrieve(request, pk)

        viewset = SyncViewSet()
        obj = models.TestModelSerializer.objects.create(name="sync", description="before")
        result = viewset.retrieve_view()(
            Request("test-model-serializers").get(), viewset.path_schema(id=obj.pk)
        )
        self.assertTrue(viewset.retrieve_called)
        self.assertEqual(result.value["name"], "sync")

    async def test_async_retrieve_handler_can_be_overridden(self):
        class AsyncViewSet(views.TestModelSerializerAPI):
            async def aretrieve(self, request, pk):
                self.retrieve_called = True
                return await super().aretrieve(request, pk)

        viewset = AsyncViewSet()
        obj = await models.TestModelSerializer.objects.acreate(name="async", description="before")
        result = await viewset.aretrieve_view()(
            Request("test-model-serializers").get(), viewset.path_schema(id=obj.pk)
        )
        self.assertTrue(viewset.retrieve_called)
        self.assertEqual(result.value["name"], "async")

    def test_sync_create_persists_and_serializes(self):
        class SyncViewSet(views.TestModelSerializerAPI):
            execution_mode = "sync"

        viewset = SyncViewSet()
        result = viewset.create_view()(
            Request("test-model-serializers").post(),
            viewset.schema_in(name="sync-created", description="created"),
        )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.value["name"], "sync-created")
        self.assertTrue(models.TestModelSerializer.objects.filter(name="sync-created").exists())

    def test_async_only_hook_is_rejected_for_sync_mode_at_startup(self):
        class SyncViewSet(views.TestModelSerializerAPI):
            execution_mode = "sync"

            async def aon_before_operation(self, request, operation):
                raise AssertionError("async hook must not run in sync mode")

        with self.assertRaisesRegex(ImproperlyConfigured, "on_before_operation"):
            SyncViewSet()

    def test_sync_crud_endpoints_preserve_http_results(self):
        class SyncViewSet(views.TestModelSerializerAPI):
            execution_mode = "sync"

        viewset = SyncViewSet()
        viewset._add_views()
        for operation in ("create", "list", "retrieve", "update", "delete"):
            with self.subTest(operation=operation):
                self.assertFalse(inspect.iscoroutinefunction(viewset._operations[operation]))
        obj = models.TestModelSerializer.objects.create(name="sync", description="before")
        request = Request("test-model-serializers")
        path = viewset.path_schema(id=obj.pk)

        retrieve = viewset.retrieve_view()
        update = viewset.update_view()
        delete = viewset.delete_view()
        for handler in (retrieve, update, delete):
            self.assertFalse(inspect.iscoroutinefunction(handler))

        self.assertEqual(retrieve(request.get(), path).value["name"], "sync")
        updated = update(
            request.patch(), viewset.schema_update(description="after"), path
        )
        self.assertEqual(updated.value["description"], "after")
        self.assertEqual(delete(request.delete(), path).status_code, 204)
        self.assertFalse(models.TestModelSerializer.objects.filter(pk=obj.pk).exists())

    def test_sync_plain_model_update(self):
        class SyncViewSet(views.TestModelAPI):
            execution_mode = "sync"

        viewset = SyncViewSet()
        obj = models.TestModel.objects.create(name="plain", description="before")
        result = viewset.update_view()(
            Request("test-models").patch(),
            viewset.schema_update(description="after"),
            viewset.path_schema(id=obj.pk),
        )
        self.assertEqual(result.value["description"], "after")
        obj.refresh_from_db()
        self.assertEqual(obj.description, "after")

    def test_sync_plain_model_create_list_delete(self):
        class SyncViewSet(views.TestModelAPI):
            execution_mode = "sync"

        viewset = SyncViewSet()
        request = Request("test-models")
        created = viewset.create_view()(
            request.post(), viewset.schema_in(name="plain", description="sync")
        )
        self.assertEqual(created.status_code, 201)
        pk = created.value["id"]
        listed = viewset.list_view()(request.get())
        self.assertIn(pk, [item["id"] for item in listed.value["items"]])
        deleted = viewset.delete_view()(request.delete(), viewset.path_schema(id=pk))
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(models.TestModel.objects.filter(pk=pk).exists())

    def test_sync_delete_returns_deleted_object_with_schema_delete_out(self):
        class SyncViewSet(views.TestModelDeleteOutAPI):
            execution_mode = "sync"

        viewset = SyncViewSet()
        obj = models.TestModel.objects.create(name="gone", description="d")
        result = viewset.delete_view()(
            Request("test-models").delete(), viewset.path_schema(id=obj.pk)
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value, {"id": obj.pk, "name": "gone"})
        self.assertFalse(models.TestModel.objects.filter(pk=obj.pk).exists())

    def test_sync_retrieve_preloads_schema_relations(self):
        class SyncViewSet(views.TestModelForeignKeyAPI):
            execution_mode = "sync"

        viewset = SyncViewSet()
        parent = models.TestModelReverseForeignKey.objects.create(
            name="parent", description="p"
        )
        child = models.TestModelForeignKey.objects.create(
            name="child", description="c", test_model=parent
        )
        result = viewset.retrieve_view()(
            Request("test-model-foreign-keys").get(), viewset.path_schema(id=child.pk)
        )
        self.assertEqual(result.value["test_model"]["name"], "parent")

    def test_sync_plain_model_update_rejects_empty_payload(self):
        class SyncViewSet(views.TestModelAPI):
            execution_mode = "sync"
            require_update_fields = True
            schema_update = OptionalUpdateSchema

        viewset = SyncViewSet()
        obj = models.TestModel.objects.create(name="plain", description="before")
        with self.assertRaisesRegex(SerializeError, "No fields provided for update"):
            viewset.update_view()(
                Request("test-models").patch(),
                viewset.schema_update(),
                viewset.path_schema(id=obj.pk),
            )

    async def test_async_plain_model_update_rejects_empty_payload(self):
        class AsyncViewSet(views.TestModelAPI):
            require_update_fields = True
            schema_update = OptionalUpdateSchema

        viewset = AsyncViewSet()
        obj = await models.TestModel.objects.acreate(name="plain", description="before")
        with self.assertRaisesRegex(SerializeError, "No fields provided for update"):
            await viewset.aupdate_view()(
                Request("test-models").patch(),
                viewset.schema_update(),
                viewset.path_schema(id=obj.pk),
            )

    def test_sync_update_handler_can_be_overridden(self):
        class SyncViewSet(views.TestModelSerializerAPI):
            execution_mode = "sync"

            def update(self, request, data, pk):
                self.update_called = True
                return super().update(request, data, pk)

        viewset = SyncViewSet()
        obj = models.TestModelSerializer.objects.create(name="sync", description="before")
        result = viewset.update_view()(
            Request("test-model-serializers").patch(),
            viewset.schema_update(description="after"),
            viewset.path_schema(id=obj.pk),
        )
        self.assertTrue(viewset.update_called)
        self.assertEqual(result.value["description"], "after")

    async def test_async_update_handler_can_be_overridden(self):
        class AsyncViewSet(views.TestModelSerializerAPI):
            async def aupdate(self, request, data, pk):
                self.update_called = True
                return await super().aupdate(request, data, pk)

        viewset = AsyncViewSet()
        obj = await models.TestModelSerializer.objects.acreate(name="async", description="before")
        result = await viewset.aupdate_view()(
            Request("test-model-serializers").patch(),
            viewset.schema_update(description="after"),
            viewset.path_schema(id=obj.pk),
        )
        self.assertTrue(viewset.update_called)
        self.assertEqual(result.value["description"], "after")

    def test_sync_delete_handler_can_be_overridden(self):
        class SyncViewSet(views.TestModelSerializerAPI):
            execution_mode = "sync"

            def delete(self, request, pk):
                self.delete_called = True
                return super().delete(request, pk)

        viewset = SyncViewSet()
        obj = models.TestModelSerializer.objects.create(name="sync", description="before")
        result = viewset.delete_view()(
            Request("test-model-serializers").delete(), viewset.path_schema(id=obj.pk)
        )
        self.assertTrue(viewset.delete_called)
        self.assertEqual(result.status_code, 204)

    async def test_async_delete_handler_can_be_overridden(self):
        class AsyncViewSet(views.TestModelSerializerAPI):
            async def adelete(self, request, pk):
                self.delete_called = True
                return await super().adelete(request, pk)

        viewset = AsyncViewSet()
        obj = await models.TestModelSerializer.objects.acreate(name="async", description="before")
        result = await viewset.adelete_view()(
            Request("test-model-serializers").delete(), viewset.path_schema(id=obj.pk)
        )
        self.assertTrue(viewset.delete_called)
        self.assertEqual(result.status_code, 204)

    def test_sync_list_paginates_and_serializes(self):
        class SyncViewSet(views.TestModelSerializerAPI):
            execution_mode = "sync"

        viewset = SyncViewSet()
        models.TestModelSerializer.objects.create(name="first", description="one")
        models.TestModelSerializer.objects.create(name="second", description="two")
        handler = viewset.list_view()
        self.assertFalse(inspect.iscoroutinefunction(handler))
        result = handler(
            Request("test-model-serializers").get(),
            ninja_pagination=viewset.pagination_class.Input(page=1, page_size=1),
        )
        self.assertEqual(result.value["count"], 2)
        self.assertEqual(len(result.value["items"]), 1)

    def test_sync_list_handler_can_be_overridden(self):
        class SyncViewSet(views.TestModelSerializerAPI):
            execution_mode = "sync"

            def list(self, request, filters, ninja_pagination):
                self.list_called = True
                return super().list(request, filters, ninja_pagination)

        viewset = SyncViewSet()
        result = viewset.list_view()(Request("test-model-serializers").get())
        self.assertTrue(viewset.list_called)
        self.assertEqual(result.status_code, 200)

    async def test_async_list_handler_can_be_overridden(self):
        class AsyncViewSet(views.TestModelSerializerAPI):
            async def alist(self, request, filters, ninja_pagination):
                self.list_called = True
                return await super().alist(request, filters, ninja_pagination)

        viewset = AsyncViewSet()
        result = await viewset.alist_view()(Request("test-model-serializers").get())
        self.assertTrue(viewset.list_called)
        self.assertEqual(result.status_code, 200)


class BaseTests:
    class SetUpViewSetTestCase:
        @property
        def _payload(self):
            return {
                "name": f"test_name_{self.model._meta.model_name}",
                "description": f"test_description_{self.model._meta.model_name}",
            }

        @property
        def payload_create(self):
            return self._payload

        @property
        def payload_update(self):
            return {
                "description": f"test_description_{self.model._meta.model_name}_update",
            }

        @property
        def response_data(self):
            return self._payload

        @property
        def create_response_data(self):
            return self.response_data

    class ModelSerializerViewSetTestCaseBase(SetUpViewSetTestCase):
        @property
        def schemas(self):
            read_s = self.model.generate_read_s()
            return (
                read_s,
                self.model.generate_detail_s(),
                self.model.generate_create_s(),
                self.model.generate_update_s(),
                read_s,
                read_s,
                None,
            )

    class ApiViewSetSetUpRelation(SetUpViewSetTestCase):
        relation_viewset: views.GenericAPIViewSet

        @classmethod
        def setUpTestData(cls):
            data = {
                "name": f"test_name_{cls.relation_viewset.model._meta.model_name}",
                "description": f"test_description_{cls.relation_viewset.model._meta.model_name}",
            }
            if not hasattr(cls, "relation_data"):
                cls.relation_data = data
            else:
                cls.relation_data = cls.relation_data | data
            super().setUpTestData()

    @tag("viewset_foreign_key")
    class ApiViewSetForeignKeyTestCaseBase(
        ApiViewSetSetUpRelation, Tests.RelationViewSetTestCase
    ):
        @property
        def payload_create(self):
            return super().payload_create | {
                "test_model_serializer_id": self.relation_pk
            }

        @property
        def response_data(self):
            return super().response_data | {
                self.relation_related_name: self.relation_obj
            }

    @tag("viewset_reverse_foreign_key")
    class ApiViewSetReverseForeignKeyTestCaseBase(
        ApiViewSetSetUpRelation, Tests.ReverseRelationViewSetTestCase
    ):
        @property
        def response_data(self):
            return super().response_data | {
                self.relation_related_name: [self.relation_schema_data]
            }

        @property
        def create_response_data(self):
            return super().response_data | {self.relation_related_name: []}

    @tag("viewset_many_to_many")
    class ApiViewSetManyToManyTestCaseBase(
        ApiViewSetSetUpRelation, Tests.RelationViewSetTestCase
    ):
        @classmethod
        def setUpTestData(cls):
            super().setUpTestData()
            obj = cls.model.objects.get(pk=cls.obj_content[cls.pk_att])
            getattr(obj, cls.relation_related_name).add(cls.relation_obj)
            obj.save()
            cls.relation_schema_data.pop(cls.foreign_key_reverse_field, None)

        @property
        def response_data(self):
            return super().response_data | {
                self.relation_related_name: [self.relation_schema_data]
            }

        @property
        def create_response_data(self):
            return super().response_data | {self.relation_related_name: []}


# ==========================================================
#             MODEL SERIALIZER VIEWSET TESTS
# ==========================================================


@tag("model_serializer_viewset")
class ApiViewSetModelSerializerTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_serializer_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_query_params_icontains_mixin(self):
        await self._drop_all_objects()
        obj = await self.model.objects.acreate(**self.payload_create)
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(), {"name": f"{self.model._meta.model_name}"}
        )
        self.assertEqual(await res.acount(), 1)
        self.assertEqual((await res.afirst()), obj)

    async def test_query_params_boolean_mixin(self):
        await self._drop_all_objects()
        obj_active = await self.model.objects.acreate(**self.payload_create)
        obj_inactive = await self.model.objects.acreate(
            **{**self.payload_create, "active": False}
        )
        res_active = await self.viewset.aquery_params_handler(
            self.model.objects.all(), {"active": True}
        )
        self.assertEqual(await res_active.acount(), 1)
        self.assertEqual((await res_active.afirst()), obj_active)
        res_inactive = await self.viewset.aquery_params_handler(
            self.model.objects.all(), {"active": False}
        )
        self.assertEqual(await res_inactive.acount(), 1)
        self.assertEqual((await res_inactive.afirst()), obj_inactive)

    async def test_query_params_numeric_mixin(self):
        await self._drop_all_objects()
        obj_age_25 = await self.model.objects.acreate(
            **{**self.payload_create, "age": 25}
        )
        obj_age_30 = await self.model.objects.acreate(
            **{**self.payload_create, "age": 30}
        )
        res_age_25 = await self.viewset.aquery_params_handler(
            self.model.objects.all(), {"age": 25}
        )
        self.assertEqual(await res_age_25.acount(), 1)
        self.assertEqual((await res_age_25.afirst()), obj_age_25)
        res_age_30 = await self.viewset.aquery_params_handler(
            self.model.objects.all(), {"age": 30}
        )
        self.assertEqual(await res_age_30.acount(), 1)
        self.assertEqual((await res_age_30.afirst()), obj_age_30)

    async def test_query_params_date_mixin(self):
        await self._drop_all_objects()
        obj_today = await self.model.objects.acreate(**self.payload_create)
        res_today = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"active_from": obj_today.active_from},
        )
        self.assertEqual(await res_today.acount(), 1)
        self.assertEqual((await res_today.afirst()), obj_today)


@tag("model_serializer_greater_than_date_viewset")
class ApiViewSetModelSerializerGreaterThanDateTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_serializer_greater_than_date_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerGreaterThanMixinAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_query_params_greater_than_date_mixin(self):
        await self._drop_all_objects()
        past_date = timezone.now() - datetime.timedelta(days=1)
        future_date = timezone.now() + datetime.timedelta(days=1)
        obj_past = await self.model.objects.acreate(**self.payload_create)
        obj_past.active_from = past_date
        await obj_past.asave()
        obj_future = await self.model.objects.acreate(**self.payload_create)
        obj_future.active_from = future_date
        await obj_future.asave()
        res_greater_than_now = await self.viewset.aquery_params_handler(
            self.model.objects.all(), {"active_from": timezone.now()}
        )
        self.assertEqual(await res_greater_than_now.acount(), 1)
        self.assertEqual((await res_greater_than_now.afirst()), obj_future)


@tag("model_serializer_less_than_date_viewset")
class ApiViewSetModelSerializerLessThanDateTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_serializer_less_than_date_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerLessThanMixinAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_query_params_less_than_date_mixin(self):
        await self._drop_all_objects()
        past_date = timezone.now() - datetime.timedelta(days=1)
        future_date = timezone.now() + datetime.timedelta(days=1)
        obj_past = await self.model.objects.acreate(**self.payload_create)
        obj_past.active_from = past_date
        await obj_past.asave()
        obj_future = await self.model.objects.acreate(**self.payload_create)
        obj_future.active_from = future_date
        await obj_future.asave()
        res_less_than_now = await self.viewset.aquery_params_handler(
            self.model.objects.all(), {"active_from": timezone.now()}
        )
        self.assertEqual(await res_less_than_now.acount(), 1)
        self.assertEqual((await res_less_than_now.afirst()), obj_past)


@tag("model_serializer_greater_equal_date_viewset")
class ApiViewSetModelSerializerGreaterEqualDateTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_serializer_greater_equal_date_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerGreaterEqualMixinAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_query_params_greater_equal_date_mixin(self):
        await self._drop_all_objects()
        past_date = timezone.now() - datetime.timedelta(days=1)
        future_date = timezone.now() + datetime.timedelta(days=1)
        obj_past = await self.model.objects.acreate(**self.payload_create)
        obj_past.active_from = past_date
        await obj_past.asave()
        obj_future = await self.model.objects.acreate(**self.payload_create)
        obj_future.active_from = future_date
        await obj_future.asave()
        res_greater_equal_now = await self.viewset.aquery_params_handler(
            self.model.objects.all(), {"active_from": timezone.now()}
        )
        self.assertEqual(await res_greater_equal_now.acount(), 1)
        self.assertEqual((await res_greater_equal_now.afirst()), obj_future)


@tag("model_serializer_less_equal_date_viewset")
class ApiViewSetModelSerializerLessEqualDateTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_serializer_less_equal_date_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerLessEqualMixinAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_query_params_less_equal_date_mixin(self):
        await self._drop_all_objects()
        past_date = timezone.now() - datetime.timedelta(days=1)
        future_date = timezone.now() + datetime.timedelta(days=1)
        obj_past = await self.model.objects.acreate(**self.payload_create)
        obj_past.active_from = past_date
        await obj_past.asave()
        obj_future = await self.model.objects.acreate(**self.payload_create)
        obj_future.active_from = future_date
        await obj_future.asave()
        res_less_equal_now = await self.viewset.aquery_params_handler(
            self.model.objects.all(), {"active_from": timezone.now()}
        )
        self.assertEqual(await res_less_equal_now.acount(), 1)
        self.assertEqual((await res_less_equal_now.afirst()), obj_past)


@tag("model_serializer_foreign_key_viewset")
class ApiViewSetModelSerializerForeignKeyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetForeignKeyTestCaseBase,
):
    namespace = "test_model_serializer_foreign_key_viewset"
    model = models.TestModelSerializerForeignKey
    viewset = views.TestModelSerializerForeignKeyAPI()
    relation_viewset = views.TestModelSerializerReverseForeignKeyAPI()
    relation_related_name = "test_model_serializer"


@tag("model_serializer_reverse_foreign_key_viewset")
class ApiViewSetModelSerializerReverseForeignKeyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetReverseForeignKeyTestCaseBase,
):
    namespace = "test_model_serializer_reverse_foreign_key_viewset"
    model = models.TestModelSerializerReverseForeignKey
    viewset = views.TestModelSerializerReverseForeignKeyAPI()
    relation_viewset = views.TestModelSerializerForeignKeyAPI()
    relation_related_name = "test_model_serializer_foreign_keys"
    foreign_key_field = "test_model_serializer"


@tag("model_serializer_one_to_one_viewset")
class ApiViewSetModelSerializerOneToOneTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetForeignKeyTestCaseBase,
):
    namespace = "test_model_serializer_one_to_one_viewset"
    model = models.TestModelSerializerOneToOne
    viewset = views.TestModelSerializerOneToOneAPI()
    relation_viewset = views.TestModelSerializerReverseOneToOneAPI()
    relation_related_name = "test_model_serializer"


@tag("model_serializer_reverse_one_to_one_viewset")
class ApiViewSetModelSerializerReverseOneToOneTestCase(
    ApiViewSetModelSerializerReverseForeignKeyTestCase
):
    namespace = "test_model_serializer_reverse_one_to_one_viewset"
    model = models.TestModelSerializerReverseOneToOne
    viewset = views.TestModelSerializerReverseOneToOneAPI()
    relation_viewset = views.TestModelSerializerOneToOneAPI()
    relation_related_name = "test_model_serializer_one_to_one"

    @property
    def response_data(self):
        return super().response_data | {
            self.relation_related_name: self.relation_schema_data
        }

    @property
    def create_response_data(self):
        return super().response_data | {self.relation_related_name: None}


@tag("model_serializer_many_to_many_viewset")
class ApiViewSetModelSerializerManyToManyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetManyToManyTestCaseBase,
):
    namespace = "test_model_serializer_many_to_many_viewset"
    model = models.TestModelSerializerManyToMany
    viewset = views.TestModelSerializerManyToManyAPI()
    relation_viewset = views.TestModelSerializerReverseManyToManyAPI()
    relation_related_name = "test_model_serializers"
    foreign_key_reverse_field = "test_model_serializer_many_to_many"


@tag("model_serializer_reverse_many_to_many_viewset")
class ApiViewSetModelSerializerReverseManyToManyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetManyToManyTestCaseBase,
):
    namespace = "test_model_serializer_reverse_many_to_many_viewset"
    model = models.TestModelSerializerReverseManyToMany
    viewset = views.TestModelSerializerReverseManyToManyAPI()
    relation_viewset = views.TestModelSerializerManyToManyAPI()
    relation_related_name = "test_model_serializer_many_to_many"
    foreign_key_reverse_field = "test_model_serializers"


# ==========================================================
#                      MODEL VIEWSET TESTS
# ==========================================================


@tag("model_viewset")
class ApiViewSetModelTestCase(
    BaseTests.SetUpViewSetTestCase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_viewset"
    model = models.TestModel
    viewset = views.TestModelAPI()

    @property
    def schemas(self):
        return (
            schema.TestModelSchemaOut,
            None,  # No detail schema for plain model
            schema.TestModelSchemaIn,
            schema.TestModelSchemaPatch,
            schema.TestModelSchemaOut,
            schema.TestModelSchemaOut,
            None,
        )


@tag("model_foreign_key_viewset")
class ApiViewSetModelForeignKeyTestCase(BaseTests.ApiViewSetForeignKeyTestCaseBase):
    namespace = "test_model_foreign_key_viewset"
    model = models.TestModelForeignKey
    viewset = views.TestModelForeignKeyAPI()
    relation_viewset = views.TestModelReverseForeignKeyAPI()
    relation_related_name = "test_model"

    @property
    def schemas(self):
        return (
            schema.TestModelForeignKeySchemaOut,
            None,  # No detail schema for plain model
            schema.TestModelForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
            schema.TestModelForeignKeySchemaOut,
            schema.TestModelForeignKeySchemaOut,
            None,
        )

    @property
    def payload_create(self):
        payload = super().payload_create
        payload.pop("test_model_serializer_id")
        return payload | {self.relation_related_name: self.relation_pk}


class ApiViewSetModelReverseForeignKeyTestCase(
    BaseTests.ApiViewSetReverseForeignKeyTestCaseBase
):
    namespace = "test_model_reverse_foreign_key_viewset"
    model = models.TestModelReverseForeignKey
    viewset = views.TestModelReverseForeignKeyAPI()
    relation_viewset = views.TestModelForeignKeyAPI()
    relation_related_name = "test_model_foreign_keys"
    foreign_key_field = "test_model"

    @property
    def schemas(self):
        return (
            schema.TestModelReverseForeignKeySchemaOut,
            None,  # No detail schema for plain model
            schema.TestModelReverseForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
            schema.TestModelReverseForeignKeySchemaOut,
            schema.TestModelReverseForeignKeySchemaOut,
            None,
        )


@tag("model_one_to_one_viewset")
class ApiViewSetModelOneToOneTestCase(ApiViewSetModelForeignKeyTestCase):
    namespace = "test_model_one_to_one_viewset"
    model = models.TestModelOneToOne
    viewset = views.TestModelOneToOneAPI()
    relation_viewset = views.TestModelReverseOneToOneAPI()

    @property
    def schemas(self):
        return (
            schema.TestModelForeignKeySchemaOut,
            None,  # No detail schema for plain model
            schema.TestModelForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
            schema.TestModelForeignKeySchemaOut,
            schema.TestModelForeignKeySchemaOut,
            None,
        )


@tag("model_reverse_one_to_one_viewset")
class ApiViewSetModelReverseOneToOneTestCase(ApiViewSetModelReverseForeignKeyTestCase):
    namespace = "test_model_reverse_one_to_one_viewset"
    model = models.TestModelReverseOneToOne
    viewset = views.TestModelReverseOneToOneAPI()
    relation_viewset = views.TestModelOneToOneAPI()
    relation_related_name = "test_model_one_to_one"

    @property
    def schemas(self):
        return (
            schema.TestModelReverseOneToOneSchemaOut,
            None,  # No detail schema for plain model
            schema.TestModelReverseForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
            schema.TestModelReverseOneToOneSchemaOut,
            schema.TestModelReverseOneToOneSchemaOut,
            None,
        )

    @property
    def response_data(self):
        return super().response_data | {
            self.relation_related_name: self.relation_schema_data
        }

    @property
    def create_response_data(self):
        return super().response_data | {self.relation_related_name: None}


@tag("model_many_to_many_viewset")
class ApiViewSetModelManyToManyTestCase(BaseTests.ApiViewSetManyToManyTestCaseBase):
    namespace = "test_model_many_to_many_viewset"
    model = models.TestModelManyToMany
    viewset = views.TestModelManyToManyAPI()
    relation_viewset = views.TestModelReverseManyToManyAPI()
    relation_related_name = "test_models"
    foreign_key_reverse_field = "test_model_serializer_many_to_many"

    @property
    def schemas(self):
        return (
            schema.TestModelManyToManySchemaOut,
            None,  # No detail schema for plain model
            schema.TestModelSchemaIn,
            schema.TestModelSchemaPatch,
            schema.TestModelManyToManySchemaOut,
            schema.TestModelManyToManySchemaOut,
            None,
        )


@tag("model_reverse_many_to_many_viewset")
class ApiViewSetModelReverseManyToManyTestCase(
    BaseTests.ApiViewSetManyToManyTestCaseBase
):
    namespace = "test_model_reverse_many_to_many_viewset"
    model = models.TestModelReverseManyToMany
    viewset = views.TestModelReverseManyToManyAPI()
    relation_viewset = views.TestModelManyToManyAPI()
    relation_related_name = "test_model_serializer_many_to_many"
    foreign_key_reverse_field = "test_models"

    @property
    def schemas(self):
        return (
            schema.TestModelReverseManyToManySchemaOut,
            None,  # No detail schema for plain model
            schema.TestModelSchemaIn,
            schema.TestModelSchemaPatch,
            schema.TestModelReverseManyToManySchemaOut,
            schema.TestModelReverseManyToManySchemaOut,
            None,
        )


@tag("model_foreign_key_serializer_viewset")
class ApiViewSetModelForeignKeySerializerTestCase(
    BaseTests.ApiViewSetForeignKeyTestCaseBase
):
    namespace = "test_model_foreign_key_serializer_viewset"
    model = models.TestModelForeignKey
    viewset = views.TestModelForeignKeySerializerAPI()
    relation_viewset = views.TestModelReverseForeignKeySerializerAPI()
    relation_related_name = "test_model"

    @property
    def schemas(self):
        read_s = serializers.TestModelForeignKeySerializer.generate_read_s()
        return (
            read_s,
            serializers.TestModelForeignKeySerializer.generate_detail_s(),
            serializers.TestModelForeignKeySerializer.generate_create_s(),
            serializers.TestModelForeignKeySerializer.generate_update_s(),
            read_s,
            read_s,
            None,
        )

    @property
    def payload_create(self):
        payload = super().payload_create
        payload.pop("test_model_serializer_id")
        return payload | {f"{self.relation_related_name}_id": self.relation_pk}


# ==========================================================
#               VIEWSET DECORATOR TEST CASES
# ==========================================================


@tag("viewset_decorator_modelserializer")
class ViewSetDecoratorModelSerializerTestCase(TestCase):
    namespace = "test_viewset_decorator_modelserializer"

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        @cls.api.viewset(model=models.TestModelSerializer)
        class DecoratedMSViewSet(APIViewSet):
            pass

        # base path inferred from verbose_name plural
        cls.base = f"{models.TestModelSerializer.util.verbose_name_path_resolver()}"

    def test_crud_routes_mounted(self):
        # default router + our viewset router
        self.assertEqual(len(self.api._routers), 2)
        path, router = self.api._routers[1]
        self.assertEqual(path, cls.base if (cls := self).base else self.base)
        urls = [str(r.pattern) for r in router.urls_paths(path)]
        # Expect list and create at base, retrieve/update/delete at /{pk}/ variants
        self.assertIn(path, urls)  # list/create


@tag("viewset_decorator_plain_model")
class ViewSetDecoratorPlainModelTestCase(TestCase):
    namespace = "test_viewset_decorator_plain_model"

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        @cls.api.viewset(model=models.TestModel)
        class DecoratedModelViewSet(APIViewSet):
            # Provide manual schemas since this is a plain Model
            schema_out = schema.TestModelSchemaOut
            schema_in = schema.TestModelSchemaIn
            schema_update = schema.TestModelSchemaPatch

        cls.base = ModelUtil(models.TestModel).verbose_name_path_resolver()

    def test_crud_routes_mounted(self):
        self.assertEqual(len(self.api._routers), 2)
        path, router = self.api._routers[1]
        self.assertEqual(path, self.base)
        urls = [str(r.pattern) for r in router.urls_paths(path)]
        # Check base and pk routes exist
        self.assertIn(self.base, urls)


@tag("viewset_decorator_operations")
class ViewSetDecoratorOperationsTestCase(TestCase):
    namespace = "test_viewset_decorator_operations"

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        @cls.api.viewset(model=models.TestModel)
        class DecoratedOpsViewSet(APIViewSet):
            # Provide manual schemas since this is a plain Model
            schema_out = schema.TestModelSchemaOut
            schema_in = schema.TestModelSchemaIn
            schema_update = schema.TestModelSchemaPatch

            @api_get("/ping", response=schema.SumSchemaOut)
            async def ping(self, request):
                # simple constant payload for testing
                return schema.SumSchemaOut(result=42).model_dump()

            @api_post("/sum", response=schema.SumSchemaOut)
            async def sum_calc(self, request, data: schema.SumSchemaIn):
                return schema.SumSchemaOut(result=data.a + data.b).model_dump()

        # base path inferred from verbose_name plural
        cls.base = ModelUtil(models.TestModel).verbose_name_path_resolver()

    def test_operation_routes_mounted(self):
        # default router + our viewset router
        self.assertEqual(len(self.api._routers), 2)
        path, router = self.api._routers[1]
        self.assertEqual(path, self.base)
        urls = [str(r.pattern) for r in router.urls_paths(path)]
        # Should include base for CRUD and custom endpoints appended to base
        self.assertIn(self.base, urls)  # list/create
        # Ensure custom endpoints are present
        self.assertTrue(any("ping" in u for u in urls))
        self.assertTrue(any("sum" in u for u in urls))

    async def test_operation_handlers(self):
        # Directly verify handler logic mirrors expectations
        ping_result = schema.SumSchemaOut(result=42).model_dump()
        self.assertEqual(ping_result, {"result": 42})
        payload = schema.SumSchemaIn(a=3, b=4)
        sum_result = schema.SumSchemaOut(result=payload.a + payload.b).model_dump()
        self.assertEqual(sum_result, {"result": 7})


# ==========================================================
#               DETAIL SCHEMA TEST CASES
# ==========================================================


@tag("relation_filter_mixin")
class RelationFilterViewSetMixinTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    """Test RelationFilterViewSetMixin functionality."""

    namespace = "test_relation_filter_mixin_viewset"
    model = models.TestModelSerializerForeignKey
    viewset = views.TestModelSerializerForeignKeyRelationFilterAPI()
    relation_model = models.TestModelSerializerReverseForeignKey

    @classmethod
    def setUpTestData(cls):
        # Create related objects first
        cls.related_obj_1 = cls.relation_model.objects.create(
            name="related_alpha", description="first related"
        )
        cls.related_obj_2 = cls.relation_model.objects.create(
            name="related_beta", description="second related"
        )
        super().setUpTestData()

    @property
    def payload_create(self):
        return {
            **self._payload,
            "test_model_serializer_id": self.related_obj_1.pk,
        }

    @property
    def response_data(self):
        return self._payload | {
            "test_model_serializer": {
                "id": self.related_obj_1.pk,
                "name": self.related_obj_1.name,
                "description": self.related_obj_1.description,
            }
        }

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_relation_filter_by_id(self):
        """Test filtering by related object's ID."""
        await self._drop_all_objects()
        obj_1 = await self.model.objects.acreate(
            name="obj1", description="desc1", test_model_serializer=self.related_obj_1
        )
        obj_2 = await self.model.objects.acreate(
            name="obj2", description="desc2", test_model_serializer=self.related_obj_2
        )
        # Filter by related_obj_1's ID
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"test_model_serializer": self.related_obj_1.pk},
        )
        self.assertEqual(await res.acount(), 1)
        self.assertEqual(await res.afirst(), obj_1)

        # Filter by related_obj_2's ID
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"test_model_serializer": self.related_obj_2.pk},
        )
        self.assertEqual(await res.acount(), 1)
        self.assertEqual(await res.afirst(), obj_2)

    async def test_relation_filter_by_name(self):
        """Test filtering by related object's name with icontains."""
        await self._drop_all_objects()
        obj_1 = await self.model.objects.acreate(
            name="obj1", description="desc1", test_model_serializer=self.related_obj_1
        )
        obj_2 = await self.model.objects.acreate(
            name="obj2", description="desc2", test_model_serializer=self.related_obj_2
        )
        # Filter by partial name "alpha" (matches related_obj_1)
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"test_model_serializer_name": "alpha"},
        )
        self.assertEqual(await res.acount(), 1)
        self.assertEqual(await res.afirst(), obj_1)

        # Filter by partial name "beta" (matches related_obj_2)
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"test_model_serializer_name": "beta"},
        )
        self.assertEqual(await res.acount(), 1)
        self.assertEqual(await res.afirst(), obj_2)

    async def test_relation_filter_with_none_value(self):
        """Test that None filter values are ignored."""
        await self._drop_all_objects()
        await self.model.objects.acreate(
            name="obj1", description="desc1", test_model_serializer=self.related_obj_1
        )
        await self.model.objects.acreate(
            name="obj2", description="desc2", test_model_serializer=self.related_obj_2
        )
        # Filter with None should return all objects
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"test_model_serializer": None, "test_model_serializer_name": None},
        )
        self.assertEqual(await res.acount(), 2)

    async def test_relation_filter_combined(self):
        """Test filtering by multiple relation filters at once."""
        await self._drop_all_objects()
        obj_1 = await self.model.objects.acreate(
            name="obj1", description="desc1", test_model_serializer=self.related_obj_1
        )
        await self.model.objects.acreate(
            name="obj2", description="desc2", test_model_serializer=self.related_obj_2
        )
        # Filter by both ID and name (both matching related_obj_1)
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {
                "test_model_serializer": self.related_obj_1.pk,
                "test_model_serializer_name": "alpha",
            },
        )
        self.assertEqual(await res.acount(), 1)
        self.assertEqual(await res.afirst(), obj_1)

    async def test_relation_filter_no_match(self):
        """Test filtering with non-matching values returns empty queryset."""
        await self._drop_all_objects()
        await self.model.objects.acreate(
            name="obj1", description="desc1", test_model_serializer=self.related_obj_1
        )
        # Filter by non-existent ID
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"test_model_serializer": 99999},
        )
        self.assertEqual(await res.acount(), 0)

    async def test_relation_filter_empty_filters(self):
        """Test that empty filters dict returns all objects."""
        await self._drop_all_objects()
        await self.model.objects.acreate(
            name="obj1", description="desc1", test_model_serializer=self.related_obj_1
        )
        await self.model.objects.acreate(
            name="obj2", description="desc2", test_model_serializer=self.related_obj_2
        )
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {},
        )
        self.assertEqual(await res.acount(), 2)

    def test_query_params_registered(self):
        """Test that relations_filters are properly registered in query_params."""
        self.assertIn("test_model_serializer", self.viewset.query_params)
        self.assertIn("test_model_serializer_name", self.viewset.query_params)
        self.assertEqual(
            self.viewset.query_params["test_model_serializer"], (int, None)
        )
        self.assertEqual(
            self.viewset.query_params["test_model_serializer_name"], (str, None)
        )


@tag("detail_schema")
class DetailSchemaModelSerializerTestCase(TestCase):
    """Test detail schema generation for ModelSerializer."""

    namespace = "test_detail_schema_modelserializer"

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        @cls.api.viewset(model=models.TestModelSerializerWithDetail)
        class DetailMSViewSet(APIViewSet):
            pass

        # The decorator returns the instance, not the class
        cls.viewset = DetailMSViewSet

    def test_read_schema_has_minimal_fields(self):
        """Test that read schema only includes ReadSerializer fields."""
        schema_out = self.viewset.schema_out
        self.assertIsNotNone(schema_out)
        self.assertIn("id", schema_out.model_fields)
        self.assertIn("name", schema_out.model_fields)
        self.assertNotIn("description", schema_out.model_fields)
        self.assertNotIn("extra_info", schema_out.model_fields)

    def test_detail_schema_has_extended_fields(self):
        """Test that detail schema includes DetailSerializer fields."""
        schema_detail = self.viewset.schema_detail
        self.assertIsNotNone(schema_detail)
        self.assertIn("id", schema_detail.model_fields)
        self.assertIn("name", schema_detail.model_fields)
        self.assertIn("description", schema_detail.model_fields)
        self.assertIn("extra_info", schema_detail.model_fields)
        self.assertIn("computed_field", schema_detail.model_fields)

    def test_get_retrieve_schema_returns_detail(self):
        """Test that _get_retrieve_schema returns detail schema when available."""
        retrieve_schema = self.viewset._get_retrieve_schema()
        self.assertEqual(retrieve_schema, self.viewset.schema_detail)

    def test_get_schemas_returns_seven_tuple(self):
        """Test that get_schemas returns a 7-tuple including per-operation out schemas."""
        result = self.viewset.get_schemas()
        self.assertEqual(len(result), 7)
        schema_out, schema_detail, _, _, schema_create_out, schema_update_out, schema_delete_out = result
        self.assertIsNotNone(schema_out)
        self.assertIsNotNone(schema_detail)
        self.assertEqual(schema_create_out, schema_out)
        self.assertEqual(schema_update_out, schema_out)
        self.assertIsNone(schema_delete_out)


@tag("detail_schema")
class DetailSchemaSerializerTestCase(TestCase):
    """Test detail schema generation for Serializer class."""

    namespace = "test_detail_schema_serializer"

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        class TestDetailSerializer(ninja_serializers.Serializer):
            class Meta:
                model = models.TestModel
                schema_in = ninja_serializers.SchemaModelConfig(
                    fields=["name", "description"]
                )
                schema_out = ninja_serializers.SchemaModelConfig(fields=["id", "name"])
                schema_detail = ninja_serializers.SchemaModelConfig(
                    fields=["id", "name", "description"]
                )

        @cls.api.viewset(model=models.TestModel)
        class DetailSerializerViewSet(APIViewSet):
            serializer_class = TestDetailSerializer

        cls.serializer_class = TestDetailSerializer
        # The decorator returns the instance, not the class
        cls.viewset = DetailSerializerViewSet

    def test_serializer_generates_detail_schema(self):
        """Test that Serializer generates detail schema from Meta.schema_detail."""
        schema_detail = self.serializer_class.generate_detail_s()
        self.assertIsNotNone(schema_detail)
        self.assertIn("id", schema_detail.model_fields)
        self.assertIn("name", schema_detail.model_fields)
        self.assertIn("description", schema_detail.model_fields)

    def test_viewset_uses_serializer_detail_schema(self):
        """Test that APIViewSet uses Serializer's detail schema."""
        schema_detail = self.viewset.schema_detail
        self.assertIsNotNone(schema_detail)
        self.assertIn("description", schema_detail.model_fields)

    def test_retrieve_uses_detail_schema(self):
        """Test that retrieve endpoint uses detail schema."""
        retrieve_schema = self.viewset._get_retrieve_schema()
        self.assertIn("description", retrieve_schema.model_fields)


@tag("detail_schema")
class DetailSchemaFallbackTestCase(TestCase):
    """Test detail schema fallback behavior."""

    namespace = "test_detail_schema_fallback"

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        @cls.api.viewset(model=models.TestModelSerializer)
        class NoDetailViewSet(APIViewSet):
            pass

        # The decorator returns the instance, not the class
        cls.viewset = NoDetailViewSet

    def test_detail_schema_falls_back_to_read_schema(self):
        """Test that schema_detail falls back to read schema when no detail config."""
        # TestModelSerializer has no DetailSerializer defined, but schema_detail
        # now falls back to the read schema instead of being None
        self.assertIsNotNone(self.viewset.schema_detail)
        retrieve_schema = self.viewset._get_retrieve_schema()
        # The retrieve schema should be the detail schema (which is the fallback)
        self.assertEqual(retrieve_schema, self.viewset.schema_detail)


# ==========================================================
#               MATCH CASE FILTER MIXIN TESTS
# ==========================================================


@tag("match_case_filter_mixin")
class MatchCaseFilterViewSetMixinTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    """Test MatchCaseFilterViewSetMixin functionality."""

    namespace = "test_match_case_filter_mixin_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerMatchCaseFilterAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_match_case_filter_true_includes(self):
        """Test filtering with True value includes matching records."""
        await self._drop_all_objects()
        obj_approved = await self.model.objects.acreate(
            name="approved_item", description="desc", status="approved"
        )
        await self.model.objects.acreate(
            name="pending_item", description="desc", status="pending"
        )
        await self.model.objects.acreate(
            name="rejected_item", description="desc", status="rejected"
        )
        # Filter with is_approved=True should return only approved items
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"is_approved": True},
        )
        self.assertEqual(await res.acount(), 1)
        self.assertEqual(await res.afirst(), obj_approved)

    async def test_match_case_filter_false_excludes(self):
        """Test filtering with False value excludes matching records."""
        await self._drop_all_objects()
        obj_approved = await self.model.objects.acreate(
            name="approved_item", description="desc", status="approved"
        )
        obj_pending = await self.model.objects.acreate(
            name="pending_item", description="desc", status="pending"
        )
        obj_rejected = await self.model.objects.acreate(
            name="rejected_item", description="desc", status="rejected"
        )
        # Filter with is_approved=False should exclude approved items
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"is_approved": False},
        )
        self.assertEqual(await res.acount(), 2)
        results = [obj async for obj in res]
        self.assertIn(obj_pending, results)
        self.assertIn(obj_rejected, results)
        self.assertNotIn(obj_approved, results)

    async def test_match_case_filter_none_no_filtering(self):
        """Test that None filter value doesn't apply any filtering."""
        await self._drop_all_objects()
        await self.model.objects.acreate(
            name="approved_item", description="desc", status="approved"
        )
        await self.model.objects.acreate(
            name="pending_item", description="desc", status="pending"
        )
        await self.model.objects.acreate(
            name="rejected_item", description="desc", status="rejected"
        )
        # Filter with None should return all objects
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"is_approved": None},
        )
        self.assertEqual(await res.acount(), 3)

    async def test_match_case_filter_empty_filters(self):
        """Test that empty filters dict returns all objects."""
        await self._drop_all_objects()
        await self.model.objects.acreate(
            name="approved_item", description="desc", status="approved"
        )
        await self.model.objects.acreate(
            name="pending_item", description="desc", status="pending"
        )
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {},
        )
        self.assertEqual(await res.acount(), 2)

    def test_query_params_registered(self):
        """Test that filters_match_cases are properly registered in query_params."""
        self.assertIn("is_approved", self.viewset.query_params)
        self.assertEqual(self.viewset.query_params["is_approved"], (bool, None))

    def test_filters_match_cases_fields_property(self):
        """Test that filters_match_cases_fields property returns correct list."""
        self.assertEqual(self.viewset.filters_match_cases_fields, ["is_approved"])


@tag("match_case_filter_mixin_exclude")
class MatchCaseFilterViewSetMixinExcludeTestCase(TestCase):
    """Test MatchCaseFilterViewSetMixin with exclude behavior."""

    model = models.TestModelSerializer
    viewset = views.TestModelSerializerMatchCaseExcludeFilterAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_match_case_exclude_true(self):
        """Test filtering with True value excludes matching records."""
        await self._drop_all_objects()
        obj_approved = await self.model.objects.acreate(
            name="approved_item", description="desc", status="approved"
        )
        obj_pending = await self.model.objects.acreate(
            name="pending_item", description="desc", status="pending"
        )
        obj_rejected = await self.model.objects.acreate(
            name="rejected_item", description="desc", status="rejected"
        )
        # Filter with hide_pending=True should exclude pending items
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"hide_pending": True},
        )
        self.assertEqual(await res.acount(), 2)
        results = [obj async for obj in res]
        self.assertIn(obj_approved, results)
        self.assertIn(obj_rejected, results)
        self.assertNotIn(obj_pending, results)

    async def test_match_case_exclude_false_includes_only(self):
        """Test filtering with False value includes only matching records."""
        await self._drop_all_objects()
        await self.model.objects.acreate(
            name="approved_item", description="desc", status="approved"
        )
        obj_pending = await self.model.objects.acreate(
            name="pending_item", description="desc", status="pending"
        )
        await self.model.objects.acreate(
            name="rejected_item", description="desc", status="rejected"
        )
        # Filter with hide_pending=False should include only pending items
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"hide_pending": False},
        )
        self.assertEqual(await res.acount(), 1)
        self.assertEqual(await res.afirst(), obj_pending)


# ==========================================================
#       MATCH CASE FILTER WITH Q OBJECTS TEST CASES
# ==========================================================


@tag("match_case_q_filter_mixin")
class MatchCaseQFilterViewSetMixinTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    """Test MatchCaseFilterViewSetMixin with Q objects."""

    namespace = "test_match_case_q_filter_mixin_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerMatchCaseQFilterAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_match_case_q_filter_true_includes(self):
        """Test Q object filtering with True value includes matching records."""
        await self._drop_all_objects()
        obj_approved = await self.model.objects.acreate(
            name="approved_item", description="desc", status="approved"
        )
        await self.model.objects.acreate(
            name="pending_item", description="desc", status="pending"
        )
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"is_approved": True},
        )
        self.assertEqual(await res.acount(), 1)
        self.assertEqual(await res.afirst(), obj_approved)

    async def test_match_case_q_filter_false_excludes(self):
        """Test Q object filtering with False value excludes matching records."""
        await self._drop_all_objects()
        await self.model.objects.acreate(
            name="approved_item", description="desc", status="approved"
        )
        obj_pending = await self.model.objects.acreate(
            name="pending_item", description="desc", status="pending"
        )
        obj_rejected = await self.model.objects.acreate(
            name="rejected_item", description="desc", status="rejected"
        )
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"is_approved": False},
        )
        self.assertEqual(await res.acount(), 2)
        results = [obj async for obj in res]
        self.assertIn(obj_pending, results)
        self.assertIn(obj_rejected, results)

    async def test_match_case_q_filter_no_param_returns_all(self):
        """Test Q object filter with no param returns all records."""
        await self._drop_all_objects()
        await self.model.objects.acreate(
            name="item1", description="desc", status="approved"
        )
        await self.model.objects.acreate(
            name="item2", description="desc", status="pending"
        )
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {},
        )
        self.assertEqual(await res.acount(), 2)


@tag("match_case_q_exclude_filter_mixin")
class MatchCaseQExcludeFilterViewSetMixinTestCase(TestCase):
    """Test MatchCaseFilterViewSetMixin with Q objects and exclude behavior."""

    model = models.TestModelSerializer
    viewset = views.TestModelSerializerMatchCaseQExcludeFilterAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_match_case_q_exclude_true(self):
        """Test Q object exclude with True value excludes matching records."""
        await self._drop_all_objects()
        obj_approved = await self.model.objects.acreate(
            name="approved_item", description="desc", status="approved"
        )
        await self.model.objects.acreate(
            name="pending_item", description="desc", status="pending"
        )
        obj_rejected = await self.model.objects.acreate(
            name="rejected_item", description="desc", status="rejected"
        )
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"hide_pending": True},
        )
        self.assertEqual(await res.acount(), 2)
        results = [obj async for obj in res]
        self.assertIn(obj_approved, results)
        self.assertIn(obj_rejected, results)

    async def test_match_case_q_exclude_false_includes_only(self):
        """Test Q object exclude with False value includes only matching records."""
        await self._drop_all_objects()
        await self.model.objects.acreate(
            name="approved_item", description="desc", status="approved"
        )
        obj_pending = await self.model.objects.acreate(
            name="pending_item", description="desc", status="pending"
        )
        await self.model.objects.acreate(
            name="rejected_item", description="desc", status="rejected"
        )
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"hide_pending": False},
        )
        self.assertEqual(await res.acount(), 1)
        self.assertEqual(await res.afirst(), obj_pending)


@tag("match_case_filter_mixin_invalid_field")
class MatchCaseFilterInvalidFieldTestCase(TestCase):
    """Test _apply_case_filter with invalid filter fields that result in empty validated_lookup."""

    model = models.TestModelSerializer

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="test_match_case_invalid_field")

        class InvalidFieldMatchCaseViewSet(
            mixins.MatchCaseFilterViewSetMixin,
            APIViewSet,
        ):
            model = models.TestModelSerializer
            filters_match_cases = [
                MatchCaseFilterSchema(
                    query_param="has_invalid",
                    cases=BooleanMatchFilterSchema(
                        true=MatchConditionFilterSchema(
                            query_filter={"nonexistent_field__invalid": "value"},
                            include=True,
                        ),
                        false=MatchConditionFilterSchema(
                            query_filter={"nonexistent_field__invalid": "value"},
                            include=False,
                        ),
                    ),
                ),
            ]

        cls.viewset = InvalidFieldMatchCaseViewSet(api=cls.api)

    async def test_apply_case_filter_empty_validated_lookup(self):
        """When all filter fields are invalid, queryset is returned unmodified."""
        await self.model.objects.all().adelete()
        await self.model.objects.acreate(
            name="item1", description="desc", status="active"
        )
        await self.model.objects.acreate(
            name="item2", description="desc", status="inactive"
        )
        res = await self.viewset.aquery_params_handler(
            self.model.objects.all(),
            {"has_invalid": True},
        )
        # All filter fields are invalid, so no filtering should occur
        self.assertEqual(await res.acount(), 2)


@tag("pagination")
class LimitOffsetPaginationTestCase(TestCase):
    """Test list_view with LimitOffsetPagination to cover the else branch."""

    @classmethod
    def setUpTestData(cls):
        from ninja.pagination import LimitOffsetPagination
        from tests.generics.views import GenericAPIViewSet
        from tests.generics.request import Request

        cls.namespace = "limit_offset_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        class LimitOffsetViewSet(GenericAPIViewSet):
            model = models.TestModel
            schema_in = schema.TestModelSchemaIn
            schema_out = schema.TestModelSchemaOut
            schema_update = schema.TestModelSchemaPatch
            pagination_class = LimitOffsetPagination

        cls.viewset = LimitOffsetViewSet()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.request = Request(ModelUtil(cls.model).verbose_name_path_resolver())

    async def test_list_with_limit_offset(self):
        """List view works with LimitOffsetPagination."""
        await self.model.objects.all().adelete()
        for i in range(5):
            await self.model.objects.acreate(name=f"item_{i}", description="d")

        view = self.viewset.alist_view()
        result = await view(self.request.get())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["count"], 5)


@tag("batch_fk")
class BatchFKResolutionTestCase(TestCase):
    """Test batch FK resolution with multi-FK model."""

    @classmethod
    def setUpTestData(cls):
        from tests.generics.request import Request

        cls.namespace = "batch_fk_test"
        cls.model = models.PerfArticle
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.PerfArticleAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.request = Request("perf-articles")

        cls.author = models.PerfAuthor.objects.create(name="author")
        cls.category = models.PerfCategory.objects.create(name="cat")
        cls.publisher = models.PerfPublisher.objects.create(name="pub")

    async def test_create_with_nonexistent_fk_raises(self):
        """Create with a nonexistent FK PK raises NotFoundError."""
        from ninja_aio.exceptions import NotFoundError

        view = self.viewset.acreate_view()
        data = schema.PerfArticleSchemaIn(
            title="test",
            author=self.author.pk,
            category=99999,  # does not exist
            publisher=self.publisher.pk,
        )
        with self.assertRaises(NotFoundError):
            await view(self.request.post(), data)


@tag("per_operation_out_schema")
class PerOperationOutSchemaTestCase(TestCase):
    """Test schema_create_out, schema_update_out, schema_delete_out on APIViewSet."""

    @classmethod
    def setUpTestData(cls):
        from tests.generics.request import Request

        cls.model = models.TestModel
        cls.pk_att = cls.model._meta.pk.attname

        cls.create_out_ns = "per_op_create_out"
        cls.create_out_api = NinjaAIO(urls_namespace=cls.create_out_ns)
        cls.create_out_viewset = views.TestModelCreateOutAPI()
        cls.create_out_viewset.api = cls.create_out_api
        cls.create_out_viewset.add_views_to_route()

        cls.update_out_ns = "per_op_update_out"
        cls.update_out_api = NinjaAIO(urls_namespace=cls.update_out_ns)
        cls.update_out_viewset = views.TestModelUpdateOutAPI()
        cls.update_out_viewset.api = cls.update_out_api
        cls.update_out_viewset.add_views_to_route()

        cls.delete_out_ns = "per_op_delete_out"
        cls.delete_out_api = NinjaAIO(urls_namespace=cls.delete_out_ns)
        cls.delete_out_viewset = views.TestModelDeleteOutAPI()
        cls.delete_out_viewset.api = cls.delete_out_api
        cls.delete_out_viewset.add_views_to_route()

        cls.request = Request("test-models")

        cls.payload = {"name": "per_op_test", "description": "per_op_desc"}
        cls.obj = models.TestModel.objects.create(**cls.payload)

    def test_schema_create_out_set_on_viewset(self):
        self.assertEqual(self.create_out_viewset.schema_create_out, schema.TestModelCreateOut)
        self.assertEqual(self.create_out_viewset.schema_out, schema.TestModelSchemaOut)

    def test_schema_update_out_set_on_viewset(self):
        self.assertEqual(self.update_out_viewset.schema_update_out, schema.TestModelUpdateOut)
        self.assertEqual(self.update_out_viewset.schema_out, schema.TestModelSchemaOut)

    def test_schema_delete_out_set_on_viewset(self):
        self.assertEqual(self.delete_out_viewset.schema_delete_out, schema.TestModelDeleteOut)

    def test_get_schemas_create_out(self):
        schemas = self.create_out_viewset.get_schemas()
        self.assertEqual(len(schemas), 7)
        schema_out, _, _, _, schema_create_out, schema_update_out, schema_delete_out = schemas
        self.assertEqual(schema_out, schema.TestModelSchemaOut)
        self.assertEqual(schema_create_out, schema.TestModelCreateOut)
        self.assertEqual(schema_update_out, schema.TestModelSchemaOut)
        self.assertIsNone(schema_delete_out)

    def test_get_schemas_update_out(self):
        schemas = self.update_out_viewset.get_schemas()
        self.assertEqual(len(schemas), 7)
        schema_out, _, _, _, schema_create_out, schema_update_out, schema_delete_out = schemas
        self.assertEqual(schema_out, schema.TestModelSchemaOut)
        self.assertEqual(schema_create_out, schema.TestModelSchemaOut)
        self.assertEqual(schema_update_out, schema.TestModelUpdateOut)
        self.assertIsNone(schema_delete_out)

    def test_get_schemas_delete_out(self):
        schemas = self.delete_out_viewset.get_schemas()
        self.assertEqual(len(schemas), 7)
        _, _, _, _, schema_create_out, schema_update_out, schema_delete_out = schemas
        self.assertEqual(schema_create_out, schema.TestModelSchemaOut)
        self.assertEqual(schema_update_out, schema.TestModelSchemaOut)
        self.assertEqual(schema_delete_out, schema.TestModelDeleteOut)

    async def test_create_returns_schema_create_out(self):
        await self.model.objects.all().adelete()
        view = self.create_out_viewset.acreate_view()
        data = schema.TestModelSchemaIn(**self.payload)
        result = await view(self.request.post(), data)
        self.assertEqual(result.status_code, 201)
        content = result.value
        self.assertIn(self.pk_att, content)
        self.assertIn("name", content)
        self.assertNotIn("description", content)

    async def test_update_returns_schema_update_out(self):
        view = self.update_out_viewset.aupdate_view()
        path_schema = self.update_out_viewset.path_schema(**{self.pk_att: self.obj.pk})
        update_data = schema.TestModelSchemaPatch(description="updated_desc")
        result = await view(self.request.patch(), update_data, path_schema)
        self.assertEqual(result.status_code, 200)
        content = result.value
        self.assertIn(self.pk_att, content)
        self.assertIn("description", content)
        self.assertNotIn("name", content)

    async def test_delete_returns_204_without_schema_delete_out(self):
        obj = await self.model.objects.acreate(name="to_delete_default", description="d")
        view = self.create_out_viewset.adelete_view()
        path_schema = self.create_out_viewset.path_schema(**{self.pk_att: obj.pk})
        result = await view(self.request.delete(), path_schema)
        self.assertEqual(result.status_code, 204)
        self.assertIsNone(result.value)

    async def test_delete_returns_200_with_schema_delete_out(self):
        obj = await self.model.objects.acreate(name="to_delete_out", description="d")
        pk = obj.pk
        view = self.delete_out_viewset.adelete_view()
        path_schema = self.delete_out_viewset.path_schema(**{self.pk_att: pk})
        result = await view(self.request.delete(), path_schema)
        self.assertEqual(result.status_code, 200)
        content = result.value
        self.assertEqual(content[self.pk_att], pk)
        self.assertIn("name", content)
        self.assertEqual(content["name"], "to_delete_out")
        self.assertNotIn("description", content)
        self.assertFalse(await self.model.objects.filter(pk=pk).aexists())

    async def test_delete_with_schema_out_fetches_object_only_once(self):
        """Regression test: adelete_view with schema_delete_out must fetch the
        object once (to serialize it), not once for serialization and again
        inside delete_s to perform the delete."""
        obj = await self.model.objects.acreate(name="fetch_once", description="d")
        pk = obj.pk
        view = self.delete_out_viewset.adelete_view()
        path_schema = self.delete_out_viewset.path_schema(**{self.pk_att: pk})

        original_get_object = ModelUtil.aget_object
        call_count = 0

        async def counting_get_object(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return await original_get_object(self, *args, **kwargs)

        with mock.patch.object(ModelUtil, "aget_object", counting_get_object):
            result = await view(self.request.delete(), path_schema)

        self.assertEqual(result.status_code, 200)
        # Previously 2: one in delete_view to fetch+serialize, one inside
        # delete_s to re-fetch the same object just to delete it.
        self.assertEqual(call_count, 1)
        self.assertFalse(await self.model.objects.filter(pk=pk).aexists())
