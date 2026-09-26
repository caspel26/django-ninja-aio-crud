import inspect
from typing import Any, get_type_hints
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.test import TestCase
from ninja import Schema

from ninja_aio.exceptions import NotFoundError, OperationValidationError
from tests.test_app.models import (
    TestModel,
    TestModelForeignKey,
    TestModelReverseForeignKey,
    TestModelSerializer,
    TestModelSerializerForeignKey,
    TestModelSerializerReverseForeignKey,
    TestModelWithSchemaOverrides,
)
from tests.test_app.serializers import (
    BookAsIdMetaSerializer,
    TestModelForeignKeySerializer,
    TestModelWithValidatorsMetaSerializer,
)


class AsyncCrudFacadeContractMixin:
    serializer_class: type
    model_class: type[models.Model]

    def create_data(self, suffix: str) -> dict[str, Any]:
        return {"name": f"name-{suffix}", "description": f"description-{suffix}"}

    def assert_async_signature(self, method_name: str) -> None:
        method = getattr(self.serializer_class, method_name)
        signature = inspect.signature(method)
        hints = get_type_hints(method)

        self.assertTrue(inspect.iscoroutinefunction(method))
        self.assertIn("return", hints)
        self.assertIsNot(hints["return"], Any)
        self.assertEqual(
            signature.parameters["request"].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertIsNone(signature.parameters["request"].default)

    def test_async_crud_methods_have_typed_keyword_only_request(self) -> None:
        for method_name in ("acreate", "aget", "aupdate", "adestroy"):
            with self.subTest(method=method_name):
                self.assert_async_signature(method_name)

    async def test_acreate_accepts_dict_and_generated_schema(self) -> None:
        from_dict = await self.serializer_class.acreate(self.create_data("dict"))
        create_schema = self.serializer_class.create_schema
        self.assertIsNotNone(create_schema)
        from_schema = await self.serializer_class.acreate(
            create_schema(**self.create_data("schema"))
        )

        self.assertIsInstance(from_dict, self.model_class)
        self.assertIsInstance(from_schema, self.model_class)
        self.assertIsNotNone(from_dict.pk)
        self.assertIsNotNone(from_schema.pk)

    async def test_acreate_validates_direct_input(self) -> None:
        with self.assertRaises(OperationValidationError) as raised:
            await self.serializer_class.acreate({"name": "missing-description"})
        self.assertEqual(raised.exception.code, "validation_error")
        self.assertIn("description", raised.exception.field_errors)

    async def test_aget_supports_exactly_one_lookup_strategy(self) -> None:
        obj = await self.serializer_class.acreate(self.create_data("get"))

        self.assertEqual(await self.serializer_class.aget(obj.pk), obj)
        self.assertEqual(await self.serializer_class.aget(name=obj.name), obj)

        with self.assertRaisesRegex(ValueError, "Exactly one"):
            await self.serializer_class.aget()
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            await self.serializer_class.aget(obj.pk, name=obj.name)
        with self.assertRaises(NotFoundError):
            await self.serializer_class.aget(999_999)

    async def test_aupdate_with_instance_skips_lookup_and_returns_instance(
        self,
    ) -> None:
        obj = await self.serializer_class.acreate(self.create_data("instance-update"))

        with mock.patch.object(
            self.serializer_class._util,
            "aget_object",
            side_effect=AssertionError("loaded instances must not be refetched"),
        ):
            updated = await self.serializer_class.aupdate(
                obj,
                {"description": "updated-instance"},
            )

        self.assertIs(updated, obj)
        self.assertEqual(updated.description, "updated-instance")
        self.assertEqual(
            await self.model_class.objects.filter(pk=obj.pk)
            .values_list("description", flat=True)
            .aget(),
            "updated-instance",
        )

    async def test_aupdate_with_pk_fetches_and_returns_instance(self) -> None:
        obj = await self.serializer_class.acreate(self.create_data("pk-update"))

        updated = await self.serializer_class.aupdate(
            obj.pk,
            {"description": "updated-pk"},
        )

        self.assertIsInstance(updated, self.model_class)
        self.assertEqual(updated.pk, obj.pk)
        self.assertEqual(updated.description, "updated-pk")

    async def test_mutations_reject_an_unsaved_instance(self) -> None:
        unsaved = self.model_class(**self.create_data("unsaved"))

        with self.assertRaisesRegex(ValueError, "persisted model instance"):
            await self.serializer_class.aupdate(
                unsaved,
                {"description": "not-saved"},
            )
        with self.assertRaisesRegex(ValueError, "persisted model instance"):
            await self.serializer_class.adestroy(unsaved)

    async def test_adestroy_with_instance_skips_lookup_and_returns_none(self) -> None:
        obj = await self.serializer_class.acreate(self.create_data("instance-destroy"))

        with mock.patch.object(
            self.serializer_class._util,
            "aget_object",
            side_effect=AssertionError("loaded instances must not be refetched"),
        ):
            result = await self.serializer_class.adestroy(obj)

        self.assertIsNone(result)
        self.assertFalse(await self.model_class.objects.filter(pk=obj.pk).aexists())

    async def test_adestroy_with_pk_returns_none(self) -> None:
        obj = await self.serializer_class.acreate(self.create_data("pk-destroy"))

        result = await self.serializer_class.adestroy(obj.pk)

        self.assertIsNone(result)
        self.assertFalse(await self.model_class.objects.filter(pk=obj.pk).aexists())


class ModelSerializerAsyncCrudFacadeTests(
    AsyncCrudFacadeContractMixin,
    TestCase,
):
    serializer_class = TestModelSerializer
    model_class = TestModelSerializer

    async def test_amodel_dump_loads_fk_and_applies_schema_override(self) -> None:
        parent = await TestModelSerializerReverseForeignKey.objects.acreate(
            **self.create_data("parent")
        )
        child = await TestModelSerializerForeignKey.objects.acreate(
            **self.create_data("child"), test_model_serializer=parent
        )
        unloaded = await TestModelSerializerForeignKey.objects.aget(pk=child.pk)

        result = await TestModelSerializerForeignKey.amodel_dump(unloaded)
        many = await TestModelSerializerForeignKey.amodel_dumps(
            TestModelSerializerForeignKey.objects.filter(pk=child.pk)
        )

        self.assertEqual(result["test_model_serializer"]["name"], parent.name)
        self.assertEqual(many[0]["test_model_serializer"]["name"], parent.name)

        overridden = await TestModelWithSchemaOverrides.objects.acreate(
            **self.create_data("override")
        )
        self.assertEqual(
            (
                await TestModelWithSchemaOverrides.amodel_dump(
                    overridden, schema=TestModelWithSchemaOverrides.read_schema
                )
            )["name"],
            overridden.name.upper(),
        )

    async def test_amodel_dumps_accepts_loaded_instances_with_custom_schema(
        self,
    ) -> None:
        class CustomSchema(Schema):
            name: str
            extra: int = 7

        instance = await self.serializer_class.acreate(self.create_data("custom"))

        result = await self.serializer_class.amodel_dumps(
            [instance], schema=CustomSchema
        )

        self.assertEqual(result, [{"name": instance.name, "extra": 7}])

    async def test_amodel_dump_prefetches_reverse_relation(self) -> None:
        parent = await TestModelSerializerReverseForeignKey.objects.acreate(
            **self.create_data("reverse")
        )
        await TestModelSerializerForeignKey.objects.acreate(
            **self.create_data("child"), test_model_serializer=parent
        )
        unloaded = await TestModelSerializerReverseForeignKey.objects.aget(pk=parent.pk)

        result = await TestModelSerializerReverseForeignKey.amodel_dump(unloaded)

        self.assertEqual(len(result["test_model_serializer_foreign_keys"]), 1)


class StandaloneSerializerAsyncCrudFacadeTests(
    AsyncCrudFacadeContractMixin,
    TestCase,
):
    serializer_class = TestModelWithValidatorsMetaSerializer
    model_class = TestModel

    def test_instance_create_is_synchronous(self) -> None:
        serializer = self.serializer_class()

        obj = serializer.create(self.create_data("instance"))

        self.assertIsInstance(obj, self.model_class)
        self.assertIsNotNone(obj.pk)

    async def test_acreate_requires_a_configured_schema(self) -> None:
        with self.assertRaisesRegex(ImproperlyConfigured, "create schema"):
            await BookAsIdMetaSerializer.acreate({"name": "book"})

    async def test_amodel_dump_and_amodel_dumps(self) -> None:
        instance = await self.serializer_class.acreate(self.create_data("dump"))

        single = await self.serializer_class.amodel_dump(instance)
        many = await self.serializer_class.amodel_dumps(
            self.model_class.objects.filter(pk=instance.pk)
        )

        self.assertEqual(single["name"], instance.name)
        self.assertEqual(many[0]["name"], instance.name)

    async def test_amodel_dump_loads_standalone_fk(self) -> None:
        parent = await TestModelReverseForeignKey.objects.acreate(
            **self.create_data("parent")
        )
        child = await TestModelForeignKey.objects.acreate(
            **self.create_data("child"), test_model=parent
        )
        unloaded = await TestModelForeignKey.objects.aget(pk=child.pk)

        result = await TestModelForeignKeySerializer.amodel_dump(unloaded)

        self.assertEqual(result["test_model"]["name"], parent.name)
