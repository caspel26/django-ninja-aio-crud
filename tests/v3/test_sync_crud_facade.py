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


class SyncCrudFacadeContractMixin:
    serializer_class: type
    model_class: type[models.Model]

    def create_data(self, suffix: str) -> dict[str, Any]:
        return {"name": f"name-{suffix}", "description": f"description-{suffix}"}

    def assert_sync_signature(self, method_name: str) -> None:
        method = getattr(self.serializer_class, method_name)
        signature = inspect.signature(method)
        hints = get_type_hints(method)

        self.assertFalse(inspect.iscoroutinefunction(method))
        self.assertIn("return", hints)
        self.assertIsNot(hints["return"], Any)
        self.assertEqual(
            signature.parameters["request"].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertIsNone(signature.parameters["request"].default)

    def test_sync_crud_methods_have_typed_keyword_only_request(self) -> None:
        for method_name in ("create", "get", "update", "destroy"):
            with self.subTest(method=method_name):
                self.assert_sync_signature(method_name)

    def test_create_accepts_dict_and_generated_schema(self) -> None:
        from_dict = self.serializer_class.create(self.create_data("dict"))
        create_schema = self.serializer_class.create_schema
        self.assertIsNotNone(create_schema)
        from_schema = self.serializer_class.create(
            create_schema(**self.create_data("schema"))
        )

        self.assertIsInstance(from_dict, self.model_class)
        self.assertIsInstance(from_schema, self.model_class)
        self.assertIsNotNone(from_dict.pk)
        self.assertIsNotNone(from_schema.pk)

    def test_create_validates_direct_input(self) -> None:
        with self.assertRaises(ValidationError):
            self.serializer_class.create({"name": "missing-description"})

    def test_get_supports_exactly_one_lookup_strategy(self) -> None:
        obj = self.serializer_class.create(self.create_data("get"))

        self.assertEqual(self.serializer_class.get(obj.pk), obj)
        self.assertEqual(self.serializer_class.get(name=obj.name), obj)

        with self.assertRaisesRegex(ValueError, "Exactly one"):
            self.serializer_class.get()
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            self.serializer_class.get(obj.pk, name=obj.name)
        with self.assertRaises(NotFoundError):
            self.serializer_class.get(999_999)

    def test_update_with_instance_skips_lookup_and_returns_instance(self) -> None:
        obj = self.serializer_class.create(self.create_data("instance-update"))

        with mock.patch.object(
            self.serializer_class.util,
            "get_object",
            side_effect=AssertionError("loaded instances must not be refetched"),
        ):
            updated = self.serializer_class.update(
                obj,
                {"description": "updated-instance"},
            )

        self.assertIs(updated, obj)
        self.assertEqual(updated.description, "updated-instance")
        self.assertEqual(
            self.model_class.objects.filter(pk=obj.pk)
            .values_list("description", flat=True)
            .get(),
            "updated-instance",
        )

    def test_destroy_with_instance_skips_lookup_and_returns_none(self) -> None:
        obj = self.serializer_class.create(self.create_data("instance-destroy"))

        with mock.patch.object(
            self.serializer_class.util,
            "get_object",
            side_effect=AssertionError("loaded instances must not be refetched"),
        ):
            result = self.serializer_class.destroy(obj)

        self.assertIsNone(result)
        self.assertFalse(self.model_class.objects.filter(pk=obj.pk).exists())

    def test_mutations_reject_an_unsaved_instance(self) -> None:
        unsaved = self.model_class(**self.create_data("unsaved"))

        with self.assertRaisesRegex(ValueError, "persisted model instance"):
            self.serializer_class.update(unsaved, {"description": "not-saved"})
        with self.assertRaisesRegex(ValueError, "persisted model instance"):
            self.serializer_class.destroy(unsaved)


class ModelSerializerSyncCrudFacadeTests(SyncCrudFacadeContractMixin, TestCase):
    serializer_class = TestModelSerializer
    model_class = TestModelSerializer


class StandaloneSerializerSyncCrudFacadeTests(SyncCrudFacadeContractMixin, TestCase):
    serializer_class = TestModelWithValidatorsMetaSerializer
    model_class = TestModel

    def test_create_requires_a_configured_schema(self) -> None:
        with self.assertRaisesRegex(ImproperlyConfigured, "create schema"):
            BookAsIdMetaSerializer.create({"name": "book"})
