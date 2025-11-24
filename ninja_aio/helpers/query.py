import enum
from ninja_aio.types import ModelSerializerMeta
from ninja_aio.schemas.helpers import ModelQuerySetSchema


class QueryScopes(enum.Enum):
    READ = "read"
    QUERYSET_REQUEST = "queryset_request"


class QueryUtil:
    def __init__(self, model: ModelSerializerMeta):
        self.model = model
        self.SCOPES = QueryScopes
        self._configuration = getattr(self.model, "QuerySet", None)
        self.read_config = self._get_config(QueryScopes.READ.value)
        self.queryset_request_config = self._get_config(
            QueryScopes.QUERYSET_REQUEST.value
        )

    def _get_config(self, conf_name: str) -> ModelQuerySetSchema:
        """Helper method to retrieve configuration attributes."""
        if self._configuration:
            return getattr(self._configuration, conf_name, ModelQuerySetSchema())
        return ModelQuerySetSchema()

    def apply_queryset_optimizations(self, queryset, scope: QueryScopes):
        """Apply select_related and prefetch_related optimizations to the queryset."""
        if not isinstance(scope, QueryScopes):
            raise ValueError(
                f"Unsupported scope '{scope}'. Must be a QueryScopes enum member."
            )

        config = getattr(self, f"{scope.value}_config")
        if config.select_related:
            queryset = queryset.select_related(*config.select_related)
        if config.prefetch_related:
            queryset = queryset.prefetch_related(*config.prefetch_related)
        return queryset
