from . import models
from ninja_aio.models import serializers


class TestModelForeignKeySerializer(serializers.Serializer):
    class Meta:
        model = models.TestModelForeignKey
        schema_in = serializers.SchemaModelConfig(
            fields=["name", "description", "test_model"]
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description", "test_model"]
        )
        schema_update = serializers.SchemaModelConfig(
            optionals=[("name", str), ("description", str)]
        )


class TestModelReverseForeignKeySerializer(serializers.Serializer):
    class Meta:
        model = models.TestModelReverseForeignKey
        schema_in = serializers.SchemaModelConfig(fields=["name", "description"])
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description", "test_model_foreign_keys"]
        )
        schema_update = serializers.SchemaModelConfig(
            optionals=[("name", str), ("description", str)]
        )
        relations_serializers = {
            "test_model_foreign_keys": TestModelForeignKeySerializer,
        }


class TestModelOneToOneSerializer(serializers.Serializer):
    """Serializer for TestModelOneToOne to test ForwardOneToOneDescriptor coverage."""

    class Meta:
        model = models.TestModelOneToOne
        schema_in = serializers.SchemaModelConfig(
            fields=["name", "description", "test_model"]
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description", "test_model"]
        )
        schema_update = serializers.SchemaModelConfig(
            optionals=[("name", str), ("description", str)]
        )


# ==========================================================
#              RELATIONS AS ID TEST SERIALIZERS
# ==========================================================


class BookAsIdMetaSerializer(serializers.Serializer):
    """Serializer for testing relations_as_id on forward FK with Meta-driven Serializer."""

    class Meta:
        model = models.TestModelForeignKey
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description", "test_model"]
        )
        relations_as_id = ["test_model"]


class AuthorAsIdMetaSerializer(serializers.Serializer):
    """Serializer for testing relations_as_id on reverse FK with Meta-driven Serializer."""

    class Meta:
        model = models.TestModelReverseForeignKey
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description", "test_model_foreign_keys"]
        )
        relations_as_id = ["test_model_foreign_keys"]


class UserAsIdMetaSerializer(serializers.Serializer):
    """Serializer for testing relations_as_id on forward O2O with Meta-driven Serializer."""

    class Meta:
        model = models.TestModelOneToOne
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description", "test_model"]
        )
        relations_as_id = ["test_model"]


class ProfileAsIdMetaSerializer(serializers.Serializer):
    """Serializer for testing relations_as_id on reverse O2O with Meta-driven Serializer."""

    class Meta:
        model = models.TestModelReverseOneToOne
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description", "test_model_one_to_one"]
        )
        relations_as_id = ["test_model_one_to_one"]


class ArticleAsIdMetaSerializer(serializers.Serializer):
    """Serializer for testing relations_as_id on forward M2M with Meta-driven Serializer."""

    class Meta:
        model = models.TestModelManyToMany
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description", "test_models"]
        )
        relations_as_id = ["test_models"]


class TagAsIdMetaSerializer(serializers.Serializer):
    """Serializer for testing relations_as_id on reverse M2M with Meta-driven Serializer."""

    class Meta:
        model = models.TestModelReverseManyToMany
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "description", "test_model_serializer_many_to_many"]
        )
        relations_as_id = ["test_model_serializer_many_to_many"]
