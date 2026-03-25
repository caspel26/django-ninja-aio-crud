import datetime

from django.db.models import Q
from ninja_aio.decorators.actions import action
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


class TestModelSerializerBulkAPI(GenericAPIViewSet):
    model = models.TestModelSerializer
    bulk_operations = ["create", "update", "delete"]


class TestModelSerializerOrderingAPI(GenericAPIViewSet):
    model = models.TestModelSerializer
    ordering_fields = ["name", "id"]
    default_ordering = "-id"


class TestModelSerializerOrderingWithFiltersAPI(
    GenericAPIViewSet,
    mixins.IcontainsFilterViewSetMixin,
):
    model = models.TestModelSerializer
    ordering_fields = ["name", "id"]
    default_ordering = "-id"
    query_params = {
        "name": (str, None),
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


class TestModelBulkAPI(GenericAPIViewSet):
    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch
    bulk_operations = ["create", "update", "delete"]


class TestModelBulkSingleFieldAPI(GenericAPIViewSet):
    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch
    bulk_operations = ["create", "update", "delete"]
    bulk_response_fields = "name"


class TestModelBulkMultiFieldAPI(GenericAPIViewSet):
    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch
    bulk_operations = ["create", "update", "delete"]
    bulk_response_fields = ["id", "name"]


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


# ==========================================================
#          MATCH CASE FILTER WITH Q OBJECTS APIS
# ==========================================================


class TestModelSerializerMatchCaseQFilterAPI(
    GenericAPIViewSet,
    mixins.MatchCaseFilterViewSetMixin,
):
    """
    ViewSet for testing MatchCaseFilterViewSetMixin with Q objects.
    Uses Q objects instead of dicts for query_filter.
    """

    model = models.TestModelSerializer
    filters_match_cases = [
        MatchCaseFilterSchema(
            query_param="is_approved",
            cases=BooleanMatchFilterSchema(
                true=MatchConditionFilterSchema(
                    query_filter=Q(status="approved"),
                    include=True,
                ),
                false=MatchConditionFilterSchema(
                    query_filter=Q(status="approved"),
                    include=False,
                ),
            ),
        ),
    ]


class TestModelSerializerMatchCaseQExcludeFilterAPI(
    GenericAPIViewSet,
    mixins.MatchCaseFilterViewSetMixin,
):
    """
    ViewSet for testing MatchCaseFilterViewSetMixin with Q objects and exclude.
    """

    model = models.TestModelSerializer
    filters_match_cases = [
        MatchCaseFilterSchema(
            query_param="hide_pending",
            cases=BooleanMatchFilterSchema(
                true=MatchConditionFilterSchema(
                    query_filter=Q(status="pending"),
                    include=False,
                ),
                false=MatchConditionFilterSchema(
                    query_filter=Q(status="pending"),
                    include=True,
                ),
            ),
        ),
    ]


# ==========================================================
#                  PERMISSION MIXIN APIS
# ==========================================================


class PermissionTestAPI(GenericAPIViewSet, mixins.PermissionViewSetMixin):
    """ViewSet using PermissionViewSetMixin with controllable permission via request attrs."""

    model = models.TestModelSerializer

    async def has_permission(self, request, operation):
        return getattr(request, "_allow", True)

    async def has_object_permission(self, request, operation, obj):
        return getattr(request, "_allow_obj", True)

    def get_permission_queryset(self, request, queryset):
        if getattr(request, "_filter_qs", False):
            return queryset.none()
        return queryset


class RoleBasedPermissionTestAPI(
    GenericAPIViewSet, mixins.RoleBasedPermissionMixin
):
    """ViewSet using RoleBasedPermissionMixin with role-to-operations mapping."""

    model = models.TestModelSerializer
    permission_roles = {
        "admin": [
            "create", "list", "retrieve", "update", "delete",
            "bulk_create", "bulk_update", "bulk_delete", "custom_action",
        ],
        "editor": ["create", "list", "retrieve", "update"],
        "reader": ["list", "retrieve"],
    }

    bulk_operations = ["create", "update", "delete"]

    @action(detail=False, methods=["post"])
    async def custom_action(self, request):
        return {"status": "ok"}


class PermissionWithFilterTestAPI(
    mixins.PermissionViewSetMixin,
    mixins.IcontainsFilterViewSetMixin,
    GenericAPIViewSet,
):
    """ViewSet combining permission and filter mixins."""

    model = models.TestModelSerializer
    query_params = {"name": (str, None)}

    async def has_permission(self, request, operation):
        return getattr(request, "_allow", True)


# ==========================================================
#                    SOFT DELETE APIS
# ==========================================================


class SoftDeleteTestAPI(mixins.SoftDeleteViewSetMixin, GenericAPIViewSet):
    """ViewSet with default soft delete (is_deleted field)."""

    model = models.SoftDeleteTestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch
    bulk_operations = ["create", "update", "delete"]


class SoftDeleteCustomFieldTestAPI(
    mixins.SoftDeleteViewSetMixin, GenericAPIViewSet
):
    """ViewSet with custom soft delete field name."""

    model = models.SoftDeleteCustomFieldTestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch
    soft_delete_field = "deleted"


class SoftDeleteIncludeDeletedTestAPI(
    mixins.SoftDeleteViewSetMixin, GenericAPIViewSet
):
    """ViewSet that includes soft-deleted records (admin view)."""

    model = models.SoftDeleteTestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch
    include_deleted = True


# ==========================================================
#                    SEARCH APIS
# ==========================================================


class SearchTestAPI(mixins.SearchViewSetMixin, GenericAPIViewSet):
    """ViewSet with multi-field search."""

    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch
    search_fields = ["name", "description"]


class SearchWithFiltersTestAPI(
    mixins.SearchViewSetMixin,
    mixins.IcontainsFilterViewSetMixin,
    GenericAPIViewSet,
):
    """ViewSet combining search and filter mixins."""

    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch
    search_fields = ["name", "description"]
    query_params = {"name": (str, None)}


class SearchDisabledTestAPI(mixins.SearchViewSetMixin, GenericAPIViewSet):
    """ViewSet with empty search_fields (no-op)."""

    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch
    search_fields = []


# ==========================================================
#              PERFORMANCE BENCHMARK APIS
# ==========================================================


class PerfArticleAPI(GenericAPIViewSet):
    """ViewSet with 3 FK relations for benchmarking."""

    model = models.PerfArticle
    schema_in = schema.PerfArticleSchemaIn
    schema_out = schema.PerfArticleSchemaOut
    schema_update = schema.PerfArticleSchemaPatch
    bulk_operations = ["create", "update", "delete"]
