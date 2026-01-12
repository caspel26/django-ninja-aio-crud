from ninja_aio.models.serializers import Serializer, ModelSerializer
from ninja_aio.schemas.helpers import (
    ModelQuerySetSchema,
    QueryUtilBaseScopesSchema,
    ModelQuerySetExtraSchema,
)


class ScopeNamespace:
    def __init__(self, **scopes):
        """Create a simple namespace where each provided scope becomes an attribute."""
        for key, value in scopes.items():
            setattr(self, key, value)

    def __iter__(self):
        """Iterate over the stored scope values."""
        return iter(self.__dict__.values())


class QueryUtil:
    """
    Helper class to manage queryset optimizations based on predefined scopes.
    Attributes:
        model (ModelSerializerMeta): The model serializer meta to which this utility is attached.
        SCOPES (ScopeNamespace): An enumeration-like object containing available scopes.
        read_config (ModelQuerySetSchema): Configuration for the 'read' scope.
        queryset_request_config (ModelQuerySetSchema): Configuration for the 'queryset_request' scope
        extra_configs (dict): Additional configurations for custom scopes.
    Methods:
        apply_queryset_optimizations(queryset, scope): Applies select_related and prefetch_related
            optimizations to the given queryset based on the specified scope.

    Example:
        query_util = QueryUtil(MyModelSerializer) or MyModel.query_util
        qs = MyModel.objects.all()
        optimized_qs = query_util.apply_queryset_optimizations(qs, query_util.SCOPES.READ)

        # Applying optimizations for a custom scope
        class MyModelSerializer(ModelSerializer):
            class QuerySet:
                extras = [
                    ModelQuerySetExtraSchema(
                        scope="custom_scope",
                        select_related=["custom_fk_field"],
                        prefetch_related=["custom_m2m_field"],
                    )
                ]
        query_util = MyModelSerializer.query_util
        qs = MyModelSerializer.objects.all()
        optimized_qs_custom = query_util.apply_queryset_optimizations(qs, "custom_scope")
    """

    SCOPES: QueryUtilBaseScopesSchema

    def __init__(self, model: ModelSerializer | Serializer):
        """Initialize QueryUtil, resolving base and extra scope configurations for a model."""
        self.model = model
        self._configuration = getattr(self.model, "QuerySet", None)
        self._extra_configuration: list[ModelQuerySetExtraSchema] = getattr(
            self._configuration, "extras", []
        )
        self._BASE_SCOPES = QueryUtilBaseScopesSchema().model_dump()
        self.SCOPES = ScopeNamespace(
            **self._BASE_SCOPES,
            **{extra.scope: extra.scope for extra in self._extra_configuration},
        )
        self.extra_configs = {extra.scope: extra for extra in self._extra_configuration}
        self._configs = {
            **{scope: self._get_config(scope) for scope in self._BASE_SCOPES.values()},
            **self.extra_configs,
        }
        self.read_config: ModelQuerySetSchema = self._configs.get(
            self.SCOPES.READ, ModelQuerySetSchema()
        )
        self.queryset_request_config: ModelQuerySetSchema = self._configs.get(
            self.SCOPES.QUERYSET_REQUEST, ModelQuerySetSchema()
        )

    def _get_config(self, conf_name: str) -> ModelQuerySetSchema:
        """Helper method to retrieve configuration attributes."""
        return getattr(self._configuration, conf_name, ModelQuerySetSchema())

    def apply_queryset_optimizations(self, queryset, scope: str):
        """
        Apply select_related and prefetch_related optimizations to the queryset
        according to the specified scope.

        Args:
            queryset (QuerySet): The Django queryset to optimize.
            scope (str): The scope to apply. Must be in self.SCOPES.

        Returns:
            QuerySet: The optimized queryset.

        Raises:
            ValueError: If the given scope is not supported.
        """
        if scope not in self._configs:
            valid_scopes = list(self._configs.keys())
            raise ValueError(
                f"Invalid scope '{scope}' for QueryUtil. Supported scopes: {valid_scopes}"
            )
        config = self._configs.get(scope, ModelQuerySetSchema())
        if config.select_related:
            queryset = queryset.select_related(*config.select_related)
        if config.prefetch_related:
            queryset = queryset.prefetch_related(*config.prefetch_related)
        return queryset
