from ninja import ModelSchema, Schema

from tests.test_app.models import TestModel


class TestModelSchemaIn(ModelSchema):
    class Meta:
        model = TestModel
        fields = ["name", "description"]


class TestModelSchemaOut(ModelSchema):
    class Meta:
        model = TestModel
        fields = ["id", "name", "description"]


class TestModelSchemaPatch(ModelSchema):
    class Meta:
        model = TestModel
        fields = ["description"]


class SumSchemaIn(Schema):
    a: int
    b: int


class SumSchemaOut(Schema):
    result: int
