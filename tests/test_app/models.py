from ninja_aio.models import ModelSerializer
from django.db import models


# ==========================================================
#                       MODELS
# ==========================================================


class BaseTestModel(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(max_length=255)

    class Meta:
        abstract = True


class TestModel(BaseTestModel):
    pass


class TestModelReverseForeignKey(BaseTestModel):
    pass


class TestModelForeignKey(BaseTestModel):
    test_model = models.ForeignKey(
        TestModelReverseForeignKey,
        on_delete=models.CASCADE,
        related_name="test_model_foreign_keys",
    )


class TestModelReverseOneToOne(BaseTestModel):
    pass


class TestModelOneToOne(BaseTestModel):
    test_model = models.OneToOneField(
        TestModelReverseOneToOne,
        on_delete=models.CASCADE,
        related_name="test_model_one_to_one",
    )


# ==========================================================
#                    MODEL SERIALIZERS
# ==========================================================


class BaseTestModelSerializer(ModelSerializer):
    name = models.CharField(max_length=255)
    description = models.TextField(max_length=255)

    class Meta:
        abstract = True

    class ReadSerializer:
        fields = ["id", "name", "description"]

    class CreateSerializer:
        fields = ["name", "description"]

    class UpdateSerializer:
        fields = ["description"]


class TestModelSerializer(BaseTestModelSerializer):
    pass


class TestModelSerializerReverseForeignKey(BaseTestModelSerializer):
    class ReadSerializer:
        fields = BaseTestModelSerializer.ReadSerializer.fields + [
            "test_model_serializer_foreign_keys"
        ]


class TestModelSerializerForeignKey(BaseTestModelSerializer):
    test_model_serializer = models.ForeignKey(
        TestModelSerializerReverseForeignKey,
        on_delete=models.CASCADE,
        related_name="test_model_serializer_foreign_keys",
    )

    class ReadSerializer:
        fields = BaseTestModelSerializer.ReadSerializer.fields + [
            "test_model_serializer"
        ]

    class CreateSerializer:
        fields = BaseTestModelSerializer.CreateSerializer.fields + [
            "test_model_serializer"
        ]


class TestModelSerializerReverseOneToOne(BaseTestModelSerializer):
    class ReadSerializer:
        fields = BaseTestModelSerializer.ReadSerializer.fields + [
            "test_model_serializer_one_to_one"
        ]


class TestModelSerializerOneToOne(BaseTestModelSerializer):
    test_model_serializer = models.OneToOneField(
        TestModelSerializerReverseOneToOne,
        on_delete=models.CASCADE,
        related_name="test_model_serializer_one_to_one",
    )

    class ReadSerializer:
        fields = BaseTestModelSerializer.ReadSerializer.fields + [
            "test_model_serializer"
        ]

    class CreateSerializer:
        fields = BaseTestModelSerializer.CreateSerializer.fields + [
            "test_model_serializer"
        ]
