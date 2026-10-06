import asyncio
from unittest.mock import patch

from django.test import TestCase
from ninja import Schema
from ninja.testing import TestAsyncClient, TestClient
from pydantic import Field

from ninja_aio import NinjaAIO, SchemaConfig, Serializer
from ninja_aio.decorators import aatomic
from ninja_aio.models.utils import _SERIALIZER_REGISTRY
from ninja_aio.schemas import M2MRelationSchema
from ninja_aio.views import APIViewSet
from tests.test_app import models


class CustomPatchRegressionTests(TestCase):
    def setUp(self):
        self.registry = patch.dict(_SERIALIZER_REGISTRY)
        self.registry.start()
        self.addCleanup(self.registry.stop)

        class PlainSerializer(Serializer):
            class Meta:
                model = models.TestModel

            class Schemas:
                update = SchemaConfig(optionals=[("name", str), ("description", str | None)])
                read = SchemaConfig(fields=["id", "name", "description"])

        class CustomPatch(Schema):
            name: str | None = "default-name"
            description: str | None = Field(None, validation_alias="text")

        self.serializer = PlainSerializer
        self.patch_schema = CustomPatch
        self.api = NinjaAIO(urls_namespace="review_custom_patch")
        for mode in ("sync", "async"):
            viewset = type(
                f"{mode.title()}PatchAPI", (APIViewSet,),
                {
                    "model": models.TestModel,
                    "serializer_class": PlainSerializer,
                    "execution_mode": mode,
                    "schema_update": CustomPatch,
                },
            )
            viewset(api=self.api, prefix=mode).add_views_to_route()
        self.obj = models.TestModel.objects.create(name="original", description="original")

    def test_sync_custom_patch_preserves_omitted_fields(self):
        response = TestClient(self.api).patch(
            f"/sync/{self.obj.pk}/", json={"text": "changed"}
        )
        self.assertEqual(response.status_code, 200)
        self.obj.refresh_from_db()
        self.assertEqual((self.obj.name, self.obj.description), ("original", "changed"))

    async def test_async_custom_patch_preserves_omitted_fields(self):
        response = await TestAsyncClient(self.api).patch(
            f"/async/{self.obj.pk}/", json={"text": "changed"}
        )
        self.assertEqual(response.status_code, 200)
        await self.obj.arefresh_from_db()
        self.assertEqual((self.obj.name, self.obj.description), ("original", "changed"))

    def test_empty_custom_patch_keeps_all_fields(self):
        self.serializer.update(self.obj, self.patch_schema())
        self.obj.refresh_from_db()
        self.assertEqual((self.obj.name, self.obj.description), ("original", "original"))

    def test_explicit_null_and_default_remain_supplied(self):
        validated = self.serializer._validate_operation_data(
            "update", self.patch_schema(name="default-name", text=None)
        )
        self.assertEqual(validated.model_fields_set, {"name", "description"})
        self.assertIsNone(validated.description)

    def test_model_serializer_also_preserves_omitted_fields(self):
        obj = models.SchemasParent.objects.create(name="original", description="original")
        models.SchemasParent.update(obj, self.patch_schema(text="changed"))
        obj.refresh_from_db()
        self.assertEqual((obj.name, obj.description), ("original", "changed"))


class RelatedQuerysetScopeRegressionTests(TestCase):
    def setUp(self):
        self.registry = patch.dict(_SERIALIZER_REGISTRY)
        self.registry.start()
        self.addCleanup(self.registry.stop)

        class RelatedSerializer(Serializer):
            class Meta:
                model = models.TestModelReverseManyToMany

            class Schemas:
                read = SchemaConfig(fields=["id", "name"])

            @classmethod
            def queryset_request(cls, request):
                return cls.model.objects.filter(name__startswith=request.headers["X-Tenant"])

            @classmethod
            async def aqueryset_request(cls, request):
                return cls.queryset_request(request)

        class OwnerSerializer(Serializer):
            class Meta:
                model = models.TestModelManyToMany

            class Schemas:
                read = SchemaConfig(fields=["id", "name"])

        self.api = NinjaAIO(urls_namespace="review_related_scope")
        for mode in ("sync", "async"):
            viewset = type(
                f"{mode.title()}RelatedAPI", (APIViewSet,),
                {
                    "model": models.TestModelManyToMany,
                    "serializer_class": OwnerSerializer,
                    "execution_mode": mode,
                    "m2m_relations": [M2MRelationSchema(
                        model=models.TestModelReverseManyToMany,
                        serializer_class=RelatedSerializer,
                        related_name="test_models", path="related",
                    )],
                },
            )
            viewset(api=self.api, prefix=mode).add_views_to_route()
        self.owner = models.TestModelManyToMany.objects.create(name="owner", description="d")
        self.visible = models.TestModelReverseManyToMany.objects.create(name="allowed-one", description="d")
        self.hidden = models.TestModelReverseManyToMany.objects.create(name="other-one", description="d")
        self.unrelated = models.TestModelReverseManyToMany.objects.create(name="allowed-two", description="d")
        self.headers = {"X-Tenant": "allowed"}

    def test_sync_add_rejects_out_of_scope_record(self):
        response = TestClient(self.api).post(
            f"/sync/{self.owner.pk}/related/",
            json={"add": [self.visible.pk, self.hidden.pk]}, headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["errors"]["count"], 1)
        self.assertEqual(list(self.owner.test_models.values_list("pk", flat=True)), [self.visible.pk])

    async def test_async_add_rejects_out_of_scope_record(self):
        response = await TestAsyncClient(self.api).post(
            f"/async/{self.owner.pk}/related/",
            json={"add": [self.visible.pk, self.hidden.pk]}, headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["errors"]["count"], 1)
        self.assertEqual([obj.pk async for obj in self.owner.test_models.all()], [self.visible.pk])

    def test_sync_list_filters_scope_before_count_and_pagination(self):
        self.owner.test_models.add(self.hidden, self.visible)
        response = TestClient(self.api).get(
            f"/sync/{self.owner.pk}/related", headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "items": [{"id": self.visible.pk, "name": self.visible.name}], "count": 1,
        })

    async def test_async_list_filters_scope_before_count_and_pagination(self):
        await self.owner.test_models.aadd(self.hidden, self.visible)
        response = await TestAsyncClient(self.api).get(
            f"/async/{self.owner.pk}/related", headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "items": [{"id": self.visible.pk, "name": self.visible.name}], "count": 1,
        })

    def test_sync_remove_rejects_out_of_scope_record(self):
        self.owner.test_models.add(self.hidden, self.visible)
        response = TestClient(self.api).post(
            f"/sync/{self.owner.pk}/related/",
            json={"remove": [self.visible.pk, self.hidden.pk]}, headers=self.headers,
        )
        self.assertEqual(response.json()["errors"]["count"], 1)
        self.assertEqual(list(self.owner.test_models.values_list("pk", flat=True)), [self.hidden.pk])

    async def test_async_remove_rejects_out_of_scope_record(self):
        await self.owner.test_models.aadd(self.hidden, self.visible)
        response = await TestAsyncClient(self.api).post(
            f"/async/{self.owner.pk}/related/",
            json={"remove": [self.visible.pk, self.hidden.pk]}, headers=self.headers,
        )
        self.assertEqual(response.json()["errors"]["count"], 1)
        self.assertEqual([obj.pk async for obj in self.owner.test_models.all()], [self.hidden.pk])


class AsyncTransactionOwnershipRegressionTests(TestCase):
    def setUp(self):
        self.registry = patch.dict(_SERIALIZER_REGISTRY)
        self.registry.start()
        self.addCleanup(self.registry.stop)

    async def _assert_independent_writes(self, *, bulk=False, plain_sibling=False):
        started, finished = asyncio.Event(), asyncio.Event()

        class HookSerializer(Serializer):
            class Meta:
                model = models.TestModel

            class Schemas:
                create = SchemaConfig(fields=["name", "description"])

            async def apost_create(self, obj):
                if obj.name == "failing":
                    started.set()
                    # The broken implementation lets the sibling finish inside
                    # this transaction; the corrected worker queues it instead.
                    try:
                        await asyncio.wait_for(finished.wait(), timeout=0.1)
                    except asyncio.TimeoutError:
                        pass
                    raise RuntimeError("rollback failing item")

        async def create(name):
            data = {"name": name, "description": "d"}
            if bulk:
                return await HookSerializer.abulk_create([data])
            return await HookSerializer.acreate(data)

        async def sibling():
            await started.wait()
            if plain_sibling:
                result = await models.TestModel.objects.acreate(name="successful", description="d")
            else:
                result = await create("successful")
            finished.set()
            return result

        failed, successful = await asyncio.wait_for(
            asyncio.gather(create("failing"), sibling(), return_exceptions=True), timeout=5
        )
        if bulk:
            self.assertEqual(len(failed.failed), 1)
            self.assertEqual(len(successful.succeeded), 1)
        else:
            self.assertIsInstance(failed, RuntimeError)
            self.assertIsInstance(successful, models.TestModel)
        self.assertFalse(await models.TestModel.objects.filter(name="failing").aexists())
        self.assertTrue(await models.TestModel.objects.filter(name="successful").aexists())

    async def test_concurrent_async_creates_keep_successful_row(self):
        await self._assert_independent_writes()

    async def test_concurrent_async_bulk_creates_keep_successful_row(self):
        await self._assert_independent_writes(bulk=True)

    async def test_unwrapped_sibling_write_cannot_join_transaction(self):
        await self._assert_independent_writes(plain_sibling=True)

    async def test_nested_atomic_rollback_preserves_outer_write(self):
        @aatomic
        async def inner():
            await models.TestModel.objects.acreate(name="inner", description="d")
            raise RuntimeError("rollback savepoint")

        @aatomic
        async def outer():
            await models.TestModel.objects.acreate(name="outer", description="d")
            with self.assertRaises(RuntimeError):
                await inner()

        await outer()
        self.assertTrue(await models.TestModel.objects.filter(name="outer").aexists())
        self.assertFalse(await models.TestModel.objects.filter(name="inner").aexists())

    async def test_cancellation_rolls_back_and_releases_worker(self):
        started = asyncio.Event()

        @aatomic
        async def operation():
            await models.TestModel.objects.acreate(name="cancelled", description="d")
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(operation())
        await asyncio.wait_for(started.wait(), timeout=5)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(await models.TestModel.objects.filter(name="cancelled").aexists())
        obj = await asyncio.wait_for(
            models.TestModel.objects.acreate(name="after-cancel", description="d"), timeout=5
        )
        self.assertIsNotNone(obj.pk)
