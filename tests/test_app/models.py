import uuid

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


class TestModelSerializerInlineCustoms(BaseTestModelSerializer):
    """Model with inline custom fields defined directly in the fields list."""

    class ReadSerializer:
        fields = ["id", "name", ("inline_computed", str, "computed_value")]

    class CreateSerializer:
        fields = ["name", ("extra_create_input", str, "")]


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


# ==========================================================
#          RELATIONS AS ID WITH UUID PK TEST MODELS
# ==========================================================


class BaseUUIDTestModel(ModelSerializer):
    """Base model with UUID primary key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)

    class Meta:
        abstract = True

    class ReadSerializer:
        fields = ["id", "name"]


class AuthorUUID(BaseUUIDTestModel):
    """Author model with UUID PK for testing relations_as_id on reverse FK."""

    class ReadSerializer:
        fields = ["id", "name", "books_uuid"]
        relations_as_id = ["books_uuid"]


class BookUUID(BaseUUIDTestModel):
    """Book model with UUID PK for testing relations_as_id on forward FK."""

    author_uuid = models.ForeignKey(
        AuthorUUID,
        on_delete=models.CASCADE,
        related_name="books_uuid",
        null=True,
        blank=True,
    )

    class ReadSerializer:
        fields = ["id", "name", "author_uuid"]
        relations_as_id = ["author_uuid"]


class ProfileUUID(BaseUUIDTestModel):
    """Profile model with UUID PK for testing relations_as_id on reverse O2O."""

    class ReadSerializer:
        fields = ["id", "name", "user_uuid"]
        relations_as_id = ["user_uuid"]


class UserUUID(BaseUUIDTestModel):
    """User model with UUID PK for testing relations_as_id on forward O2O."""

    profile_uuid = models.OneToOneField(
        ProfileUUID,
        on_delete=models.CASCADE,
        related_name="user_uuid",
        null=True,
        blank=True,
    )

    class ReadSerializer:
        fields = ["id", "name", "profile_uuid"]
        relations_as_id = ["profile_uuid"]


class TagUUID(BaseUUIDTestModel):
    """Tag model with UUID PK for testing relations_as_id on reverse M2M."""

    class ReadSerializer:
        fields = ["id", "name", "articles_uuid"]
        relations_as_id = ["articles_uuid"]


class ArticleUUID(BaseUUIDTestModel):
    """Article model with UUID PK for testing relations_as_id on forward M2M."""

    tags_uuid = models.ManyToManyField(
        TagUUID,
        related_name="articles_uuid",
        blank=True,
    )

    class ReadSerializer:
        fields = ["id", "name", "tags_uuid"]
        relations_as_id = ["tags_uuid"]


# ==========================================================
#        RELATIONS AS ID WITH STRING PK TEST MODELS
# ==========================================================


class BaseStringPKTestModel(ModelSerializer):
    """Base model with string (CharField) primary key."""

    id = models.CharField(primary_key=True, max_length=50)
    name = models.CharField(max_length=255)

    class Meta:
        abstract = True

    class ReadSerializer:
        fields = ["id", "name"]


class AuthorStringPK(BaseStringPKTestModel):
    """Author model with string PK for testing relations_as_id on reverse FK."""

    class ReadSerializer:
        fields = ["id", "name", "books_str"]
        relations_as_id = ["books_str"]


class BookStringPK(BaseStringPKTestModel):
    """Book model with string PK for testing relations_as_id on forward FK."""

    author_str = models.ForeignKey(
        AuthorStringPK,
        on_delete=models.CASCADE,
        related_name="books_str",
        null=True,
        blank=True,
    )

    class ReadSerializer:
        fields = ["id", "name", "author_str"]
        relations_as_id = ["author_str"]


class ProfileStringPK(BaseStringPKTestModel):
    """Profile model with string PK for testing relations_as_id on reverse O2O."""

    class ReadSerializer:
        fields = ["id", "name", "user_str"]
        relations_as_id = ["user_str"]


class UserStringPK(BaseStringPKTestModel):
    """User model with string PK for testing relations_as_id on forward O2O."""

    profile_str = models.OneToOneField(
        ProfileStringPK,
        on_delete=models.CASCADE,
        related_name="user_str",
        null=True,
        blank=True,
    )

    class ReadSerializer:
        fields = ["id", "name", "profile_str"]
        relations_as_id = ["profile_str"]


class TagStringPK(BaseStringPKTestModel):
    """Tag model with string PK for testing relations_as_id on reverse M2M."""

    class ReadSerializer:
        fields = ["id", "name", "articles_str"]
        relations_as_id = ["articles_str"]


class ArticleStringPK(BaseStringPKTestModel):
    """Article model with string PK for testing relations_as_id on forward M2M."""

    tags_str = models.ManyToManyField(
        TagStringPK,
        related_name="articles_str",
        blank=True,
    )

    class ReadSerializer:
        fields = ["id", "name", "tags_str"]
        relations_as_id = ["tags_str"]


# ==========================================================
#                VALIDATOR TEST MODELS
# ==========================================================


class TestModelWithValidators(BaseTestModelSerializer):
    """ModelSerializer with field_validator and model_validator on inner classes."""

    from pydantic import field_validator, model_validator

    class CreateSerializer:
        from pydantic import field_validator, model_validator

        fields = ["name", "description"]

        @field_validator("name")
        @classmethod
        def validate_name_min_length(cls, v):
            if len(v) < 3:
                raise ValueError("Name must be at least 3 characters")
            return v

    class UpdateSerializer:
        from pydantic import field_validator

        optionals = [("name", str), ("description", str)]

        @field_validator("name")
        @classmethod
        def validate_name_not_empty(cls, v):
            if v is not None and len(v.strip()) == 0:
                raise ValueError("Name cannot be blank")
            return v

    class ReadSerializer:
        from pydantic import model_validator

        fields = ["id", "name", "description"]

        @model_validator(mode="after")
        def add_display_check(self):
            return self
