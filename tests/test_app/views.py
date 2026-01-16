import datetime
from ninja_aio.views import mixins

from tests.generics.views import GenericAPIViewSet
from tests.test_app import models, schema, serializers

# ==========================================================
#                  MODEL SERIALIZERS APIS
# ==========================================================


class TestModelSerializerAPI(
    GenericAPIViewSet,
    mixins.IcontainsFilterViewSetMixin,
    mixins.BooleanFilterViewSetMixin,
    mixins.NumericFilterViewSetMixin,
    mixins.DateFilterViewSetMixin,
):
    model = models.TestModelSerializer
    query_params = {
        "name": (str, None),
        "description": (str, None),
        "active": (bool, None),
        "age": (int, None),
        "active_from": (datetime.datetime, None),
    }


class TestModelSerializerGreaterThanMixinAPI(
    GenericAPIViewSet, mixins.GreaterDateFilterViewSetMixin
):
    model = models.TestModelSerializer
    query_params = {
        "active_from": (datetime.datetime, None),
    }


class TestModelSerializerLessThanMixinAPI(
    GenericAPIViewSet, mixins.LessDateFilterViewSetMixin
):
    model = models.TestModelSerializer
    query_params = {
        "active_from": (datetime.datetime, None),
    }


class TestModelSerializerGreaterEqualMixinAPI(
    GenericAPIViewSet, mixins.GreaterEqualDateFilterViewSetMixin
):
    model = models.TestModelSerializer
    query_params = {
        "active_from": (datetime.datetime, None),
    }


class TestModelSerializerLessEqualMixinAPI(
    GenericAPIViewSet, mixins.LessEqualDateFilterViewSetMixin
):
    model = models.TestModelSerializer
    query_params = {
        "active_from": (datetime.datetime, None),
    }


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


# ==========================================================
#                       SERIALIZERS APIS
# ==========================================================


class TestModelForeignKeySerializerAPI(GenericAPIViewSet):
    model = models.TestModelForeignKey
    serializer_class = serializers.TestModelForeignKeySerializer


class TestModelReverseForeignKeySerializerAPI(GenericAPIViewSet):
    model = models.TestModelReverseForeignKey
    serializer_class = serializers.TestModelReverseForeignKeySerializer
