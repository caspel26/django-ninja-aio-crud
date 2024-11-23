from tests.generics.views import GenericAPI
from tests.test_app.models import TestModelSerializer, TestModel
from tests.test_app.schema import (
    TestModelSchemaIn,
    TestModelSchemaOut,
    TestModelSchemaPatch,
)


class TestModelSerializerAPI(GenericAPI):
    model = TestModelSerializer


class TestModelAPI(GenericAPI):
    model = TestModel
    schema_in = TestModelSchemaIn
    schema_out = TestModelSchemaOut
    schema_update = TestModelSchemaPatch
