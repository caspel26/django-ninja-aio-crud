from ninja import ModelSchema

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
