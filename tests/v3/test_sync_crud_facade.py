import inspect
from typing import Any, get_type_hints
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.test import TestCase
from ninja import Schema
from pydantic import ValidationError

from ninja_aio.exceptions import NotFoundError
from tests.test_app.models import (
    BookAsId,
    TestModel,
    TestModelForeignKey,
    TestModelReverseForeignKey,
    TestModelSerializer,
    TestModelSerializerForeignKey,
    TestModelSerializerReverseForeignKey,
)
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

    def test_bulk_create_keeps_valid_rows_after_validation_failure(self) -> None:
        successes, errors = self.serializer_class.bulk_create(
            [
                self.create_data("first"),
                {"name": "missing-description"},
                self.create_data("last"),
            ]
        )
        self.assertEqual([obj.name for obj in successes], ["name-first", "name-last"])
        self.assertEqual(len(errors), 1)
        self.assertEqual(self.model_class.objects.count(), 2)

    def test_bulk_update_and_destroy_preserve_partial_success(self) -> None:
        first = self.serializer_class.create(self.create_data("first"))
        second = self.serializer_class.create(self.create_data("second"))
        updated, errors = self.serializer_class.bulk_update(
            [
                {"id": first.pk, "description": "changed"},
                {"id": 999_999, "description": "missing"},
                (second, {"description": "also changed"}),
            ]
        )
        self.assertEqual([obj.pk for obj in updated], [first.pk, second.pk])
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            self.model_class.objects.get(pk=first.pk).description, "changed"
        )

        expected_pks = [first.pk, second.pk]
        destroyed, errors = self.serializer_class.bulk_destroy(
            [first, 999_999, second.pk]
        )
        self.assertEqual(destroyed, expected_pks)
        self.assertEqual(len(errors), 1)
        self.assertFalse(self.model_class.objects.exists())

    async def test_async_bulk_partial_success(self) -> None:
        created, errors = await self.serializer_class.abulk_create(
            [self.create_data("first"), {"name": "invalid"}, self.create_data("last")]
        )
        self.assertEqual([obj.name for obj in created], ["name-first", "name-last"])
        self.assertEqual(len(errors), 1)
        updated, errors = await self.serializer_class.abulk_update(
            [
                {"id": created[0].pk, "description": "changed"},
                {"id": 999_999, "description": "missing"},
                (created[1], {"description": "also changed"}),
            ]
        )
        self.assertEqual([obj.pk for obj in updated], [obj.pk for obj in created])
        self.assertEqual(len(errors), 1)
        expected_pks = [obj.pk for obj in created]
        destroyed, errors = await self.serializer_class.abulk_destroy(
            [created[0], 999_999, created[1].pk]
        )
        self.assertEqual(destroyed, expected_pks)
        self.assertEqual(len(errors), 1)
        self.assertFalse(await self.model_class.objects.aexists())

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

    def test_model_dump_serializes_without_queries(self) -> None:
        instance = self.serializer_class.create(self.create_data("dump"))

        with self.assertNumQueries(0):
            result = self.serializer_class.model_dump(instance)

        self.assertEqual(result["name"], instance.name)

    def test_model_dump_uses_explicit_schema_with_custom_field(self) -> None:
        class CustomSchema(Schema):
            name: str
            extra: int = 7

        instance = self.serializer_class.create(self.create_data("custom"))

        with self.assertNumQueries(0):
            result = self.serializer_class.model_dump(instance, schema=CustomSchema)

        self.assertEqual(result, {"name": instance.name, "extra": 7})

    def test_model_dump_requires_a_schema(self) -> None:
        instance = self.serializer_class.create(self.create_data("missing-schema"))

        with mock.patch.object(self.serializer_class, "get_schema", return_value=None):
            with self.assertRaisesRegex(ImproperlyConfigured, "detail schema"):
                self.serializer_class.model_dump(instance)

    def test_model_dump_rejects_schema_queries(self) -> None:
        class QueryingSchema(self.serializer_class.read_schema):
            def model_dump(self, **kwargs):
                TestModelSerializer.objects.count()
                return super().model_dump(**kwargs)

        instance = self.serializer_class.create(self.create_data("querying"))

        with self.assertRaisesRegex(ValueError, "preloaded fields and relations"):
            self.serializer_class.model_dump(instance, schema=QueryingSchema)

    def test_model_dumps_requires_evaluated_queryset(self) -> None:
        instance = self.serializer_class.create(self.create_data("list"))

        with self.assertRaisesRegex(ValueError, "evaluated queryset"):
            self.serializer_class.model_dumps(self.model_class.objects.all())

        queryset = self.model_class.objects.filter(pk=instance.pk)
        list(queryset)
        with self.assertNumQueries(0):
            result = self.serializer_class.model_dumps(queryset)

        self.assertEqual([item["name"] for item in result], [instance.name])

    def test_model_dump_rejects_deferred_fields_without_querying(self) -> None:
        instance = self.serializer_class.create(self.create_data("deferred"))
        deferred = self.model_class.objects.only("id").get(pk=instance.pk)

        with (
            self.assertNumQueries(0),
            self.assertRaisesRegex(ValueError, "preloaded fields and relations"),
        ):
            self.serializer_class.model_dump(deferred)

    def test_model_dump_rejects_unloaded_relation_without_querying(self) -> None:
        parent = TestModelSerializerReverseForeignKey.objects.create(
            **self.create_data("parent")
        )
        TestModelSerializerForeignKey.objects.create(
            **self.create_data("child"), test_model_serializer=parent
        )
        child = TestModelSerializerForeignKey.objects.get(name="name-child")

        with (
            self.assertNumQueries(0),
            self.assertRaisesRegex(ValueError, "preloaded fields and relations"),
        ):
            TestModelSerializerForeignKey.model_dump(child)

        loaded = TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).get(pk=child.pk)
        with self.assertNumQueries(0):
            result = TestModelSerializerForeignKey.model_dump(loaded)

        self.assertEqual(result["test_model_serializer"]["name"], parent.name)

    def test_model_dump_requires_prefetched_reverse_relation(self) -> None:
        parent = TestModelSerializerReverseForeignKey.objects.create(
            **self.create_data("reverse")
        )
        TestModelSerializerForeignKey.objects.create(
            **self.create_data("child"), test_model_serializer=parent
        )

        with (
            self.assertNumQueries(0),
            self.assertRaisesRegex(ValueError, "preloaded fields and relations"),
        ):
            TestModelSerializerReverseForeignKey.model_dump(parent)

        loaded = TestModelSerializerReverseForeignKey.objects.prefetch_related(
            "test_model_serializer_foreign_keys"
        ).get(pk=parent.pk)
        with self.assertNumQueries(0):
            result = TestModelSerializerReverseForeignKey.model_dump(loaded)

        self.assertEqual(len(result["test_model_serializer_foreign_keys"]), 1)

    def test_model_dump_allows_null_relation_without_query(self) -> None:
        instance = BookAsId.objects.create(**self.create_data("no-author"))

        with self.assertNumQueries(0):
            result = BookAsId.model_dump(instance)

        self.assertIsNone(result["author_as_id"])


class StandaloneSerializerSyncCrudFacadeTests(SyncCrudFacadeContractMixin, TestCase):
    serializer_class = TestModelWithValidatorsMetaSerializer
    model_class = TestModel

    def test_create_requires_a_configured_schema(self) -> None:
        with self.assertRaisesRegex(ImproperlyConfigured, "create schema"):
            BookAsIdMetaSerializer.create({"name": "book"})

    def test_model_dump_and_model_dumps_use_loaded_instances(self) -> None:
        instance = self.serializer_class.create(self.create_data("dump"))

        with self.assertNumQueries(0):
            single = self.serializer_class.model_dump(instance)
            many = self.serializer_class.model_dumps([instance])

        self.assertEqual(single["name"], instance.name)
        self.assertEqual(many, [single])

    def test_relations_as_id_requires_loaded_fk(self) -> None:
        parent = TestModelReverseForeignKey.objects.create(**self.create_data("parent"))
        child = TestModelForeignKey.objects.create(
            **self.create_data("child"), test_model=parent
        )
        unloaded = TestModelForeignKey.objects.get(pk=child.pk)

        with (
            self.assertNumQueries(0),
            self.assertRaisesRegex(ValueError, "preloaded fields and relations"),
        ):
            BookAsIdMetaSerializer.model_dump(unloaded)

        loaded = TestModelForeignKey.objects.select_related("test_model").get(
            pk=child.pk
        )
        with self.assertNumQueries(0):
            result = BookAsIdMetaSerializer.model_dump(loaded)

        self.assertEqual(result["test_model"], parent.pk)
