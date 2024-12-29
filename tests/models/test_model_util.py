from django.test import tag

from tests.test_app import models
from tests.generics.models import Tests


@tag("model_util_model_serializer_base")
class ModelUtilModelSerializerBaseTestCase(Tests.ModelUtilTestCaseBase):
    model = models.TestModelSerializer

    @property
    def serializable_fields(self):
        return self.model.ReadSerializer.fields

    @property
    def model_verbose_name_path(self):
        return "test-model-serializers"

    @property
    def model_verbose_name_view(self):
        return "testmodelserializers"

    @property
    def create_data(self):
        return {"name": "test", "description": "test"}
