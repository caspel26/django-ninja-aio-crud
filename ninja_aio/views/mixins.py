from ninja_aio.views.api import APIViewSet


class IcontainsFilterViewSetMixin(APIViewSet):
    """
    Mixin providing a convenience method to apply case-insensitive substring filters
    to a Django queryset based on request query parameters.

    This mixin is intended for use with viewsets that support asynchronous handling
    and dynamic filtering. It converts string-type filter values into Django ORM
    `__icontains` lookups, enabling partial, case-insensitive matches.

    Usage:
        - Include this mixin in a viewset class that exposes a queryset and
          passes a dictionary of filters (e.g., from request query params) to
          `query_params_handler`.
        - Only string values are considered; non-string values are ignored.

    Example:
        filters = {"name": "john", "email": "example.com", "age": 30}
        # Resulting queryset filter:
        # queryset.filter(name__icontains="john", email__icontains="example.com")
        # Note: "age" is ignored because its value is not a string.

        Apply `__icontains` filters to the provided queryset based on the given filter
        dictionary.

        Parameters:
            queryset (django.db.models.QuerySet):
                The base queryset to filter.
            filters (dict[str, Any]):
                A mapping of field names to desired filter values. Only entries with
                string values will be transformed into `field__icontains=value`
                filters. Non-string values are ignored.

        Returns:
            django.db.models.QuerySet:
                A queryset filtered with `__icontains` lookups for all string-valued
                keys in `filters`.

        Notes:
            - This method is asynchronous to align with async view workflows, but it
              performs a synchronous queryset filter call typical in Django ORM usage.
            - Ensure that the fields referenced in `filters` exist on the model
              associated with `queryset`, otherwise a FieldError may be raised at
              evaluation time.
    """

    async def query_params_handler(self, queryset, filters):
        """
        Apply icontains filter to the queryset based on provided filters.
        """
        base_qs = await super().query_params_handler(queryset, filters)
        return base_qs.filter(
            **{
                f"{key}__icontains": value
                for key, value in filters.items()
                if isinstance(value, str)
            }
        )


class BooleanFilterViewSetMixin(APIViewSet):
    """
    Mixin providing boolean-based filtering for Django QuerySets.

    This mixin defines a helper to apply boolean filters from a dictionary of query
    parameters, selecting only those values that are strictly boolean (True/False)
    and ignoring any non-boolean entries. It is intended to be used with viewsets
    that expose queryable endpoints.

    Methods:
        query_params_handler(queryset, filters):
            Apply boolean filters to the given queryset based on the provided
            dictionary. Only keys with boolean values are included in the filter.

            Parameters:
                queryset (QuerySet): A Django QuerySet to be filtered.
                filters (dict): A mapping of field names to potential filter values.

            Returns:
                QuerySet: A new QuerySet filtered by the boolean entries in `filters`.

            Notes:
                - Non-boolean values in `filters` are ignored.
                - Keys should correspond to valid model fields or lookups.
                - This method does not mutate the original queryset; it returns a
                  filtered clone.
    """

    async def query_params_handler(self, queryset, filters):
        """
        Apply boolean filter to the queryset based on provided filters.
        """
        base_qs = await super().query_params_handler(queryset, filters)
        return base_qs.filter(
            **{key: value for key, value in filters.items() if isinstance(value, bool)}
        )


class ReverseBooleanFilterViewSetMixin(APIViewSet):
    """
    Mixin that applies reverse boolean filters to a Django queryset.

    This mixin is intended for use with API viewsets that need to invert boolean
    filters: instead of selecting records where a boolean field matches the given
    value, it excludes them. For example, providing {"is_active": True} will
    exclude all records where `is_active` is True.

    Designed to be composed with a viewset class that provides `queryset` and
    invokes `query_params_handler` with parsed filters.

    Apply reverse boolean filters to the queryset.

    Parameters:
    - queryset: A Django QuerySet to be filtered.
    - filters: A mapping of field names to values. Only boolean values are considered.

    Behavior:
    - Identifies keys in `filters` whose values are booleans.
    - Excludes records from `queryset` where those fields match the provided boolean values.

    Returns:
    - A new QuerySet with the matching boolean rows excluded.

    Example:
    - Given filters {"is_active": True, "name": "Alice"}, only the boolean filter
        on `is_active` is applied, resulting in queryset.exclude(is_active=True).
    """

    async def query_params_handler(self, queryset, filters):
        """
        Apply reverse boolean filter to the queryset based on provided filters.
        """
        base_qs = await super().query_params_handler(queryset, filters)
        return base_qs.exclude(
            **{key: value for key, value in filters.items() if isinstance(value, bool)}
        )


class NumericFilterViewSetMixin(APIViewSet):
    """
    Mixin providing numeric filtering for Django QuerySets.

    This mixin defines a helper to apply numeric filters from a dictionary of query
    parameters, selecting only those values that are of numeric type (int or float)
    and ignoring any non-numeric entries. It is intended to be used with viewsets
    that expose queryable endpoints.

    Methods:
        query_params_handler(queryset, filters):
            Apply numeric filters to the given queryset based on the provided
            dictionary. Only keys with numeric values are included in the filter.

            Parameters:
                queryset (QuerySet): A Django QuerySet to be filtered.
                filters (dict): A mapping of field names to potential filter values.

            Returns:
                QuerySet: A new QuerySet filtered by the numeric entries in `filters`.

            Notes:
                - Non-numeric values in `filters` are ignored.
                - Keys should correspond to valid model fields or lookups.
                - This method does not mutate the original queryset; it returns a
                  filtered clone.
    """

    async def query_params_handler(self, queryset, filters):
        """
        Apply numeric filter to the queryset based on provided filters.
        """
        base_qs = await super().query_params_handler(queryset, filters)
        return base_qs.filter(
            **{
                key: value
                for key, value in filters.items()
                if isinstance(value, (int, float))
            }
        )


class DateFilterViewSetMixin(APIViewSet):
    """
    Mixin for API view sets that provides date-based filtering for querysets.

    This mixin allows subclasses to apply dynamic date or datetime filters to a
    queryset based on incoming filter parameters. It supports field aliasing and
    customizable comparison lookups for flexible query construction.

    Attributes:
        field_alias (dict[str, str]):
            A mapping of incoming filter keys to actual model field names. If a key
            is present in this mapping, its value will be used as the field name in
            the filter; otherwise, the original key is used.

    Methods:
        query_params_handler(queryset, filters):
            Apply date or datetime filters to the provided queryset.

            Args:
                queryset:
                    A Django queryset to be filtered.
                filters (dict):
                    A dictionary of filter parameters where keys represent field names
                    (or aliases) and values are expected to be date or datetime-like
                    objects (i.e., objects implementing `isoformat`).

            Returns:
                A Django queryset filtered using the provided date/datetime parameters.

            Notes:
                - Only filter entries whose values implement `isoformat` are applied,
                  ensuring non-date parameters are ignored.
                - Field names are resolved via `field_alias` when present.
                - Subclasses can define the comparison behavior (e.g., greater-than,
                  less-than, etc.) used for building lookups.
    """

    field_alias: dict[str, str] = {}
    _compare_attr: str = ""

    async def query_params_handler(self, queryset, filters):
        """
        Apply date filter to the queryset based on provided filters.
        """
        base_qs = await super().query_params_handler(queryset, filters)
        return base_qs.filter(
            **{
                f"{self.field_alias.get(key, key)}{self._compare_attr}": value
                for key, value in filters.items()
                if hasattr(value, "isoformat")  # checks for date or datetime
            }
        )


class GreaterThenDateFilterViewSetMixin(DateFilterViewSetMixin):
    """
    Mixin that configures date filtering to return records with dates strictly greater than a given value.
    This class extends DateFilterViewSetMixin and sets the internal comparison attribute to `__gt`,
    ensuring that any date-based filtering uses the "greater than" operation.
    Attributes:
        _compare_attr (str): The Django ORM comparison operator used for filtering, set to "__gt".
    Usage:
        - Include this mixin in a ViewSet to filter queryset results where the specified date field is
          greater than the provided date value.
        - Typically used in endpoints that need to fetch items created/updated after a certain timestamp.
    Example:
        class MyViewSet(GreaterThenDateFilterViewSetMixin, ModelViewSet):
            date_filter_field = "created_at"
            ...
        # Filtering will apply: queryset.filter(created_at__gt=<provided_date>)
    """

    _compare_attr = "__gt"


class LessThenDateFilterViewSetMixin(DateFilterViewSetMixin):
    """
    Mixin that configures date filtering to return records with dates strictly less than a given value.
    This class extends DateFilterViewSetMixin and sets the internal comparison attribute to `__lt`,
    ensuring that any date-based filtering uses the "less than" operation.
    Attributes:
        _compare_attr (str): The Django ORM comparison operator used for filtering, set to "__lt".
    Usage:
        - Include this mixin in a ViewSet to filter queryset results where the specified date field is
          less than the provided date value.
        - Typically used in endpoints that need to fetch items created/updated before a certain timestamp.
    Example:
        class MyViewSet(LessThenDateFilterViewSetMixin, ModelViewSet):
            date_filter_field = "created_at"
            ...
        # Filtering will apply: queryset.filter(created_at__lt=<provided_date>)
    """

    _compare_attr = "__lt"


class GreaterEqualDateFilterViewSetMixin(DateFilterViewSetMixin):
    """
    Mixin for date-based filtering that uses a "greater than or equal to" comparison.

    This mixin extends DateFilterViewSetMixin by setting the internal comparison
    attribute to "__gte", enabling querysets to be filtered to include records whose
    date or datetime fields are greater than or equal to the provided value.

    Intended Use:
    - Apply to Django Ninja or DRF viewsets that support date filtering.
    - Combine with DateFilterViewSetMixin to standardize date filter behavior.

    Behavior:
    - When a date filter parameter is present, the queryset is filtered using
        Django's "__gte" lookup, e.g., MyModel.objects.filter(created_at__gte=value).

    Attributes:
    - _compare_attr: str
        The Django ORM comparison operator used for filtering; set to "__gte".

    Notes:
    - Ensure the target field and provided filter value are compatible (date or datetime).
    - Timezone-aware comparisons should be handled consistently within the project settings.
    """

    _compare_attr = "__gte"


class LessEqualDateFilterViewSetMixin(DateFilterViewSetMixin):
    """
    Mixin for date-based filtering that uses a "less than or equal to" comparison.
    This mixin extends DateFilterViewSetMixin by setting the internal comparison
    attribute to "__lte", enabling querysets to be filtered to include records whose
    date or datetime fields are less than or equal to the provided value.
    Intended Use:
    - Apply to Django Ninja or DRF viewsets that support date filtering.
    - Combine with DateFilterViewSetMixin to standardize date filter behavior.
    Behavior:
    - When a date filter parameter is present, the queryset is filtered using
        Django's "__lte" lookup, e.g., MyModel.objects.filter(created_at__lte=value).
    Attributes:
    - _compare_attr: str
        The Django ORM comparison operator used for filtering; set to "__lte".
    Notes:
    - Ensure the target field and provided filter value are compatible (date or datetime).
    - Timezone-aware comparisons should be handled consistently within the project settings.
    """

    _compare_attr = "__lte"
