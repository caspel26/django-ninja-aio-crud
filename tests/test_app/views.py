from tests.generics.views import GenericAPI
from tests.test_app import models
from tests.test_app import schema

# ==========================================================
#                  MODEL SERIALIZERS APIS
# ==========================================================


class TestModelSerializerAPI(GenericAPI):
    model = models.TestModelSerializer


class TestModelSerializerReverseForeignKeyAPI(GenericAPI):
    model = models.TestModelSerializerReverseForeignKey


class TestModelSerializerForeignKeyAPI(GenericAPI):
    model = models.TestModelSerializerForeignKey


class TestModelSerializerOneToOneAPI(GenericAPI):
    model = models.TestModelSerializerOneToOne


class TestModelSerializerReverseOneToOneAPI(GenericAPI):
    model = models.TestModelSerializerReverseOneToOne


class TestModelSerializerManyToManyAPI(GenericAPI):
    model = models.TestModelSerializerManyToMany


class TestModelSerializerReverseManyToManyAPI(GenericAPI):
    model = models.TestModelSerializerReverseManyToMany


# ==========================================================
#                       MODEL APIS
# ==========================================================


class TestModelAPI(GenericAPI):
    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelReverseForeignKeyAPI(GenericAPI):
    model = models.TestModelReverseForeignKey
    schema_in = schema.TestModelReverseForeignKeySchemaIn
    schema_out = schema.TestModelReverseForeignKeySchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelForeignKeyAPI(GenericAPI):
    model = models.TestModelForeignKey
    schema_in = schema.TestModelForeignKeySchemaIn
    schema_out = schema.TestModelForeignKeySchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelReverseOneToOneAPI(GenericAPI):
    model = models.TestModelReverseOneToOne
    schema_in = schema.TestModelReverseForeignKeySchemaIn
    schema_out = schema.TestModelReverseOneToOneSchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelOneToOneAPI(GenericAPI):
    model = models.TestModelOneToOne
    schema_in = schema.TestModelForeignKeySchemaIn
    schema_out = schema.TestModelForeignKeySchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelManyToManyAPI(GenericAPI):
    model = models.TestModelManyToMany
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelManyToManySchemaOut
    schema_update = schema.TestModelSchemaPatch


class TestModelReverseManyToManyAPI(GenericAPI):
    model = models.TestModelReverseManyToMany
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelReverseManyToManySchemaOut
    schema_update = schema.TestModelSchemaPatch
