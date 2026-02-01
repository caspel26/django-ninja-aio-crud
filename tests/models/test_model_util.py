from django.test import tag, TestCase
from unittest import mock

from ninja.errors import ConfigError
from ninja_aio.models import ModelUtil
from tests.test_app import models, schema
from tests.generics.models import Tests


class BaseTests:
    class ModelUtilTestCaseBase(Tests.GenericModelUtilTestCase):
        @property
        def create_data(self):
            return {"name": "test", "description": "test"}

        @property
        def parsed_input_data(self):
            return {"payload": self.create_data}

        @property
        def read_data(self):
            return {"id": 1, "name": "test", "description": "test"}

        @property
        def additional_getters(self):
            return {"description": "test"}

        @property
        def additional_filters(self):
            return {"name": "test"}

    @tag("model_util_model_serializer")
    class ModelUtilModelSerializerTestCase(ModelUtilTestCaseBase):
        @property
        def serializable_fields(self):
            return self.model.ReadSerializer.fields

    @tag("model_util_model")
    class ModelUtilModelBaseTestCase(ModelUtilTestCaseBase):
        @property
        def serializable_fields(self):
            return ["id", "name", "description"]


@tag("model_util_model_serializer_base")
class ModelUtilModelSerializerBaseTestCase(BaseTests.ModelUtilModelSerializerTestCase):
    model = models.TestModelSerializer

    @property
    def model_verbose_name_path(self):
        return "test-model-serializers"

    @property
    def model_verbose_name_view(self):
        return "testmodelserializers"


@tag("model_util_model_base")
class ModelUtilModelBaseTestCase(BaseTests.ModelUtilModelBaseTestCase):
    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_patch = schema.TestModelSchemaPatch

    @property
    def model_verbose_name_path(self):
        return "test-models"

    @property
    def model_verbose_name_view(self):
        return "testmodels"


@tag("model_util_config_error")
class ModelUtilConfigErrorTestCase(TestCase):
    """Test ModelUtil ConfigError edge cases (covers lines 113-115)."""

    def test_model_util_raises_config_error_for_model_serializer_with_serializer_class(
        self,
    ):
        """Test that ModelUtil raises ConfigError when both model is ModelSerializer and serializer_class is provided."""
        from tests.test_app.serializers import TestModelForeignKeySerializer

        with self.assertRaises(ConfigError) as ctx:
            ModelUtil(
                models.TestModelSerializer,
                serializer_class=TestModelForeignKeySerializer,
            )

        self.assertIn(
            "cannot accept both model and serializer_class", str(ctx.exception)
        )


@tag("model_util_pk_field_type")
class ModelUtilPkFieldTypeTestCase(TestCase):
    """Test ModelUtil pk_field_type error handling (covers lines 152-158)."""

    def test_pk_field_type_raises_config_error_for_unknown_type(self):
        """Test that pk_field_type raises ConfigError for unknown field types."""
        from ninja.orm import fields

        # Create a mock model with an unknown pk field type
        mock_pk_field = mock.Mock()
        mock_pk_field.get_internal_type.return_value = "UnknownFieldType"

        mock_meta = mock.Mock()
        mock_meta.pk = mock_pk_field

        mock_model = mock.Mock()
        mock_model._meta = mock_meta

        util = ModelUtil(mock_model)

        # Temporarily remove the key if it exists to ensure KeyError
        original_types = fields.TYPES.copy()
        fields.TYPES.pop("UnknownFieldType", None)

        try:
            with self.assertRaises(ConfigError) as ctx:
                _ = util.pk_field_type

            self.assertIn("Do not know how to convert", str(ctx.exception))
            self.assertIn("UnknownFieldType", str(ctx.exception))
        finally:
            # Restore original types
            fields.TYPES.update(original_types)


@tag("model_util_objects_query_default")
class ModelUtilObjectsQueryDefaultTestCase(TestCase):
    """Test ModelUtil get_objects with default ObjectsQuerySchema (covers line 351)."""

    async def test_get_objects_with_none_query_data_uses_default(self):
        """Test that get_objects uses default ObjectsQuerySchema when query_data is None."""
        # Create a test object
        obj = await models.TestModel.objects.acreate(name="test", description="desc")

        util = ModelUtil(models.TestModel)

        # Create a mock request
        request = mock.Mock()

        # Call get_objects with query_data=None (will use default ObjectsQuerySchema)
        qs = await util.get_objects(request, query_data=None)

        # Should return a queryset
        count = await qs.acount()
        self.assertGreaterEqual(count, 1)

        # Cleanup
        await obj.adelete()
