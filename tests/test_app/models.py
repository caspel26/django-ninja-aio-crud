from ninja_aio.models import ModelSerializer
from django.db import models

from ninja_aio.schemas.helpers import ModelQuerySetExtraSchema, ModelQuerySetSchema


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


class TestModelReverseManyToMany(BaseTestModel):
    pass


class TestModelManyToMany(BaseTestModel):
    test_models = models.ManyToManyField(
        TestModelReverseManyToMany,
        related_name="test_model_serializer_many_to_many",
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
    age = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    active_from = models.DateTimeField(auto_now_add=True)


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

    class QuerySet:
        read = ModelQuerySetSchema(
            select_related=["test_model_serializer"],
            prefetch_related=[],
        )
        extras = [
            ModelQuerySetExtraSchema(
                scope="custom_scope",
                select_related=["test_model_serializer"],
                prefetch_related=[],
            )
        ]

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


class TestModelSerializerReverseManyToMany(BaseTestModelSerializer):
    class ReadSerializer:
        fields = BaseTestModelSerializer.ReadSerializer.fields + [
            "test_model_serializer_many_to_many",
        ]


class TestModelSerializerManyToMany(BaseTestModelSerializer):
    test_model_serializers = models.ManyToManyField(
        TestModelSerializerReverseManyToMany,
        related_name="test_model_serializer_many_to_many",
    )

    class QuerySet:
        queryset_request = ModelQuerySetSchema(
            select_related=[],
            prefetch_related=["test_model_serializers"],
        )

    class ReadSerializer:
        fields = BaseTestModelSerializer.ReadSerializer.fields + [
            "test_model_serializers"
        ]

    class CreateSerializer:
        fields = BaseTestModelSerializer.CreateSerializer.fields
