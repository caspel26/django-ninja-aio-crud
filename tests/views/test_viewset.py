from django.test import tag

from tests.generics.views import Tests
from tests.test_app import schema, models, views


class BaseTests:
    class SetUpViewSetTestCase:
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

        @property
        def create_response_data(self):
            return self.response_data

    class ModelSerializerViewSetTestCaseBase(SetUpViewSetTestCase):
        @property
        def schemas(self):
            return (
                self.model.generate_read_s(),
                self.model.generate_create_s(),
                self.model.generate_update_s(),
            )

    class ApiViewSetSetUpRelation(SetUpViewSetTestCase):
        relation_viewset: views.GenericAPIViewSet

        @classmethod
        def setUpTestData(cls):
            cls.relation_data = {
                "name": f"test_name_{cls.relation_viewset.model._meta.model_name}",
                "description": f"test_description_{cls.relation_viewset.model._meta.model_name}",
            }
            super().setUpTestData()

    @tag("viewset_foreign_key")
    class ApiViewSetForeignKeyTestCaseBase(
        ApiViewSetSetUpRelation, Tests.RelationViewSetTestCase
    ):
        @property
        def payload_create(self):
            return super().payload_create | {
                "test_model_serializer_id": self.relation_pk
            }

        @property
        def response_data(self):
            return super().response_data | {
                self.relation_related_name: self.relation_obj
            }

    @tag("viewset_reverse_foreign_key")
    class ApiViewSetReverseForeignKeyTestCaseBase(
        ApiViewSetSetUpRelation, Tests.ReverseRelationViewSetTestCase
    ):
        @property
        def response_data(self):
            return super().response_data | {
                self.relation_related_name: [self.relation_schema_data]
            }

        @property
        def create_response_data(self):
            return super().response_data | {self.relation_related_name: []}

    @tag("viewset_many_to_many")
    class ApiViewSetManyToManyTestCaseBase(
        ApiViewSetSetUpRelation, Tests.RelationViewSetTestCase
    ):
        @classmethod
        def setUpTestData(cls):
            super().setUpTestData()
            obj = cls.model.objects.get(pk=cls.obj_content[cls.pk_att])
            getattr(obj, cls.relation_related_name).add(cls.relation_obj)
            obj.save()
            cls.relation_schema_data.pop(cls.foreign_key_reverse_field, None)

        @property
        def response_data(self):
            return super().response_data | {
                self.relation_related_name: [self.relation_schema_data]
            }

        @property
        def create_response_data(self):
            return super().response_data | {self.relation_related_name: []}


# ==========================================================
#             MODEL SERIALIZER VIEWSET TESTS
# ==========================================================


@tag("model_serializer_viewset")
class ApiViewSetModelSerializerTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
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
    relation_related_name = "test_model_serializer"


@tag("model_serializer_reverse_foreign_key_viewset")
class ApiViewSetModelSerializerReverseForeignKeyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetReverseForeignKeyTestCaseBase,
):
    namespace = "test_model_serializer_reverse_foreign_key_viewset"
    model = models.TestModelSerializerReverseForeignKey
    viewset = views.TestModelSerializerReverseForeignKeyAPI()
    relation_viewset = views.TestModelSerializerForeignKeyAPI()
    relation_related_name = "test_model_serializer_foreign_keys"
    foreign_key_field = "test_model_serializer"


@tag("model_serializer_one_to_one_viewset")
class ApiViewSetModelSerializerOneToOneTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetForeignKeyTestCaseBase,
):
    namespace = "test_model_serializer_one_to_one_viewset"
    model = models.TestModelSerializerOneToOne
    viewset = views.TestModelSerializerOneToOneAPI()
    relation_viewset = views.TestModelSerializerReverseOneToOneAPI()
    relation_related_name = "test_model_serializer"


@tag("model_serializer_reverse_one_to_one_viewset")
class ApiViewSetModelSerializerReverseOneToOneTestCase(
    ApiViewSetModelSerializerReverseForeignKeyTestCase
):
    namespace = "test_model_serializer_reverse_one_to_one_viewset"
    model = models.TestModelSerializerReverseOneToOne
    viewset = views.TestModelSerializerReverseOneToOneAPI()
    relation_viewset = views.TestModelSerializerOneToOneAPI()
    relation_related_name = "test_model_serializer_one_to_one"

    @property
    def response_data(self):
        return super().response_data | {
            self.relation_related_name: self.relation_schema_data
        }

    @property
    def create_response_data(self):
        return super().response_data | {self.relation_related_name: None}


@tag("model_serializer_many_to_many_viewset")
class ApiViewSetModelSerializerManyToManyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetManyToManyTestCaseBase,
):
    namespace = "test_model_serializer_many_to_many_viewset"
    model = models.TestModelSerializerManyToMany
    viewset = views.TestModelSerializerManyToManyAPI()
    relation_viewset = views.TestModelSerializerReverseManyToManyAPI()
    relation_related_name = "test_model_serializers"
    foreign_key_reverse_field = "test_model_serializer_many_to_many"


@tag("model_serializer_reverse_many_to_many_viewset")
class ApiViewSetModelSerializerReverseManyToManyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetManyToManyTestCaseBase,
):
    namespace = "test_model_serializer_reverse_many_to_many_viewset"
    model = models.TestModelSerializerReverseManyToMany
    viewset = views.TestModelSerializerReverseManyToManyAPI()
    relation_viewset = views.TestModelSerializerManyToManyAPI()
    relation_related_name = "test_model_serializer_many_to_many"
    foreign_key_reverse_field = "test_model_serializers"


# ==========================================================
#                      MODEL VIEWSET TESTS
# ==========================================================


@tag("model_viewset")
class ApiViewSetModelTestCase(
    BaseTests.SetUpViewSetTestCase,
    Tests.ViewSetTestCase,
):
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
    relation_related_name = "test_model"

    @property
    def schemas(self):
        return (
            schema.TestModelForeignKeySchemaOut,
            schema.TestModelForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
        )

    @property
    def payload_create(self):
        payload = super().payload_create
        payload.pop("test_model_serializer_id")
        return payload | {self.relation_related_name: self.relation_pk}


class ApiViewSetModelReverseForeignKeyTestCase(
    BaseTests.ApiViewSetReverseForeignKeyTestCaseBase
):
    namespace = "test_model_reverse_foreign_key_viewset"
    model = models.TestModelReverseForeignKey
    viewset = views.TestModelReverseForeignKeyAPI()
    relation_viewset = views.TestModelForeignKeyAPI()
    relation_related_name = "test_model_foreign_keys"
    foreign_key_field = "test_model"

    @property
    def schemas(self):
        return (
            schema.TestModelReverseForeignKeySchemaOut,
            schema.TestModelReverseForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
        )


@tag("model_one_to_one_viewset")
class ApiViewSetModelOneToOneTestCase(ApiViewSetModelForeignKeyTestCase):
    namespace = "test_model_one_to_one_viewset"
    model = models.TestModelOneToOne
    viewset = views.TestModelOneToOneAPI()
    relation_viewset = views.TestModelReverseOneToOneAPI()

    @property
    def schemas(self):
        return (
            schema.TestModelForeignKeySchemaOut,
            schema.TestModelForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
        )


@tag("model_reverse_one_to_one_viewset")
class ApiViewSetModelReverseOneToOneTestCase(ApiViewSetModelReverseForeignKeyTestCase):
    namespace = "test_model_reverse_one_to_one_viewset"
    model = models.TestModelReverseOneToOne
    viewset = views.TestModelReverseOneToOneAPI()
    relation_viewset = views.TestModelOneToOneAPI()
    relation_related_name = "test_model_one_to_one"

    @property
    def schemas(self):
        return (
            schema.TestModelReverseOneToOneSchemaOut,
            schema.TestModelReverseForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
        )

    @property
    def response_data(self):
        return super().response_data | {
            self.relation_related_name: self.relation_schema_data
        }

    @property
    def create_response_data(self):
        return super().response_data | {self.relation_related_name: None}


@tag("model_many_to_many_viewset")
class ApiViewSetModelManyToManyTestCase(BaseTests.ApiViewSetManyToManyTestCaseBase):
    namespace = "test_model_many_to_many_viewset"
    model = models.TestModelManyToMany
    viewset = views.TestModelManyToManyAPI()
    relation_viewset = views.TestModelReverseManyToManyAPI()
    relation_related_name = "test_models"
    foreign_key_reverse_field = "test_model_serializer_many_to_many"

    @property
    def schemas(self):
        return (
            schema.TestModelManyToManySchemaOut,
            schema.TestModelSchemaIn,
            schema.TestModelSchemaPatch,
        )


@tag("model_reverse_many_to_many_viewset")
class ApiViewSetModelReverseManyToManyTestCase(
    BaseTests.ApiViewSetManyToManyTestCaseBase
):
    namespace = "test_model_reverse_many_to_many_viewset"
    model = models.TestModelReverseManyToMany
    viewset = views.TestModelReverseManyToManyAPI()
    relation_viewset = views.TestModelManyToManyAPI()
    relation_related_name = "test_model_serializer_many_to_many"
    foreign_key_reverse_field = "test_models"

    @property
    def schemas(self):
        return (
            schema.TestModelReverseManyToManySchemaOut,
            schema.TestModelSchemaIn,
            schema.TestModelSchemaPatch,
        )
