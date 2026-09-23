from typing import ClassVar, get_type_hints
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from ninja import Schema

from ninja_aio.models.serializers import BaseSerializer, SchemaKind
from tests.test_app.models import TestModelSerializer
from tests.test_app.serializers import TestModelForeignKeySerializer


class CustomDetailSchema(Schema):
    id: int


class ExplicitSchemaSerializer(BaseSerializer):
    detail_schema: ClassVar[type[Schema] | None] = CustomDetailSchema


class EmptySchemaSerializer(BaseSerializer):
    detail_schema: ClassVar[type[Schema] | None] = None


class InvalidSchemaSerializer(BaseSerializer):
    detail_schema = "not-a-schema"  # type: ignore[assignment]


class LazySchemaAttributeTests(SimpleTestCase):
    serializer_classes = (
        TestModelSerializer,
        TestModelForeignKeySerializer,
    )

    def test_default_attributes_match_version_2_factories(self) -> None:
        mappings = (
            ("create_schema", "generate_create_s"),
            ("update_schema", "generate_update_s"),
            ("read_schema", "generate_read_s"),
            ("detail_schema", "generate_detail_s"),
            ("related_schema", "generate_related_s"),
        )
        for serializer_class in self.serializer_classes:
            for attribute, factory in mappings:
                with self.subTest(
                    serializer=serializer_class.__name__,
                    attribute=attribute,
                ):
                    self.assertIs(
                        getattr(serializer_class, attribute),
                        getattr(serializer_class, factory)(),
                    )

    def test_attribute_generation_is_lazy_and_cached(self) -> None:
        TestModelSerializer.clear_schema_cache()
        original = TestModelSerializer._generate_model_schema
        with patch.object(
            TestModelSerializer,
            "_generate_model_schema",
            side_effect=original,
        ) as generate:
            first = TestModelSerializer.read_schema
            second = TestModelSerializer.read_schema

        self.assertIs(first, second)
        generate.assert_called_once_with("Out", 1)

    def test_get_schema_supports_depth_for_read_and_detail(self) -> None:
        for kind, factory_name in (
            ("read", "generate_read_s"),
            ("detail", "generate_detail_s"),
        ):
            with self.subTest(kind=kind):
                schema = TestModelSerializer.get_schema(kind, depth=0)
                expected = getattr(TestModelSerializer, factory_name)(0)
                self.assertIs(schema, expected)

    def test_get_schema_rejects_unknown_kind(self) -> None:
        with self.assertRaisesMessage(ValueError, "Unknown schema kind"):
            TestModelSerializer.get_schema("unknown")  # type: ignore[arg-type]

    def test_get_schema_rejects_invalid_depth(self) -> None:
        invalid_depths = (-1, True, 1.5, "1")
        for depth in invalid_depths:
            with self.subTest(depth=depth):
                with self.assertRaisesMessage(
                    ValueError,
                    "Schema depth must be a non-negative integer",
                ):
                    TestModelSerializer.get_schema(
                        "read",
                        depth=depth,  # type: ignore[arg-type]
                    )

    def test_non_relational_schema_rejects_custom_depth(self) -> None:
        with self.assertRaisesMessage(ValueError, "does not support custom depth"):
            TestModelSerializer.get_schema("create", depth=2)

    def test_explicit_schema_override_is_returned(self) -> None:
        self.assertIs(ExplicitSchemaSerializer.detail_schema, CustomDetailSchema)
        self.assertIs(
            ExplicitSchemaSerializer.get_schema("detail"),
            CustomDetailSchema,
        )

    def test_explicit_none_disables_schema(self) -> None:
        self.assertIsNone(EmptySchemaSerializer.detail_schema)
        self.assertIsNone(EmptySchemaSerializer.get_schema("detail"))

    def test_invalid_override_raises_configuration_error(self) -> None:
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "must be a Schema subclass or None",
        ):
            InvalidSchemaSerializer.get_schema("detail")

    def test_clear_schema_cache_forces_regeneration(self) -> None:
        TestModelSerializer.clear_schema_cache()
        original = TestModelSerializer._generate_model_schema
        with patch.object(
            TestModelSerializer,
            "_generate_model_schema",
            side_effect=original,
        ) as generate:
            first = TestModelSerializer.read_schema
            cached = TestModelSerializer.read_schema
            TestModelSerializer.clear_schema_cache()
            regenerated = TestModelSerializer.read_schema

        self.assertIs(first, cached)
        self.assertIsNotNone(regenerated)
        self.assertEqual(generate.call_count, 2)

    def test_clear_schema_cache_does_not_invalidate_other_serializers(self) -> None:
        standalone_schema = TestModelForeignKeySerializer.read_schema
        TestModelSerializer.clear_schema_cache()
        self.assertIs(
            TestModelForeignKeySerializer.read_schema,
            standalone_schema,
        )

    def test_public_schema_api_has_precise_return_annotations(self) -> None:
        class_hints = get_type_hints(BaseSerializer)
        get_schema_hints = get_type_hints(BaseSerializer.get_schema)
        clear_cache_hints = get_type_hints(BaseSerializer.clear_schema_cache)

        for attribute in (
            "create_schema",
            "update_schema",
            "read_schema",
            "detail_schema",
            "related_schema",
        ):
            with self.subTest(attribute=attribute):
                self.assertEqual(
                    class_hints[attribute],
                    ClassVar[type[Schema] | None],
                )
        self.assertEqual(
            get_schema_hints["kind"],
            SchemaKind,
        )
        self.assertIs(get_schema_hints["depth"], int)
        self.assertEqual(
            get_schema_hints["return"],
            type[Schema] | None,
        )
        self.assertIs(clear_cache_hints["return"], type(None))
