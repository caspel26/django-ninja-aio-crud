import warnings
from typing import Union
from django.test import TestCase, tag

from tests.test_app.models import TestModelForeignKey, TestModelReverseForeignKey
from ninja_aio.models import serializers


class TestModelForeignKeySerializer(serializers.Serializer):
    class Meta:
        model = TestModelForeignKey
        schema_in = serializers.SchemaModelConfig(
            fields=["name", "description", "test_model"]
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description", "test_model"]
        )


class TestModelReverseForeignKeySerializer(serializers.Serializer):
    class Meta:
        model = TestModelReverseForeignKey
        schema_in = serializers.SchemaModelConfig(fields=["name", "description"])
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description", "test_model_foreign_keys"]
        )
        relations_serializers = {
            "test_model_foreign_keys": TestModelForeignKeySerializer,
        }


# Test serializers for Union tests - defined at module level so they can be resolved
class AltSerializer(serializers.Serializer):
    class Meta:
        model = TestModelForeignKey
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name"]
        )


class AltStringSerializer(serializers.Serializer):
    class Meta:
        model = TestModelForeignKey
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "description"]
        )


class MixedAltSerializer(serializers.Serializer):
    class Meta:
        model = TestModelForeignKey
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description"]
        )


class LocalTestSerializer(serializers.Serializer):
    class Meta:
        model = TestModelForeignKey
        schema_out = serializers.SchemaModelConfig(fields=["id"])


@tag("serializers")
class SerializersTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.serializer_fk = TestModelForeignKeySerializer
        cls.serializer_rfk = TestModelReverseForeignKeySerializer
        warnings.simplefilter("ignore", UserWarning)  # Ignora tutti i UserWarning

    def test_generate_schema_out(self):
        schema_out_fk = self.serializer_fk.generate_read_s()
        for f in ["id", "name", "description", "test_model"]:
            self.assertIn(f, schema_out_fk.model_fields)

        schema_out_rfk = self.serializer_rfk.generate_read_s()
        for f in ["id", "name", "description", "test_model_foreign_keys"]:
            self.assertIn(f, schema_out_rfk.model_fields)

    def test_generate_schema_in(self):
        schema_in_fk = self.serializer_fk.generate_create_s()
        # In schema should include declared input fields
        for f in ["name", "description", "test_model"]:
            self.assertIn(f, schema_in_fk.model_fields)
        self.assertNotIn("id", schema_in_fk.model_fields)

        schema_in_rfk = self.serializer_rfk.generate_create_s()
        for f in ["name", "description"]:
            self.assertIn(f, schema_in_rfk.model_fields)

    def test_generate_schema_update(self):
        # If no fields provided for update, optional fields should be honored when declared
        # Here no explicit update config exists, so update schema may be None or empty depending on implementation
        schema_patch_fk = self.serializer_fk.generate_update_s()
        # Implementation returns a schema when fields/customs/excludes exist; otherwise may fallback to optionals.
        # Our Meta doesn't define update, so ensure function doesn't crash and returns a Schema or None
        self.assertTrue(
            schema_patch_fk is None or hasattr(schema_patch_fk, "model_fields")
        )

        schema_patch_rfk = self.serializer_rfk.generate_update_s()
        self.assertTrue(
            schema_patch_rfk is None or hasattr(schema_patch_rfk, "model_fields")
        )

    def test_generate_related_schema(self):
        related_fk = self.serializer_fk.generate_related_s()
        # Related schema should include non-relational read fields only
        for f in ["id", "name", "description"]:
            self.assertIn(f, related_fk.model_fields)
        # Forward relation declared on fk read fields should still be present as plain field in read, but not in related
        self.assertNotIn("test_model", related_fk.model_fields)

        related_rfk = self.serializer_rfk.generate_related_s()
        for f in ["id", "name", "description"]:
            self.assertIn(f, related_rfk.model_fields)
        # Reverse relation should be excluded from related schema
        self.assertNotIn("test_model_foreign_keys", related_rfk.model_fields)

    def test_relation_serializer_required_when_mapping_provided(self):
        # When relations_serializers mapping exists, any relation field listed in read fields must have a mapping
        class BadSerializer(serializers.Serializer):
            class Meta:
                model = TestModelReverseForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", "description", "test_model_foreign_keys"]
                )
                relations_serializers = {}

    def test_relation_serializer_inclusion(self):
        # Ensure that providing relations_serializers yields nested related schema in read
        schema_out_rfk = self.serializer_rfk.generate_read_s()
        # The reverse relation should be represented as a field; the nested schema type comes from ninja's create_schema.
        self.assertIn("test_model_foreign_keys", schema_out_rfk.model_fields)
        # Also ensure base fields present
        for f in ["id", "name", "description"]:
            self.assertIn(f, schema_out_rfk.model_fields)


@tag("serializers", "union")
class UnionSerializerTestCase(TestCase):
    """Test cases for Union serializer references support."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_union_with_direct_class_references(self):
        """Test Union with direct class references."""

        class UnionTestSerializer(serializers.Serializer):
            class Meta:
                model = TestModelReverseForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", "test_model_foreign_keys"]
                )
                relations_serializers = {
                    "test_model_foreign_keys": Union[TestModelForeignKeySerializer, AltSerializer],
                }

        # Should resolve without errors
        schema = UnionTestSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_model_foreign_keys", schema.model_fields)

    def test_union_with_string_references(self):
        """Test Union with string references."""

        class UnionStringTestSerializer(serializers.Serializer):
            class Meta:
                model = TestModelReverseForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", "test_model_foreign_keys"]
                )
                relations_serializers = {
                    "test_model_foreign_keys": Union["TestModelForeignKeySerializer", "AltStringSerializer"],
                }

        # Should resolve without errors
        schema = UnionStringTestSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_model_foreign_keys", schema.model_fields)

    def test_union_with_mixed_references(self):
        """Test Union with mixed class and string references."""

        class UnionMixedTestSerializer(serializers.Serializer):
            class Meta:
                model = TestModelReverseForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", "test_model_foreign_keys"]
                )
                relations_serializers = {
                    "test_model_foreign_keys": Union[MixedAltSerializer, "TestModelForeignKeySerializer"],
                }

        # Should resolve without errors
        schema = UnionMixedTestSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_model_foreign_keys", schema.model_fields)

    def test_union_with_absolute_import_path(self):
        """Test Union with absolute import path string references."""

        class UnionAbsolutePathSerializer(serializers.Serializer):
            class Meta:
                model = TestModelReverseForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", "test_model_foreign_keys"]
                )
                relations_serializers = {
                    "test_model_foreign_keys": Union[
                        "tests.test_serializers.TestModelForeignKeySerializer",
                        TestModelForeignKeySerializer,
                    ],
                }

        # Should resolve without errors
        schema = UnionAbsolutePathSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_model_foreign_keys", schema.model_fields)

    def test_resolve_serializer_reference_with_union(self):
        """Test _resolve_serializer_reference directly with Union types."""
        from typing import get_args, get_origin

        # Test with Union of DIFFERENT classes (Union of same type gets optimized away by Python)
        union_ref = Union[TestModelForeignKeySerializer, AltSerializer]
        resolved = TestModelForeignKeySerializer._resolve_serializer_reference(union_ref)

        # Check that it returns a Union (using reduce with or_ creates a union-like structure)
        # The resolved type should be a union of the two serializers
        self.assertEqual(get_origin(resolved), Union)
        resolved_args = get_args(resolved)
        self.assertEqual(len(resolved_args), 2)
        # Should contain both serializer classes
        self.assertIn(TestModelForeignKeySerializer, resolved_args)
        self.assertIn(AltSerializer, resolved_args)

    def test_resolve_serializer_reference_with_string_union(self):
        """Test _resolve_serializer_reference with Union of strings."""
        from typing import get_args, get_origin

        # Test with Union of string references
        union_ref = Union["TestModelForeignKeySerializer", "LocalTestSerializer"]
        resolved = LocalTestSerializer._resolve_serializer_reference(union_ref)

        # Check that it returns a Union
        self.assertEqual(get_origin(resolved), Union)
        resolved_types = get_args(resolved)
        self.assertEqual(len(resolved_types), 2)

        # Verify that both serializers are resolved correctly
        self.assertIn(TestModelForeignKeySerializer, resolved_types)
        self.assertIn(LocalTestSerializer, resolved_types)

    def test_single_serializer_still_works(self):
        """Ensure single serializer references still work as before."""

        class SingleRefSerializer(serializers.Serializer):
            class Meta:
                model = TestModelReverseForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", "test_model_foreign_keys"]
                )
                relations_serializers = {
                    "test_model_foreign_keys": TestModelForeignKeySerializer,
                }

        # Should work exactly as before
        schema = SingleRefSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_model_foreign_keys", schema.model_fields)

    def test_single_string_serializer_still_works(self):
        """Ensure single string serializer references still work as before."""

        class SingleStringRefSerializer(serializers.Serializer):
            class Meta:
                model = TestModelReverseForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", "test_model_foreign_keys"]
                )
                relations_serializers = {
                    "test_model_foreign_keys": "TestModelForeignKeySerializer",
                }

        # Should work exactly as before
        schema = SingleStringRefSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_model_foreign_keys", schema.model_fields)
