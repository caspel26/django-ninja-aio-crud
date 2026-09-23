import inspect
from typing import Any, get_type_hints
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.test import TestCase
from pydantic import ValidationError

from ninja_aio.exceptions import NotFoundError
from tests.test_app.models import TestModel, TestModelSerializer
from tests.test_app.serializers import (
    BookAsIdMetaSerializer,
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
        with self.assertRaises(ValidationError):
            await self.serializer_class.acreate({"name": "missing-description"})

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
            self.serializer_class.util,
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
            self.serializer_class.util,
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


class StandaloneSerializerAsyncCrudFacadeTests(
    AsyncCrudFacadeContractMixin,
    TestCase,
):
    serializer_class = TestModelWithValidatorsMetaSerializer
    model_class = TestModel

    async def test_v2_instance_create_remains_available(self) -> None:
        serializer = self.serializer_class()

        obj = await serializer.create(self.create_data("legacy"))

        self.assertIsInstance(obj, self.model_class)
        self.assertIsNotNone(obj.pk)

    async def test_acreate_requires_a_configured_schema(self) -> None:
        with self.assertRaisesRegex(ImproperlyConfigured, "create schema"):
            await BookAsIdMetaSerializer.acreate({"name": "book"})
