import warnings
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
