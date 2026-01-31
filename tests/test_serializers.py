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


@tag("serializers", "detail")
class DetailSerializerTestCase(TestCase):
    """Test cases for Detail schema generation support."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_detail_fallback_customs_from_read(self):
        """Test that detail schema falls back to read customs when not configured."""

        class DetailFallbackCustomsSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name"],
                    customs=[("read_custom", str, "default")],
                )
                # No schema_detail defined - should fall back to schema_out

        # Detail should inherit customs from read schema
        schema_detail = DetailFallbackCustomsSerializer.generate_detail_s()
        self.assertIsNotNone(schema_detail)
        self.assertIn("id", schema_detail.model_fields)
        self.assertIn("name", schema_detail.model_fields)
        self.assertIn("read_custom", schema_detail.model_fields)

    def test_detail_fallback_optionals_from_read(self):
        """Test that detail schema falls back to read optionals when not configured."""

        class DetailFallbackOptionalsSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name"],
                    optionals=[("description", str)],
                )
                # No schema_detail defined - should fall back to schema_out

        # Detail should inherit optionals from read schema
        schema_detail = DetailFallbackOptionalsSerializer.generate_detail_s()
        self.assertIsNotNone(schema_detail)
        self.assertIn("id", schema_detail.model_fields)
        self.assertIn("name", schema_detail.model_fields)
        self.assertIn("description", schema_detail.model_fields)

    def test_detail_fallback_excludes_from_read(self):
        """Test that detail schema falls back to read excludes when not configured."""

        class DetailFallbackExcludesSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name"],
                    exclude=["test_model"],  # Exclude forward relation
                )
                # No schema_detail defined - should fall back to schema_out

        # Detail should inherit excludes from read schema
        schema_detail = DetailFallbackExcludesSerializer.generate_detail_s()
        read_schema = DetailFallbackExcludesSerializer.generate_read_s()
        self.assertIsNotNone(schema_detail)
        # Both should have the same excludes applied
        self.assertEqual(
            set(schema_detail.model_fields.keys()),
            set(read_schema.model_fields.keys()),
        )

    def test_detail_does_not_inherit_when_defined(self):
        """Test that detail does NOT inherit from read when schema_detail is defined."""

        class DetailDoesNotInheritSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name"],
                    customs=[("read_custom", str, "default")],
                )
                schema_detail = serializers.SchemaModelConfig(
                    fields=["id", "name", "description"],
                    # No customs defined - does NOT inherit from read
                    # because schema_detail is defined (fallback is at schema level)
                )

        # Read schema should have the custom
        schema_read = DetailDoesNotInheritSerializer.generate_read_s()
        self.assertIn("read_custom", schema_read.model_fields)

        # Detail schema does NOT inherit customs from read because schema_detail is defined
        # (Serializer fallback is at the schema level, not per-field-type)
        schema_detail = DetailDoesNotInheritSerializer.generate_detail_s()
        self.assertIn("id", schema_detail.model_fields)
        self.assertIn("name", schema_detail.model_fields)
        self.assertIn("description", schema_detail.model_fields)
        self.assertNotIn("read_custom", schema_detail.model_fields)

    def test_generate_detail_schema_with_serializer(self):
        """Test generate_detail_s() with Serializer class."""

        class DetailTestSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name"]
                )
                schema_detail = serializers.SchemaModelConfig(
                    fields=["id", "name", "description", "test_model"]
                )

        # Out schema should have fewer fields
        schema_out = DetailTestSerializer.generate_read_s()
        self.assertIsNotNone(schema_out)
        self.assertIn("id", schema_out.model_fields)
        self.assertIn("name", schema_out.model_fields)
        self.assertNotIn("description", schema_out.model_fields)

        # Detail schema should have more fields
        schema_detail = DetailTestSerializer.generate_detail_s()
        self.assertIsNotNone(schema_detail)
        self.assertIn("id", schema_detail.model_fields)
        self.assertIn("name", schema_detail.model_fields)
        self.assertIn("description", schema_detail.model_fields)
        self.assertIn("test_model", schema_detail.model_fields)

    def test_generate_detail_schema_falls_back_to_read_when_not_configured(self):
        """Test generate_detail_s() falls back to read schema when no detail config."""

        class NoDetailSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name"]
                )

        # Detail schema should fall back to read schema when not configured
        schema_detail = NoDetailSerializer.generate_detail_s()
        schema_out = NoDetailSerializer.generate_read_s()
        self.assertIsNotNone(schema_detail)
        # Both should have the same fields since detail falls back to read
        self.assertEqual(
            set(schema_detail.model_fields.keys()),
            set(schema_out.model_fields.keys()),
        )

    def test_detail_schema_with_relations(self):
        """Test detail schema includes relation serializers."""

        class DetailWithRelationsSerializer(serializers.Serializer):
            class Meta:
                model = TestModelReverseForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name"]
                )
                schema_detail = serializers.SchemaModelConfig(
                    fields=["id", "name", "description", "test_model_foreign_keys"]
                )
                relations_serializers = {
                    "test_model_foreign_keys": TestModelForeignKeySerializer,
                }

        # Out schema should be minimal
        schema_out = DetailWithRelationsSerializer.generate_read_s()
        self.assertIn("id", schema_out.model_fields)
        self.assertIn("name", schema_out.model_fields)
        self.assertNotIn("test_model_foreign_keys", schema_out.model_fields)

        # Detail schema should include relations
        schema_detail = DetailWithRelationsSerializer.generate_detail_s()
        self.assertIsNotNone(schema_detail)
        self.assertIn("id", schema_detail.model_fields)
        self.assertIn("name", schema_detail.model_fields)
        self.assertIn("description", schema_detail.model_fields)
        self.assertIn("test_model_foreign_keys", schema_detail.model_fields)

    def test_detail_schema_with_custom_fields(self):
        """Test detail schema supports custom fields."""

        class DetailWithCustomsSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name"]
                )
                schema_detail = serializers.SchemaModelConfig(
                    fields=["id", "name", "description"],
                    customs=[("extra_info", str, "default_value")],
                )

        schema_detail = DetailWithCustomsSerializer.generate_detail_s()
        self.assertIsNotNone(schema_detail)
        self.assertIn("id", schema_detail.model_fields)
        self.assertIn("name", schema_detail.model_fields)
        self.assertIn("description", schema_detail.model_fields)
        self.assertIn("extra_info", schema_detail.model_fields)

    def test_detail_schema_with_optionals(self):
        """Test detail schema supports optional fields."""

        class DetailWithOptionalsSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name"]
                )
                schema_detail = serializers.SchemaModelConfig(
                    fields=["id", "name"],
                    optionals=[("description", str)],
                )

        schema_detail = DetailWithOptionalsSerializer.generate_detail_s()
        self.assertIsNotNone(schema_detail)
        self.assertIn("id", schema_detail.model_fields)
        self.assertIn("name", schema_detail.model_fields)
        self.assertIn("description", schema_detail.model_fields)


@tag("serializers", "detail", "model_serializer")
class ModelSerializerDetailFallbackTestCase(TestCase):
    """Test cases for ModelSerializer detail->read fallback behavior."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_model_serializer_detail_fallback_fields(self):
        """Test ModelSerializer detail falls back to read fields when not configured."""
        from tests.test_app.models import TestModelSerializer

        # TestModelSerializer has ReadSerializer with fields but no DetailSerializer
        read_fields = TestModelSerializer.get_fields("read")
        detail_fields = TestModelSerializer.get_fields("detail")

        # Detail should fall back to read fields
        self.assertEqual(read_fields, detail_fields)

    def test_model_serializer_detail_fallback_customs(self):
        """Test ModelSerializer detail falls back to read customs when not configured."""
        from tests.test_app.models import TestModelSerializerWithReadCustoms

        read_customs = TestModelSerializerWithReadCustoms.get_custom_fields("read")
        detail_customs = TestModelSerializerWithReadCustoms.get_custom_fields("detail")

        # Detail should fall back to read customs
        self.assertEqual(read_customs, detail_customs)
        self.assertEqual(len(detail_customs), 1)
        self.assertEqual(detail_customs[0][0], "custom_field")

    def test_model_serializer_detail_fallback_optionals(self):
        """Test ModelSerializer detail falls back to read optionals when not configured."""
        from tests.test_app.models import TestModelSerializerWithReadOptionals

        read_optionals = TestModelSerializerWithReadOptionals.get_optional_fields("read")
        detail_optionals = TestModelSerializerWithReadOptionals.get_optional_fields("detail")

        # Detail should fall back to read optionals
        self.assertEqual(read_optionals, detail_optionals)
        self.assertEqual(len(detail_optionals), 1)
        self.assertEqual(detail_optionals[0][0], "description")

    def test_model_serializer_detail_fallback_excludes(self):
        """Test ModelSerializer detail falls back to read excludes when not configured."""
        from tests.test_app.models import TestModelSerializerWithReadExcludes

        read_excludes = TestModelSerializerWithReadExcludes.get_excluded_fields("read")
        detail_excludes = TestModelSerializerWithReadExcludes.get_excluded_fields("detail")

        # Detail should fall back to read excludes
        self.assertEqual(read_excludes, detail_excludes)
        self.assertIn("description", detail_excludes)

    def test_model_serializer_detail_inherits_per_field_type(self):
        """Test ModelSerializer detail inherits from read per-field-type when empty."""
        from tests.test_app.models import TestModelSerializerWithBothSerializers

        read_customs = TestModelSerializerWithBothSerializers.get_custom_fields("read")
        detail_customs = TestModelSerializerWithBothSerializers.get_custom_fields("detail")

        # Read has customs defined
        self.assertEqual(len(read_customs), 1)
        # Detail inherits customs from read because DetailSerializer.customs is empty
        # (fallback is per-field-type, not per-serializer)
        self.assertEqual(len(detail_customs), 1)
        self.assertEqual(detail_customs[0][0], "read_custom")

        # But fields are different (DetailSerializer.fields overrides)
        read_fields = TestModelSerializerWithBothSerializers.get_fields("read")
        detail_fields = TestModelSerializerWithBothSerializers.get_fields("detail")
        self.assertEqual(read_fields, ["id", "name"])
        self.assertEqual(detail_fields, ["id", "name", "description"])

    def test_model_serializer_with_detail_generates_different_schemas(self):
        """Test that ModelSerializer with DetailSerializer generates distinct schemas."""
        from tests.test_app.models import TestModelSerializerWithDetail

        read_schema = TestModelSerializerWithDetail.generate_read_s()
        detail_schema = TestModelSerializerWithDetail.generate_detail_s()

        # Read schema should have fewer fields
        self.assertIn("id", read_schema.model_fields)
        self.assertIn("name", read_schema.model_fields)
        self.assertNotIn("description", read_schema.model_fields)
        self.assertNotIn("extra_info", read_schema.model_fields)

        # Detail schema should have more fields plus custom
        self.assertIn("id", detail_schema.model_fields)
        self.assertIn("name", detail_schema.model_fields)
        self.assertIn("description", detail_schema.model_fields)
        self.assertIn("extra_info", detail_schema.model_fields)
        self.assertIn("computed_field", detail_schema.model_fields)


@tag("serializers", "relations_as_id")
class RelationsAsIdModelSerializerTestCase(TestCase):
    """Test cases for relations_as_id with ModelSerializer."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_forward_fk_relations_as_id_schema(self):
        """Test forward FK field in relations_as_id generates int type."""
        from tests.test_app.models import BookAsId

        schema = BookAsId.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("author_as_id", schema.model_fields)

        # Check the field type annotation includes int (PkFromModel extracts to int)
        field_info = schema.model_fields["author_as_id"]
        # Field should be Optional[int] (nullable FK)
        self.assertTrue(
            field_info.annotation is not None,
            "author_as_id field should have a type annotation",
        )

    def test_reverse_fk_relations_as_id_schema(self):
        """Test reverse FK field in relations_as_id generates list[int] type."""
        from tests.test_app.models import AuthorAsId

        schema = AuthorAsId.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("books_as_id", schema.model_fields)

        # Check the field is present and has annotation
        field_info = schema.model_fields["books_as_id"]
        self.assertTrue(
            field_info.annotation is not None,
            "books_as_id field should have a type annotation",
        )

    def test_forward_o2o_relations_as_id_schema(self):
        """Test forward O2O field in relations_as_id generates int type."""
        from tests.test_app.models import UserAsId

        schema = UserAsId.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("profile_as_id", schema.model_fields)

        field_info = schema.model_fields["profile_as_id"]
        self.assertTrue(
            field_info.annotation is not None,
            "profile_as_id field should have a type annotation",
        )

    def test_reverse_o2o_relations_as_id_schema(self):
        """Test reverse O2O field in relations_as_id generates int type."""
        from tests.test_app.models import ProfileAsId

        schema = ProfileAsId.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("user_profile_as_id", schema.model_fields)

        field_info = schema.model_fields["user_profile_as_id"]
        self.assertTrue(
            field_info.annotation is not None,
            "user_profile_as_id field should have a type annotation",
        )

    def test_forward_m2m_relations_as_id_schema(self):
        """Test forward M2M field in relations_as_id generates list[int] type."""
        from tests.test_app.models import ArticleAsId

        schema = ArticleAsId.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("tags_as_id", schema.model_fields)

        field_info = schema.model_fields["tags_as_id"]
        self.assertTrue(
            field_info.annotation is not None,
            "tags_as_id field should have a type annotation",
        )

    def test_reverse_m2m_relations_as_id_schema(self):
        """Test reverse M2M field in relations_as_id generates list[int] type."""
        from tests.test_app.models import TagAsId

        schema = TagAsId.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("articles_as_id", schema.model_fields)

        field_info = schema.model_fields["articles_as_id"]
        self.assertTrue(
            field_info.annotation is not None,
            "articles_as_id field should have a type annotation",
        )


@tag("serializers", "relations_as_id")
class RelationsAsIdSerializerTestCase(TestCase):
    """Test cases for relations_as_id with Meta-driven Serializer."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_forward_fk_relations_as_id_schema(self):
        """Test forward FK field in relations_as_id with Serializer."""
        from tests.test_app.serializers import BookAsIdMetaSerializer

        schema = BookAsIdMetaSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_model", schema.model_fields)

        field_info = schema.model_fields["test_model"]
        self.assertTrue(
            field_info.annotation is not None,
            "test_model field should have a type annotation",
        )

    def test_reverse_fk_relations_as_id_schema(self):
        """Test reverse FK field in relations_as_id with Serializer."""
        from tests.test_app.serializers import AuthorAsIdMetaSerializer

        schema = AuthorAsIdMetaSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_model_foreign_keys", schema.model_fields)

        field_info = schema.model_fields["test_model_foreign_keys"]
        self.assertTrue(
            field_info.annotation is not None,
            "test_model_foreign_keys field should have a type annotation",
        )

    def test_forward_o2o_relations_as_id_schema(self):
        """Test forward O2O field in relations_as_id with Serializer."""
        from tests.test_app.serializers import UserAsIdMetaSerializer

        schema = UserAsIdMetaSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_model", schema.model_fields)

        field_info = schema.model_fields["test_model"]
        self.assertTrue(
            field_info.annotation is not None,
            "test_model field should have a type annotation",
        )

    def test_reverse_o2o_relations_as_id_schema(self):
        """Test reverse O2O field in relations_as_id with Serializer."""
        from tests.test_app.serializers import ProfileAsIdMetaSerializer

        schema = ProfileAsIdMetaSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_model_one_to_one", schema.model_fields)

        field_info = schema.model_fields["test_model_one_to_one"]
        self.assertTrue(
            field_info.annotation is not None,
            "test_model_one_to_one field should have a type annotation",
        )

    def test_forward_m2m_relations_as_id_schema(self):
        """Test forward M2M field in relations_as_id with Serializer."""
        from tests.test_app.serializers import ArticleAsIdMetaSerializer

        schema = ArticleAsIdMetaSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_models", schema.model_fields)

        field_info = schema.model_fields["test_models"]
        self.assertTrue(
            field_info.annotation is not None,
            "test_models field should have a type annotation",
        )

    def test_reverse_m2m_relations_as_id_schema(self):
        """Test reverse M2M field in relations_as_id with Serializer."""
        from tests.test_app.serializers import TagAsIdMetaSerializer

        schema = TagAsIdMetaSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("test_model_serializer_many_to_many", schema.model_fields)

        field_info = schema.model_fields["test_model_serializer_many_to_many"]
        self.assertTrue(
            field_info.annotation is not None,
            "test_model_serializer_many_to_many field should have a type annotation",
        )


@tag("serializers", "relations_as_id", "integration")
class RelationsAsIdIntegrationTestCase(TestCase):
    """Integration tests for relations_as_id with actual data serialization."""

    @classmethod
    def setUpTestData(cls):
        from tests.test_app.models import (
            AuthorAsId,
            BookAsId,
            ProfileAsId,
            UserAsId,
            TagAsId,
            ArticleAsId,
        )

        # Create test data for FK relations
        cls.author = AuthorAsId.objects.create(name="Author 1", description="Test author")
        cls.book1 = BookAsId.objects.create(
            name="Book 1", description="Test book 1", author_as_id=cls.author
        )
        cls.book2 = BookAsId.objects.create(
            name="Book 2", description="Test book 2", author_as_id=cls.author
        )
        cls.book_no_author = BookAsId.objects.create(
            name="Book 3", description="Test book without author", author_as_id=None
        )

        # Create test data for O2O relations
        cls.profile = ProfileAsId.objects.create(name="Profile 1", description="Test profile")
        cls.user = UserAsId.objects.create(
            name="User 1", description="Test user", profile_as_id=cls.profile
        )

        # Create test data for M2M relations
        cls.tag1 = TagAsId.objects.create(name="Tag 1", description="Test tag 1")
        cls.tag2 = TagAsId.objects.create(name="Tag 2", description="Test tag 2")
        cls.article = ArticleAsId.objects.create(name="Article 1", description="Test article")
        cls.article.tags_as_id.add(cls.tag1, cls.tag2)

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_forward_fk_serialization(self):
        """Test forward FK field serializes as ID."""
        from tests.test_app.models import BookAsId

        schema = BookAsId.generate_read_s()
        result = schema.from_orm(self.book1)

        self.assertEqual(result.author_as_id, self.author.pk)

    def test_forward_fk_null_serialization(self):
        """Test forward FK field with null value serializes as None."""
        from tests.test_app.models import BookAsId

        schema = BookAsId.generate_read_s()
        result = schema.from_orm(self.book_no_author)

        self.assertIsNone(result.author_as_id)

    def test_reverse_fk_serialization(self):
        """Test reverse FK field serializes as list of IDs."""
        from tests.test_app.models import AuthorAsId

        # Prefetch the related books
        author = AuthorAsId.objects.prefetch_related("books_as_id").get(pk=self.author.pk)

        schema = AuthorAsId.generate_read_s()
        result = schema.from_orm(author)

        self.assertIsInstance(result.books_as_id, list)
        self.assertEqual(len(result.books_as_id), 2)
        self.assertIn(self.book1.pk, result.books_as_id)
        self.assertIn(self.book2.pk, result.books_as_id)

    def test_forward_o2o_serialization(self):
        """Test forward O2O field serializes as ID."""
        from tests.test_app.models import UserAsId

        schema = UserAsId.generate_read_s()
        result = schema.from_orm(self.user)

        self.assertEqual(result.profile_as_id, self.profile.pk)

    def test_reverse_o2o_serialization(self):
        """Test reverse O2O field serializes as ID."""
        from tests.test_app.models import ProfileAsId

        # Get profile with prefetched user
        profile = ProfileAsId.objects.select_related("user_profile_as_id").get(pk=self.profile.pk)

        schema = ProfileAsId.generate_read_s()
        result = schema.from_orm(profile)

        self.assertEqual(result.user_profile_as_id, self.user.pk)

    def test_forward_m2m_serialization(self):
        """Test forward M2M field serializes as list of IDs."""
        from tests.test_app.models import ArticleAsId

        # Prefetch the related tags
        article = ArticleAsId.objects.prefetch_related("tags_as_id").get(pk=self.article.pk)

        schema = ArticleAsId.generate_read_s()
        result = schema.from_orm(article)

        self.assertIsInstance(result.tags_as_id, list)
        self.assertEqual(len(result.tags_as_id), 2)
        self.assertIn(self.tag1.pk, result.tags_as_id)
        self.assertIn(self.tag2.pk, result.tags_as_id)

    def test_reverse_m2m_serialization(self):
        """Test reverse M2M field serializes as list of IDs."""
        from tests.test_app.models import TagAsId

        # Prefetch the related articles
        tag = TagAsId.objects.prefetch_related("articles_as_id").get(pk=self.tag1.pk)

        schema = TagAsId.generate_read_s()
        result = schema.from_orm(tag)

        self.assertIsInstance(result.articles_as_id, list)
        self.assertEqual(len(result.articles_as_id), 1)
        self.assertIn(self.article.pk, result.articles_as_id)


@tag("serializers", "relations_as_id", "uuid_pk")
class RelationsAsIdUUIDModelSerializerTestCase(TestCase):
    """Test cases for relations_as_id with UUID primary keys."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_forward_fk_uuid_relations_as_id_schema(self):
        """Test forward FK field with UUID PK in relations_as_id generates UUID type."""
        from tests.test_app.models import BookUUID

        schema = BookUUID.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("author_uuid", schema.model_fields)

        field_info = schema.model_fields["author_uuid"]
        self.assertTrue(
            field_info.annotation is not None,
            "author_uuid field should have a type annotation",
        )

    def test_reverse_fk_uuid_relations_as_id_schema(self):
        """Test reverse FK field with UUID PK in relations_as_id generates list[UUID] type."""
        from tests.test_app.models import AuthorUUID

        schema = AuthorUUID.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("books_uuid", schema.model_fields)

        field_info = schema.model_fields["books_uuid"]
        self.assertTrue(
            field_info.annotation is not None,
            "books_uuid field should have a type annotation",
        )

    def test_forward_o2o_uuid_relations_as_id_schema(self):
        """Test forward O2O field with UUID PK in relations_as_id generates UUID type."""
        from tests.test_app.models import UserUUID

        schema = UserUUID.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("profile_uuid", schema.model_fields)

        field_info = schema.model_fields["profile_uuid"]
        self.assertTrue(
            field_info.annotation is not None,
            "profile_uuid field should have a type annotation",
        )

    def test_reverse_o2o_uuid_relations_as_id_schema(self):
        """Test reverse O2O field with UUID PK in relations_as_id generates UUID type."""
        from tests.test_app.models import ProfileUUID

        schema = ProfileUUID.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("user_uuid", schema.model_fields)

        field_info = schema.model_fields["user_uuid"]
        self.assertTrue(
            field_info.annotation is not None,
            "user_uuid field should have a type annotation",
        )

    def test_forward_m2m_uuid_relations_as_id_schema(self):
        """Test forward M2M field with UUID PK in relations_as_id generates list[UUID] type."""
        from tests.test_app.models import ArticleUUID

        schema = ArticleUUID.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("tags_uuid", schema.model_fields)

        field_info = schema.model_fields["tags_uuid"]
        self.assertTrue(
            field_info.annotation is not None,
            "tags_uuid field should have a type annotation",
        )

    def test_reverse_m2m_uuid_relations_as_id_schema(self):
        """Test reverse M2M field with UUID PK in relations_as_id generates list[UUID] type."""
        from tests.test_app.models import TagUUID

        schema = TagUUID.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("articles_uuid", schema.model_fields)

        field_info = schema.model_fields["articles_uuid"]
        self.assertTrue(
            field_info.annotation is not None,
            "articles_uuid field should have a type annotation",
        )


@tag("serializers", "relations_as_id", "uuid_pk", "integration")
class RelationsAsIdUUIDIntegrationTestCase(TestCase):
    """Integration tests for relations_as_id with UUID primary keys and actual data serialization."""

    @classmethod
    def setUpTestData(cls):
        from tests.test_app.models import (
            AuthorUUID,
            BookUUID,
            ProfileUUID,
            UserUUID,
            TagUUID,
            ArticleUUID,
        )

        # Create test data for FK relations with UUID PKs
        cls.author = AuthorUUID.objects.create(name="UUID Author 1")
        cls.book1 = BookUUID.objects.create(name="UUID Book 1", author_uuid=cls.author)
        cls.book2 = BookUUID.objects.create(name="UUID Book 2", author_uuid=cls.author)
        cls.book_no_author = BookUUID.objects.create(name="UUID Book 3", author_uuid=None)

        # Create test data for O2O relations with UUID PKs
        cls.profile = ProfileUUID.objects.create(name="UUID Profile 1")
        cls.user = UserUUID.objects.create(name="UUID User 1", profile_uuid=cls.profile)

        # Create test data for M2M relations with UUID PKs
        cls.tag1 = TagUUID.objects.create(name="UUID Tag 1")
        cls.tag2 = TagUUID.objects.create(name="UUID Tag 2")
        cls.article = ArticleUUID.objects.create(name="UUID Article 1")
        cls.article.tags_uuid.add(cls.tag1, cls.tag2)

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_forward_fk_uuid_serialization(self):
        """Test forward FK field with UUID PK serializes as UUID."""
        from tests.test_app.models import BookUUID
        from uuid import UUID

        schema = BookUUID.generate_read_s()
        result = schema.from_orm(self.book1)

        self.assertIsInstance(result.author_uuid, UUID)
        self.assertEqual(result.author_uuid, self.author.pk)

    def test_forward_fk_uuid_null_serialization(self):
        """Test forward FK field with UUID PK and null value serializes as None."""
        from tests.test_app.models import BookUUID

        schema = BookUUID.generate_read_s()
        result = schema.from_orm(self.book_no_author)

        self.assertIsNone(result.author_uuid)

    def test_reverse_fk_uuid_serialization(self):
        """Test reverse FK field with UUID PK serializes as list of UUIDs."""
        from tests.test_app.models import AuthorUUID
        from uuid import UUID

        author = AuthorUUID.objects.prefetch_related("books_uuid").get(pk=self.author.pk)

        schema = AuthorUUID.generate_read_s()
        result = schema.from_orm(author)

        self.assertIsInstance(result.books_uuid, list)
        self.assertEqual(len(result.books_uuid), 2)
        for book_id in result.books_uuid:
            self.assertIsInstance(book_id, UUID)
        self.assertIn(self.book1.pk, result.books_uuid)
        self.assertIn(self.book2.pk, result.books_uuid)

    def test_forward_o2o_uuid_serialization(self):
        """Test forward O2O field with UUID PK serializes as UUID."""
        from tests.test_app.models import UserUUID
        from uuid import UUID

        schema = UserUUID.generate_read_s()
        result = schema.from_orm(self.user)

        self.assertIsInstance(result.profile_uuid, UUID)
        self.assertEqual(result.profile_uuid, self.profile.pk)

    def test_reverse_o2o_uuid_serialization(self):
        """Test reverse O2O field with UUID PK serializes as UUID."""
        from tests.test_app.models import ProfileUUID
        from uuid import UUID

        profile = ProfileUUID.objects.select_related("user_uuid").get(pk=self.profile.pk)

        schema = ProfileUUID.generate_read_s()
        result = schema.from_orm(profile)

        self.assertIsInstance(result.user_uuid, UUID)
        self.assertEqual(result.user_uuid, self.user.pk)

    def test_forward_m2m_uuid_serialization(self):
        """Test forward M2M field with UUID PK serializes as list of UUIDs."""
        from tests.test_app.models import ArticleUUID
        from uuid import UUID

        article = ArticleUUID.objects.prefetch_related("tags_uuid").get(pk=self.article.pk)

        schema = ArticleUUID.generate_read_s()
        result = schema.from_orm(article)

        self.assertIsInstance(result.tags_uuid, list)
        self.assertEqual(len(result.tags_uuid), 2)
        for tag_id in result.tags_uuid:
            self.assertIsInstance(tag_id, UUID)
        self.assertIn(self.tag1.pk, result.tags_uuid)
        self.assertIn(self.tag2.pk, result.tags_uuid)

    def test_reverse_m2m_uuid_serialization(self):
        """Test reverse M2M field with UUID PK serializes as list of UUIDs."""
        from tests.test_app.models import TagUUID
        from uuid import UUID

        tag = TagUUID.objects.prefetch_related("articles_uuid").get(pk=self.tag1.pk)

        schema = TagUUID.generate_read_s()
        result = schema.from_orm(tag)

        self.assertIsInstance(result.articles_uuid, list)
        self.assertEqual(len(result.articles_uuid), 1)
        self.assertIsInstance(result.articles_uuid[0], UUID)
        self.assertIn(self.article.pk, result.articles_uuid)


@tag("serializers", "relations_as_id", "string_pk")
class RelationsAsIdStringPKModelSerializerTestCase(TestCase):
    """Test cases for relations_as_id with string (CharField) primary keys."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_forward_fk_string_relations_as_id_schema(self):
        """Test forward FK field with string PK in relations_as_id generates str type."""
        from tests.test_app.models import BookStringPK

        schema = BookStringPK.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("author_str", schema.model_fields)

        field_info = schema.model_fields["author_str"]
        self.assertTrue(
            field_info.annotation is not None,
            "author_str field should have a type annotation",
        )

    def test_reverse_fk_string_relations_as_id_schema(self):
        """Test reverse FK field with string PK in relations_as_id generates list[str] type."""
        from tests.test_app.models import AuthorStringPK

        schema = AuthorStringPK.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("books_str", schema.model_fields)

        field_info = schema.model_fields["books_str"]
        self.assertTrue(
            field_info.annotation is not None,
            "books_str field should have a type annotation",
        )

    def test_forward_o2o_string_relations_as_id_schema(self):
        """Test forward O2O field with string PK in relations_as_id generates str type."""
        from tests.test_app.models import UserStringPK

        schema = UserStringPK.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("profile_str", schema.model_fields)

        field_info = schema.model_fields["profile_str"]
        self.assertTrue(
            field_info.annotation is not None,
            "profile_str field should have a type annotation",
        )

    def test_reverse_o2o_string_relations_as_id_schema(self):
        """Test reverse O2O field with string PK in relations_as_id generates str type."""
        from tests.test_app.models import ProfileStringPK

        schema = ProfileStringPK.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("user_str", schema.model_fields)

        field_info = schema.model_fields["user_str"]
        self.assertTrue(
            field_info.annotation is not None,
            "user_str field should have a type annotation",
        )

    def test_forward_m2m_string_relations_as_id_schema(self):
        """Test forward M2M field with string PK in relations_as_id generates list[str] type."""
        from tests.test_app.models import ArticleStringPK

        schema = ArticleStringPK.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("tags_str", schema.model_fields)

        field_info = schema.model_fields["tags_str"]
        self.assertTrue(
            field_info.annotation is not None,
            "tags_str field should have a type annotation",
        )

    def test_reverse_m2m_string_relations_as_id_schema(self):
        """Test reverse M2M field with string PK in relations_as_id generates list[str] type."""
        from tests.test_app.models import TagStringPK

        schema = TagStringPK.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("articles_str", schema.model_fields)

        field_info = schema.model_fields["articles_str"]
        self.assertTrue(
            field_info.annotation is not None,
            "articles_str field should have a type annotation",
        )


@tag("serializers", "customs_only")
class CustomsOnlySchemaTestCase(TestCase):
    """Test cases for schemas with only customs/optionals defined (no fields/excludes)."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_serializer_create_schema_with_only_customs(self):
        """Test that create schema with only customs does NOT include model fields."""

        class CustomsOnlyCreateSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_in = serializers.SchemaModelConfig(
                    customs=[("custom_input", str, ...)]
                )
                schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

        schema = CustomsOnlyCreateSerializer.generate_create_s()
        self.assertIsNotNone(schema)
        # Should only have the custom field, not model fields
        self.assertIn("custom_input", schema.model_fields)
        # Should NOT have model fields auto-included
        self.assertNotIn("name", schema.model_fields)
        self.assertNotIn("description", schema.model_fields)
        self.assertNotIn("test_model", schema.model_fields)
        self.assertNotIn("id", schema.model_fields)

    def test_serializer_update_schema_with_only_customs(self):
        """Test that update schema with only customs does NOT include model fields."""

        class CustomsOnlyUpdateSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_update = serializers.SchemaModelConfig(
                    customs=[("custom_patch_field", str, None)]
                )
                schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

        schema = CustomsOnlyUpdateSerializer.generate_update_s()
        self.assertIsNotNone(schema)
        # Should only have the custom field
        self.assertIn("custom_patch_field", schema.model_fields)
        # Should NOT have model fields auto-included
        self.assertNotIn("name", schema.model_fields)
        self.assertNotIn("description", schema.model_fields)
        self.assertNotIn("test_model", schema.model_fields)
        self.assertNotIn("id", schema.model_fields)

    def test_serializer_create_schema_with_customs_and_optionals(self):
        """Test create schema with customs + optionals includes only those fields."""

        class CustomsAndOptionalsSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_in = serializers.SchemaModelConfig(
                    customs=[("custom_field", str, ...)],
                    optionals=[("name", str)],  # name is a model field made optional
                )
                schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

        schema = CustomsAndOptionalsSerializer.generate_create_s()
        self.assertIsNotNone(schema)
        # Should have custom field
        self.assertIn("custom_field", schema.model_fields)
        # Should have the optional model field
        self.assertIn("name", schema.model_fields)
        # Should NOT have other model fields
        self.assertNotIn("description", schema.model_fields)
        self.assertNotIn("test_model", schema.model_fields)
        self.assertNotIn("id", schema.model_fields)

    def test_serializer_with_fields_still_works(self):
        """Test that defining fields still works as expected."""

        class FieldsDefinedSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_in = serializers.SchemaModelConfig(
                    fields=["name", "description"],
                    customs=[("extra", int, 0)],
                )
                schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

        schema = FieldsDefinedSerializer.generate_create_s()
        self.assertIsNotNone(schema)
        # Should have specified fields
        self.assertIn("name", schema.model_fields)
        self.assertIn("description", schema.model_fields)
        # Should have custom field
        self.assertIn("extra", schema.model_fields)
        # Should NOT have other model fields
        self.assertNotIn("test_model", schema.model_fields)
        self.assertNotIn("id", schema.model_fields)

    def test_serializer_with_only_excludes_and_customs(self):
        """Test schema with excludes and customs but no fields only has customs."""

        class ExcludesOnlySerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_in = serializers.SchemaModelConfig(
                    exclude=["id", "test_model"],
                    customs=[("extra", int, 0)],
                )
                schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

        schema = ExcludesOnlySerializer.generate_create_s()
        self.assertIsNotNone(schema)
        # With excludes but no fields, only customs are included
        # because fields=[] is passed to create_schema (no model fields)
        self.assertIn("extra", schema.model_fields)
        # This is expected behavior: without explicit fields, no model fields included
        self.assertEqual(len(schema.model_fields), 1)

    def test_serializer_empty_schema_returns_none(self):
        """Test that schema with nothing defined returns None."""

        class EmptySchemaSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_in = serializers.SchemaModelConfig()
                schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

        schema = EmptySchemaSerializer.generate_create_s()
        self.assertIsNone(schema)

    def test_serializer_multiple_customs_no_model_fields(self):
        """Test schema with multiple customs but no model fields."""

        class MultipleCustomsSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_in = serializers.SchemaModelConfig(
                    customs=[
                        ("custom1", str, ...),
                        ("custom2", int, 0),
                        ("custom3", bool, False),
                    ]
                )
                schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

        schema = MultipleCustomsSerializer.generate_create_s()
        self.assertIsNotNone(schema)
        # Should have all custom fields
        self.assertIn("custom1", schema.model_fields)
        self.assertIn("custom2", schema.model_fields)
        self.assertIn("custom3", schema.model_fields)
        # Should NOT have any model fields
        self.assertNotIn("name", schema.model_fields)
        self.assertNotIn("description", schema.model_fields)
        self.assertNotIn("test_model", schema.model_fields)
        self.assertNotIn("id", schema.model_fields)


@tag("serializers", "relations_as_id", "string_pk", "integration")
class RelationsAsIdStringPKIntegrationTestCase(TestCase):
    """Integration tests for relations_as_id with string primary keys and actual data serialization."""

    @classmethod
    def setUpTestData(cls):
        from tests.test_app.models import (
            AuthorStringPK,
            BookStringPK,
            ProfileStringPK,
            UserStringPK,
            TagStringPK,
            ArticleStringPK,
        )

        # Create test data for FK relations with string PKs
        cls.author = AuthorStringPK.objects.create(id="author-001", name="String Author 1")
        cls.book1 = BookStringPK.objects.create(id="book-001", name="String Book 1", author_str=cls.author)
        cls.book2 = BookStringPK.objects.create(id="book-002", name="String Book 2", author_str=cls.author)
        cls.book_no_author = BookStringPK.objects.create(id="book-003", name="String Book 3", author_str=None)

        # Create test data for O2O relations with string PKs
        cls.profile = ProfileStringPK.objects.create(id="profile-001", name="String Profile 1")
        cls.user = UserStringPK.objects.create(id="user-001", name="String User 1", profile_str=cls.profile)

        # Create test data for M2M relations with string PKs
        cls.tag1 = TagStringPK.objects.create(id="tag-001", name="String Tag 1")
        cls.tag2 = TagStringPK.objects.create(id="tag-002", name="String Tag 2")
        cls.article = ArticleStringPK.objects.create(id="article-001", name="String Article 1")
        cls.article.tags_str.add(cls.tag1, cls.tag2)

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_forward_fk_string_serialization(self):
        """Test forward FK field with string PK serializes as str."""
        from tests.test_app.models import BookStringPK

        schema = BookStringPK.generate_read_s()
        result = schema.from_orm(self.book1)

        self.assertIsInstance(result.author_str, str)
        self.assertEqual(result.author_str, self.author.pk)
        self.assertEqual(result.author_str, "author-001")

    def test_forward_fk_string_null_serialization(self):
        """Test forward FK field with string PK and null value serializes as None."""
        from tests.test_app.models import BookStringPK

        schema = BookStringPK.generate_read_s()
        result = schema.from_orm(self.book_no_author)

        self.assertIsNone(result.author_str)

    def test_reverse_fk_string_serialization(self):
        """Test reverse FK field with string PK serializes as list of strs."""
        from tests.test_app.models import AuthorStringPK

        author = AuthorStringPK.objects.prefetch_related("books_str").get(pk=self.author.pk)

        schema = AuthorStringPK.generate_read_s()
        result = schema.from_orm(author)

        self.assertIsInstance(result.books_str, list)
        self.assertEqual(len(result.books_str), 2)
        for book_id in result.books_str:
            self.assertIsInstance(book_id, str)
        self.assertIn(self.book1.pk, result.books_str)
        self.assertIn(self.book2.pk, result.books_str)

    def test_forward_o2o_string_serialization(self):
        """Test forward O2O field with string PK serializes as str."""
        from tests.test_app.models import UserStringPK

        schema = UserStringPK.generate_read_s()
        result = schema.from_orm(self.user)

        self.assertIsInstance(result.profile_str, str)
        self.assertEqual(result.profile_str, self.profile.pk)
        self.assertEqual(result.profile_str, "profile-001")

    def test_reverse_o2o_string_serialization(self):
        """Test reverse O2O field with string PK serializes as str."""
        from tests.test_app.models import ProfileStringPK

        profile = ProfileStringPK.objects.select_related("user_str").get(pk=self.profile.pk)

        schema = ProfileStringPK.generate_read_s()
        result = schema.from_orm(profile)

        self.assertIsInstance(result.user_str, str)
        self.assertEqual(result.user_str, self.user.pk)
        self.assertEqual(result.user_str, "user-001")

    def test_forward_m2m_string_serialization(self):
        """Test forward M2M field with string PK serializes as list of strs."""
        from tests.test_app.models import ArticleStringPK

        article = ArticleStringPK.objects.prefetch_related("tags_str").get(pk=self.article.pk)

        schema = ArticleStringPK.generate_read_s()
        result = schema.from_orm(article)

        self.assertIsInstance(result.tags_str, list)
        self.assertEqual(len(result.tags_str), 2)
        for tag_id in result.tags_str:
            self.assertIsInstance(tag_id, str)
        self.assertIn(self.tag1.pk, result.tags_str)
        self.assertIn(self.tag2.pk, result.tags_str)

    def test_reverse_m2m_string_serialization(self):
        """Test reverse M2M field with string PK serializes as list of strs."""
        from tests.test_app.models import TagStringPK

        tag = TagStringPK.objects.prefetch_related("articles_str").get(pk=self.tag1.pk)

        schema = TagStringPK.generate_read_s()
        result = schema.from_orm(tag)

        self.assertIsInstance(result.articles_str, list)
        self.assertEqual(len(result.articles_str), 1)
        self.assertIsInstance(result.articles_str[0], str)
        self.assertIn(self.article.pk, result.articles_str)
        self.assertEqual(result.articles_str[0], "article-001")


@tag("serializers", "inline_customs")
class InlineCustomsSerializerTestCase(TestCase):
    """Test cases for inline custom fields defined directly in the fields list."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_serializer_read_schema_with_inline_customs_3_tuple(self):
        """Test that inline customs (3-tuple) in schema_out fields work correctly."""

        class InlineCustomsReadSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", ("custom_read", str, "default_value")]
                )

        schema = InlineCustomsReadSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("id", schema.model_fields)
        self.assertIn("name", schema.model_fields)
        self.assertIn("custom_read", schema.model_fields)

    def test_serializer_read_schema_with_inline_customs_2_tuple(self):
        """Test that inline customs (2-tuple, required) in schema_out fields work correctly."""

        class InlineCustoms2TupleSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", ("required_custom", int)]
                )

        schema = InlineCustoms2TupleSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("id", schema.model_fields)
        self.assertIn("name", schema.model_fields)
        self.assertIn("required_custom", schema.model_fields)

    def test_serializer_create_schema_with_inline_customs(self):
        """Test that inline customs in schema_in fields work correctly."""

        class InlineCustomsCreateSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_in = serializers.SchemaModelConfig(
                    fields=["name", ("extra_input", str, "")]
                )
                schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

        schema = InlineCustomsCreateSerializer.generate_create_s()
        self.assertIsNotNone(schema)
        self.assertIn("name", schema.model_fields)
        self.assertIn("extra_input", schema.model_fields)
        # Should NOT have model fields that weren't explicitly listed
        self.assertNotIn("description", schema.model_fields)

    def test_serializer_update_schema_with_inline_customs(self):
        """Test that inline customs in schema_update fields work correctly."""

        class InlineCustomsUpdateSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_update = serializers.SchemaModelConfig(
                    fields=[("update_flag", bool, False)],
                    optionals=[("name", str)],
                )
                schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

        schema = InlineCustomsUpdateSerializer.generate_update_s()
        self.assertIsNotNone(schema)
        self.assertIn("update_flag", schema.model_fields)
        self.assertIn("name", schema.model_fields)

    def test_serializer_inline_customs_combined_with_explicit_customs(self):
        """Test that inline customs and explicit customs can coexist."""

        class CombinedCustomsSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", ("inline_custom", str, "inline")],
                    customs=[("explicit_custom", int, 0)],
                )

        schema = CombinedCustomsSerializer.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("id", schema.model_fields)
        self.assertIn("name", schema.model_fields)
        self.assertIn("inline_custom", schema.model_fields)
        self.assertIn("explicit_custom", schema.model_fields)

    def test_serializer_get_fields_excludes_inline_customs(self):
        """Test that get_fields() returns only string field names."""

        class FieldsOnlySerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", ("custom", str, "val")]
                )

        fields = FieldsOnlySerializer.get_fields("read")
        self.assertEqual(fields, ["id", "name"])
        # Should not include tuples
        self.assertNotIn(("custom", str, "val"), fields)

    def test_serializer_get_inline_customs_returns_only_tuples(self):
        """Test that get_inline_customs() returns only inline custom tuples."""

        class InlineCustomsOnlySerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", ("custom1", str, "val"), ("custom2", int)]
                )

        inline_customs = InlineCustomsOnlySerializer.get_inline_customs("read")
        self.assertEqual(len(inline_customs), 2)
        # First is a 3-tuple
        self.assertEqual(inline_customs[0], ("custom1", str, "val"))
        # Second is normalized from 2-tuple to 3-tuple with Ellipsis
        self.assertEqual(inline_customs[1], ("custom2", int, ...))

    def test_serializer_detail_schema_with_inline_customs(self):
        """Test that inline customs work in schema_detail."""

        class DetailInlineCustomsSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(fields=["id", "name"])
                schema_detail = serializers.SchemaModelConfig(
                    fields=["id", "name", "description", ("detail_extra", str, "extra")]
                )

        read_schema = DetailInlineCustomsSerializer.generate_read_s()
        detail_schema = DetailInlineCustomsSerializer.generate_detail_s()

        # Read schema should NOT have detail_extra
        self.assertNotIn("detail_extra", read_schema.model_fields)

        # Detail schema should have all fields including inline custom
        self.assertIn("id", detail_schema.model_fields)
        self.assertIn("name", detail_schema.model_fields)
        self.assertIn("description", detail_schema.model_fields)
        self.assertIn("detail_extra", detail_schema.model_fields)

    def test_serializer_related_schema_with_inline_customs(self):
        """Test that inline customs are included in related schema for non-relation fields."""

        class RelatedInlineCustomsSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(
                    fields=["id", "name", ("computed", str, "computed_value")]
                )

        related_schema = RelatedInlineCustomsSerializer.generate_related_s()
        self.assertIsNotNone(related_schema)
        self.assertIn("id", related_schema.model_fields)
        self.assertIn("name", related_schema.model_fields)
        self.assertIn("computed", related_schema.model_fields)

    def test_inline_customs_only_schema(self):
        """Test schema with only inline customs (no regular fields)."""

        class OnlyInlineCustomsSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_in = serializers.SchemaModelConfig(
                    fields=[("custom_only", str, ...)]
                )
                schema_out = serializers.SchemaModelConfig(fields=["id"])

        schema = OnlyInlineCustomsSerializer.generate_create_s()
        self.assertIsNotNone(schema)
        self.assertIn("custom_only", schema.model_fields)
        # Should NOT have any model fields auto-included
        self.assertNotIn("name", schema.model_fields)
        self.assertNotIn("description", schema.model_fields)


@tag("serializers", "inline_customs", "model_serializer")
class InlineCustomsModelSerializerTestCase(TestCase):
    """Test cases for inline custom fields with ModelSerializer."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_model_serializer_read_schema_with_inline_customs(self):
        """Test ModelSerializer ReadSerializer with inline customs."""
        from tests.test_app.models import TestModelSerializerInlineCustoms

        schema = TestModelSerializerInlineCustoms.generate_read_s()
        self.assertIsNotNone(schema)
        self.assertIn("id", schema.model_fields)
        self.assertIn("name", schema.model_fields)
        self.assertIn("inline_computed", schema.model_fields)

    def test_model_serializer_create_schema_with_inline_customs(self):
        """Test ModelSerializer CreateSerializer with inline customs."""
        from tests.test_app.models import TestModelSerializerInlineCustoms

        schema = TestModelSerializerInlineCustoms.generate_create_s()
        self.assertIsNotNone(schema)
        self.assertIn("name", schema.model_fields)
        self.assertIn("extra_create_input", schema.model_fields)

    def test_model_serializer_get_inline_customs(self):
        """Test get_inline_customs() works for ModelSerializer."""
        from tests.test_app.models import TestModelSerializerInlineCustoms

        inline_customs = TestModelSerializerInlineCustoms.get_inline_customs("read")
        self.assertEqual(len(inline_customs), 1)
        self.assertEqual(inline_customs[0][0], "inline_computed")

    def test_model_serializer_get_fields_excludes_inline_customs(self):
        """Test get_fields() excludes inline customs for ModelSerializer."""
        from tests.test_app.models import TestModelSerializerInlineCustoms

        fields = TestModelSerializerInlineCustoms.get_fields("read")
        self.assertIn("id", fields)
        self.assertIn("name", fields)
        self.assertNotIn("inline_computed", fields)
        # Should not contain tuples
        for f in fields:
            self.assertIsInstance(f, str)


@tag("serializers", "pk_from_model")
class PkFromModelTestCase(TestCase):
    """Test cases for PkFromModel class (covers lines 46, 65)."""

    def test_pk_from_model_extracts_pk_from_model_instance(self):
        """Test _extract_pk extracts pk from model instance."""
        from ninja_aio.models.serializers import _extract_pk

        class MockModel:
            pk = 42

        result = _extract_pk(MockModel())
        self.assertEqual(result, 42)

    def test_pk_from_model_returns_value_as_is_when_no_pk(self):
        """Test _extract_pk returns value as-is when no pk attribute (covers line 46)."""
        from ninja_aio.models.serializers import _extract_pk

        result = _extract_pk(123)
        self.assertEqual(result, 123)

        result = _extract_pk("string_value")
        self.assertEqual(result, "string_value")

    def test_pk_from_model_default_type(self):
        """Test PkFromModel() returns default int type (covers line 65)."""
        from ninja_aio.models.serializers import PkFromModel

        default_type = PkFromModel()
        self.assertIsNotNone(default_type)

    def test_pk_from_model_subscriptable_with_int(self):
        """Test PkFromModel[int] returns annotated int type."""
        from ninja_aio.models.serializers import PkFromModel

        int_type = PkFromModel[int]
        self.assertIsNotNone(int_type)

    def test_pk_from_model_subscriptable_with_str(self):
        """Test PkFromModel[str] returns annotated str type."""
        from ninja_aio.models.serializers import PkFromModel

        str_type = PkFromModel[str]
        self.assertIsNotNone(str_type)

    def test_pk_from_model_subscriptable_with_uuid(self):
        """Test PkFromModel[UUID] returns annotated UUID type."""
        from ninja_aio.models.serializers import PkFromModel
        from uuid import UUID

        uuid_type = PkFromModel[UUID]
        self.assertIsNotNone(uuid_type)


@tag("serializers", "string_reference")
class StringReferenceResolutionTestCase(TestCase):
    """Test cases for string reference resolution errors (covers lines 144-179)."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_resolve_string_reference_absolute_import(self):
        """Test resolving absolute import path."""
        # This should work since the module exists
        resolved = serializers.BaseSerializer._resolve_string_reference(
            "tests.test_serializers.LocalTestSerializer"
        )
        self.assertEqual(resolved, LocalTestSerializer)

    def test_resolve_string_reference_local_class(self):
        """Test resolving local class name in same module."""
        # The LocalTestSerializer is defined at module level in test_serializers.py
        # We need a class that can be resolved from its own module

        class TestResolveSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(fields=["id"])

        # Try to resolve from own module - this tests the local resolution path
        resolved = TestResolveSerializer._resolve_string_reference("TestModelForeignKeySerializer")
        self.assertEqual(resolved, TestModelForeignKeySerializer)

    def test_resolve_string_reference_import_error(self):
        """Test that invalid module path raises ValueError (covers lines 158-162)."""
        with self.assertRaises(ValueError) as cm:
            serializers.BaseSerializer._resolve_string_reference(
                "nonexistent.module.SomeClass"
            )
        self.assertIn("failed to import module", str(cm.exception))

    def test_resolve_string_reference_class_not_found_in_module(self):
        """Test that missing class in valid module raises ValueError (covers lines 152-155)."""
        with self.assertRaises(ValueError) as cm:
            serializers.BaseSerializer._resolve_string_reference(
                "tests.test_serializers.NonExistentClass"
            )
        self.assertIn("not found in module", str(cm.exception))

    def test_resolve_string_reference_local_not_found(self):
        """Test that missing local class raises ValueError (covers lines 176-179)."""
        with self.assertRaises(ValueError) as cm:
            serializers.BaseSerializer._resolve_string_reference(
                "CompletelyFakeSerializerThatDoesNotExist"
            )
        self.assertIn("Cannot resolve serializer reference", str(cm.exception))


@tag("serializers", "union_schema")
class UnionSchemaTestCase(TestCase):
    """Test cases for Union schema generation (covers lines 232, 280, 284)."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_single_type_union_optimization(self):
        """Test that single-type Union is optimized (covers line 232)."""
        # Create a Union with single type and test resolution
        from typing import Union

        single_union = Union[AltSerializer]

        resolved = serializers.BaseSerializer._resolve_serializer_reference(single_union)
        # Should be optimized to single type, not Union
        self.assertEqual(resolved, AltSerializer)

    def test_union_schema_all_none(self):
        """Test _generate_union_schema when all schemas return None (covers line 280)."""
        # This tests the case where all serializers in a Union have empty schemas
        from typing import Union

        class EmptySerializer1(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(fields=[])

            @classmethod
            def generate_related_s(cls):
                return None

        class EmptySerializer2(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(fields=[])

            @classmethod
            def generate_related_s(cls):
                return None

        empty_union = Union[EmptySerializer1, EmptySerializer2]
        result = serializers.BaseSerializer._generate_union_schema(empty_union)
        self.assertIsNone(result)

    def test_union_schema_single_result(self):
        """Test _generate_union_schema with only one non-None schema (covers line 284)."""
        from typing import Union

        class ValidSerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

        class EmptySerializer(serializers.Serializer):
            class Meta:
                model = TestModelForeignKey
                schema_out = serializers.SchemaModelConfig(fields=[])

            @classmethod
            def generate_related_s(cls):
                return None

        mixed_union = Union[ValidSerializer, EmptySerializer]
        result = serializers.BaseSerializer._generate_union_schema(mixed_union)
        # Should return single schema, not Union
        self.assertIsNotNone(result)


@tag("serializers", "custom_fields_validation")
class CustomFieldsValidationTestCase(TestCase):
    """Test cases for custom fields validation errors (covers lines 354-355, 406-409)."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_get_custom_fields_2_tuple(self):
        """Test get_custom_fields with 2-tuple format (covers lines 354-355)."""
        from unittest.mock import patch

        # Mock _get_fields to return 2-tuple customs
        with patch.object(
            serializers.BaseSerializer,
            "_get_fields",
            return_value=[("custom_required", str)],
        ):
            customs = serializers.BaseSerializer.get_custom_fields("read")
            self.assertEqual(len(customs), 1)
            name, py_type, default = customs[0]
            self.assertEqual(name, "custom_required")
            self.assertEqual(py_type, str)
            self.assertEqual(default, ...)  # Ellipsis for required

    def test_get_custom_fields_invalid_tuple_length(self):
        """Test get_custom_fields raises error for invalid tuple length."""
        from unittest.mock import patch

        # Mock _get_fields to return 1-tuple (invalid)
        with patch.object(
            serializers.BaseSerializer,
            "_get_fields",
            return_value=[("only_name",)],
        ):
            with self.assertRaises(ValueError) as cm:
                serializers.BaseSerializer.get_custom_fields("read")
            self.assertIn("must have length 2 or 3", str(cm.exception))

    def test_get_custom_fields_non_tuple(self):
        """Test get_custom_fields raises error for non-tuple spec."""
        from unittest.mock import patch

        # Mock _get_fields to return non-tuple
        with patch.object(
            serializers.BaseSerializer,
            "_get_fields",
            return_value=["not_a_tuple"],
        ):
            with self.assertRaises(ValueError) as cm:
                serializers.BaseSerializer.get_custom_fields("read")
            self.assertIn("must be a tuple", str(cm.exception))

    def test_get_inline_customs_invalid_tuple_length(self):
        """Test get_inline_customs raises error for invalid tuple length (covers lines 406-409)."""
        from unittest.mock import patch

        # Mock _get_fields to return fields with invalid 1-tuple
        with patch.object(
            serializers.BaseSerializer,
            "_get_fields",
            return_value=["id", ("only_one",)],
        ):
            with self.assertRaises(ValueError) as cm:
                serializers.BaseSerializer.get_inline_customs("read")
            self.assertIn("must have length 2 or 3", str(cm.exception))


@tag("serializers", "model_validation")
class ModelValidationTestCase(TestCase):
    """Test cases for model validation errors (covers lines 1189, 1191)."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    def test_serializer_without_model_raises_error(self):
        """Test that Serializer without model raises ValueError (covers line 1189)."""
        with self.assertRaises(ValueError) as cm:
            class NoModelSerializer(serializers.Serializer):
                class Meta:
                    schema_out = serializers.SchemaModelConfig(fields=["id"])

            NoModelSerializer.generate_read_s()
        self.assertIn("Meta.model must be defined", str(cm.exception))

    def test_serializer_with_non_model_raises_error(self):
        """Test that Serializer with non-Django model raises ValueError (covers line 1191)."""
        with self.assertRaises(ValueError) as cm:
            class NotAModel:
                pass

            class NonModelSerializer(serializers.Serializer):
                class Meta:
                    model = NotAModel
                    schema_out = serializers.SchemaModelConfig(fields=["id"])

            NonModelSerializer.generate_read_s()
        self.assertIn("must be a Django model", str(cm.exception))


@tag("serializers", "base_serializer")
class BaseSerializerAbstractMethodsTestCase(TestCase):
    """Test cases for BaseSerializer abstract method errors (covers lines 108, 113)."""

    def test_get_fields_raises_not_implemented(self):
        """Test _get_fields raises NotImplementedError (covers line 108)."""
        with self.assertRaises(NotImplementedError):
            serializers.BaseSerializer._get_fields("read", "fields")

    def test_get_model_raises_not_implemented(self):
        """Test _get_model raises NotImplementedError (covers line 113)."""
        with self.assertRaises(NotImplementedError):
            serializers.BaseSerializer._get_model()


@tag("serializers", "validators")
class ValidatorsOnSerializersTestCase(TestCase):
    """Test cases for @field_validator and @model_validator on serializers."""

    def setUp(self):
        warnings.simplefilter("ignore", UserWarning)

    # ----- ModelSerializer validators -----

    def test_model_serializer_field_validator_rejects_invalid(self):
        """Test that @field_validator on CreateSerializer rejects invalid input."""
        from tests.test_app.models import TestModelWithValidators
        from pydantic import ValidationError

        schema = TestModelWithValidators.generate_create_s()
        with self.assertRaises(ValidationError) as cm:
            schema(name="ab", description="test")
        self.assertIn("Name must be at least 3 characters", str(cm.exception))

    def test_model_serializer_field_validator_accepts_valid(self):
        """Test that @field_validator on CreateSerializer accepts valid input."""
        from tests.test_app.models import TestModelWithValidators

        schema = TestModelWithValidators.generate_create_s()
        instance = schema(name="abc", description="test")
        self.assertEqual(instance.name, "abc")

    def test_model_serializer_update_validator_rejects_blank(self):
        """Test that @field_validator on UpdateSerializer rejects blank name."""
        from tests.test_app.models import TestModelWithValidators
        from pydantic import ValidationError

        schema = TestModelWithValidators.generate_update_s()
        with self.assertRaises(ValidationError) as cm:
            schema(name="   ")
        self.assertIn("Name cannot be blank", str(cm.exception))

    def test_model_serializer_update_validator_accepts_valid(self):
        """Test that @field_validator on UpdateSerializer accepts valid input."""
        from tests.test_app.models import TestModelWithValidators

        schema = TestModelWithValidators.generate_update_s()
        instance = schema(name="valid")
        self.assertEqual(instance.name, "valid")

    def test_model_serializer_read_model_validator(self):
        """Test that @model_validator on ReadSerializer is applied to output schema."""
        from tests.test_app.models import TestModelWithValidators

        schema = TestModelWithValidators.generate_read_s()
        # model_validator(mode="after") should be present on the schema
        self.assertIn("add_display_check", schema.__pydantic_decorators__.model_validators)

    def test_model_serializer_no_validators_returns_plain_schema(self):
        """Test that serializers without validators still work normally."""
        from tests.test_app.models import TestModelSerializer

        schema = TestModelSerializer.generate_create_s()
        instance = schema(name="ab", description="test")
        self.assertEqual(instance.name, "ab")  # No min-length validator here

    # ----- Meta-driven Serializer validators -----

    def test_meta_serializer_field_validator_rejects_invalid(self):
        """Test that CreateValidators @field_validator rejects invalid input."""
        from tests.test_app.serializers import TestModelWithValidatorsMetaSerializer
        from pydantic import ValidationError

        schema = TestModelWithValidatorsMetaSerializer.generate_create_s()
        with self.assertRaises(ValidationError) as cm:
            schema(name="ab", description="test")
        self.assertIn("Name must be at least 3 characters", str(cm.exception))

    def test_meta_serializer_field_validator_accepts_valid(self):
        """Test that CreateValidators @field_validator accepts valid input."""
        from tests.test_app.serializers import TestModelWithValidatorsMetaSerializer

        schema = TestModelWithValidatorsMetaSerializer.generate_create_s()
        instance = schema(name="abc", description="test")
        self.assertEqual(instance.name, "abc")

    def test_meta_serializer_update_validator_rejects_blank(self):
        """Test that UpdateValidators @field_validator rejects blank name."""
        from tests.test_app.serializers import TestModelWithValidatorsMetaSerializer
        from pydantic import ValidationError

        schema = TestModelWithValidatorsMetaSerializer.generate_update_s()
        with self.assertRaises(ValidationError) as cm:
            schema(name="   ")
        self.assertIn("Name cannot be blank", str(cm.exception))

    def test_meta_serializer_read_model_validator(self):
        """Test that ReadValidators @model_validator is applied to output schema."""
        from tests.test_app.serializers import TestModelWithValidatorsMetaSerializer

        schema = TestModelWithValidatorsMetaSerializer.generate_read_s()
        self.assertIn("add_display_check", schema.__pydantic_decorators__.model_validators)

    # ----- Utility method tests -----

    def test_collect_validators_returns_empty_for_none(self):
        """Test _collect_validators returns empty dict for None input."""
        result = serializers.BaseSerializer._collect_validators(None)
        self.assertEqual(result, {})

    def test_collect_validators_returns_empty_for_no_validators(self):
        """Test _collect_validators returns empty dict for class without validators."""

        class PlainClass:
            fields = ["name"]

        result = serializers.BaseSerializer._collect_validators(PlainClass)
        self.assertEqual(result, {})

    def test_apply_validators_returns_none_for_none_schema(self):
        """Test _apply_validators returns None when schema is None."""
        result = serializers.BaseSerializer._apply_validators(None, {"v": "val"})
        self.assertIsNone(result)

    def test_apply_validators_returns_schema_for_empty_validators(self):
        """Test _apply_validators returns original schema when no validators."""
        from ninja import Schema

        class MySchema(Schema):
            name: str

        result = serializers.BaseSerializer._apply_validators(MySchema, {})
        self.assertIs(result, MySchema)
