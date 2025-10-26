from django.test import tag

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
