from django.test import tag

from tests.generics.views import Tests
from tests.test_app import schema, models, views


class BaseTests:
    class ApiViewSetTestCaseBase(Tests.GenericViewSetTestCase):
        @property
        def _payload(self):
            return {
                "name": f"test_name_{self.model._meta.model_name}",
                "description": f"test_description_{self.model._meta.model_name}",
            }

        @property
        def payload_create(self):
            return self._payload

        @property
        def payload_update(self):
            return {
                "description": f"test_description_{self.model._meta.model_name}_update",
            }

        @property
        def response_data(self):
            return self._payload

    class ModelSerializerViewSetTestCaseBase(ApiViewSetTestCaseBase):
        @property
        def schemas(self):
            return (
                self.model.generate_read_s(),
                self.model.generate_create_s(),
                self.model.generate_update_s(),
            )

    @tag("viewset_foreign_key")
    class ApiViewSetForeignKeyTestCaseBase(
        ApiViewSetTestCaseBase, Tests.GenericRelationViewSetTestCase
    ):
        @property
        def payload_create(self):
            return super().payload_create | {
                "test_model_serializer_id": self.relation_pk
            }


"""
MODEL SERIALIZER VIEWSET TESTS
"""


@tag("model_serializer_viewset")
class ApiViewSetModelSerializerTestCase(BaseTests.ModelSerializerViewSetTestCaseBase):
    namespace = "test_model_serializer_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerAPI()


@tag("model_serializer_foreign_key_viewset")
class ApiViewSetModelSerializerForeignKeyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetForeignKeyTestCaseBase,
):
    namespace = "test_model_serializer_foreign_key_viewset"
    model = models.TestModelSerializerForeignKey
    viewset = views.TestModelSerializerForeignKeyAPI()
    relation_viewset = views.TestModelSerializerReverseForeignKeyAPI()

    @classmethod
    def setUpTestData(cls):
        cls.relation_data = {
            "name": f"test_name_{cls.relation_viewset.model._meta.model_name}",
            "description": f"test_description_{cls.relation_viewset.model._meta.model_name}",
        }
        super().setUpTestData()

    @property
    def response_data(self):
        return super().response_data | {"test_model_serializer": self.relation_obj}


"""
MODEL VIEWSET TESTS
"""


@tag("model_viewset")
class ApiViewSetModelTestCase(BaseTests.ApiViewSetTestCaseBase):
    namespace = "test_model_viewset"
    model = models.TestModel
    viewset = views.TestModelAPI()

    @property
    def schemas(self):
        return (
            schema.TestModelSchemaOut,
            schema.TestModelSchemaIn,
            schema.TestModelSchemaPatch,
        )


@tag("model_foreign_key_viewset")
class ApiViewSetModelForeignKeyTestCase(BaseTests.ApiViewSetForeignKeyTestCaseBase):
    namespace = "test_model_foreign_key_viewset"
    model = models.TestModelForeignKey
    viewset = views.TestModelForeignKeyAPI()
    relation_viewset = views.TestModelReverseForeignKeyAPI()

    @property
    def schemas(self):
        return (
            schema.TestModelForeignKeySchemaOut,
            schema.TestModelForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
        )

    @classmethod
    def setUpTestData(cls):
        cls.relation_data = {
            "name": f"test_name_{cls.relation_viewset.model._meta.model_name}",
            "description": f"test_description_{cls.relation_viewset.model._meta.model_name}",
        }
        super().setUpTestData()

    @property
    def payload_create(self):
        payload = super().payload_create
        payload.pop("test_model_serializer_id")
        return payload | {"test_model_serializer": self.relation_pk}

    @property
    def response_data(self):
        return super().response_data | {"test_model_serializer": self.relation_obj}
