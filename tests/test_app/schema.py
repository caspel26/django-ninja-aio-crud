from ninja import Schema


class BaseSchemaIn(Schema):
    name: str
    description: str


class BaseSchemaOut(Schema):
    id: int | str
    name: str
    description: str


class BaseSchemaPatch(Schema):
    description: str


class TestModelSchemaIn(BaseSchemaIn):
    pass


class TestModelSchemaOut(BaseSchemaOut):
    pass


class TestModelSchemaPatch(BaseSchemaPatch):
    pass


class TestModelForeignKeySchemaIn(BaseSchemaIn):
    test_model: int


class TestModelForeignKeyRelated(BaseSchemaOut):
    pass


class TestModelForeignKeySchemaOut(TestModelForeignKeyRelated):
    test_model: "TestModelReverseForeignKeyRelated"


class TestModelReverseForeignKeySchemaIn(BaseSchemaIn):
    pass


class TestModelReverseForeignKeyRelated(BaseSchemaOut):
    pass


class TestModelReverseForeignKeySchemaOut(TestModelReverseForeignKeyRelated):
    test_model_foreign_keys: list[TestModelForeignKeyRelated]


class TestModelReverseOneToOneSchemaOut(TestModelReverseForeignKeyRelated):
    test_model_one_to_one: TestModelForeignKeyRelated | None = None


class TestModelManyToManySchemaOut(BaseSchemaOut):
    test_models: list[TestModelForeignKeyRelated]


class TestModelReverseManyToManySchemaOut(BaseSchemaOut):
    test_model_serializer_many_to_many: list[TestModelForeignKeyRelated]


class SumSchemaIn(Schema):
    a: int
    b: int


class SumSchemaOut(Schema):
    result: int
