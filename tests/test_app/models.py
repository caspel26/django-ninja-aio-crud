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
    status = models.CharField(max_length=20, default="pending")


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


class TestModelSerializerWithDetail(BaseTestModelSerializer):
    """Model with separate read and detail serializer configurations."""

    extra_info = models.TextField(blank=True, default="")

    class ReadSerializer:
        fields = ["id", "name"]

    class DetailSerializer:
        fields = ["id", "name", "description", "extra_info"]
        customs = [("computed_field", str, "computed_value")]


class TestModelSerializerWithReadCustoms(BaseTestModelSerializer):
    """Model with customs on ReadSerializer but no DetailSerializer."""

    class ReadSerializer:
        fields = ["id", "name"]
        customs = [("custom_field", str, "default")]


class TestModelSerializerWithReadOptionals(BaseTestModelSerializer):
    """Model with optionals on ReadSerializer but no DetailSerializer."""

    class ReadSerializer:
        fields = ["id", "name"]
        optionals = [("description", str)]


class TestModelSerializerWithReadExcludes(BaseTestModelSerializer):
    """Model with excludes on ReadSerializer but no DetailSerializer."""

    class ReadSerializer:
        fields = ["id", "name", "description"]
        excludes = ["description"]


class TestModelSerializerWithBothSerializers(BaseTestModelSerializer):
    """Model with both ReadSerializer and DetailSerializer configured."""

    class ReadSerializer:
        fields = ["id", "name"]
        customs = [("read_custom", str, "default")]

    class DetailSerializer:
        fields = ["id", "name", "description"]
        # No customs defined - should NOT inherit from read


# ==========================================================
#              RELATIONS AS ID TEST MODELS
# ==========================================================


class AuthorAsId(BaseTestModelSerializer):
    """Author model for testing relations_as_id on reverse FK."""

    class ReadSerializer:
        fields = ["id", "name", "description", "books_as_id"]
        relations_as_id = ["books_as_id"]


class BookAsId(BaseTestModelSerializer):
    """Book model for testing relations_as_id on forward FK."""

    author_as_id = models.ForeignKey(
        AuthorAsId,
        on_delete=models.CASCADE,
        related_name="books_as_id",
        null=True,
        blank=True,
    )

    class ReadSerializer:
        fields = ["id", "name", "description", "author_as_id"]
        relations_as_id = ["author_as_id"]


class ProfileAsId(BaseTestModelSerializer):
    """Profile model for testing relations_as_id on reverse O2O."""

    class ReadSerializer:
        fields = ["id", "name", "description", "user_profile_as_id"]
        relations_as_id = ["user_profile_as_id"]


class UserAsId(BaseTestModelSerializer):
    """User model for testing relations_as_id on forward O2O."""

    profile_as_id = models.OneToOneField(
        ProfileAsId,
        on_delete=models.CASCADE,
        related_name="user_profile_as_id",
        null=True,
        blank=True,
    )

    class ReadSerializer:
        fields = ["id", "name", "description", "profile_as_id"]
        relations_as_id = ["profile_as_id"]


class TagAsId(BaseTestModelSerializer):
    """Tag model for testing relations_as_id on reverse M2M."""

    class ReadSerializer:
        fields = ["id", "name", "description", "articles_as_id"]
        relations_as_id = ["articles_as_id"]


class ArticleAsId(BaseTestModelSerializer):
    """Article model for testing relations_as_id on forward M2M."""

    tags_as_id = models.ManyToManyField(
        TagAsId,
        related_name="articles_as_id",
        blank=True,
    )

    class ReadSerializer:
        fields = ["id", "name", "description", "tags_as_id"]
        relations_as_id = ["tags_as_id"]
