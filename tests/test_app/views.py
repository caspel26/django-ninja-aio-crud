from tests.generics.views import GenericAPIViewSet
from tests.test_app import models
from tests.test_app import schema

# ==========================================================
#                  MODEL SERIALIZERS APIS
# ==========================================================


class TestModelSerializerAPI(GenericAPIViewSet):
    model = models.TestModelSerializer


class TestModelSerializerReverseForeignKeyAPI(GenericAPIViewSet):
    model = models.TestModelSerializerReverseForeignKey


class TestModelSerializerForeignKeyAPI(GenericAPIViewSet):
    model = models.TestModelSerializerForeignKey


class TestModelSerializerOneToOneAPI(GenericAPIViewSet):
    model = models.TestModelSerializerOneToOne


class TestModelSerializerReverseOneToOneAPI(GenericAPIViewSet):
    model = models.TestModelSerializerReverseOneToOne


class TestModelSerializerManyToManyAPI(GenericAPIViewSet):
    model = models.TestModelSerializerManyToMany


class TestModelSerializerReverseManyToManyAPI(GenericAPIViewSet):
    model = models.TestModelSerializerReverseManyToMany


# ==========================================================
#                       MODEL APIS
# ==========================================================


class TestModelAPI(GenericAPIViewSet):
    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelReverseForeignKeyAPI(GenericAPIViewSet):
    model = models.TestModelReverseForeignKey
    schema_in = schema.TestModelReverseForeignKeySchemaIn
    schema_out = schema.TestModelReverseForeignKeySchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelForeignKeyAPI(GenericAPIViewSet):
    model = models.TestModelForeignKey
    schema_in = schema.TestModelForeignKeySchemaIn
    schema_out = schema.TestModelForeignKeySchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelReverseOneToOneAPI(GenericAPIViewSet):
    model = models.TestModelReverseOneToOne
    schema_in = schema.TestModelReverseForeignKeySchemaIn
    schema_out = schema.TestModelReverseOneToOneSchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelOneToOneAPI(GenericAPIViewSet):
    model = models.TestModelOneToOne
    schema_in = schema.TestModelForeignKeySchemaIn
    schema_out = schema.TestModelForeignKeySchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelManyToManyAPI(GenericAPIViewSet):
    model = models.TestModelManyToMany
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelManyToManySchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelReverseManyToManyAPI(GenericAPIViewSet):
    model = models.TestModelReverseManyToMany
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelReverseManyToManySchemaOut
    schema_update = schema.TestModelSchemaPatch
