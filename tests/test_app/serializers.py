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
