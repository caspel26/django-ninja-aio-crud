import datetime
from ninja_aio.views import mixins
from ninja_aio.schemas import (
    RelationFilterSchema,
    MatchCaseFilterSchema,
    MatchConditionFilterSchema,
    BooleanMatchFilterSchema,
)

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


# ==========================================================
#                  RELATION FILTER MIXIN APIS
# ==========================================================


class TestModelSerializerForeignKeyRelationFilterAPI(
    GenericAPIViewSet,
    mixins.RelationFilterViewSetMixin,
):
    model = models.TestModelSerializerForeignKey
    relations_filters = [
        RelationFilterSchema(
            query_param="test_model_serializer",
            query_filter="test_model_serializer__id",
            filter_type=(int, None),
        ),
        RelationFilterSchema(
            query_param="test_model_serializer_name",
            query_filter="test_model_serializer__name__icontains",
            filter_type=(str, None),
        ),
    ]


# ==========================================================
#                  MATCH CASE FILTER MIXIN APIS
# ==========================================================


class TestModelSerializerMatchCaseFilterAPI(
    GenericAPIViewSet,
    mixins.MatchCaseFilterViewSetMixin,
):
    """
    ViewSet for testing MatchCaseFilterViewSetMixin.
    Uses status field to filter by 'is_approved' boolean query param.
    """

    model = models.TestModelSerializer
    filters_match_cases = [
        MatchCaseFilterSchema(
            query_param="is_approved",
            cases=BooleanMatchFilterSchema(
                true=MatchConditionFilterSchema(
                    query_filter={"status": "approved"},
                    include=True,
                ),
                false=MatchConditionFilterSchema(
                    query_filter={"status": "approved"},
                    include=False,
                ),
            ),
        ),
    ]


class TestModelSerializerMatchCaseExcludeFilterAPI(
    GenericAPIViewSet,
    mixins.MatchCaseFilterViewSetMixin,
):
    """
    ViewSet for testing MatchCaseFilterViewSetMixin with exclude behavior.
    Uses status field to filter by 'hide_pending' boolean query param.
    """

    model = models.TestModelSerializer
    filters_match_cases = [
        MatchCaseFilterSchema(
            query_param="hide_pending",
            cases=BooleanMatchFilterSchema(
                true=MatchConditionFilterSchema(
                    query_filter={"status": "pending"},
                    include=False,  # exclude pending when True
                ),
                false=MatchConditionFilterSchema(
                    query_filter={"status": "pending"},
                    include=True,  # include only pending when False
                ),
            ),
        ),
    ]
