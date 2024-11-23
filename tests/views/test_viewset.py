from django.test import tag

from tests.generics.views import Tests
from tests.test_app.views import TestModelSerializerAPI, TestModelAPI
from tests.test_app.models import TestModelSerializer, TestModel
from tests.test_app.schema import (
    TestModelSchemaIn,
    TestModelSchemaOut,
    TestModelSchemaPatch,
)


class BaseTests:
    class ApiViewSetTestCaseBase(Tests.GenericViewSetTestCase):
        @property
        def payload_create(self):
            return {
                "name": f"test_name_{self.model._meta.model_name}",
                "description": f"test_description_{self.model._meta.model_name}",
            }

        @property
        def payload_update(self):
            return {
                "description": f"test_description_{self.model._meta.model_name}_update",
            }

        @property
        def response_data(self):
            return self.payload_create


@tag("model_serializer_viewset")
class ApiViewSetModelSerializerTestCase(BaseTests.ApiViewSetTestCaseBase):
    namespace = "test_model_serializer_viewset"
    model = TestModelSerializer
    viewset = TestModelSerializerAPI()

    @property
    def schemas(self):
        return (
            self.model.generate_read_s(),
            self.model.generate_create_s(),
            self.model.generate_update_s(),
        )


@tag("model_viewset")
class ApiViewSetModelTestCase(BaseTests.ApiViewSetTestCaseBase):
    namespace = "test_model_viewset"
    model = TestModel
    viewset = TestModelAPI()

    @property
    def schemas(self):
        return (
            TestModelSchemaOut,
            TestModelSchemaIn,
            TestModelSchemaPatch,
        )
